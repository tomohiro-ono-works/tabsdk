from __future__ import annotations

import copy
import logging
import re
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from lxml import etree as ET

from .calculation import create_calculated_field_el, normalize_formula_for_datasource
from .column import list_columns_from_datasource
from .context import UNSET, ConnectedModel, WorkbookContext, _UnsetType, xml_equal
from .datasource import datasource_elements, update_source_el
from .errors import (
    AmbiguousCaptionError,
    DetachedModelError,
    NotFoundError,
    ResourceInUseError,
    ResourceReference,
    UnsupportedFeatureError,
)
from .folder import _ensure_folders_common, move_column_to_folder_el, remove_column_from_folder_el
from .models import BigQuerySource, CsvSource, ExcelSource, UnknownSource
from .relation import (
    list_relations_from_datasource,
    list_relationships_from_datasource,
    relation_elements_in_order,
    relations_in_order,
    relationship_elements,
)
from .references import datasource_references, field_references
from .sources import detect_source


Source = BigQuerySource | ExcelSource | CsvSource | UnknownSource
_FORMULA_REFERENCE_RE = re.compile(r"\[([^\]]+)\]\.\[([^\]]+)\]|\[([^\]]+)\]")
_LOGGER = logging.getLogger(__name__)
_TABLEAU_USER_NAMESPACE = "http://www.tableausoftware.com/xml/user"


def get_xml_id(element: ET._Element) -> str:
    value = element.get("name")
    if not value:
        raise ValueError("XML resource has no name attribute")
    return value


def get_display_name(element: ET._Element, *, strip_field_brackets: bool = False) -> str:
    caption = (element.get("caption") or "").strip()
    if caption:
        return caption
    xml_id = get_xml_id(element)
    if strip_field_brackets and xml_id.startswith("[") and xml_id.endswith("]"):
        return xml_id[1:-1]
    return xml_id


def _validate_get_args(id: str | None, name: str | None) -> None:
    if id is not None and name is not None:
        raise ValueError("id and name cannot be specified together")


def _matches(*, model_id: str, model_name: str, id: str | None, name: str | None) -> bool:
    if id is not None:
        return model_id == id
    if name is not None:
        return model_name == name
    return True


def _folder_elements(datasource_el: ET._Element) -> list[ET._Element]:
    result: list[ET._Element] = []
    for child in datasource_el:
        local_name = ET.QName(child).localname
        if local_name == "folder":
            result.append(child)
        elif local_name in {"folders-common", "folders-parameters"}:
            result.extend(
                folder
                for folder in child
                if ET.QName(folder).localname == "folder"
            )
    return result


def _datasource_layout(
    datasource_el: ET._Element,
    *,
    create: bool = False,
) -> ET._Element | None:
    layouts = [
        child
        for child in datasource_el
        if ET.QName(child).localname == "layout"
    ]
    if len(layouts) > 1:
        raise UnsupportedFeatureError("datasource has multiple layout elements")
    if layouts or not create:
        return layouts[0] if layouts else None

    layout = ET.Element("layout")
    following = next(
        (
            child
            for child in datasource_el
            if ET.QName(child).localname in {"semantic-values", "object-graph"}
        ),
        None,
    )
    datasource_el.insert(
        datasource_el.index(following) if following is not None else len(datasource_el),
        layout,
    )
    return layout


def _metadata_text(record: ET._Element, child_name: str) -> str | None:
    for child in record:
        if ET.QName(child).localname == child_name:
            return child.text
    return None


class _FieldDefinition(NamedTuple):
    id: str
    column: ET._Element | None
    metadata: ET._Element | None


def _effective_field_definitions(datasource_el: ET._Element) -> list[_FieldDefinition]:
    metadata_by_id: dict[str, ET._Element] = {}
    for record in datasource_el.xpath(
        "./*[local-name()='connection']/*[local-name()='metadata-records']"
        "/*[local-name()='metadata-record' and @class='column']"
        " | ./*[local-name()='extract']/*[local-name()='connection']"
        "/*[local-name()='metadata-records']"
        "/*[local-name()='metadata-record' and @class='column']"
    ):
        field_id = _metadata_text(record, "local-name")
        if field_id:
            metadata_by_id.setdefault(field_id, record)

    columns_by_id = {
        field_id: column
        for column in datasource_el.findall("./column")
        if (field_id := column.get("name"))
    }
    field_ids = list(metadata_by_id)
    field_ids.extend(field_id for field_id in columns_by_id if field_id not in metadata_by_id)
    return [
        _FieldDefinition(field_id, columns_by_id.get(field_id), metadata_by_id.get(field_id))
        for field_id in field_ids
    ]


def _metadata_field_role(record: ET._Element) -> str:
    datatype = (_metadata_text(record, "local-type") or "").lower()
    aggregation = (_metadata_text(record, "aggregation") or "").lower()
    if datatype in {"integer", "real", "decimal", "number"} and aggregation not in {
        "",
        "attribute",
        "count",
        "countd",
        "none",
    }:
        return "measure"
    return "dimension"


def _column_from_metadata_record(record: ET._Element) -> ET._Element:
    field_id = _metadata_text(record, "local-name")
    if not field_id:
        raise ValueError("metadata field has no local-name")
    column = ET.Element("column")
    column.set("name", field_id)
    datatype = _metadata_text(record, "local-type")
    if datatype:
        column.set("datatype", datatype)
    role = _metadata_field_role(record)
    column.set("role", role)
    column.set("type", "quantitative" if role == "measure" else "nominal")
    return column


def _field_display_name(definition: _FieldDefinition) -> str:
    if definition.column is not None:
        return get_display_name(definition.column, strip_field_brackets=True)
    if definition.id.startswith("[") and definition.id.endswith("]"):
        return definition.id[1:-1]
    return definition.id


def _insert_field_column(datasource_el: ET._Element, column: ET._Element) -> None:
    preceding = {
        "repository-location",
        "connection",
        "utility-dimensions",
        "dimension",
        "overridable-settings",
        "aliases",
        "column",
    }
    insert_at = 0
    for index, child in enumerate(datasource_el):
        if ET.QName(child).localname in preceding:
            insert_at = index + 1
    datasource_el.insert(insert_at, column)


def _replace_if_changed(
    current: ET._Element,
    updated: ET._Element,
    context: WorkbookContext,
) -> bool:
    if xml_equal(current, updated):
        return False
    parent = current.getparent()
    if parent is None:
        raise DetachedModelError("XML resource is detached")
    parent.replace(current, updated)
    context.mark_dirty()
    return True


def _insert_shared_views(root: ET._Element, shared_views: ET._Element) -> None:
    datasources = next(
        (
            child
            for child in root
            if ET.QName(child).localname == "datasources"
        ),
        None,
    )
    root.insert(root.index(datasources) + 1 if datasources is not None else 0, shared_views)


class TwbDatasource(ConnectedModel):
    def __init__(self, context: WorkbookContext, datasource_id: str):
        super().__init__(context)
        self._id = datasource_id

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        hits = self._context.tree.getroot().xpath(
            "/workbook/datasources/datasource[@name=$id]",
            id=self._id,
        )
        if not hits or self._id == "Parameters":
            self._detach()
            raise DetachedModelError(f"datasource is detached: {self._id}")
        return hits[0]

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        return get_display_name(self._resolve_element())

    @property
    def source_type(self) -> str:
        return detect_source(self._resolve_element())[0]

    @property
    def source(self) -> Source:
        return detect_source(self._resolve_element())[1]

    def get_fields(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbField]:
        _validate_get_args(id, name)
        datasource_el = self._resolve_element()
        result: list[TwbField] = []
        for definition in _effective_field_definitions(datasource_el):
            if _matches(
                model_id=definition.id,
                model_name=_field_display_name(definition),
                id=id,
                name=name,
            ):
                result.append(
                    TwbField(
                        self._context,
                        self._id,
                        definition.id,
                        datasource_el=datasource_el,
                        definition=definition,
                    )
                )
        return result

    def get_folders(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbFolder]:
        _validate_get_args(id, name)
        result: list[TwbFolder] = []
        for folder_el in _folder_elements(self._resolve_element()):
            folder_id = folder_el.get("name")
            if not folder_id:
                continue
            if _matches(model_id=folder_id, model_name=folder_id, id=id, name=name):
                result.append(TwbFolder(self._context, self._id, folder_id))
        return result

    def get_relations(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbRelation]:
        """ルートのリレーション。入れ子は `TwbRelation.get_children()` で辿る。"""
        _validate_get_args(id, name)
        datasource_el = self._resolve_element()
        ordered = relations_in_order(datasource_el)
        roots = list_relations_from_datasource(datasource_el)
        return [
            TwbRelation(self._context, self._id, ordered.index(root))
            for root in roots
            if _matches(
                model_id=root.id or "",
                model_name=root.name or root.id or "",
                id=id,
                name=name,
            )
        ]

    def get_relationships(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbRelationship]:
        _validate_get_args(id, name)
        result = list_relationships_from_datasource(self._resolve_element())
        return [
            TwbRelationship(self._context, self._id, index)
            for index, item in enumerate(result)
            if _matches(
                model_id=item.id or "",
                model_name=item.id or "",
                id=id,
                name=name,
            )
        ]

    @property
    def field_grouping(self) -> str | None:
        """フィールドの grouping 方式。"""
        layout = _datasource_layout(self._resolve_element())
        if layout is None:
            return None
        value = layout.get("show-structure")
        if value is None:
            return None
        return "table" if value.lower() == "true" else "folder"

    def set_filter(self, field: TwbField) -> TwbDatasource:
        if not isinstance(field, TwbField):
            raise TypeError("field must be TwbField")
        if field._context is not self._context:
            raise ValueError("field must belong to the same workbook")
        if field.datasource_id != self.id:
            raise ValueError("field must belong to this datasource")

        root = self._context.tree.getroot()
        field_id = field.id
        token = field_id[1:-1] if field_id.startswith("[") and field_id.endswith("]") else field_id
        instance_name = f"[none:{token}:nk]"
        reference = f"[{self.id}].{instance_name}"

        shared_views = root.xpath("./*[local-name()='shared-views']")
        if len(shared_views) > 1:
            raise UnsupportedFeatureError("workbook has multiple shared-views elements")
        if shared_views:
            shared_views_el = shared_views[0]
        else:
            shared_views_el = ET.Element("shared-views")
            _insert_shared_views(root, shared_views_el)

        views = shared_views_el.xpath(
            "./*[local-name()='shared-view'][@name=$id]",
            id=self.id,
        )
        if len(views) > 1:
            raise UnsupportedFeatureError("datasource has duplicate shared views")
        if views:
            shared_view = views[0]
        else:
            shared_view = ET.SubElement(shared_views_el, "shared-view", name=self.id)

        datasources = shared_view.xpath("./*[local-name()='datasources']")
        if len(datasources) > 1:
            raise UnsupportedFeatureError("shared view has multiple datasources elements")
        if datasources:
            datasources_el = datasources[0]
        else:
            datasources_el = ET.Element("datasources")
            shared_view.insert(0, datasources_el)
        if not datasources_el.xpath(
            "./*[local-name()='datasource'][@name=$id]",
            id=self.id,
        ):
            attrs = {"name": self.id}
            if self.name != self.id:
                attrs["caption"] = self.name
            ET.SubElement(datasources_el, "datasource", attrib=attrs)

        dependencies = shared_view.xpath(
            "./*[local-name()='datasource-dependencies'][@datasource=$id]",
            id=self.id,
        )
        if len(dependencies) > 1:
            raise UnsupportedFeatureError("shared view has duplicate datasource dependencies")
        if dependencies:
            dependency = dependencies[0]
        else:
            dependency = ET.Element(
                "datasource-dependencies",
                datasource=self.id,
            )
            filters = shared_view.xpath("./*[local-name()='filter']")
            shared_view.insert(
                shared_view.index(filters[0]) if filters else len(shared_view),
                dependency,
            )

        if not dependency.xpath(
            "./*[local-name()='column'][@name=$field_id]",
            field_id=field_id,
        ):
            column = copy.deepcopy(field._resolve_element())
            instances = dependency.xpath("./*[local-name()='column-instance']")
            dependency.insert(
                dependency.index(instances[0]) if instances else len(dependency),
                column,
            )
        if not dependency.xpath(
            "./*[local-name()='column-instance'][@name=$name]",
            name=instance_name,
        ):
            ET.SubElement(
                dependency,
                "column-instance",
                attrib={
                    "column": field_id,
                    "derivation": "None",
                    "name": instance_name,
                    "pivot": "key",
                    "type": "nominal",
                },
            )

        filters = shared_view.xpath(
            "./*[local-name()='filter'][@column=$reference]",
            reference=reference,
        )
        if len(filters) > 1:
            raise UnsupportedFeatureError("shared view has duplicate filters")
        if filters:
            filter_el = filters[0]
            filter_el.attrib.clear()
            filter_el.attrib.update({"class": "categorical", "column": reference})
            filter_el[:] = []
        else:
            filter_el = ET.SubElement(
                shared_view,
                "filter",
                attrib={"class": "categorical", "column": reference},
            )
        ET.SubElement(
            filter_el,
            "groupfilter",
            attrib={
                "function": "level-members",
                "level": instance_name,
                f"{{{_TABLEAU_USER_NAMESPACE}}}ui-enumeration": "all",
                f"{{{_TABLEAU_USER_NAMESPACE}}}ui-marker": "enumerate",
            },
        )
        self._context.mark_dirty()
        return self

    def apply_field_config(
        self,
        config: str | Path | dict[str, dict[str, str]],
        *,
        field_grouping: str = "folder",
    ) -> TwbDatasource:
        if isinstance(config, (str, Path)):
            with Path(config).open(encoding="utf-8") as file:
                config = yaml.safe_load(file)
        if not isinstance(config, dict):
            raise ValueError("field config must be a mapping")

        plans: list[tuple[str, str, TwbField]] = []
        seen_fields: set[str] = set()
        for folder_name, rename_map in config.items():
            if not isinstance(folder_name, str) or not folder_name.strip():
                raise ValueError("folder name must be a non-empty string")
            if not isinstance(rename_map, dict):
                raise ValueError(f"folder fields must be a mapping: {folder_name}")
            for original_name, display_name in rename_map.items():
                if not isinstance(original_name, str) or not original_name.strip():
                    raise ValueError("field name must be a non-empty string")
                if not isinstance(display_name, str) or not display_name.strip():
                    raise ValueError(f"display name must be a non-empty string: {original_name}")
                if original_name in seen_fields:
                    raise ValueError(f"field is assigned more than once: {original_name}")
                seen_fields.add(original_name)

                matches = self.get_fields(name=original_name)
                if not matches:
                    matches = self.get_fields(id=f"[{original_name}]")
                if not matches:
                    raise NotFoundError(f"field not found: {original_name}")
                if len(matches) > 1:
                    raise AmbiguousCaptionError(f"field name is ambiguous: {original_name}")
                plans.append((folder_name, display_name, matches[0]))

        folders = {
            folder_name: (
                existing[0]
                if (existing := self.get_folders(name=folder_name))
                else self.create_folder(name=folder_name)
            )
            for folder_name in config
        }
        for folder_name, display_name, field in plans:
            field.update(name=display_name)
            field.move_to_folder(folders[folder_name])
        self.update(field_grouping=field_grouping)
        return self

    def _resolve_folder(self, folder: "str | TwbFolder | None") -> "TwbFolder | None":
        """`folder=` 引数を `TwbFolder` へ解決する。

        `folder=` を受け取るメソッドはすべてこれを通す。個々のメソッドで
        解決処理を書くと、今回のように片方だけ文字列を受け付けない不揃いが起きる。
        """
        if folder is None:
            return None
        if isinstance(folder, str):
            name = folder.strip()
            if not name:
                raise ValueError("folder must not be empty")
            matches = self.get_folders(name=name)
            if not matches:
                raise NotFoundError(f"folder not found: {name}")
            return matches[0]
        if not isinstance(folder, TwbFolder):
            raise TypeError("folder must be a name, TwbFolder, or None")
        folder._ensure_attached()
        folder._resolve_element()
        if folder.datasource_id != self._id or folder._context is not self._context:
            raise ValueError("folder must belong to the same datasource")
        return folder

    def create_folder(self, *, name: str) -> TwbFolder:
        name = name.strip()
        if not name:
            raise ValueError("name must not be empty")
        datasource_el = self._resolve_element()
        if any(folder.get("name") == name for folder in _folder_elements(datasource_el)):
            raise ValueError(f"folder already exists: {name}")
        container = _ensure_folders_common(datasource_el)
        ET.SubElement(container, "folder", attrib={"name": name})
        self._context.mark_dirty()
        return TwbFolder(self._context, self._id, name)

    def create_calculated_field(
        self,
        *,
        name: str,
        formula: str,
        datatype: str = "real",
        role: str = "measure",
        discrete: bool | None = False,
        folder: str | TwbFolder | None = None,
        hidden: bool | None = False,
        number_format: str | None = None,
        table_calculation: str | None = None,
        formula_ref: str = "auto",
        strict: bool = True,
        ref_map: dict[str, str] | None = None,
    ) -> TwbField:
        name = name.strip()
        if not name:
            raise ValueError("name must not be empty")
        datasource_el = self._resolve_element()
        folder = self._resolve_folder(folder)
        if table_calculation is not None:
            if not isinstance(table_calculation, str) or not table_calculation.strip():
                raise ValueError("table_calculation must be a non-empty string or None")
            table_calculation = table_calculation.strip()

        original = copy.deepcopy(datasource_el)
        try:
            created = create_calculated_field_el(
                datasource_el,
                name=None,
                caption=name,
                formula=formula,
                datatype=datatype,
                role=role,
                discrete=discrete,
                hidden=hidden,
                number_format=number_format,
                formula_ref=formula_ref,
                strict=strict,
                ref_map=ref_map,
            )
            if table_calculation is not None:
                created_columns = datasource_el.xpath(
                    "./column[@name=$field_id]",
                    field_id=created.id or created.name,
                )
                calculation = created_columns[0].find("./calculation")
                if calculation is None:
                    raise ValueError("created field has no calculation")
                ET.SubElement(
                    calculation,
                    "table-calc",
                    attrib={"ordering-type": table_calculation},
                )
            if folder is not None:
                move_column_to_folder_el(
                    datasource_el,
                    created.id or created.name,
                    folder.id,
                    by="name",
                    create_if_missing=False,
                )
        except Exception:
            parent = datasource_el.getparent()
            if parent is not None:
                parent.replace(datasource_el, original)
            raise

        self._context.mark_dirty()
        field = TwbField(self._context, self._id, created.id or created.name)
        _LOGGER.info(
            "計算フィールドを作成しました: datasource=%s, name=%s, id=%s",
            self.name,
            field.name,
            field.id,
        )
        return field

    def create_calculated_fields(
        self,
        calculations: dict[str, str | tuple[str, str] | tuple[str, str, str]],
        *,
        folder: str | TwbFolder | None = None,
        role: str = "measure",
        discrete: bool | None = False,
        strict: bool = True,
    ) -> list[TwbField]:
        if not isinstance(calculations, dict):
            raise TypeError("calculations must be a dict")
        for name, definition in calculations.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("calculation name must be a non-empty string")
            if isinstance(definition, str):
                continue
            if (
                not isinstance(definition, tuple)
                or len(definition) not in {2, 3}
                or not all(isinstance(value, str) for value in definition)
            ):
                raise TypeError(
                    "calculation must be a formula, (formula, datatype), "
                    "or (formula, datatype, number_format)"
                )

        target_folder = self._resolve_folder(folder)

        created: list[TwbField] = []
        for name, definition in calculations.items():
            if isinstance(definition, str):
                formula, datatype, number_format = definition, "string", None
            elif len(definition) == 2:
                formula, datatype = definition
                number_format = None
            else:
                formula, datatype, number_format = definition
            created.append(
                self.create_calculated_field(
                    name=name,
                    formula=formula,
                    datatype=datatype,
                    role=role,
                    discrete=discrete,
                    folder=target_folder,
                    number_format=number_format,
                    strict=strict,
                )
            )
        return created

    def create_yoy_calculated_fields(
        self,
        *,
        metric: str,
        year_category: str,
        folder: str | TwbFolder | None = None,
    ) -> list[TwbField]:
        current = f"{metric}|当年"
        previous = f"{metric}|昨年"
        difference = f"{metric}|昨年差"
        calculations = {
            current: (f'IIF([{year_category}]="当年",[{metric}],null)', "real"),
            previous: (f'IIF([{year_category}]="昨年",[{metric}],null)', "real"),
            difference: (f"SUM([{current}])-SUM([{previous}])", "real"),
            f"{metric}|昨年差<0": (
                f"IIF([{difference}]<0,SUM([{current}]),null)",
                "real",
            ),
            f"{metric}|昨年差>=0": (
                f"IIF(zn([{difference}])>=0,SUM([{current}]),null)",
                "real",
            ),
            f"{metric}色|昨年差": (
                f"IIF(zn([{difference}])>=0,SUM([{current}]),null)",
                "real",
            ),
            f"{metric}比|昨年比": (
                f"SUM([{current}])/SUM([{previous}])",
                "real",
                "%",
            ),
        }
        datasource_el = self._resolve_element()
        original = copy.deepcopy(datasource_el)
        original_revision = self._context.revision
        original_dirty = self._context.is_dirty
        try:
            return self.create_calculated_fields(calculations, folder=folder)
        except Exception:
            current_datasource_el = self._resolve_element()
            parent = current_datasource_el.getparent()
            if parent is not None:
                parent.replace(current_datasource_el, original)
            self._context.revision = original_revision
            self._context.invalidate_caches()
            self._context.is_dirty = original_dirty
            raise

    def update(
        self,
        *,
        source: Source | _UnsetType = UNSET,
        name: str | None | _UnsetType = UNSET,
        field_grouping: str | _UnsetType = UNSET,
    ) -> TwbDatasource:
        datasource_el = self._resolve_element()
        updated = copy.deepcopy(datasource_el)

        if name is not UNSET:
            if name is None:
                updated.attrib.pop("caption", None)
            else:
                display_name = name.strip()
                if not display_name:
                    raise ValueError("name must not be empty")
                for other in datasource_elements(self._context.tree, include_parameters=False):
                    if other is not datasource_el and get_display_name(other) == display_name:
                        raise ValueError(f"datasource name already exists: {display_name}")
                updated.set("caption", display_name)

        if source is not UNSET:
            if source is None:
                raise ValueError("source cannot be None")
            update_source_el(updated, source)

        if field_grouping is not UNSET:
            if field_grouping not in {"folder", "table"}:
                raise ValueError("field_grouping must be folder or table")
            layout = _datasource_layout(updated, create=True)
            assert layout is not None
            layout.set(
                "show-structure",
                "false" if field_grouping == "folder" else "true",
            )

        _replace_if_changed(datasource_el, updated, self._context)
        return self

    def delete(self) -> None:
        datasource_el = self._resolve_element()
        tree = self._context.tree
        references: list[ResourceReference] = []
        references.extend(
            ResourceReference(
                resource_type="Field",
                resource_id=column.get("name") or "",
                location=tree.getpath(column),
            )
            for column in datasource_el.findall("./column")
        )
        references.extend(
            ResourceReference(
                resource_type="Folder",
                resource_id=folder.get("name") or "",
                location=tree.getpath(folder),
            )
            for folder in _folder_elements(datasource_el)
        )
        references.extend(datasource_references(tree, self._id))
        if references:
            raise ResourceInUseError("Datasource", self._id, references)
        parent = datasource_el.getparent()
        if parent is None:
            raise DetachedModelError(f"datasource is detached: {self._id}")
        parent.remove(datasource_el)
        self._context.mark_dirty()
        self._detach()


class TwbRelation(ConnectedModel):
    """データソースの物理リレーション（`relation` 要素）。**読み取り専用。**

    join / union / カスタム SQL の編集は H-8 として見送っているため、
    `update()` と `delete()` は用意しない。追加する手段も無いので、
    消せないことは欠落ではない。

    ネストするため、位置（走査順の添字）で対象要素を解決する。
    """

    def __init__(self, context: WorkbookContext, datasource_id: str, index: int):
        super().__init__(context)
        self._datasource_id = datasource_id
        self._index = index

    def _resolve_datasource_element(self) -> ET._Element:
        return TwbDatasource(self._context, self._datasource_id)._resolve_element()

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        elements = relation_elements_in_order(self._resolve_datasource_element())
        if self._index >= len(elements):
            self._detach()
            raise DetachedModelError(f"relation is detached: {self._index}")
        return elements[self._index]

    def _snapshot(self):
        self._resolve_element()
        return relations_in_order(self._resolve_datasource_element())[self._index]

    @property
    def id(self) -> str | None:
        return self._snapshot().id

    @property
    def name(self) -> str | None:
        snapshot = self._snapshot()
        return snapshot.name or snapshot.id

    @property
    def datasource_id(self) -> str:
        return self._datasource_id

    @property
    def type(self) -> str | None:
        return self._snapshot().type

    @property
    def table(self) -> str | None:
        return self._snapshot().table

    @property
    def connection(self) -> str | None:
        return self._snapshot().connection

    @property
    def join(self) -> str | None:
        return self._snapshot().join

    @property
    def custom_sql(self) -> str | None:
        return self._snapshot().custom_sql

    @property
    def scope(self) -> str | None:
        return self._snapshot().scope

    @property
    def logical_table(self) -> str | None:
        return self._snapshot().logical_table

    @property
    def logical_table_id(self) -> str | None:
        return self._snapshot().logical_table_id

    @property
    def clauses(self) -> list[dict[str, object]]:
        return self._snapshot().clauses

    @property
    def attrs(self) -> dict[str, str]:
        return self._snapshot().attrs

    def get_children(self) -> list["TwbRelation"]:
        """入れ子になったリレーション。join / union は子を持つ。"""
        element = self._resolve_element()
        elements = relation_elements_in_order(self._resolve_datasource_element())
        return [
            TwbRelation(self._context, self._datasource_id, elements.index(child))
            for child in element
            if ET.QName(child).localname == "relation"
        ]


class TwbRelationship(ConnectedModel):
    """論理テーブル間のリレーションシップ。**読み取り専用**（`TwbRelation` と同じ理由）。"""

    def __init__(self, context: WorkbookContext, datasource_id: str, index: int):
        super().__init__(context)
        self._datasource_id = datasource_id
        self._index = index

    def _resolve_datasource_element(self) -> ET._Element:
        return TwbDatasource(self._context, self._datasource_id)._resolve_element()

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        elements = relationship_elements(self._resolve_datasource_element())
        if self._index >= len(elements):
            self._detach()
            raise DetachedModelError(f"relationship is detached: {self._index}")
        return elements[self._index]

    def _snapshot(self):
        self._resolve_element()
        return list_relationships_from_datasource(self._resolve_datasource_element())[self._index]

    @property
    def id(self) -> str | None:
        return self._snapshot().id

    @property
    def name(self) -> str | None:
        return self._snapshot().id

    @property
    def datasource_id(self) -> str:
        return self._datasource_id

    @property
    def left_object(self) -> str | None:
        return self._snapshot().left_object

    @property
    def left_object_id(self) -> str | None:
        return self._snapshot().left_object_id

    @property
    def right_object(self) -> str | None:
        return self._snapshot().right_object

    @property
    def right_object_id(self) -> str | None:
        return self._snapshot().right_object_id

    @property
    def expression(self) -> dict[str, object] | None:
        return self._snapshot().expression

    @property
    def attrs(self) -> dict[str, str]:
        return self._snapshot().attrs


class TwbField(ConnectedModel):
    def __init__(
        self,
        context: WorkbookContext,
        datasource_id: str,
        field_id: str,
        *,
        datasource_el: ET._Element | None = None,
        definition: _FieldDefinition | None = None,
    ):
        super().__init__(context)
        self._datasource_id = datasource_id
        self._id = field_id
        self._definition_cache = (
            (context.revision, context.cache_epoch, datasource_el, definition)
            if datasource_el is not None and definition is not None
            else None
        )

    @property
    def datasource_id(self) -> str:
        self._ensure_attached()
        return self._datasource_id

    def _resolve_datasource_element(self) -> ET._Element:
        self._ensure_attached()
        hits = self._context.tree.getroot().xpath(
            "/workbook/datasources/datasource[@name=$id]",
            id=self._datasource_id,
        )
        if not hits:
            self._detach()
            raise DetachedModelError(f"datasource is detached: {self._datasource_id}")
        return hits[0]

    def _resolve_definition(self) -> tuple[ET._Element, _FieldDefinition]:
        self._ensure_attached()
        if self._definition_cache is not None:
            revision, cache_epoch, datasource_el, definition = self._definition_cache
            if (
                revision == self._context.revision
                and cache_epoch == self._context.cache_epoch
            ):
                return datasource_el, definition
        datasource_el = self._resolve_datasource_element()
        for definition in _effective_field_definitions(datasource_el):
            if definition.id == self._id:
                self._definition_cache = (
                    self._context.revision,
                    self._context.cache_epoch,
                    datasource_el,
                    definition,
                )
                return datasource_el, definition
        self._detach()
        raise DetachedModelError(f"field is detached: {self._id}")

    def _resolve_element(self) -> ET._Element:
        _, definition = self._resolve_definition()
        if definition.column is not None:
            return definition.column
        assert definition.metadata is not None
        return _column_from_metadata_record(definition.metadata)

    def _materialize_element(self) -> ET._Element:
        datasource_el, definition = self._resolve_definition()
        if definition.column is not None:
            return definition.column
        assert definition.metadata is not None
        column = _column_from_metadata_record(definition.metadata)
        _insert_field_column(datasource_el, column)
        self._context.mark_dirty()
        return column

    def _snapshot(self, datasource_el: ET._Element | None = None) -> Any:
        if datasource_el is None:
            datasource_el = self._resolve_datasource_element()
        for field in list_columns_from_datasource(datasource_el):
            if field.id == self._id:
                return field
        self._detach()
        raise DetachedModelError(f"field is detached: {self._id}")

    @property
    def id(self) -> str:
        self._resolve_definition()
        return self._id

    @property
    def name(self) -> str:
        _, definition = self._resolve_definition()
        return _field_display_name(definition)

    @property
    def datatype(self) -> str | None:
        _, definition = self._resolve_definition()
        if definition.column is not None:
            return definition.column.get("datatype")
        assert definition.metadata is not None
        return _metadata_text(definition.metadata, "local-type")

    @property
    def default_aggregation(self) -> str | None:
        _, definition = self._resolve_definition()
        if definition.metadata is None:
            return None
        value = (_metadata_text(definition.metadata, "aggregation") or "").lower()
        return {
            "sum": "sum",
            "average": "avg",
            "avg": "avg",
            "minimum": "min",
            "min": "min",
            "maximum": "max",
            "max": "max",
            "count": "count",
            "countd": "countd",
            "countdistinct": "countd",
            "attribute": "attr",
            "attr": "attr",
        }.get(value)

    @property
    def role(self) -> str | None:
        _, definition = self._resolve_definition()
        if definition.column is not None:
            return definition.column.get("role")
        assert definition.metadata is not None
        return _metadata_field_role(definition.metadata)

    @property
    def discrete(self) -> bool | None:
        _, definition = self._resolve_definition()
        if definition.column is None:
            assert definition.metadata is not None
            return _metadata_field_role(definition.metadata) == "dimension"
        value = definition.column.get("type")
        if value == "nominal":
            return True
        if value == "quantitative":
            return False
        return None

    @property
    def hidden(self) -> bool:
        _, definition = self._resolve_definition()
        if definition.column is None:
            return False
        return (definition.column.get("hidden") or "false").lower() == "true"

    @property
    def formula(self) -> str | None:
        datasource_el, definition = self._resolve_definition()
        if definition.column is None:
            return None
        return self._snapshot(datasource_el).formula

    @property
    def raw_formula(self) -> str | None:
        datasource_el, definition = self._resolve_definition()
        if definition.column is None:
            return None
        return self._snapshot(datasource_el).raw_formula

    @property
    def referenced_fields(self) -> list[str]:
        raw_formula = self.raw_formula
        if raw_formula is None:
            return []

        references: list[str] = []
        for match in _FORMULA_REFERENCE_RE.finditer(raw_formula):
            datasource_token, qualified_field, local_field = match.groups()
            target_datasource = self._resolve_datasource_element()
            if datasource_token is not None:
                candidates = [
                    element
                    for element in datasource_elements(self._context.tree, include_parameters=True)
                    if get_xml_id(element) == datasource_token
                    or get_display_name(element) == datasource_token
                ]
                if len(candidates) != 1:
                    reference_id = match.group(0)
                    if reference_id not in references:
                        references.append(reference_id)
                    continue
                target_datasource = candidates[0]

            field_token = qualified_field or local_field or ""
            field_candidates = [
                element
                for element in target_datasource.findall("./column")
                if get_xml_id(element) in {field_token, f"[{field_token}]"}
            ]
            if len(field_candidates) == 1:
                field_id = get_xml_id(field_candidates[0])
                reference_id = (
                    f"{get_xml_id(target_datasource)}.{field_id}"
                    if datasource_token is not None
                    else field_id
                )
            else:
                reference_id = match.group(0)
            if reference_id not in references:
                references.append(reference_id)
        return references

    @property
    def formats(self) -> list[dict[str, str]]:
        datasource_el, definition = self._resolve_definition()
        if definition.column is None:
            return []
        return [dict(item) for item in self._snapshot(datasource_el).format]

    @property
    def folder(self) -> TwbFolder | None:
        datasource_el, definition = self._resolve_definition()
        if definition.column is None:
            return None
        folder_name = self._snapshot(datasource_el).folder
        if folder_name is None:
            return None
        return TwbFolder(self._context, self._datasource_id, folder_name)

    @property
    def is_calculated(self) -> bool:
        _, definition = self._resolve_definition()
        return definition.column is not None and definition.column.find("./calculation") is not None

    def update(
        self,
        *,
        name: str | None | _UnsetType = UNSET,
        datatype: str | _UnsetType = UNSET,
        role: str | _UnsetType = UNSET,
        discrete: bool | None | _UnsetType = UNSET,
        hidden: bool | _UnsetType = UNSET,
        formula: str | _UnsetType = UNSET,
        formula_ref: str = "auto",
        strict: bool = True,
        ref_map: dict[str, str] | None = None,
    ) -> TwbField:
        datasource_el, definition = self._resolve_definition()
        field_el = definition.column
        if field_el is None:
            assert definition.metadata is not None
            field_el = _column_from_metadata_record(definition.metadata)

        resolved_name: str | None | _UnsetType = name
        if name is not UNSET and name is not None:
            resolved_name = name.strip()
            if not resolved_name:
                raise ValueError("name must not be empty")
            for other in _effective_field_definitions(datasource_el):
                if other.id == self._id:
                    continue
                if _field_display_name(other) == resolved_name:
                    raise ValueError(f"field name already exists: {resolved_name}")

        if datatype is not UNSET:
            if not isinstance(datatype, str) or not datatype.strip():
                raise ValueError("datatype must be a non-empty string")
            datatype = datatype.strip()
            if definition.column is None or definition.column.find("./calculation") is None:
                raise UnsupportedFeatureError(
                    "datatype can only be changed on calculated fields"
                )
        if role is not UNSET and not isinstance(role, str):
            raise TypeError("role must be a string")
        if discrete is not UNSET and discrete is not None and not isinstance(discrete, bool):
            raise TypeError("discrete must be bool or None")
        if hidden is not UNSET and not isinstance(hidden, bool):
            raise TypeError("hidden must be bool")
        if formula is UNSET and (formula_ref != "auto" or ref_map is not None or strict is not True):
            raise ValueError("formula options require formula")

        normalized_formula: str | _UnsetType = UNSET
        if formula is not UNSET:
            if not isinstance(formula, str) or not formula.strip():
                raise ValueError("formula must not be empty")
            effective_ref_map = dict(ref_map or {})
            if resolved_name is not UNSET:
                future_name = (
                    self._id.strip("[]")
                    if resolved_name is None
                    else resolved_name
                )
                effective_ref_map.setdefault(future_name, self._id)
            normalized_formula = normalize_formula_for_datasource(
                datasource_el,
                formula,
                formula_ref=formula_ref,
                strict=strict,
                ref_map=effective_ref_map or None,
            )

        updated = copy.deepcopy(field_el)
        if resolved_name is not UNSET:
            if resolved_name is None:
                updated.attrib.pop("caption", None)
            else:
                updated.set("caption", resolved_name)
        if datatype is not UNSET:
            updated.set("datatype", datatype)
        if role is not UNSET:
            updated.set("role", role)
        if discrete is not UNSET:
            if discrete is None:
                updated.attrib.pop("type", None)
            else:
                updated.set("type", "nominal" if discrete else "quantitative")
        if hidden is not UNSET:
            updated.set("hidden", "true" if hidden else "false")
        if normalized_formula is not UNSET:
            calculation = updated.find("./calculation")
            if calculation is None:
                calculation = ET.SubElement(updated, "calculation")
                calculation.set("class", "tableau")
            calculation.set("formula", normalized_formula)

        if definition.column is None:
            if not xml_equal(field_el, updated):
                _insert_field_column(datasource_el, updated)
                self._context.mark_dirty()
        else:
            _replace_if_changed(field_el, updated, self._context)
        return self

    def move_to_folder(self, folder: TwbFolder) -> TwbField:
        if not isinstance(folder, TwbFolder):
            raise TypeError("folder must be TwbFolder")
        folder._ensure_attached()
        folder._resolve_element()
        if folder._context is not self._context or folder.datasource_id != self._datasource_id:
            raise ValueError("folder must belong to the same datasource")
        datasource_el = self._resolve_datasource_element()
        self._materialize_element()
        before = ET.tostring(datasource_el)
        move_column_to_folder_el(
            datasource_el,
            self._id,
            folder.id,
            by="name",
            create_if_missing=False,
        )
        if before != ET.tostring(datasource_el):
            self._context.mark_dirty()
        return self

    def remove_from_folder(self) -> TwbField:
        datasource_el, definition = self._resolve_definition()
        if definition.column is None:
            return self
        before = ET.tostring(datasource_el)
        remove_column_from_folder_el(datasource_el, self._id, by="name")
        if before != ET.tostring(datasource_el):
            self._context.mark_dirty()
        return self

    def delete(self) -> None:
        _, definition = self._resolve_definition()
        field_el = definition.column
        if field_el is None:
            raise UnsupportedFeatureError("physical metadata fields cannot be deleted")
        references = field_references(
            self._context.tree,
            self._datasource_id,
            self._id,
        )
        if references:
            raise ResourceInUseError("Field", self._id, references)
        parent = field_el.getparent()
        if parent is None:
            raise DetachedModelError(f"field is detached: {self._id}")
        parent.remove(field_el)
        self._context.mark_dirty()
        self._detach()


class TwbFolder(ConnectedModel):
    def __init__(self, context: WorkbookContext, datasource_id: str, folder_id: str):
        super().__init__(context)
        self._datasource_id = datasource_id
        self._id = folder_id

    @property
    def datasource_id(self) -> str:
        self._ensure_attached()
        return self._datasource_id

    def _resolve_datasource_element(self) -> ET._Element:
        self._ensure_attached()
        hits = self._context.tree.getroot().xpath(
            "/workbook/datasources/datasource[@name=$id]",
            id=self._datasource_id,
        )
        if not hits:
            self._detach()
            raise DetachedModelError(f"datasource is detached: {self._datasource_id}")
        return hits[0]

    def _resolve_element(self) -> ET._Element:
        for folder_el in _folder_elements(self._resolve_datasource_element()):
            if folder_el.get("name") == self._id:
                return folder_el
        self._detach()
        raise DetachedModelError(f"folder is detached: {self._id}")

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        self._resolve_element()
        return self._id

    def get_fields(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbField]:
        _validate_get_args(id, name)
        folder_el = self._resolve_element()
        item_ids = [
            item.get("name")
            for item in folder_el.findall("./folder-item")
            if item.get("name")
        ]
        fields = TwbDatasource(self._context, self._datasource_id).get_fields()
        by_id = {field.id: field for field in fields}
        result: list[TwbField] = []
        for field_id in item_ids:
            field = by_id.get(field_id)
            if field is None:
                continue
            if _matches(model_id=field.id, model_name=field.name, id=id, name=name):
                result.append(field)
        return result

    def delete(self) -> None:
        folder_el = self._resolve_element()
        items = [
            item
            for item in folder_el.findall("./folder-item")
            if item.get("name")
        ]
        if items:
            tree = self._context.tree
            references = [
                ResourceReference(
                    resource_type="Field",
                    resource_id=item.get("name") or "",
                    location=f"{tree.getpath(item)}/@name",
                )
                for item in items
            ]
            raise ResourceInUseError("Folder", self._id, references)
        parent = folder_el.getparent()
        if parent is None:
            raise DetachedModelError(f"folder is detached: {self._id}")
        parent.remove(folder_el)
        self._context.mark_dirty()
        self._detach()


def get_datasources(
    context: WorkbookContext,
    *,
    id: str | None = None,
    name: str | None = None,
) -> list[TwbDatasource]:
    _validate_get_args(id, name)
    result: list[TwbDatasource] = []
    for datasource_el in datasource_elements(context.tree, include_parameters=False):
        datasource_id = datasource_el.get("name")
        if not datasource_id:
            continue
        datasource_name = get_display_name(datasource_el)
        if _matches(model_id=datasource_id, model_name=datasource_name, id=id, name=name):
            result.append(TwbDatasource(context, datasource_id))
    return result
