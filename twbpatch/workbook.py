from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from lxml import etree as ET
from .parser import ParsedWorkbook, open_workbook_file
from .writer import save_twb, save_twbx
from .models import (
    BigQuerySource,
    CsvSource,
    ExcelSource,
    TwbColumn,
    TwbDashboardAction,
    TwbDashboardZone,
    TwbDashboard,
    TwbDatasource,
    TwbFilterControl,
    TwbParameter,
    TwbRelation,
    TwbRelationship,
    TwbReferenceLine,
    TwbUnsupportedFeature,
    TwbValidationMessage,
    TwbWorksheet,
    TwbWorksheetField,
    TwbWorksheetFilter,
    UnknownSource,
)
from .datasource import datasource_elements, list_datasources_from_tree, resolve_datasource_el, update_source_el
from .column import list_columns_from_datasource, resolve_column_el, rename_column_el, reset_column_caption_el, update_column_el
from .calculation import create_calculated_field_el, update_formula_el
from .parameter import list_parameters_from_tree
from .folder import move_column_to_folder_el, remove_column_from_folder_el
from .validator import validate_tree
from .unsupported import unsupported_features_from_tree
from .dashboard import dashboard_elements, get_dashboard_from_tree, list_dashboards_from_tree, resolve_dashboard_el
from .dashboard_field import list_dashboard_fields_from_tree
from .dashboard_action import list_actions_from_tree
from .dashboard_zone import list_zones_from_dashboard
from .filter import list_dashboard_filter_controls_from_tree, list_filters_from_tree
from .worksheet import (
    get_worksheet_from_tree,
    list_reference_lines_from_tree,
    list_worksheet_fields_from_tree,
    list_worksheets_from_tree,
)
from .relation import list_relations_from_datasource, list_relationships_from_datasource
from .errors import AmbiguousCaptionError, NotFoundError, SaveError, ValidationError
from .connected import TwbDatasource as ConnectedDatasource, get_datasources as get_connected_datasources
from .connected_worksheet import (
    TwbWorksheet as ConnectedWorksheet,
    create_worksheet as create_connected_worksheet,
    get_worksheets as get_connected_worksheets,
)
from .connected_dashboard import (
    TwbDashboard as ConnectedDashboard,
    create_dashboard as create_connected_dashboard,
    get_dashboards as get_connected_dashboards,
)
from .connected_parameter import (
    TwbParameter as ConnectedParameter,
    create_parameter as create_connected_parameter,
    get_parameters as get_connected_parameters,
)
from .context import WorkbookContext
from .serialization import serialize_workbook
from .html_export import render_workbook_html

if TYPE_CHECKING:
    from .draw import FieldInput


class TwbWorkbook:
    def __init__(self, parsed: ParsedWorkbook):
        self._parsed = parsed
        self.tree = parsed.tree
        self._context = WorkbookContext(self.tree)

    @classmethod
    def open(cls, path: str) -> "TwbWorkbook":
        return cls(open_workbook_file(path))

    @property
    def is_dirty(self) -> bool:
        return self._context.is_dirty

    def reload(self) -> "TwbWorkbook":
        parsed = open_workbook_file(str(self._parsed.source_path))
        self._parsed = parsed
        self.tree = parsed.tree
        self._context.replace_tree(self.tree)
        return self

    def set_default_font(self, font: str = "Meiryo UI") -> TwbWorkbook:
        if not isinstance(font, str):
            raise TypeError("font must be a string")
        font = font.strip()
        if not font or len(font) > 50:
            raise ValueError("font must contain 1 to 50 characters")

        root = self.tree.getroot()
        updated_root = copy.deepcopy(root)
        styles = updated_root.xpath("./*[local-name()='style']")
        if styles:
            style = styles[0]
        else:
            style = ET.Element("style")
            insert_at = next(
                (
                    index
                    for index, child in enumerate(updated_root)
                    if ET.QName(child).localname
                    in {"datasources", "worksheets", "dashboards", "windows"}
                ),
                len(updated_root),
            )
            updated_root.insert(insert_at, style)
        rules = style.xpath("./*[local-name()='style-rule'][@element='all']")
        if rules:
            rule = rules[0]
        else:
            rule = ET.SubElement(style, "style-rule", attrib={"element": "all"})
        formats = rule.xpath("./*[local-name()='format'][@attr='font-family']")
        if formats:
            formats[0].set("value", font)
            for duplicate in formats[1:]:
                rule.remove(duplicate)
        else:
            ET.SubElement(
                rule,
                "format",
                attrib={"attr": "font-family", "value": font},
            )
        if ET.tostring(root) != ET.tostring(updated_root):
            self.tree._setroot(updated_root)
            self._context.mark_dirty()
        return self

    def save(self, path: str, *, validate: bool = True, overwrite: bool = False) -> None:
        if validate:
            errors = [m for m in self.validate() if m.severity == "error"]
            if errors:
                raise ValidationError(f"validation failed: {errors[0].code}: {errors[0].message}")
        if path.lower().endswith(".twbx"):
            if not self._parsed.is_twbx or not self._parsed.extract_dir or not self._parsed.twb_inner_path:
                raise SaveError(".twbx 保存には .twbx から開いたワークブックが必要です。")
            save_twbx(
                self.tree,
                path,
                extract_dir=self._parsed.extract_dir,
                twb_inner_path=self._parsed.twb_inner_path,
                overwrite=overwrite,
            )
        else:
            save_twb(self.tree, path, overwrite=overwrite)
        self._context.mark_saved()

    def export_json(self) -> dict:
        return serialize_workbook(self)

    def export_html(
        self,
        path: str | Path,
        *,
        title: str = "twbpatch 設定",
        overwrite: bool = False,
    ) -> Path:
        target = Path(path)
        if target.exists() and not overwrite:
            raise FileExistsError(f"file already exists: {target}")
        html = render_workbook_html(serialize_workbook(self), title=title)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        return target

    def validate(self) -> list[TwbValidationMessage]:
        return validate_tree(self.tree)

    def unsupported_features(self) -> list[TwbUnsupportedFeature]:
        return unsupported_features_from_tree(self.tree)

    def get_unsupported_features(self) -> list[TwbUnsupportedFeature]:
        return unsupported_features_from_tree(self.tree)


    def list_dashboards(self) -> list[TwbDashboard]:
        return list_dashboards_from_tree(self.tree)

    def get_dashboards(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[ConnectedDashboard]:
        return get_connected_dashboards(self._context, id=id, name=name)

    def create_dashboard(
        self,
        *,
        name: str,
        width: int = 1200,
        height: int = 800,
        sizing_mode: str = "fixed",
    ) -> ConnectedDashboard:
        return create_connected_dashboard(
            self._context,
            name=name,
            width=width,
            height=height,
            sizing_mode=sizing_mode,
        )

    def get_dashboard(self, dashboard: str, *, by: str = "auto") -> TwbDashboard:
        return get_dashboard_from_tree(self.tree, dashboard, by=by)

    def list_dashboard_fields(
        self,
        dashboard: str | None = None,
        *,
        by: str = "auto",
        max_filter_value_chars: int = 40,
    ) -> list[TwbWorksheetField]:
        return list_dashboard_fields_from_tree(
            self.tree,
            dashboard,
            by=by,
            max_filter_value_chars=max_filter_value_chars,
        )

    def list_dashboard_zones(
        self,
        dashboard: str | None = None,
        *,
        by: str = "auto",
        width_px: int | None = None,
        height_px: int | None = None,
        include_device_layouts: bool = False,
    ) -> list[TwbDashboardZone]:
        dashboard_els = (
            [resolve_dashboard_el(self.tree, dashboard, by=by)]
            if dashboard is not None
            else dashboard_elements(self.tree)
        )
        return [
            zone
            for dashboard_el in dashboard_els
            for zone in list_zones_from_dashboard(
                dashboard_el,
                width_px=width_px,
                height_px=height_px,
                include_device_layouts=include_device_layouts,
            )
        ]

    def list_dashboard_actions(
        self,
        dashboard: str | None = None,
        *,
        by: str = "auto",
    ) -> list[TwbDashboardAction]:
        if dashboard is None:
            return list_actions_from_tree(self.tree)
        dashboard_el = resolve_dashboard_el(self.tree, dashboard, by=by)
        return list_actions_from_tree(self.tree, dashboard_el)

    def list_worksheets(self) -> list[TwbWorksheet]:
        return list_worksheets_from_tree(self.tree)

    def get_worksheets(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[ConnectedWorksheet]:
        return get_connected_worksheets(self._context, id=id, name=name)

    def create_worksheet(
        self,
        *,
        name: str,
        visible: bool = True,
    ) -> ConnectedWorksheet:
        return create_connected_worksheet(
            self._context,
            name=name,
            visible=visible,
        )

    def set_filter(self, field: tuple[str, str]) -> TwbWorkbook:
        if (
            not isinstance(field, tuple)
            or len(field) != 2
            or not all(isinstance(value, str) and value.strip() for value in field)
        ):
            raise TypeError("field must be (datasource name, field name)")
        datasource_name, field_name = field
        datasources = self.get_datasources(name=datasource_name)
        if not datasources:
            raise NotFoundError(f"datasource not found: {datasource_name}")
        if len(datasources) > 1:
            raise AmbiguousCaptionError(
                f"datasource name is ambiguous: {datasource_name}"
            )
        datasource = datasources[0]
        fields = datasource.get_fields(name=field_name)
        if not fields:
            raise NotFoundError(f"field not found: {field_name}")
        if len(fields) > 1:
            raise AmbiguousCaptionError(f"field name is ambiguous: {field_name}")

        datasource.set_filter(fields[0])
        for worksheet in self.get_worksheets():
            uses_datasource = worksheet._resolve_element().xpath(
                ".//*[local-name()='datasource-dependencies'][@datasource=$id]"
                " | .//*[local-name()='datasource'][@name=$id]",
                id=datasource.id,
            )
            if uses_datasource:
                worksheet.add_filter_slice(field=fields[0])
        return self

    def draw_sheet(
        self,
        datasource: ConnectedDatasource | None = None,
        *,
        name: str,
        items: list[FieldInput] | None = None,
        item_shelf: str = "rows",
        title: str | None = None,
        visible: bool = True,
    ) -> ConnectedWorksheet:
        from .draw import draw_sheet

        return draw_sheet(
            self,
            datasource,
            name=name,
            items=items,
            item_shelf=item_shelf,
            title=title,
            visible=visible,
        )

    def draw_colored_yoy_sheet(
        self,
        datasource: ConnectedDatasource | None = None,
        *,
        name: str,
        items: list[FieldInput],
        metrics: list[FieldInput],
        negative_color: str = "#ff007f",
        positive_color: str = "#602fff",
        ratio_color: str = "#555555",
        mark_type: str = "bar",
        bar_color: str | None = None,
        axis_min: float = 0,
        axis_max: float = 1,
        show_axes: bool = False,
        bar_opacity: float = 1.0,
        index_partition_by: FieldInput | None = None,
        visible: bool = True,
    ) -> ConnectedWorksheet:
        from .draw import draw_colored_yoy_sheet

        return draw_colored_yoy_sheet(
            self,
            datasource,
            name=name,
            items=items,
            metrics=metrics,
            negative_color=negative_color,
            positive_color=positive_color,
            ratio_color=ratio_color,
            mark_type=mark_type,
            bar_color=bar_color,
            axis_min=axis_min,
            axis_max=axis_max,
            show_axes=show_axes,
            bar_opacity=bar_opacity,
            index_partition_by=index_partition_by,
            visible=visible,
        )

    def draw_yoy(
        self,
        datasource: ConnectedDatasource | None = None,
        *,
        name: str,
        item: FieldInput,
        metric: FieldInput,
        item_shelf: str = "columns",
        aggregation: str = "sum",
        date_level: str = "month",
        color: str | None = None,
        show_axes: bool = True,
        visible: bool = True,
    ) -> ConnectedWorksheet:
        from .draw import draw_yoy

        return draw_yoy(
            self,
            datasource,
            name=name,
            item=item,
            metric=metric,
            item_shelf=item_shelf,
            aggregation=aggregation,
            date_level=date_level,
            color=color,
            show_axes=show_axes,
            visible=visible,
        )

    def draw_bar(
        self,
        datasource: ConnectedDatasource | None = None,
        *,
        name: str,
        item: FieldInput,
        metric: FieldInput,
        item_shelf: str = "rows",
        aggregation: str = "sum",
        descending: bool = True,
        visible: bool = True,
    ) -> ConnectedWorksheet:
        from .draw import draw_bar

        return draw_bar(
            self,
            datasource,
            name=name,
            item=item,
            metric=metric,
            item_shelf=item_shelf,
            aggregation=aggregation,
            descending=descending,
            visible=visible,
        )

    def draw_card(
        self,
        datasource: ConnectedDatasource | None = None,
        *,
        name: str,
        main_metric: FieldInput,
        sub_metric: FieldInput | None = None,
        main_color: str = "#602fff",
        value_color: str = "#333333",
        title_background_color: str | None = None,
        vertical_alignment: str = "center",
        aggregation: str | None = "auto",
        main_aggregation: str | None = "auto",
        sub_aggregation: str | None = "auto",
        visible: bool = True,
    ) -> ConnectedWorksheet:
        from .draw import draw_card

        return draw_card(
            self,
            datasource,
            name=name,
            main_metric=main_metric,
            sub_metric=sub_metric,
            main_color=main_color,
            value_color=value_color,
            title_background_color=title_background_color,
            vertical_alignment=vertical_alignment,
            aggregation=aggregation,
            main_aggregation=main_aggregation,
            sub_aggregation=sub_aggregation,
            visible=visible,
        )

    def draw_quadrant(
        self,
        datasource: ConnectedDatasource | None = None,
        *,
        name: str,
        item: FieldInput,
        x_metric: FieldInput,
        y_metric: FieldInput,
        size_metric: FieldInput,
        colors: tuple[str, str, str, str] | list[str] = (
            "#4400FF",
            "#FF007F",
            "#00C888",
            "#CCD500",
        ),
        x_aggregation: str | None = "auto",
        y_aggregation: str | None = "auto",
        size_aggregation: str | None = "auto",
        opacity: float = 0.6,
        title: str | None = None,
        visible: bool = True,
    ) -> ConnectedWorksheet:
        from .draw import draw_quadrant

        return draw_quadrant(
            self,
            datasource,
            name=name,
            item=item,
            x_metric=x_metric,
            y_metric=y_metric,
            size_metric=size_metric,
            colors=colors,
            x_aggregation=x_aggregation,
            y_aggregation=y_aggregation,
            size_aggregation=size_aggregation,
            opacity=opacity,
            title=title,
            visible=visible,
        )

    def draw_crosstab(
        self,
        datasource: ConnectedDatasource | None = None,
        *,
        name: str,
        x_item: FieldInput,
        y_item: FieldInput,
        color_metric: FieldInput,
        label_metric: FieldInput,
        color_aggregation: str | None = "auto",
        label_aggregation: str | None = "auto",
        min_color: str | None = None,
        mid_color: str | None = None,
        max_color: str | None = None,
        title: str | None = None,
        visible: bool = True,
    ) -> ConnectedWorksheet:
        from .draw import draw_crosstab

        return draw_crosstab(
            self,
            datasource,
            name=name,
            x_item=x_item,
            y_item=y_item,
            color_metric=color_metric,
            label_metric=label_metric,
            color_aggregation=color_aggregation,
            label_aggregation=label_aggregation,
            min_color=min_color,
            mid_color=mid_color,
            max_color=max_color,
            title=title,
            visible=visible,
        )

    def get_worksheet(self, worksheet: str, *, by: str = "auto") -> TwbWorksheet:
        return get_worksheet_from_tree(self.tree, worksheet, by=by)

    def list_worksheet_fields(
        self,
        worksheet: str | None = None,
        *,
        by: str = "auto",
        max_filter_value_chars: int = 40,
    ) -> list[TwbWorksheetField]:
        return list_worksheet_fields_from_tree(
            self.tree,
            worksheet,
            by=by,
            max_filter_value_chars=max_filter_value_chars,
        )

    def list_reference_lines(self, worksheet: str | None = None, *, by: str = "auto") -> list[TwbReferenceLine]:
        return list_reference_lines_from_tree(self.tree, worksheet, by=by)

    def list_filters(self, worksheet: str | None = None, *, by: str = "auto") -> list[TwbWorksheetFilter]:
        return list_filters_from_tree(self.tree, worksheet, by=by)

    def list_dashboard_filter_controls(
        self,
        dashboard: str | None = None,
        *,
        by: str = "auto",
    ) -> list[TwbFilterControl]:
        return list_dashboard_filter_controls_from_tree(self.tree, dashboard, by=by)

    def list_datasources(self) -> list[TwbDatasource]:
        return list_datasources_from_tree(self.tree)

    def get_datasources(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[ConnectedDatasource]:
        return get_connected_datasources(self._context, id=id, name=name)

    def apply_field_config(
        self,
        yaml_path: str | Path,
        *,
        field_grouping: str = "folder",
    ) -> TwbWorkbook:
        with Path(yaml_path).open(encoding="utf-8") as file:
            config = yaml.safe_load(file)
        if not isinstance(config, dict):
            raise ValueError("field config must be a mapping")

        plans: list[tuple[ConnectedDatasource, dict[str, dict[str, str]]]] = []
        for datasource_name, folder_config in config.items():
            matches = self.get_datasources(name=datasource_name)
            if not matches:
                raise NotFoundError(f"datasource not found: {datasource_name}")
            if len(matches) > 1:
                raise AmbiguousCaptionError(
                    f"datasource name is ambiguous: {datasource_name}"
                )
            plans.append((matches[0], folder_config))

        for datasource, folder_config in plans:
            datasource.apply_field_config(
                folder_config,
                field_grouping=field_grouping,
            )
        return self

    def get_datasource(self, datasource: str, *, by: str = "auto") -> TwbDatasource:
        ds_el = resolve_datasource_el(self.tree, datasource, by=by, include_parameters=False)
        for ds in self.list_datasources():
            if ds.id == ds_el.get("name"):
                return ds
        raise RuntimeError("resolved datasource could not be materialized")

    def list_relations(self, datasource: str | None = None, *, by: str = "auto") -> list[TwbRelation]:
        datasource_els = (
            [resolve_datasource_el(self.tree, datasource, by=by, include_parameters=False)]
            if datasource is not None
            else datasource_elements(self.tree, include_parameters=False)
        )
        return [
            relation
            for datasource_el in datasource_els
            for relation in list_relations_from_datasource(datasource_el)
        ]

    def list_relationships(self, datasource: str | None = None, *, by: str = "auto") -> list[TwbRelationship]:
        datasource_els = (
            [resolve_datasource_el(self.tree, datasource, by=by, include_parameters=False)]
            if datasource is not None
            else datasource_elements(self.tree, include_parameters=False)
        )
        return [
            relationship
            for datasource_el in datasource_els
            for relationship in list_relationships_from_datasource(datasource_el)
        ]

    def list_parameters(self, *, include_hidden: bool = False) -> list[TwbParameter]:
        return list_parameters_from_tree(self.tree, include_hidden=include_hidden)

    def get_parameters(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        include_hidden: bool = False,
    ) -> list[ConnectedParameter]:
        return get_connected_parameters(
            self._context,
            id=id,
            name=name,
            include_hidden=include_hidden,
        )

    def create_parameter(
        self,
        *,
        name: str,
        value: object,
        datatype: str = "string",
        domain_type: str = "any",
        allowable_values: list[object] | dict[object, str] | None = None,
        min_value: object | None = None,
        max_value: object | None = None,
        step_size: object | None = None,
        hidden: bool = False,
    ) -> ConnectedParameter:
        return create_connected_parameter(
            self._context,
            name=name,
            value=value,
            datatype=datatype,
            domain_type=domain_type,
            allowable_values=allowable_values,
            min_value=min_value,
            max_value=max_value,
            step_size=step_size,
            hidden=hidden,
        )

    def _materialize_column_from_el(self, datasource_el: ET._Element, column_el: ET._Element) -> TwbColumn:
        column_name = column_el.get("name")
        for col in list_columns_from_datasource(datasource_el):
            if col.name == column_name:
                return col
        raise RuntimeError("resolved column could not be materialized")

    def update_source(
        self,
        datasource: str,
        source: BigQuerySource | ExcelSource | CsvSource | UnknownSource,
    ) -> None:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        update_source_el(ds_el, source)

    def list_columns(self, datasource: str) -> list[TwbColumn]:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        return list_columns_from_datasource(ds_el)

    def get_column(self, datasource: str, column: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        col_el = resolve_column_el(ds_el, column, by=by)
        return self._materialize_column_from_el(ds_el, col_el)

    def rename_field(self, datasource: str, field: str, caption: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = rename_column_el(ds_el, field, caption, by=by)
        return self._materialize_column_from_el(ds_el, col_el)

    def reset_field_caption(self, datasource: str, field: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = reset_column_caption_el(ds_el, field, by=by)
        return self._materialize_column_from_el(ds_el, col_el)

    def update_column(
        self,
        datasource: str,
        column: str,
        *,
        by: str = "auto",
        caption: str | None = None,
        role: str | None = None,
        discrete: bool | None = None,
        hidden: bool | None = None,
        folder: str | None = None,
    ) -> None:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        col_el = resolve_column_el(ds_el, column, by=by)
        update_column_el(col_el, caption=caption, role=role, discrete=discrete, hidden=hidden)
        if folder is not None:
            move_column_to_folder_el(ds_el, col_el.get("name") or column, folder, by="name")

    def update_formula(
        self,
        datasource: str,
        column: str,
        formula: str,
        *,
        by: str = "auto",
        formula_ref: str = "auto",
        strict: bool = False,
        ref_map: dict[str, str] | None = None,
    ) -> None:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        update_formula_el(ds_el, column, formula, by=by, formula_ref=formula_ref, strict=strict, ref_map=ref_map)

    def create_calculated_field(
        self,
        datasource: str,
        caption: str,
        formula: str,
        *,
        datatype: str = "real",
        role: str = "measure",
        discrete: bool | None = False,
        folder: str | None = None,
        hidden: bool = False,
        number_format: str | None = None,
        formula_ref: str = "auto",
        strict: bool = False,
        ref_map: dict[str, str] | None = None,
    ) -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        created = create_calculated_field_el(
            ds_el,
            name=None,
            caption=caption,
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
        if folder is not None:
            move_column_to_folder_el(ds_el, created.name, folder, by="name", role="measures" if role == "measure" else None)
        created_el = resolve_column_el(ds_el, created.name, by="name")
        return self._materialize_column_from_el(ds_el, created_el)

    def move_field_to_folder(
        self,
        datasource: str,
        field: str,
        folder: str,
        *,
        by: str = "auto",
        role: str | None = None,
        create_if_missing: bool = True,
    ) -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = resolve_column_el(ds_el, field, by=by)
        move_column_to_folder_el(
            ds_el,
            col_el.get("name") or field,
            folder,
            by="name",
            role=role,
            create_if_missing=create_if_missing,
        )
        return self._materialize_column_from_el(ds_el, col_el)

    def remove_field_from_folder(self, datasource: str, field: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = resolve_column_el(ds_el, field, by=by)
        remove_column_from_folder_el(ds_el, col_el.get("name") or field, by="name")
        return self._materialize_column_from_el(ds_el, col_el)

    def move_column_to_folder(
        self,
        datasource: str,
        column: str,
        folder: str,
        *,
        by: str = "auto",
        role: str | None = None,
        create_if_missing: bool = True,
    ) -> TwbColumn:
        return self.move_field_to_folder(
            datasource,
            column,
            folder,
            by=by,
            role=role,
            create_if_missing=create_if_missing,
        )
