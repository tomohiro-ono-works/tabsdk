from __future__ import annotations

import copy
import re
import uuid
from dataclasses import dataclass
from typing import Any, TypedDict

from lxml import etree as ET

from .connected import TwbField, get_display_name, get_xml_id, _matches, _validate_get_args
from .context import (
    UNSET,
    ConnectedModel,
    WorkbookContext,
    _UnsetType,
    validate_style_group as _validate_style_group,
    xml_equal,
)
from .errors import DetachedModelError, ResourceInUseError, UnsupportedFeatureError
from .field_input import (
    FieldInput,
    resolve_field_input,
    worksheet_datasources,
)
from .field_ref import FIELD_REF_RE, field_name_from_token
from .filter import list_filters_from_tree
from .references import worksheet_references
from .worksheet import list_reference_lines_from_tree, worksheet_elements


class TableStyle(TypedDict, total=False):
    """`TwbWorksheet.update(table_style=...)` が受け取る表スタイル。"""

    header_background: str | None
    header_bold: bool | None
    header_color: str | None
    row_band: bool | None
    column_widths: dict[str, int]


class LabelStyle(TypedDict, total=False):
    """`TwbPane.update(label_style=...)` が受け取るラベル表示の設定。"""

    show: bool
    cull: bool


class TitleStyle(TypedDict, total=False):
    """`TwbWorksheet.update(title_style=...)` が受け取るタイトルスタイル。"""

    background_color: str


class GrandTotals(TypedDict, total=False):
    """`TwbWorksheet.update(grand_totals=...)` が受け取る総計の設定。

    値は合計が現れる位置。`None` は総計を付けないことを表す。
    """

    row: str | None
    column: str | None


_TABLE_STYLE_KEYS = frozenset(TableStyle.__annotations__)
_TITLE_STYLE_KEYS = frozenset(TitleStyle.__annotations__)
_LABEL_STYLE_KEYS = frozenset(LabelStyle.__annotations__)
_GRAND_TOTALS_KEYS = frozenset(GrandTotals.__annotations__)
# 総計は新しい要素ではなく、既存シェルフ要素の属性として書かれる。
# <rows total="true" onTop="true|false"> / <cols total="true" onLeft="true|false">
_GRAND_TOTAL_SHELVES = {
    "row": ("rows", "onTop", {"top": True, "bottom": False}),
    "column": ("cols", "onLeft", {"left": True, "right": False}),
}

_FIELD_REF = re.compile(r"^\[([^\]]+)\]\.\[([^\]]+)\]$")
_SHELVES = {"rows": "rows", "columns": "cols", "pages": "pages"}
_AGGREGATIONS = {
    "agg": "usr",
    "sum": "sum",
    "avg": "avg",
    "min": "min",
    "max": "max",
    "count": "cnt",
    "countd": "ctd",
    "attr": "attr",
}
_STORED_AGGREGATIONS = {value: key for key, value in _AGGREGATIONS.items()}
_ENCODINGS = {
    "color": "color",
    "label": "text",
    "size": "size",
    "detail": "lod",
    "tooltip": "tooltip",
    "shape": "shape",
    "path": "path",
    "angle": "wedge-size",
}
_STORED_ENCODINGS = {value: key for key, value in _ENCODINGS.items()}
_MARK_TYPES = {
    "automatic": "Automatic",
    "bar": "Bar",
    "line": "Line",
    "text": "Text",
    "circle": "Circle",
    "square": "Square",
    "shape": "Shape",
    "area": "Area",
    "pie": "Pie",
}
_TABLE_CALCULATIONS = {
    "automatic": (None, None),
    "table_down": ("Rows", "Columns"),
    "field": ("Rows", "Field"),
}
_DATE_LEVELS = {
    "month": ("tmn", "Month-Trunc"),
}
_VIEW_CHILD_ORDER = (
    "datasources",
    "mapsources",
    "datasource-dependencies",
    "filter",
    "computed-sort",
    "sort",
    "perspectives",
    "slices",
    "aggregation",
)
_TABLE_CHILD_ORDER = (
    "view",
    "style",
    "panes",
    "mark-layout",
    "rows",
    "cols",
    "table-calc-densification",
    "pages",
    "join-lod-include-overrides",
    "join-lod-exclude-overrides",
    "subtotals",
)
_PANE_CHILD_ORDER = (
    "view", "mark", "mark-sizing", "encodings", "label-data", "dropline",
    "trendline", "reference-line", "customized-tooltip", "customized-label",
    "style",
)
_DATASOURCE_CHILD_ORDER = (
    "repository-location", "connection", "utility-dimensions", "dimension",
    "overridable-settings", "aliases", "column", "column-instance", "group",
    "mapped-images", "drill-paths", "unlinked-server-hierarchies",
    "folders-common", "folders-parameters", "actions", "calculated-members",
    "extract", "layout", "style", "semantic-values", "date-options",
    "default-date-format", "default-sorts", "field-sort-info",
    "datasource-dependencies", "explainability", "filter", "object-graph",
)
_STYLE_RULE_ORDER = (
    "axis", "title", "header", "field-labels", "field-labels-decoration", "pane", "table"
)
_TRANSPARENT = "#00000000"


def _local_name(element: ET._Element) -> str:
    return ET.QName(element).localname


def _direct_child(parent: ET._Element, local_name: str) -> ET._Element | None:
    return next((child for child in parent if _local_name(child) == local_name), None)


def _insert_in_order(
    parent: ET._Element,
    child: ET._Element,
    order: tuple[str, ...],
) -> None:
    rank = {name: index for index, name in enumerate(order)}
    target_rank = rank[_local_name(child)]
    insert_at = len(parent)
    for index, existing in enumerate(parent):
        if rank.get(_local_name(existing), len(order)) > target_rank:
            insert_at = index
            break
    parent.insert(insert_at, child)


def _ensure_manifest_feature(context: WorkbookContext, name: str) -> None:
    root = context.tree.getroot()
    manifest = _direct_child(root, "document-format-change-manifest")
    if manifest is None:
        manifest = ET.Element("document-format-change-manifest")
        root.insert(0, manifest)
    if _direct_child(manifest, name) is not None:
        return
    feature = ET.Element(name)
    insert_at = next(
        (index for index, child in enumerate(manifest) if _local_name(child) > name),
        len(manifest),
    )
    manifest.insert(insert_at, feature)
    context.mark_dirty()


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


def _validate_grand_totals(
    value: dict[str, Any] | _UnsetType,
) -> dict[str, Any] | _UnsetType:
    """`update(grand_totals=...)` の位置指定を XML へ触れる前に検証する。"""
    if value is UNSET:
        return value
    for key, position in value.items():
        if position is None:
            continue
        positions = _GRAND_TOTAL_SHELVES[key][2]
        if position not in positions:
            expected = " or ".join(sorted(positions))
            raise ValueError(f"grand_totals[{key!r}] must be {expected} or None")
    return value


def _worksheet_display_name(element: ET._Element) -> str:
    return get_xml_id(element)


def _rename_worksheet_references(
    root: ET._Element,
    old_id: str,
    new_id: str,
) -> None:
    for window in root.xpath(
        "/workbook/windows/window[@class='worksheet'][@name=$old_id]",
        old_id=old_id,
    ):
        window.set("name", new_id)

    for zone in root.xpath(
        "//*[local-name()='zone'][@name=$old_id]",
        old_id=old_id,
    ):
        zone.set("name", new_id)

    # ダッシュボードの window が持つ viewpoint も worksheet の内部 ID を指す
    for viewpoint in root.xpath(
        "/workbook/windows/window/*[local-name()='viewpoints']"
        "/*[local-name()='viewpoint'][@name=$old_id]",
        old_id=old_id,
    ):
        viewpoint.set("name", new_id)

    for action in root.xpath("/workbook/actions/action"):
        for element in action.iterdescendants():
            for attribute, value in list(element.attrib.items()):
                attribute_name = str(attribute).split("}")[-1]
                if attribute_name in {"name", "worksheet", "sheet"} and value == old_id:
                    element.set(attribute, new_id)


def _pane_elements(worksheet_el: ET._Element) -> list[ET._Element]:
    return list(worksheet_el.xpath(".//*[local-name()='panes']/*[local-name()='pane']"))


def _pane_id(pane_el: ET._Element, index: int) -> str:
    return pane_el.get("id") or str(index + 1)


def _field_details(
    context: WorkbookContext,
    worksheet_el: ET._Element,
    reference: str,
) -> tuple[str, str, str, str | None, bool | None]:
    match = _FIELD_REF.match(reference)
    if match is None:
        raise UnsupportedFeatureError(f"unsupported worksheet field reference: {reference}")
    datasource_id, token = match.groups()
    field_token = field_name_from_token(token)
    candidate_ids = {field_token, f"[{field_token}]"}

    columns = context.tree.getroot().xpath(
        "/workbook/datasources/datasource[@name=$datasource_id]/column[@name]",
        datasource_id=datasource_id,
    )
    column_el = next((column for column in columns if column.get("name") in candidate_ids), None)
    if column_el is None:
        dependency_columns = worksheet_el.xpath(
            ".//*[local-name()='datasource-dependencies'][@datasource=$datasource_id]"
            "/*[local-name()='column'][@name]",
            datasource_id=datasource_id,
        )
        column_el = next(
            (column for column in dependency_columns if column.get("name") in candidate_ids),
            None,
        )
    if column_el is None:
        field_id = f"[{field_token}]" if not field_token.startswith("[") else field_token
        return datasource_id, field_id, field_token.strip("[]"), None, _discrete_from_token(token)
    field_id = get_xml_id(column_el)
    return (
        datasource_id,
        field_id,
        get_display_name(column_el, strip_field_brackets=True),
        column_el.get("role"),
        _discrete_from_token(token),
    )


def _aggregation_from_reference(reference: str) -> str | None:
    match = _FIELD_REF.match(reference)
    if match is None:
        return None
    parts = match.group(2).split(":")
    if len(parts) < 3 or parts[0] in {"none", *[item[0] for item in _DATE_LEVELS.values()]}:
        return None
    if parts[0] == "usr":
        return "agg" if len(parts) == 3 and parts[-1] in {"qk", "nk"} else None
    return _STORED_AGGREGATIONS.get(parts[0], parts[0])


def _discrete_from_token(token: str) -> bool | None:
    parts = token.split(":")
    if len(parts) < 3:
        return None
    kind = parts[-1].lower()
    if kind.startswith(("n", "o")):
        return True
    if kind.startswith("q"):
        return False
    return None


def _discrete_from_reference(reference: str) -> bool | None:
    match = _FIELD_REF.match(reference)
    return _discrete_from_token(match.group(2)) if match is not None else None


def _validate_field(field: TwbField, context: WorkbookContext) -> None:
    if not isinstance(field, TwbField):
        raise TypeError("field must be TwbField")
    field._ensure_attached()
    field._resolve_element()
    if field._context is not context:
        raise ValueError("field must belong to the same workbook")


def _table_calculation_kind(field: TwbField) -> str | None:
    formula = re.sub(r"(?m)//.*$", "", field.raw_formula or "").strip().lower()
    return "automatic" if formula == "index()" else None


def _build_reference(
    field: TwbField,
    *,
    aggregation: str | None,
    discrete: bool | None,
    table_calculation: str | None = None,
    table_calculation_field: TwbField | None = None,
    date_level: str | None = None,
) -> str:
    if table_calculation is not None:
        table_calculation = table_calculation.lower()
        if table_calculation not in _TABLE_CALCULATIONS:
            raise ValueError(f"unsupported table calculation: {table_calculation}")
        if aggregation is not None:
            raise ValueError("aggregation cannot be combined with table_calculation")
        if not field.is_calculated:
            raise ValueError("table_calculation requires a calculated field")
    if table_calculation == "field":
        if not isinstance(table_calculation_field, TwbField):
            raise ValueError("field table calculation requires table_calculation_field")
        _validate_field(table_calculation_field, field._context)
        if table_calculation_field.datasource_id != field.datasource_id:
            raise ValueError("table calculation field must use the same datasource")
    elif table_calculation_field is not None:
        raise ValueError("table_calculation_field requires field table calculation")
    if date_level is not None:
        date_level = date_level.lower()
        if date_level not in _DATE_LEVELS:
            raise ValueError(f"unsupported date level: {date_level}")
        if field.datatype not in {"date", "datetime"}:
            raise ValueError("date_level requires a date field")
        if aggregation is not None or table_calculation is not None:
            raise ValueError("date_level cannot be combined with aggregation or table_calculation")
    if aggregation is not None:
        aggregation = aggregation.lower()
        if aggregation not in _AGGREGATIONS:
            raise ValueError(f"unsupported aggregation: {aggregation}")
    if discrete is not None and not isinstance(discrete, bool):
        raise TypeError("discrete must be bool or None")

    effective_discrete = discrete
    if effective_discrete is None:
        effective_discrete = field.discrete
    if effective_discrete is None:
        effective_discrete = field.role != "measure"

    field_token = field.id[1:-1] if field.id.startswith("[") and field.id.endswith("]") else field.id
    if table_calculation is not None:
        if table_calculation == "field":
            return f"[{field.datasource_id}].[usr:{field_token}:nk:2]"
        return f"[{field.datasource_id}].[usr:{field_token}:ok]"
    if date_level is not None:
        prefix = _DATE_LEVELS[date_level][0]
        kind = "nk" if effective_discrete else "qk"
        return f"[{field.datasource_id}].[{prefix}:{field_token}:{kind}]"
    prefix = _AGGREGATIONS[aggregation] if aggregation is not None else "none"
    kind = "nk" if effective_discrete else "qk"
    return f"[{field.datasource_id}].[{prefix}:{field_token}:{kind}]"


def _ensure_table(worksheet_el: ET._Element) -> ET._Element:
    tables = [child for child in worksheet_el if _local_name(child) == "table"]
    if len(tables) > 1:
        raise UnsupportedFeatureError("worksheet has multiple table elements")
    if tables:
        return tables[0]
    table = ET.Element("table")
    simple_id = _direct_child(worksheet_el, "simple-id")
    worksheet_el.insert(worksheet_el.index(simple_id) if simple_id is not None else len(worksheet_el), table)
    return table


def _ensure_view(worksheet_el: ET._Element) -> ET._Element:
    table = _ensure_table(worksheet_el)
    views = [child for child in table if _local_name(child) == "view"]
    if len(views) > 1:
        raise UnsupportedFeatureError("worksheet has multiple view elements")
    if views:
        return views[0]
    view = ET.Element("view")
    table.insert(0, view)
    return view


def _ensure_shelf(table_el: ET._Element, tag: str) -> ET._Element:
    shelves = [child for child in table_el if _local_name(child) == tag]
    if len(shelves) > 1:
        raise UnsupportedFeatureError(f"worksheet has multiple {tag} shelves")
    if shelves:
        return shelves[0]
    shelf = ET.Element(tag)
    _insert_in_order(table_el, shelf, _TABLE_CHILD_ORDER)
    return shelf


def _ensure_table_style(table_el: ET._Element) -> ET._Element:
    styles = [child for child in table_el if _local_name(child) == "style"]
    if len(styles) > 1:
        raise UnsupportedFeatureError("worksheet has multiple table style elements")
    if styles:
        return styles[0]
    style = ET.Element("style")
    _insert_in_order(table_el, style, _TABLE_CHILD_ORDER)
    return style


def _ensure_layout_title(worksheet_el: ET._Element) -> ET._Element:
    layout = _direct_child(worksheet_el, "layout-options")
    if layout is None:
        layout = ET.Element("layout-options")
        table = _direct_child(worksheet_el, "table")
        worksheet_el.insert(worksheet_el.index(table) if table is not None else 0, layout)
    title = _direct_child(layout, "title")
    if title is None:
        title = ET.SubElement(layout, "title")
    formatted = _direct_child(title, "formatted-text")
    if formatted is None:
        formatted = ET.SubElement(title, "formatted-text")
    runs = formatted.xpath("./*[local-name()='run']")
    run = runs[0] if runs else ET.SubElement(formatted, "run")
    run.set("fontsize", "6")
    run.text = "-"
    return title


def _style_rule(style_el: ET._Element, element: str, *, create: bool) -> ET._Element | None:
    rules = style_el.xpath("./*[local-name()='style-rule'][@element=$element]", element=element)
    if len(rules) > 1:
        raise UnsupportedFeatureError(f"worksheet has duplicate {element} style rules")
    if rules:
        return rules[0]
    if not create:
        return None
    rule = ET.Element("style-rule", attrib={"element": element})
    rank = {name: index for index, name in enumerate(_STYLE_RULE_ORDER)}
    target_rank = rank.get(element, len(rank))
    insert_at = next(
        (
            index
            for index, existing in enumerate(style_el)
            if rank.get(existing.get("element") or "", len(rank)) > target_rank
        ),
        len(style_el),
    )
    style_el.insert(insert_at, rule)
    return rule


def _style_value(
    style_el: ET._Element,
    element: str,
    attr: str,
    **qualifiers: str,
) -> str | None:
    rule = _style_rule(style_el, element, create=False)
    if rule is None:
        return None
    matches = [
        item
        for item in rule
        if _local_name(item) == "format"
        and item.get("attr") == attr
        and all(item.get(key) == value for key, value in qualifiers.items())
    ]
    return matches[0].get("value") if matches else None


def _set_style_value(
    style_el: ET._Element,
    element: str,
    attr: str,
    value: str | None,
    **qualifiers: str,
) -> None:
    rule = _style_rule(style_el, element, create=value is not None)
    if rule is None:
        return
    matches = [
        item
        for item in rule
        if _local_name(item) == "format"
        and item.get("attr") == attr
        and all(item.get(key) == expected for key, expected in qualifiers.items())
    ]
    if value is None:
        for item in matches:
            rule.remove(item)
    elif matches:
        matches[0].set("value", value)
        for item in matches[1:]:
            rule.remove(item)
    else:
        ET.SubElement(rule, "format", attrib={"attr": attr, **qualifiers, "value": value})
    if not len(rule):
        style_el.remove(rule)


def _sync_datasource_categorical_colors(
    root: ET._Element,
    worksheet_el: ET._Element,
    reference: str,
    colors: dict[str, str],
) -> None:
    match = _FIELD_REF.match(reference)
    if match is None:
        raise UnsupportedFeatureError(f"unsupported color field reference: {reference}")
    datasource_id, token = match.groups()
    datasources = root.xpath(
        "/workbook/datasources/datasource[@name=$id]",
        id=datasource_id,
    )
    if len(datasources) != 1:
        raise UnsupportedFeatureError("color field datasource definition is unavailable")
    datasource_el = datasources[0]

    instance_name = f"[{token}]"
    instances = worksheet_el.xpath(
        ".//*[local-name()='datasource-dependencies'][@datasource=$datasource_id]"
        "/*[local-name()='column-instance'][@name=$instance_name]",
        datasource_id=datasource_id,
        instance_name=instance_name,
    )
    if len(instances) != 1:
        raise UnsupportedFeatureError("color field instance is unavailable")
    direct_instances = datasource_el.xpath(
        "./*[local-name()='column-instance'][@name=$instance_name]",
        instance_name=instance_name,
    )
    if len(direct_instances) > 1:
        raise UnsupportedFeatureError("datasource has duplicate color field instances")
    copied_instance = copy.deepcopy(instances[0])
    if direct_instances:
        datasource_el.replace(direct_instances[0], copied_instance)
    else:
        _insert_in_order(datasource_el, copied_instance, _DATASOURCE_CHILD_ORDER)

    style = _direct_child(datasource_el, "style")
    if style is None:
        style = ET.Element("style")
        _insert_in_order(datasource_el, style, _DATASOURCE_CHILD_ORDER)
    rule = _style_rule(style, "mark", create=True)
    assert rule is not None
    for existing in rule.xpath(
        "./*[local-name()='encoding' and @attr='color' and @field=$field]",
        field=instance_name,
    ):
        rule.remove(existing)
    encoding = ET.SubElement(
        rule,
        "encoding",
        attrib={"attr": "color", "field": instance_name, "type": "palette"},
    )
    for label, color in colors.items():
        mapping = ET.SubElement(encoding, "map", attrib={"to": color})
        ET.SubElement(mapping, "bucket").text = f'"{label}"'


def _style_field_reference(
    context: WorkbookContext,
    worksheet_el: ET._Element,
    field: str,
) -> str:
    if _FIELD_REF.match(field):
        return field
    matches = []
    for placement in _placements(worksheet_el):
        _, field_id, name, _, _ = _field_details(context, worksheet_el, placement.reference)
        if field in {field_id, field_id.strip("[]"), name}:
            matches.append(placement.reference)
    matches = list(dict.fromkeys(matches))
    if not matches:
        raise ValueError(f"worksheet field not found: {field}")
    if len(matches) > 1:
        raise ValueError(f"worksheet field is ambiguous: {field}")
    return matches[0]


def _style_field_name(
    context: WorkbookContext,
    worksheet_el: ET._Element,
    reference: str,
) -> str:
    try:
        return _field_details(context, worksheet_el, reference)[2]
    except UnsupportedFeatureError:
        return reference


def _ensure_dependency(
    worksheet_el: ET._Element,
    field: TwbField,
    reference: str,
    table_calculation: str | None = None,
    table_calculation_field: TwbField | None = None,
) -> None:
    view = _ensure_view(worksheet_el)
    datasources = _direct_child(view, "datasources")
    if datasources is None:
        datasources = ET.Element("datasources")
        _insert_in_order(view, datasources, _VIEW_CHILD_ORDER)
    if not datasources.xpath("./*[local-name()='datasource'][@name=$id]", id=field.datasource_id):
        datasource_el = field._resolve_datasource_element()
        attrs = {"name": field.datasource_id}
        caption = get_display_name(datasource_el)
        if caption != field.datasource_id:
            attrs["caption"] = caption
        ET.SubElement(datasources, "datasource", attrib=attrs)

    dependencies = [
        child
        for child in view
        if _local_name(child) == "datasource-dependencies"
        and child.get("datasource") == field.datasource_id
    ]
    if len(dependencies) > 1:
        raise UnsupportedFeatureError("worksheet has duplicate datasource dependencies")
    if dependencies:
        dependency = dependencies[0]
    else:
        dependency = ET.Element("datasource-dependencies", attrib={"datasource": field.datasource_id})
        _insert_in_order(view, dependency, _VIEW_CHILD_ORDER)

    if _direct_child(view, "aggregation") is None:
        aggregation = ET.Element("aggregation", attrib={"value": "true"})
        _insert_in_order(view, aggregation, _VIEW_CHILD_ORDER)

    columns = dependency.xpath(
        "./*[local-name()='column'][@name=$field_id]",
        field_id=field.id,
    )
    if not columns:
        column = copy.deepcopy(field._resolve_element())
        instances = dependency.xpath("./*[local-name()='column-instance']")
        dependency.insert(dependency.index(instances[0]) if instances else len(dependency), column)
    else:
        column = columns[0]

    match = _FIELD_REF.match(reference)
    if match is None:
        raise UnsupportedFeatureError(f"unsupported worksheet field reference: {reference}")
    token = match.group(2)

    if table_calculation is not None:
        definition_order, instance_order = _TABLE_CALCULATIONS[table_calculation]
        column.set("type", "nominal" if table_calculation == "field" else "quantitative")
        calculation = _direct_child(column, "calculation")
        if calculation is None:
            raise ValueError("table_calculation requires a calculated field")
        if definition_order is not None:
            table_calc = _direct_child(calculation, "table-calc")
            if table_calc is None:
                table_calc = ET.SubElement(calculation, "table-calc")
            table_calc.set("ordering-type", definition_order)

    instance_name = f"[{token}]"
    if not dependency.xpath(
        "./*[local-name()='column-instance'][@name=$instance_name]",
        instance_name=instance_name,
    ):
        aggregation = token.split(":", 1)[0]
        derivation = "User" if table_calculation is not None or aggregation == "usr" else {
            "none": "None", "sum": "Sum", "avg": "Avg", "min": "Min",
            "max": "Max", "cnt": "Count", "ctd": "CountD", "attr": "Attribute",
            **{token: derivation for token, derivation in _DATE_LEVELS.values()},
        }[aggregation]
        instance = ET.Element("column-instance", attrib={
            "column": field.id,
            "derivation": derivation,
            "name": instance_name,
            "pivot": "key",
            "type": "nominal" if table_calculation == "field" else (
                "ordinal" if table_calculation is not None else
                "nominal" if _discrete_from_token(token) else "quantitative"
            ),
        })
        if table_calculation == "field":
            assert table_calculation_field is not None
            ET.SubElement(
                instance,
                "table-calc",
                attrib={
                    "ordering-field": (
                        f"[{table_calculation_field.datasource_id}]."
                        f"{table_calculation_field.id}"
                    ),
                    "ordering-type": "Field",
                },
            )
        elif table_calculation is not None and instance_order is not None:
            ET.SubElement(instance, "table-calc", attrib={"ordering-type": instance_order})
        dependency.append(instance)


def _shelf_references(element: ET._Element) -> list[str]:
    if len(element):
        raise UnsupportedFeatureError("nested shelf XML is not supported")
    return FIELD_REF_RE.findall(element.text or "")


def _format_shelf_references(references: list[str]) -> str:
    if len(references) > 1 and ".[usr:" in references[0]:
        return f"({references[0]} / ({' / '.join(references[1:])}))"
    return " / ".join(references)


def _reference_targets_field(reference: str, datasource_id: str, field_id: str) -> bool:
    match = _FIELD_REF.match(reference)
    if match is None or match.group(1) != datasource_id:
        return False
    token = field_name_from_token(match.group(2))
    target = field_id[1:-1] if field_id.startswith("[") and field_id.endswith("]") else field_id
    return token in {target, field_id}


def _remove_unused_dependency(
    worksheet_el: ET._Element,
    datasource_id: str,
    field_id: str,
) -> None:
    for element in worksheet_el.iter():
        if any(_local_name(node) == "datasource-dependencies" for node in [element, *element.iterancestors()]):
            continue
        values = [*element.attrib.values(), element.text or ""]
        if any(
            _reference_targets_field(reference, datasource_id, field_id)
            for value in values
            for reference in FIELD_REF_RE.findall(str(value))
        ):
            return

    dependencies = worksheet_el.xpath(
        ".//*[local-name()='datasource-dependencies'][@datasource=$datasource_id]",
        datasource_id=datasource_id,
    )
    for dependency in dependencies:
        for column in list(
            dependency.xpath(
                "./*[local-name()='column'][@name=$field_id]"
                " | ./*[local-name()='column-instance'][@column=$field_id]",
                field_id=field_id,
            )
        ):
            dependency.remove(column)
        if len(dependency) == 0 and set(dependency.attrib) == {"datasource"}:
            parent = dependency.getparent()
            if parent is not None:
                parent.remove(dependency)


@dataclass
class _Placement:
    id: str
    reference: str
    source_el: ET._Element
    shelf: str | None = None
    encoding: str | None = None
    pane_id: str | None = None
    token_index: int | None = None


def _placements(worksheet_el: ET._Element) -> list[_Placement]:
    result: list[_Placement] = []
    for shelf, tag in _SHELVES.items():
        shelf_els = list(worksheet_el.xpath(f".//*[local-name()='{tag}']"))
        for shelf_index, shelf_el in enumerate(shelf_els):
            for token_index, reference in enumerate(_shelf_references(shelf_el)):
                result.append(
                    _Placement(
                        id=f"shelf:{shelf}:{shelf_index}:{token_index}",
                        reference=reference,
                        source_el=shelf_el,
                        shelf=shelf,
                        token_index=token_index,
                    )
                )

    filters = list(worksheet_el.xpath(".//*[local-name()='filter'][@column]"))
    for index, filter_el in enumerate(filters):
        result.append(
            _Placement(
                id=f"shelf:filters:{index}:0",
                reference=filter_el.get("column") or "",
                source_el=filter_el,
                shelf="filters",
            )
        )

    for pane_index, pane_el in enumerate(_pane_elements(worksheet_el)):
        pane_id = _pane_id(pane_el, pane_index)
        encodings = list(pane_el.xpath("./*[local-name()='encodings']/*[@column]"))
        for encoding_index, encoding_el in enumerate(encodings):
            stored_encoding = _local_name(encoding_el)
            result.append(
                _Placement(
                    id=f"pane:{pane_index}:{encoding_index}",
                    reference=encoding_el.get("column") or "",
                    source_el=encoding_el,
                    encoding=_STORED_ENCODINGS.get(stored_encoding, stored_encoding),
                    pane_id=pane_id,
                )
            )
    return result


class TwbWorksheet(ConnectedModel):
    def __init__(self, context: WorkbookContext, worksheet_id: str):
        super().__init__(context)
        self._id = worksheet_id

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        hits = self._context.tree.getroot().xpath(
            "/workbook/worksheets/worksheet[@name=$id]",
            id=self._id,
        )
        if not hits:
            self._detach()
            raise DetachedModelError(f"worksheet is detached: {self._id}")
        return hits[0]

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        return _worksheet_display_name(self._resolve_element())

    @property
    def visible(self) -> bool:
        self._resolve_element()
        windows = self._context.tree.getroot().xpath(
            "/workbook/windows/window[@class='worksheet'][@name=$id]",
            id=self._id,
        )
        if not windows:
            return True
        return (windows[0].get("hidden") or "false").lower() != "true"

    def get_fields(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbWorksheetField]:
        _validate_get_args(id, name)
        worksheet_el = self._resolve_element()
        result: list[TwbWorksheetField] = []
        for placement in _placements(worksheet_el):
            model = TwbWorksheetField(self._context, self._id, placement.id)
            if _matches(model_id=model.id, model_name=model.name, id=id, name=name):
                result.append(model)
        return result

    def get_panes(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbPane]:
        _validate_get_args(id, name)
        result: list[TwbPane] = []
        for index, pane_el in enumerate(_pane_elements(self._resolve_element())):
            pane_id = _pane_id(pane_el, index)
            if _matches(model_id=pane_id, model_name=pane_id, id=id, name=name):
                result.append(TwbPane(self._context, self._id, pane_id, index))
        return result

    def get_reference_lines(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbReferenceLine]:
        _validate_get_args(id, name)
        lines = list_reference_lines_from_tree(self._context.tree, self._id, by="name")
        return [
            TwbReferenceLine(self._context, self._id, line.id or "")
            for line in lines
            if line.id
            and _matches(
                model_id=line.id,
                model_name=line.id,
                id=id,
                name=name,
            )
        ]

    def add_reference_line(
        self,
        *,
        field: TwbWorksheetField,
        pane: TwbPane | None = None,
        formula: str = "median",
        scope: str = "per-table",
        label_type: str = "value",
        probability: int = 95,
        z_order: int = 1,
    ) -> TwbReferenceLine:
        """参照線を 1 本引く。

        Pane が複数あるワークシート（二重軸など）では `pane=` が要る。
        以前は先頭の Pane へ暗黙に引いていて、意図しない側に線が出ていた
        （仕様 §6.7、2026-09-07 に修正）。Pane が 1 つなら省略できる。
        """
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        if pane is not None and not isinstance(pane, TwbPane):
            raise TypeError("pane must be TwbPane or None")
        if pane is not None and (
            pane._context is not self._context or pane._worksheet_id != self._id
        ):
            raise ValueError("pane must belong to the worksheet")
        if field._context is not self._context or field._worksheet_id != self._id:
            raise ValueError("field must belong to the worksheet")
        if field.shelf not in {"rows", "columns"}:
            raise ValueError("reference line field must be on rows or columns")
        formula = formula.lower()
        if formula not in {"average", "median", "minimum", "maximum"}:
            raise ValueError("unsupported reference line formula")

        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        panes = _pane_elements(updated)
        if not panes:
            raise UnsupportedFeatureError("worksheet has no pane")
        if pane is not None:
            pane_index = pane._pane_index
        elif len(panes) == 1:
            pane_index = 0
        else:
            raise ValueError(
                "worksheet has more than one pane, pass pane= from get_panes()"
            )
        if pane_index >= len(panes):
            raise DetachedModelError(f"pane is detached: {self._id}")
        reference = field._resolve_placement().reference
        line_id = f"refline{len(self.get_reference_lines())}"
        line = ET.Element(
            "reference-line",
            attrib={
                "id": line_id,
                "axis-column": reference,
                "value-column": reference,
                "formula": formula,
                "scope": scope,
                "label-type": label_type,
                "probability": str(probability),
                "z-order": str(z_order),
                "enable-instant-analytics": "true",
            },
        )
        _insert_in_order(panes[pane_index], line, _PANE_CHILD_ORDER)
        _replace_if_changed(worksheet_el, updated, self._context)
        return self.get_reference_lines(id=line_id)[0]

    def get_filters(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbWorksheetFilter]:
        _validate_get_args(id, name)
        filters = list_filters_from_tree(self._context.tree, self._id, by="name")
        return [
            TwbWorksheetFilter(self._context, self._id, item.column or "")
            for item in filters
            if item.column
            and _matches(
                model_id=item.column,
                model_name=item.field or item.column,
                id=id,
                name=name,
            )
        ]

    @property
    def grand_totals(self) -> dict[str, str | None]:
        """総計の位置。`update(grand_totals=...)` と対になる。"""
        worksheet_el = self._resolve_element()
        table_el = _direct_child(worksheet_el, "table")
        result: dict[str, str | None] = {}
        for key, (tag, position_attr, positions) in _GRAND_TOTAL_SHELVES.items():
            shelf = _direct_child(table_el, tag) if table_el is not None else None
            if shelf is None or (shelf.get("total") or "false").lower() != "true":
                result[key] = None
                continue
            on = (shelf.get(position_attr) or "false").lower() == "true"
            result[key] = next(name for name, flag in positions.items() if flag is on)
        return result

    @property
    def table_style(self) -> dict[str, Any]:
        """表スタイル。`update(table_style=...)` と対になる。"""
        worksheet_el = self._resolve_element()
        table_el = _direct_child(worksheet_el, "table")
        style_el = _direct_child(table_el, "style") if table_el is not None else None
        if style_el is None:
            return {
                "header_background": None,
                "header_bold": None,
                "header_color": None,
                "row_band": None,
                "column_widths": {},
            }

        decoration_weight = _style_value(
            style_el, "field-labels-decoration", "font-weight"
        )
        label_weight = _style_value(style_el, "field-labels", "font-weight")
        weight = decoration_weight or label_weight
        band_values = [
            _style_value(style_el, "header", "band-color", scope="rows"),
            _style_value(style_el, "pane", "band-color", scope="rows"),
        ]
        band_size = _style_value(style_el, "table", "band-size", scope="rows")
        present_bands = [value for value in band_values if value is not None]
        row_band = None
        if present_bands or band_size is not None:
            row_band = not present_bands or any(
                value.lower() != _TRANSPARENT for value in present_bands
            )

        widths: dict[str, int | str] = {}
        header_rule = _style_rule(style_el, "header", create=False)
        if header_rule is not None:
            for item in header_rule:
                if _local_name(item) != "format" or item.get("attr") != "width":
                    continue
                reference = item.get("field") or ""
                value = item.get("value") or ""
                widths[_style_field_name(self._context, worksheet_el, reference)] = (
                    int(value) if value.isdigit() else value
                )

        return {
            "header_background": _style_value(
                style_el, "field-labels", "background-color"
            ),
            "header_bold": None if weight is None else weight.lower() == "bold",
            "header_color": _style_value(
                style_el, "field-labels-decoration", "color"
            ),
            "row_band": row_band,
            "column_widths": widths,
        }

    def _apply_table_style(
        self,
        *,
        header_background: str | None | _UnsetType = UNSET,
        header_bold: bool | None | _UnsetType = UNSET,
        header_color: str | None | _UnsetType = UNSET,
        row_band: bool | None | _UnsetType = UNSET,
        column_widths: dict[str, int] | _UnsetType = UNSET,
    ) -> TwbWorksheet:
        if all(
            value is UNSET
            for value in (
                header_background,
                header_bold,
                header_color,
                row_band,
                column_widths,
            )
        ):
            return self
        for name, value in {
            "header_background": header_background,
            "header_color": header_color,
        }.items():
            if value is not UNSET and value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None")
        for name, value in {"header_bold": header_bold, "row_band": row_band}.items():
            if value is not UNSET and value is not None and not isinstance(value, bool):
                raise TypeError(f"{name} must be bool or None")
        if column_widths is not UNSET and not isinstance(column_widths, dict):
            raise TypeError("column_widths must be a dict")

        worksheet_el = self._resolve_element()
        resolved_widths: dict[str, int] | _UnsetType = UNSET
        if column_widths is not UNSET:
            resolved_widths = {}
            for field, width in column_widths.items():
                if not isinstance(field, str):
                    raise TypeError("column_widths keys must be strings")
                if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
                    raise ValueError("column widths must be positive integers")
                resolved_widths[_style_field_reference(self._context, worksheet_el, field)] = width

        updated = copy.deepcopy(worksheet_el)
        table_el = _ensure_table(updated)
        style_el = _ensure_table_style(table_el)
        if header_background is not UNSET:
            _set_style_value(
                style_el,
                "field-labels",
                "background-color",
                header_background,
            )
        if header_bold is not UNSET:
            weight = None if header_bold is None else ("bold" if header_bold else "normal")
            _set_style_value(style_el, "field-labels", "font-weight", None if weight is None else "normal")
            _set_style_value(style_el, "field-labels-decoration", "font-weight", weight)
        if header_color is not UNSET:
            _set_style_value(
                style_el,
                "field-labels-decoration",
                "color",
                header_color,
            )
        if resolved_widths is not UNSET:
            header_rule = _style_rule(style_el, "header", create=bool(resolved_widths))
            if header_rule is not None:
                for item in list(header_rule):
                    if _local_name(item) == "format" and item.get("attr") == "width":
                        header_rule.remove(item)
                for reference, width in resolved_widths.items():
                    ET.SubElement(
                        header_rule,
                        "format",
                        attrib={
                            "attr": "width",
                            "field": reference,
                            "value": str(width),
                        },
                    )
                if not len(header_rule):
                    style_el.remove(header_rule)
        if row_band is not UNSET:
            color = _TRANSPARENT if row_band is False else None
            _set_style_value(style_el, "header", "band-color", color, scope="rows")
            _set_style_value(style_el, "pane", "band-color", color, scope="rows")
            _set_style_value(
                style_el,
                "table",
                "band-size",
                None if row_band is None else "1",
                scope="rows",
            )
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    @property
    def title_style(self) -> dict[str, Any]:
        """タイトルスタイル。`update(title_style=...)` と対になる。"""
        worksheet_el = self._resolve_element()
        table_el = _direct_child(worksheet_el, "table")
        style_el = _direct_child(table_el, "style") if table_el is not None else None
        if style_el is None:
            return {
                "background_color": None,
                "border_width": None,
                "border_style": None,
            }
        return {
            "background_color": _style_value(style_el, "title", "background-color"),
            "border_width": _style_value(style_el, "title", "border-width"),
            "border_style": _style_value(style_el, "title", "border-style"),
        }

    @property
    def title(self) -> str | None:
        title = self._resolve_element().find("./layout-options/title/formatted-text")
        if title is None:
            return None
        text = "".join(title.itertext()).strip()
        if not text or text == "-":
            return None
        return self.name if text == "<Sheet Name>" else text

    def _apply_title(self, title: str | None) -> TwbWorksheet:
        if title is not None:
            if not isinstance(title, str):
                raise TypeError("title must be a string or None")
            title = title.strip()
            if not title:
                raise ValueError("title must not be empty")
        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        if title is None:
            layout = _direct_child(updated, "layout-options")
            title_el = _direct_child(layout, "title") if layout is not None else None
            if layout is not None and title_el is not None:
                layout.remove(title_el)
                if not len(layout):
                    updated.remove(layout)
        else:
            title_el = _ensure_layout_title(updated)
            formatted = _direct_child(title_el, "formatted-text")
            assert formatted is not None
            for child in list(formatted):
                formatted.remove(child)
            ET.SubElement(
                formatted,
                "run",
                attrib={"bold": "true", "fontsize": "12"},
            ).text = title
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def _apply_title_style(self, *, background_color: str) -> TwbWorksheet:
        if not isinstance(background_color, str) or not background_color.strip():
            raise ValueError("background_color must be a non-empty string")
        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        _ensure_layout_title(updated)
        style_el = _ensure_table_style(_ensure_table(updated))
        _set_style_value(style_el, "title", "border-width", "0")
        _set_style_value(style_el, "title", "border-style", "none")
        _set_style_value(style_el, "title", "background-color", background_color)
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def _apply_grand_totals(self, grand_totals: dict[str, Any]) -> TwbWorksheet:
        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        table_el = _ensure_table(updated)
        for key, position in grand_totals.items():
            tag, position_attr, positions = _GRAND_TOTAL_SHELVES[key]
            if position is None:
                shelf = _direct_child(table_el, tag)
                if shelf is not None:
                    shelf.attrib.pop("total", None)
                    shelf.attrib.pop(position_attr, None)
                continue
            shelf = _ensure_shelf(table_el, tag)
            shelf.set("total", "true")
            shelf.set(position_attr, str(positions[position]).lower())
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def set_subtotal_visibility(
        self,
        *,
        field: TwbWorksheetField,
        visible: bool = True,
    ) -> TwbWorksheet:
        """行・列に配置したフィールドへ小計を付ける、または外す。"""
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        if not isinstance(visible, bool):
            raise TypeError("visible must be bool")
        if field._context is not self._context or field._worksheet_id != self._id:
            raise ValueError("field must belong to the worksheet")
        placement = field._resolve_placement()
        if placement.shelf not in {"rows", "columns"}:
            raise ValueError("field must be placed on rows or columns")

        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        table_el = _ensure_table(updated)
        subtotals = _direct_child(table_el, "subtotals")
        existing = (
            subtotals.xpath("./*[local-name()='column'][text()=$ref]", ref=placement.reference)
            if subtotals is not None
            else []
        )
        if visible and not existing:
            if subtotals is None:
                subtotals = ET.Element("subtotals")
                _insert_in_order(table_el, subtotals, _TABLE_CHILD_ORDER)
            column = ET.SubElement(subtotals, "column")
            column.text = placement.reference
        elif not visible and existing:
            for column in existing:
                subtotals.remove(column)
            # <subtotals> は column を 1 件以上要求するため、空になったら要素ごと外す。
            if _direct_child(subtotals, "column") is None:
                table_el.remove(subtotals)
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def set_axis_visibility(
        self,
        *,
        field: TwbWorksheetField,
        visible: bool,
    ) -> TwbWorksheet:
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        if not isinstance(visible, bool):
            raise TypeError("visible must be bool")
        if field._context is not self._context or field._worksheet_id != self._id:
            raise ValueError("field must belong to the worksheet")
        placement = field._resolve_placement()
        if placement.shelf not in {"rows", "columns"}:
            raise ValueError("field must be placed on rows or columns")

        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        style = _ensure_table_style(_ensure_table(updated))
        _set_style_value(
            style,
            "axis",
            "display",
            str(visible).lower(),
            **{
                "class": "0",
                "field": placement.reference,
                "scope": "rows" if placement.shelf == "rows" else "cols",
            },
        )
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def _resolve_field(self, value: FieldInput, *, argument: str = "field") -> TwbField:
        """`field=` を `TwbField` へ解決する。素の文字列はこのシートの依存から探す。"""
        return resolve_field_input(
            self._context,
            value,
            datasources=worksheet_datasources(self._context, self._resolve_element()),
            argument=argument,
        )

    def add_field(
        self,
        *,
        field: FieldInput,
        shelf: str,
        aggregation: str | None = None,
        discrete: bool | None = None,
        table_calculation: str | None | _UnsetType = UNSET,
        table_calculation_field: FieldInput | None = None,
        date_level: str | None = None,
    ) -> TwbWorksheetField:
        field = self._resolve_field(field)
        if table_calculation_field is not None:
            table_calculation_field = self._resolve_field(
                table_calculation_field, argument="table_calculation_field"
            )
        shelf = shelf.lower()
        if shelf not in {*_SHELVES, "filters"}:
            raise ValueError(f"unsupported shelf: {shelf}")
        if table_calculation is UNSET:
            table_calculation = _table_calculation_kind(field)
        reference = _build_reference(
            field,
            aggregation=aggregation,
            discrete=discrete,
            table_calculation=table_calculation,
            table_calculation_field=table_calculation_field,
            date_level=date_level,
        )

        worksheet_el = self._resolve_element()
        existing = next(
            (
                placement
                for placement in _placements(worksheet_el)
                if placement.shelf == shelf and placement.reference == reference
            ),
            None,
        )
        if existing is not None:
            return TwbWorksheetField(self._context, self._id, existing.id)

        updated = copy.deepcopy(worksheet_el)
        _ensure_dependency(
            updated,
            field,
            reference,
            table_calculation,
            table_calculation_field,
        )
        if shelf == "filters":
            view = _ensure_view(updated)
            filter_el = ET.Element("filter", attrib={"column": reference})
            _insert_in_order(view, filter_el, _VIEW_CHILD_ORDER)
        else:
            table = _ensure_table(updated)
            tag = _SHELVES[shelf]
            shelf_el = _ensure_shelf(table, tag)
            references = _shelf_references(shelf_el)
            references.append(reference)
            shelf_el.text = _format_shelf_references(references)

        created = next(
            placement
            for placement in reversed(_placements(updated))
            if placement.shelf == shelf and placement.reference == reference
        )
        _replace_if_changed(worksheet_el, updated, self._context)
        return TwbWorksheetField(self._context, self._id, created.id)

    def _set_table_calculation_partition(
        self,
        field: TwbWorksheetField,
        partition_field: TwbField,
    ) -> TwbWorksheet:
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        if field._context is not self._context or field._worksheet_id != self._id:
            raise ValueError("field must belong to the worksheet")
        _validate_field(partition_field, self._context)
        placement = field._resolve_placement()
        if placement.shelf not in {"rows", "columns"}:
            raise ValueError("field must be placed on rows or columns")
        if field.table_calculation is None:
            raise ValueError("field must use a table calculation")
        if field.datasource_id != partition_field.datasource_id:
            raise ValueError("partition field must use the same datasource")

        partition_reference = _build_reference(
            partition_field,
            aggregation=None,
            discrete=True,
        )
        old_reference = placement.reference
        match = _FIELD_REF.match(old_reference)
        if match is None:
            raise UnsupportedFeatureError(
                f"unsupported worksheet field reference: {old_reference}"
            )
        token = match.group(2)
        if token.endswith(":2"):
            return self
        new_token = f"{token}:2"
        new_reference = f"[{match.group(1)}].[{new_token}]"

        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        updated_placement = next(
            item for item in _placements(updated) if item.id == placement.id
        )
        updated_placement.source_el.text = (
            updated_placement.source_el.text or ""
        ).replace(old_reference, new_reference, 1)

        _ensure_dependency(updated, partition_field, partition_reference)
        view = _ensure_view(updated)
        dependencies = view.xpath(
            "./*[local-name()='datasource-dependencies'][@datasource=$datasource]",
            datasource=field.datasource_id,
        )
        if len(dependencies) != 1:
            raise UnsupportedFeatureError("table calculation dependency is unavailable")
        dependency = dependencies[0]
        columns = dependency.xpath(
            "./*[local-name()='column'][@name=$field]",
            field=field.field_id,
        )
        if len(columns) != 1:
            raise UnsupportedFeatureError("table calculation field definition is unavailable")
        columns[0].set("type", "ordinal")
        instances = dependency.xpath(
            "./*[local-name()='column-instance'][@name=$name]",
            name=f"[{token}]",
        )
        if len(instances) != 1:
            raise UnsupportedFeatureError("table calculation field instance is unavailable")
        instances[0].set("name", f"[{new_token}]")

        slices = _direct_child(view, "slices")
        if slices is None:
            slices = ET.Element("slices")
            _insert_in_order(view, slices, _VIEW_CHILD_ORDER)
        if not slices.xpath(
            "./*[local-name()='column'][text()=$reference]",
            reference=partition_reference,
        ):
            ET.SubElement(slices, "column").text = partition_reference

        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def _configure_colored_yoy_columns(
        self,
        layout_field: TwbField,
        metric_fields: list[tuple[TwbField, TwbField, TwbField]],
        *,
        negative_color: str,
        positive_color: str,
        ratio_color: str,
        mark_type: str,
        bar_color: str | None,
        axis_min: float,
        axis_max: float,
        show_axes: bool,
        bar_opacity: float,
    ) -> TwbWorksheet:
        _validate_field(layout_field, self._context)
        if not metric_fields:
            raise ValueError("metric_fields must not be empty")
        for fields in metric_fields:
            if len(fields) != 3:
                raise ValueError("each metric must contain negative, positive, and ratio fields")
            for field in fields:
                _validate_field(field, self._context)
        colors = {
            "negative_color": negative_color,
            "positive_color": positive_color,
            "ratio_color": ratio_color,
        }
        for name, color in colors.items():
            if not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
                raise ValueError(f"{name} must use #RRGGBB")
        if not isinstance(mark_type, str) or mark_type.lower() not in {"bar", "text"}:
            raise ValueError("mark_type must be bar or text")
        mark_type = mark_type.lower()
        if bar_color is not None and (
            not isinstance(bar_color, str)
            or re.fullmatch(r"#[0-9A-Fa-f]{6}", bar_color) is None
        ):
            raise ValueError("bar_color must use #RRGGBB or None")
        if not isinstance(axis_min, (int, float)) or isinstance(axis_min, bool):
            raise TypeError("axis_min must be a number")
        if not isinstance(axis_max, (int, float)) or isinstance(axis_max, bool):
            raise TypeError("axis_max must be a number")
        if axis_min >= axis_max:
            raise ValueError("axis_min must be less than axis_max")
        if not isinstance(show_axes, bool):
            raise TypeError("show_axes must be bool")
        if not isinstance(bar_opacity, (int, float)) or isinstance(bar_opacity, bool):
            raise TypeError("bar_opacity must be a number")
        bar_opacity = float(bar_opacity)
        if not 0 <= bar_opacity <= 1:
            raise ValueError("bar_opacity must be between 0 and 1")
        negative_color, positive_color, ratio_color = (
            color.lower() for color in colors.values()
        )
        bar_color = bar_color.lower() if bar_color is not None else None

        layout_reference = _build_reference(
            layout_field,
            aggregation="agg",
            discrete=False,
        )
        label_references = [
            tuple(
                _build_reference(field, aggregation="agg", discrete=False)
                for field in fields
            )
            for fields in metric_fields
        ]
        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        _ensure_dependency(updated, layout_field, layout_reference)
        for fields, references in zip(metric_fields, label_references):
            for field, reference in zip(fields, references):
                _ensure_dependency(updated, field, reference)

        table = _ensure_table(updated)
        cols = _ensure_shelf(table, "cols")
        expression = layout_reference
        for _ in range(len(metric_fields) - 1):
            expression = f"({layout_reference} + {expression})"
        cols.text = expression

        def format_number(value: float) -> str:
            numeric = float(value)
            return str(int(numeric)) if numeric.is_integer() else str(numeric)

        table_style = _ensure_table_style(table)
        axis_rule = _style_rule(table_style, "axis", create=True)
        assert axis_rule is not None
        for existing in list(axis_rule):
            if existing.get("field") == layout_reference and existing.get("scope") == "cols":
                axis_rule.remove(existing)
        for index in range(len(metric_fields)):
            ET.SubElement(
                axis_rule,
                "encoding",
                attrib={
                    "attr": "space",
                    "class": str(index),
                    "field": layout_reference,
                    "field-type": "quantitative",
                    "max": format_number(axis_max),
                    "min": format_number(axis_min),
                    "range-type": "fixed",
                    "scope": "cols",
                    "type": "space",
                },
            )
        for index in range(len(metric_fields)):
            ET.SubElement(
                axis_rule,
                "format",
                attrib={
                    "attr": "display",
                    "class": str(index),
                    "field": layout_reference,
                    "scope": "cols",
                    "value": str(show_axes).lower(),
                },
            )

        panes = _direct_child(table, "panes")
        if panes is None:
            panes = ET.Element("panes")
            _insert_in_order(table, panes, _TABLE_CHILD_ORDER)
        for child in list(panes):
            panes.remove(child)

        base_pane = ET.SubElement(
            panes,
            "pane",
            attrib={
                "id": "1",
                "selection-relaxation-option": "selection-relaxation-allow",
            },
        )
        base_view = ET.SubElement(base_pane, "view")
        ET.SubElement(base_view, "breakdown", attrib={"value": "auto"})
        ET.SubElement(base_pane, "mark", attrib={"class": _MARK_TYPES[mark_type]})

        for index, references in enumerate(label_references):
            attributes = {
                "id": str(index + 2),
                "selection-relaxation-option": "selection-relaxation-allow",
                "x-axis-name": layout_reference,
            }
            if index:
                attributes["x-index"] = str(index)
            pane = ET.SubElement(panes, "pane", attrib=attributes)
            view = ET.SubElement(pane, "view")
            ET.SubElement(view, "breakdown", attrib={"value": "auto"})
            ET.SubElement(pane, "mark", attrib={"class": _MARK_TYPES[mark_type]})
            encodings = ET.SubElement(pane, "encodings")
            for reference in references:
                ET.SubElement(encodings, "text", attrib={"column": reference})

            customized = ET.SubElement(pane, "customized-label")
            formatted = ET.SubElement(customized, "formatted-text")
            run = ET.SubElement(formatted, "run", attrib={"fontcolor": negative_color})
            run.text = ET.CDATA(f"<{references[0]}>")
            run = ET.SubElement(formatted, "run", attrib={"fontcolor": positive_color})
            run.text = ET.CDATA(f"<{references[1]}>  ")
            run = ET.SubElement(
                formatted,
                "run",
                attrib={"fontcolor": ratio_color, "fontsize": "7"},
            )
            run.text = ET.CDATA(f"<{references[2]}>")

            style = ET.SubElement(pane, "style")
            rule = ET.SubElement(style, "style-rule", attrib={"element": "mark"})
            ET.SubElement(
                rule,
                "format",
                attrib={"attr": "mark-labels-show", "value": "true"},
            )
            ET.SubElement(
                rule,
                "format",
                attrib={"attr": "mark-labels-cull", "value": "false"},
            )
            if bar_color is not None:
                ET.SubElement(
                    rule,
                    "format",
                    attrib={"attr": "mark-color", "value": bar_color},
                )
            transparency = round(255 * bar_opacity ** (1 / 2.4))
            ET.SubElement(
                rule,
                "format",
                attrib={"attr": "mark-transparency", "value": str(transparency)},
            )

        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def add_filter(self, *, field: FieldInput) -> TwbWorksheetField:
        placement = self.add_field(
            field=field,
            shelf="filters",
            discrete=True,
            table_calculation=None,
        )
        reference = placement._resolve_placement().reference
        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        filters = updated.xpath(
            "./*[local-name()='table']/*[local-name()='view']"
            "/*[local-name()='filter'][@column=$reference]",
            reference=reference,
        )
        if len(filters) != 1:
            raise UnsupportedFeatureError("worksheet has duplicate filters")
        filter_el = filters[0]
        filter_el.set("class", "categorical")
        for child in list(filter_el):
            if _local_name(child) == "groupfilter":
                filter_el.remove(child)
        token = _FIELD_REF.match(reference)
        if token is None:
            raise UnsupportedFeatureError(f"unsupported filter field reference: {reference}")
        ET.SubElement(
            filter_el,
            "groupfilter",
            attrib={
                "function": "level-members",
                "level": f"[{token.group(2)}]",
            },
        )

        view = filter_el.getparent()
        assert view is not None
        slices = _direct_child(view, "slices")
        if slices is None:
            slices = ET.Element("slices")
            _insert_in_order(view, slices, _VIEW_CHILD_ORDER)
        if not slices.xpath("./*[local-name()='column'][text()=$reference]", reference=reference):
            ET.SubElement(slices, "column").text = reference
        _replace_if_changed(worksheet_el, updated, self._context)
        return placement

    def add_filter_slice(self, *, field: FieldInput) -> TwbWorksheet:
        field = self._resolve_field(field)
        reference = _build_reference(
            field,
            aggregation=None,
            discrete=True,
            table_calculation=None,
        )
        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        _ensure_dependency(updated, field, reference)
        view = _ensure_view(updated)
        for filter_el in view.xpath(
            "./*[local-name()='filter'][@column=$reference]",
            reference=reference,
        ):
            view.remove(filter_el)
        slices = _direct_child(view, "slices")
        if slices is None:
            slices = ET.Element("slices")
            _insert_in_order(view, slices, _VIEW_CHILD_ORDER)
        if not slices.xpath(
            "./*[local-name()='column'][text()=$reference]",
            reference=reference,
        ):
            ET.SubElement(slices, "column").text = reference
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def add_sort(
        self,
        *,
        field: FieldInput,
        by: FieldInput,
        direction: str = "descending",
        aggregation: str | None = "sum",
    ) -> TwbWorksheet:
        field = self._resolve_field(field)
        by = self._resolve_field(by, argument="by")
        directions = {"ascending": "ASC", "descending": "DESC"}
        if direction not in directions:
            raise ValueError("direction must be ascending or descending")

        column = _build_reference(field, aggregation=None, discrete=None)
        using = _build_reference(by, aggregation=aggregation, discrete=False)
        worksheet_el = self._resolve_element()
        updated = copy.deepcopy(worksheet_el)
        _ensure_dependency(updated, field, column)
        _ensure_dependency(updated, by, using)
        view = _ensure_view(updated)
        sorts = view.xpath("./*[local-name()='computed-sort'][@column=$column]", column=column)
        if len(sorts) > 1:
            raise UnsupportedFeatureError("worksheet has duplicate computed sorts")
        attrs = {"column": column, "direction": directions[direction], "using": using}
        if sorts:
            sorts[0].attrib.clear()
            sorts[0].attrib.update(attrs)
        else:
            _insert_in_order(view, ET.Element("computed-sort", attrib=attrs), _VIEW_CHILD_ORDER)
        _replace_if_changed(worksheet_el, updated, self._context)
        _ensure_manifest_feature(self._context, "SortTagCleanup")
        return self

    def update(
        self,
        *,
        name: str | _UnsetType = UNSET,
        visible: bool | _UnsetType = UNSET,
        title: str | None | _UnsetType = UNSET,
        table_style: TableStyle | _UnsetType = UNSET,
        title_style: TitleStyle | _UnsetType = UNSET,
        grand_totals: GrandTotals | _UnsetType = UNSET,
    ) -> TwbWorksheet:
        worksheet_el = self._resolve_element()
        table_style = _validate_style_group(
            "table_style", table_style, _TABLE_STYLE_KEYS
        )
        title_style = _validate_style_group(
            "title_style", title_style, _TITLE_STYLE_KEYS
        )
        grand_totals = _validate_grand_totals(
            _validate_style_group("grand_totals", grand_totals, _GRAND_TOTALS_KEYS)
        )
        if name is not UNSET:
            if not isinstance(name, str):
                raise TypeError("name must be a string")
            name = name.strip()
            if not name:
                raise ValueError("name must not be empty")
            for other in worksheet_elements(self._context.tree):
                if other is not worksheet_el and other.get("name") == name:
                    raise ValueError(f"worksheet name already exists: {name}")
        if visible is not UNSET and not isinstance(visible, bool):
            raise TypeError("visible must be bool")

        if title is not UNSET:
            self._apply_title(title)
        if table_style is not UNSET:
            self._apply_table_style(**table_style)
        if title_style is not UNSET:
            self._apply_title_style(**title_style)
        if grand_totals is not UNSET:
            self._apply_grand_totals(grand_totals)

        root = self._context.tree.getroot()
        updated_root = copy.deepcopy(root)
        updated_worksheet = updated_root.xpath(
            "/workbook/worksheets/worksheet[@name=$id]",
            id=self._id,
        )[0]
        target_id = self._id
        if name is not UNSET:
            target_id = name
            updated_worksheet.set("name", target_id)
            _rename_worksheet_references(updated_root, self._id, target_id)

        if visible is not UNSET:
            windows = updated_root.xpath(
                "/workbook/windows/window[@class='worksheet'][@name=$id]",
                id=target_id,
            )
            if windows:
                windows[0].set("hidden", "false" if visible else "true")
            elif not visible:
                windows_container = _direct_child(updated_root, "windows")
                if windows_container is None:
                    windows_container = ET.Element("windows")
                    updated_root.insert(0, windows_container)
                ET.SubElement(
                    windows_container,
                    "window",
                    attrib={"class": "worksheet", "name": target_id, "hidden": "true"},
                )

        if not xml_equal(root, updated_root):
            self._context.tree._setroot(updated_root)
            self._context.mark_dirty()
            self._id = target_id
        return self

    def delete(self) -> None:
        self._resolve_element()
        references = worksheet_references(self._context.tree, self._id)
        if references:
            raise ResourceInUseError("Worksheet", self._id, references)

        root = self._context.tree.getroot()
        updated_root = copy.deepcopy(root)
        worksheets = updated_root.xpath(
            "/workbook/worksheets/worksheet[@name=$id]",
            id=self._id,
        )
        if len(worksheets) != 1 or worksheets[0].getparent() is None:
            raise DetachedModelError(f"worksheet is detached: {self._id}")
        worksheets[0].getparent().remove(worksheets[0])
        for window in updated_root.xpath(
            "/workbook/windows/window[@class='worksheet'][@name=$id]",
            id=self._id,
        ):
            parent = window.getparent()
            if parent is not None:
                parent.remove(window)
        self._context.tree._setroot(updated_root)
        self._context.mark_dirty()
        self._detach()


_REFERENCE_LINE_FORMULAS = {"average", "median", "minimum", "maximum"}


class TwbReferenceLine(ConnectedModel):
    """ペインに置かれたリファレンスライン（`pane/reference-line[@id]`）。

    `id` は XML の `@id`。表示名を持たない要素なので `name` は `id` と同じ。
    """

    def __init__(self, context: WorkbookContext, worksheet_id: str, line_id: str):
        super().__init__(context)
        self._worksheet_id = worksheet_id
        self._id = line_id

    def _resolve_worksheet_element(self) -> ET._Element:
        return TwbWorksheet(self._context, self._worksheet_id)._resolve_element()

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        matches = self._resolve_worksheet_element().xpath(
            ".//*[local-name()='reference-line'][@id=$line_id]",
            line_id=self._id,
        )
        if not matches:
            self._detach()
            raise DetachedModelError(f"reference line is detached: {self._id}")
        return matches[0]

    def _snapshot(self):
        """読み取りは既存の materialize を使い回す（実装を二重に持たない）。"""
        self._resolve_element()
        for item in list_reference_lines_from_tree(
            self._context.tree, self._worksheet_id, by="name"
        ):
            if item.id == self._id:
                return item
        raise DetachedModelError(f"reference line is detached: {self._id}")

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._id

    @property
    def worksheet_id(self) -> str:
        return self._worksheet_id

    @property
    def axis_field_id(self) -> str | None:
        """軸のフィールドの XML 内部参照（`[ds1].[none:Sales:qk]` の形）。"""
        return self._snapshot().axis_column

    @property
    def axis_name(self) -> str | None:
        """軸のフィールドの表示名。"""
        return self._snapshot().axis_caption

    @property
    def axis_role(self) -> str | None:
        return self._snapshot().axis_role

    @property
    def value_field_id(self) -> str | None:
        """値のフィールドの XML 内部参照。"""
        return self._snapshot().value_column

    @property
    def value_name(self) -> str | None:
        """値のフィールドの表示名。"""
        return self._snapshot().value_caption

    @property
    def value_role(self) -> str | None:
        return self._snapshot().value_role

    @property
    def formula(self) -> str | None:
        return self._snapshot().formula

    @property
    def scope(self) -> str | None:
        return self._snapshot().scope

    @property
    def label_type(self) -> str | None:
        return self._snapshot().label_type

    @property
    def tooltip_type(self) -> str | None:
        return self._snapshot().tooltip_type

    @property
    def attrs(self) -> dict[str, str]:
        return self._snapshot().attrs

    def update(
        self,
        *,
        formula: str | _UnsetType = UNSET,
        scope: str | _UnsetType = UNSET,
        label_type: str | _UnsetType = UNSET,
    ) -> TwbReferenceLine:
        """`add_reference_line()` で指定できる値を後から変える。"""
        if formula is not UNSET:
            if not isinstance(formula, str):
                raise TypeError("formula must be a string")
            formula = formula.lower()
            if formula not in _REFERENCE_LINE_FORMULAS:
                raise ValueError("unsupported reference line formula")
        for argument, value in (("scope", scope), ("label_type", label_type)):
            if value is not UNSET:
                if not isinstance(value, str):
                    raise TypeError(f"{argument} must be a string")
                if not value.strip():
                    raise ValueError(f"{argument} must not be empty")

        worksheet_el = self._resolve_worksheet_element()
        updated = copy.deepcopy(worksheet_el)
        line = updated.xpath(
            ".//*[local-name()='reference-line'][@id=$line_id]",
            line_id=self._id,
        )[0]
        if formula is not UNSET:
            line.set("formula", formula)
        if scope is not UNSET:
            line.set("scope", scope)
        if label_type is not UNSET:
            line.set("label-type", label_type)
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def delete(self) -> None:
        worksheet_el = self._resolve_worksheet_element()
        updated = copy.deepcopy(worksheet_el)
        for line in updated.xpath(
            ".//*[local-name()='reference-line'][@id=$line_id]",
            line_id=self._id,
        ):
            parent = line.getparent()
            assert parent is not None
            parent.remove(line)
        _replace_if_changed(worksheet_el, updated, self._context)
        self._detach()


class TwbWorksheetFilter(ConnectedModel):
    """ワークシートに置かれたフィルタ（`view/filter[@column]`）。

    `id` は XML 内部参照（`[ds1].[none:Region:nk]`）、`name` は解決済みのフィールド名。
    """

    def __init__(self, context: WorkbookContext, worksheet_id: str, column: str):
        super().__init__(context)
        self._worksheet_id = worksheet_id
        self._id = column

    def _resolve_worksheet_element(self) -> ET._Element:
        return TwbWorksheet(self._context, self._worksheet_id)._resolve_element()

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        matches = self._resolve_worksheet_element().xpath(
            ".//*[local-name()='filter'][@column=$column]",
            column=self._id,
        )
        if not matches:
            self._detach()
            raise DetachedModelError(f"worksheet filter is detached: {self._id}")
        return matches[0]

    def _snapshot(self):
        """読み取りは既存の materialize を使い回す（実装を二重に持たない）。"""
        self._resolve_element()
        for item in list_filters_from_tree(self._context.tree, self._worksheet_id, by="name"):
            if item.column == self._id:
                return item
        raise DetachedModelError(f"worksheet filter is detached: {self._id}")

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        snapshot = self._snapshot()
        return snapshot.field or snapshot.column or self._id

    @property
    def worksheet_id(self) -> str:
        return self._worksheet_id

    @property
    def field(self) -> str | None:
        return self._snapshot().field

    @property
    def role(self) -> str | None:
        return self._snapshot().role

    @property
    def filter_class(self) -> str | None:
        return self._snapshot().filter_class

    @property
    def filter_group(self) -> str | None:
        return self._snapshot().filter_group

    @property
    def domain(self) -> str | None:
        return self._snapshot().domain

    @property
    def enumeration(self) -> str | None:
        return self._snapshot().enumeration

    @property
    def value_scope(self) -> str | None:
        return self._snapshot().value_scope

    @property
    def value_scope_label(self) -> str | None:
        return self._snapshot().value_scope_label

    @property
    def apply_scope(self) -> str | None:
        return self._snapshot().apply_scope

    @property
    def apply_scope_label(self) -> str | None:
        return self._snapshot().apply_scope_label

    @property
    def selection_type(self) -> str | None:
        return self._snapshot().selection_type

    @property
    def values(self) -> list[str]:
        return self._snapshot().values

    @property
    def functions(self) -> list[str]:
        return self._snapshot().functions

    @property
    def attrs(self) -> dict[str, str]:
        return self._snapshot().attrs

    def update(self, *, values: list[str] | _UnsetType = UNSET) -> TwbWorksheetFilter:
        """選択値を入れ替える。空リストは「すべての値」を表す。"""
        if values is UNSET:
            return self
        if not isinstance(values, list):
            raise TypeError("values must be a list")
        for value in values:
            if not isinstance(value, str):
                raise TypeError("values must be strings")
            if not value.strip():
                raise ValueError("values must not be empty strings")

        token = _FIELD_REF.match(self._id)
        if token is None:
            raise UnsupportedFeatureError(f"unsupported filter field reference: {self._id}")
        level = f"[{token.group(2)}]"

        worksheet_el = self._resolve_worksheet_element()
        updated = copy.deepcopy(worksheet_el)
        filter_el = updated.xpath(
            ".//*[local-name()='filter'][@column=$column]",
            column=self._id,
        )[0]

        # 既存の member 用 groupfilter を雛形にすると、user:ui-* の設定と
        # 名前空間の接頭辞をそのまま引き継げる。
        template = next(
            (
                child
                for child in filter_el
                if _local_name(child) == "groupfilter" and child.get("function") == "member"
            ),
            None,
        )
        for child in list(filter_el):
            if _local_name(child) == "groupfilter":
                filter_el.remove(child)

        if not values:
            ET.SubElement(
                filter_el,
                "groupfilter",
                attrib={"function": "level-members", "level": level},
            )
        else:
            for value in values:
                if template is not None:
                    child = copy.deepcopy(template)
                    for grandchild in list(child):
                        child.remove(grandchild)
                else:
                    child = ET.SubElement(filter_el, "groupfilter")
                    child.set("function", "member")
                    child.set("level", level)
                if template is not None:
                    filter_el.append(child)
                child.set("member", f'"{value}"')

        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def delete(self) -> None:
        worksheet_el = self._resolve_worksheet_element()
        updated = copy.deepcopy(worksheet_el)
        for filter_el in updated.xpath(
            ".//*[local-name()='filter'][@column=$column]",
            column=self._id,
        ):
            parent = filter_el.getparent()
            assert parent is not None
            parent.remove(filter_el)
        # add_filter() が置く slices の参照も一緒に外す
        for slices in updated.xpath(".//*[local-name()='slices']"):
            for column_el in slices.xpath(
                "./*[local-name()='column'][text()=$column]",
                column=self._id,
            ):
                slices.remove(column_el)
            if not len(slices):
                slices_parent = slices.getparent()
                assert slices_parent is not None
                slices_parent.remove(slices)
        _replace_if_changed(worksheet_el, updated, self._context)
        self._detach()


class TwbPane(ConnectedModel):
    def __init__(
        self,
        context: WorkbookContext,
        worksheet_id: str,
        pane_id: str,
        pane_index: int,
    ):
        super().__init__(context)
        self._worksheet_id = worksheet_id
        self._id = pane_id
        self._pane_index = pane_index

    def _resolve_worksheet_element(self) -> ET._Element:
        return TwbWorksheet(self._context, self._worksheet_id)._resolve_element()

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        panes = _pane_elements(self._resolve_worksheet_element())
        if self._pane_index >= len(panes):
            self._detach()
            raise DetachedModelError(f"pane is detached: {self._id}")
        pane_el = panes[self._pane_index]
        if _pane_id(pane_el, self._pane_index) != self._id:
            self._detach()
            raise DetachedModelError(f"pane is detached: {self._id}")
        return pane_el

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        return self.id

    @property
    def mark_type(self) -> str:
        marks = self._resolve_element().xpath("./*[local-name()='mark']")
        stored = marks[0].get("class") if marks else "Automatic"
        normalized = (stored or "Automatic").lower()
        return next(
            (public for public, xml_value in _MARK_TYPES.items() if xml_value.lower() == normalized),
            normalized,
        )

    def get_fields(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbWorksheetField]:
        _validate_get_args(id, name)
        worksheet = TwbWorksheet(self._context, self._worksheet_id)
        return [
            field
            for field in worksheet.get_fields(id=id, name=name)
            if field.pane_id == self._id and field.encoding is not None
        ]

    @property
    def customized_label(self) -> dict[str, str | None] | None:
        """カスタムラベルの構成。`set_customized_label()` と対になる。"""
        pane_el = self._resolve_element()
        customized = _direct_child(pane_el, "customized-label")
        if customized is None:
            return None
        runs = customized.xpath("./*[local-name()='formatted-text']/*[local-name()='run']")
        references = [
            match.group(0)
            for run in runs
            if (match := FIELD_REF_RE.search(run.text or "")) is not None
        ]
        worksheet_el = self._resolve_worksheet_element()
        names = [
            _field_details(self._context, worksheet_el, reference)[2]
            for reference in references
        ]
        label_color = next(
            (run.get("fontcolor") for run in runs if run.get("fontsize") == "12"),
            None,
        )
        value_color = next(
            (run.get("fontcolor") for run in runs if run.get("fontsize") == "18"),
            None,
        )
        return {
            "main_metric": names[0] if names else None,
            "sub_metric": names[1] if len(names) > 1 else None,
            "main_color": label_color,
            "value_color": value_color,
        }

    def set_customized_label(
        self,
        *,
        main_metric: TwbWorksheetField,
        sub_metric: TwbWorksheetField | None,
        main_color: str,
        value_color: str = "#333333",
        vertical_alignment: str = "center",
    ) -> TwbPane:
        if not isinstance(main_metric, TwbWorksheetField):
            raise TypeError("main_metric must be TwbWorksheetField")
        if sub_metric is not None and not isinstance(sub_metric, TwbWorksheetField):
            raise TypeError("sub_metric must be TwbWorksheetField or None")
        if not isinstance(main_color, str) or not main_color.strip():
            raise ValueError("main_color must be a non-empty string")
        if not isinstance(value_color, str) or not value_color.strip():
            raise ValueError("value_color must be a non-empty string")
        if vertical_alignment not in {"top", "center", "bottom"}:
            raise ValueError("vertical_alignment must be top, center, or bottom")
        metrics = [main_metric, *([] if sub_metric is None else [sub_metric])]
        placements = []
        for metric in metrics:
            if metric._context is not self._context:
                raise ValueError("metrics must belong to the same workbook")
            placement = metric._resolve_placement()
            if placement.pane_id != self._id or placement.encoding != "label":
                raise ValueError("metrics must be label fields in this pane")
            placements.append(placement)

        pane_el = self._resolve_element()
        updated = copy.deepcopy(pane_el)
        existing = _direct_child(updated, "customized-label")
        if existing is not None:
            updated.remove(existing)
        customized = ET.Element("customized-label")
        formatted = ET.SubElement(customized, "formatted-text")

        run = ET.SubElement(formatted, "run", attrib={
            "bold": "true", "fontalignment": "0", "fontcolor": main_color, "fontsize": "12",
        })
        run.text = main_metric.name
        ET.SubElement(formatted, "run").text = "Æ\n"
        run = ET.SubElement(formatted, "run", attrib={
            "bold": "true", "fontcolor": value_color, "fontsize": "18",
        })
        run.text = ET.CDATA(f"<{placements[0].reference}>")
        if sub_metric is not None:
            ET.SubElement(formatted, "run").text = "Æ\n"
            run = ET.SubElement(formatted, "run", attrib={
                "bold": "true", "fontcolor": "#555555", "fontsize": "10",
            })
            run.text = ET.CDATA(f"({sub_metric.name} <{placements[1].reference}>)")
        _insert_in_order(updated, customized, _PANE_CHILD_ORDER)

        style = _direct_child(updated, "style")
        if style is None:
            style = ET.Element("style")
            _insert_in_order(updated, style, _PANE_CHILD_ORDER)
        _set_style_value(style, "cell", "vertical-align", vertical_alignment)
        _set_style_value(style, "cell", "text-align", "center")
        _set_style_value(style, "mark", "mark-labels-show", "true")
        _set_style_value(style, "mark", "mark-labels-cull", "true")
        _replace_if_changed(pane_el, updated, self._context)
        return self

    def _apply_label_style(
        self,
        *,
        show: bool = True,
        cull: bool = False,
    ) -> TwbPane:
        if not isinstance(show, bool) or not isinstance(cull, bool):
            raise TypeError("show and cull must be bool")
        pane_el = self._resolve_element()
        updated = copy.deepcopy(pane_el)
        style = _direct_child(updated, "style")
        if style is None:
            style = ET.Element("style")
            _insert_in_order(updated, style, _PANE_CHILD_ORDER)
        _set_style_value(style, "mark", "mark-labels-show", str(show).lower())
        _set_style_value(style, "mark", "mark-labels-cull", str(cull).lower())
        _replace_if_changed(pane_el, updated, self._context)
        return self

    @property
    def mark_opacity(self) -> float | None:
        """マークの不透明度。"""
        style = _direct_child(self._resolve_element(), "style")
        if style is None:
            return None
        transparency = _style_value(style, "mark", "mark-transparency")
        if transparency is None:
            return None
        return (float(transparency) / 255) ** 2.4

    def _apply_mark_opacity(self, opacity: float) -> TwbPane:
        if not isinstance(opacity, (int, float)) or isinstance(opacity, bool):
            raise TypeError("opacity must be a number")
        opacity = float(opacity)
        if not 0 <= opacity <= 1:
            raise ValueError("opacity must be between 0 and 1")
        pane_el = self._resolve_element()
        updated = copy.deepcopy(pane_el)
        style = _direct_child(updated, "style")
        if style is None:
            style = ET.Element("style")
            _insert_in_order(updated, style, _PANE_CHILD_ORDER)
        transparency = round(255 * opacity ** (1 / 2.4))
        _set_style_value(style, "mark", "mark-transparency", str(transparency))
        _replace_if_changed(pane_el, updated, self._context)
        return self

    def _apply_mark_sizing(self, *, scaling: bool) -> TwbPane:
        if not isinstance(scaling, bool):
            raise TypeError("scaling must be bool")
        pane_el = self._resolve_element()
        updated = copy.deepcopy(pane_el)
        sizing = _direct_child(updated, "mark-sizing")
        if sizing is None:
            sizing = ET.Element("mark-sizing")
            _insert_in_order(updated, sizing, _PANE_CHILD_ORDER)
        sizing.set(
            "mark-sizing-setting",
            "marks-scaling-on" if scaling else "marks-scaling-off",
        )
        _replace_if_changed(pane_el, updated, self._context)
        return self

    def _apply_mark_size(self, size: float) -> TwbPane:
        if not isinstance(size, (int, float)) or isinstance(size, bool):
            raise TypeError("size must be a number")
        size = float(size)
        if size <= 0:
            raise ValueError("size must be greater than zero")
        pane_el = self._resolve_element()
        updated = copy.deepcopy(pane_el)
        style = _direct_child(updated, "style")
        if style is None:
            style = ET.Element("style")
            _insert_in_order(updated, style, _PANE_CHILD_ORDER)
        value = str(int(size)) if size.is_integer() else str(size)
        _set_style_value(style, "mark", "size", value)
        _replace_if_changed(pane_el, updated, self._context)
        return self

    def _apply_mark_color(self, color: str) -> TwbPane:
        if not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
            raise ValueError("color must use #RRGGBB")
        pane_el = self._resolve_element()
        updated = copy.deepcopy(pane_el)
        style = _direct_child(updated, "style")
        if style is None:
            style = ET.Element("style")
            _insert_in_order(updated, style, _PANE_CHILD_ORDER)
        _set_style_value(style, "mark", "mark-color", color.lower())
        _replace_if_changed(pane_el, updated, self._context)
        return self

    def _resolve_field(self, value: FieldInput, *, argument: str = "field") -> TwbField:
        """`field=` を `TwbField` へ解決する。素の文字列は属するシートの依存から探す。"""
        return resolve_field_input(
            self._context,
            value,
            datasources=worksheet_datasources(
                self._context, self._resolve_worksheet_element()
            ),
            argument=argument,
        )

    def add_field(
        self,
        *,
        field: FieldInput,
        encoding: str,
        aggregation: str | None = None,
        discrete: bool | None = None,
        table_calculation: str | None = None,
        table_calculation_field: FieldInput | None = None,
    ) -> TwbWorksheetField:
        field = self._resolve_field(field)
        if table_calculation_field is not None:
            table_calculation_field = self._resolve_field(
                table_calculation_field, argument="table_calculation_field"
            )
        encoding = encoding.lower()
        if encoding not in _ENCODINGS:
            raise ValueError(f"unsupported encoding: {encoding}")
        reference = _build_reference(
            field,
            aggregation=aggregation,
            discrete=discrete,
            table_calculation=table_calculation,
            table_calculation_field=table_calculation_field,
        )

        pane_el = self._resolve_element()
        worksheet_el = self._resolve_worksheet_element()
        existing = next(
            (
                placement
                for placement in _placements(worksheet_el)
                if placement.pane_id == self._id
                and placement.encoding == encoding
                and placement.reference == reference
            ),
            None,
        )
        if existing is not None:
            return TwbWorksheetField(self._context, self._worksheet_id, existing.id)

        updated = copy.deepcopy(worksheet_el)
        _ensure_dependency(
            updated,
            field,
            reference,
            table_calculation,
            table_calculation_field,
        )
        updated_pane = _pane_elements(updated)[self._pane_index]
        encodings = _direct_child(updated_pane, "encodings")
        if encodings is None:
            encodings = ET.Element("encodings")
            _insert_in_order(updated_pane, encodings, _PANE_CHILD_ORDER)
        ET.SubElement(encodings, _ENCODINGS[encoding], attrib={"column": reference})
        created = next(
            placement
            for placement in reversed(_placements(updated))
            if placement.pane_id == self._id
            and placement.encoding == encoding
            and placement.reference == reference
        )
        _replace_if_changed(worksheet_el, updated, self._context)
        return TwbWorksheetField(self._context, self._worksheet_id, created.id)

    def get_categorical_colors(
        self,
        field: TwbWorksheetField,
    ) -> dict[str, str]:
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        reference = field._resolve_placement().reference
        worksheet_el = self._resolve_worksheet_element()
        encodings = worksheet_el.xpath(
            "./*[local-name()='table']/*[local-name()='style']"
            "/*[local-name()='style-rule' and @element='mark']"
            "/*[local-name()='encoding' and @attr='color' and @field=$reference]",
            reference=reference,
        )
        if not encodings:
            return {}
        result: dict[str, str] = {}
        for mapping in encodings[0].xpath("./*[local-name()='map']"):
            buckets = mapping.xpath("./*[local-name()='bucket']")
            if not buckets or not mapping.get("to"):
                continue
            label = (buckets[0].text or "").strip()
            if len(label) >= 2 and label[0] == label[-1] == '"':
                label = label[1:-1]
            result[label] = mapping.get("to") or ""
        return result

    def set_categorical_colors(
        self,
        field: TwbWorksheetField,
        colors: dict[str, str],
    ) -> TwbPane:
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        if field._context is not self._context or field.pane_id != self._id:
            raise ValueError("field must belong to the pane")
        if field.encoding != "color":
            raise ValueError("field must use the color encoding")
        if not isinstance(colors, dict) or not colors:
            raise ValueError("colors must be a non-empty dict")
        for label, color in colors.items():
            if not isinstance(label, str) or not label:
                raise ValueError("color labels must be non-empty strings")
            if not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
                raise ValueError("colors must use #RRGGBB")

        reference = field._resolve_placement().reference
        root = self._context.tree.getroot()
        updated_root = copy.deepcopy(root)
        worksheets = updated_root.xpath(
            "/workbook/worksheets/worksheet[@name=$id]",
            id=self._worksheet_id,
        )
        if len(worksheets) != 1:
            raise DetachedModelError(f"worksheet is detached: {self._worksheet_id}")
        updated_worksheet = worksheets[0]
        style = _ensure_table_style(_ensure_table(updated_worksheet))
        rule = _style_rule(style, "mark", create=True)
        assert rule is not None
        for existing in rule.xpath(
            "./*[local-name()='encoding' and @attr='color' and @field=$reference]",
            reference=reference,
        ):
            rule.remove(existing)
        encoding = ET.SubElement(
            rule,
            "encoding",
            attrib={"attr": "color", "field": reference, "type": "palette"},
        )
        for label, color in colors.items():
            mapping = ET.SubElement(encoding, "map", attrib={"to": color})
            bucket = ET.SubElement(mapping, "bucket")
            bucket.text = f'"{label}"'
        _sync_datasource_categorical_colors(
            updated_root,
            updated_worksheet,
            reference,
            colors,
        )
        if not xml_equal(root, updated_root):
            self._context.tree._setroot(updated_root)
            self._context.mark_dirty()
        return self

    def set_continuous_colors(
        self,
        field: TwbWorksheetField,
        *,
        min_color: str,
        mid_color: str,
        max_color: str,
    ) -> TwbPane:
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        if field._context is not self._context or field.pane_id != self._id:
            raise ValueError("field must belong to the pane")
        if field.encoding != "color":
            raise ValueError("field must use the color encoding")
        colors = (min_color, mid_color, max_color)
        if any(
            not isinstance(color, str)
            or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None
            for color in colors
        ):
            raise ValueError("colors must use #RRGGBB")

        reference = field._resolve_placement().reference
        palette_name = "twbpatch-" + uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{self._worksheet_id}:{reference}",
        ).hex[:12]
        root = self._context.tree.getroot()
        updated_root = copy.deepcopy(root)
        preferences = _direct_child(updated_root, "preferences")
        if preferences is None:
            preferences = ET.Element("preferences")
            insert_at = next(
                (
                    index
                    for index, child in enumerate(updated_root)
                    if _local_name(child)
                    in {"style", "datasources", "worksheets", "dashboards", "windows"}
                ),
                len(updated_root),
            )
            updated_root.insert(insert_at, preferences)
        for palette in preferences.xpath(
            "./*[local-name()='color-palette'][@name=$name]",
            name=palette_name,
        ):
            preferences.remove(palette)
        palette = ET.SubElement(
            preferences,
            "color-palette",
            attrib={
                "custom": "true",
                "name": palette_name,
                "type": "ordered-diverging",
            },
        )
        for color in colors:
            ET.SubElement(palette, "color").text = color.lower()

        worksheets = updated_root.xpath(
            "/workbook/worksheets/worksheet[@name=$id]",
            id=self._worksheet_id,
        )
        if len(worksheets) != 1:
            raise DetachedModelError(f"worksheet is detached: {self._worksheet_id}")
        style = _ensure_table_style(_ensure_table(worksheets[0]))
        rule = _style_rule(style, "mark", create=True)
        assert rule is not None
        for existing in rule.xpath(
            "./*[local-name()='encoding' and @attr='color' and @field=$field]",
            field=reference,
        ):
            rule.remove(existing)
        ET.SubElement(
            rule,
            "encoding",
            attrib={
                "attr": "color",
                "field": reference,
                "palette": palette_name,
                "type": "interpolated",
            },
        )
        if not xml_equal(root, updated_root):
            self._context.tree._setroot(updated_root)
            self._context.mark_dirty()
        return self

    def update(
        self,
        *,
        mark_type: str | _UnsetType = UNSET,
        mark_color: str | _UnsetType = UNSET,
        mark_size: float | _UnsetType = UNSET,
        mark_opacity: float | _UnsetType = UNSET,
        mark_scaling: bool | _UnsetType = UNSET,
        label_style: LabelStyle | _UnsetType = UNSET,
    ) -> TwbPane:
        label_style = _validate_style_group(
            "label_style", label_style, _LABEL_STYLE_KEYS
        )
        if mark_color is not UNSET:
            self._apply_mark_color(mark_color)
        if mark_size is not UNSET:
            self._apply_mark_size(mark_size)
        if mark_opacity is not UNSET:
            self._apply_mark_opacity(mark_opacity)
        if mark_scaling is not UNSET:
            self._apply_mark_sizing(scaling=mark_scaling)
        if label_style is not UNSET:
            self._apply_label_style(**label_style)

        if mark_type is UNSET:
            return self
        if not isinstance(mark_type, str):
            raise TypeError("mark_type must be a string")
        mark_type = mark_type.lower()
        if mark_type not in _MARK_TYPES:
            raise ValueError(f"unsupported mark type: {mark_type}")

        pane_el = self._resolve_element()
        updated = copy.deepcopy(pane_el)
        marks = updated.xpath("./*[local-name()='mark']")
        if marks:
            marks[0].set("class", _MARK_TYPES[mark_type])
        else:
            mark = ET.Element("mark", attrib={"class": _MARK_TYPES[mark_type]})
            _insert_in_order(updated, mark, _PANE_CHILD_ORDER)
        _replace_if_changed(pane_el, updated, self._context)
        return self


class TwbWorksheetField(ConnectedModel):
    def __init__(self, context: WorkbookContext, worksheet_id: str, placement_id: str):
        super().__init__(context)
        self._worksheet_id = worksheet_id
        self._id = placement_id

    def _resolve_worksheet_element(self) -> ET._Element:
        return TwbWorksheet(self._context, self._worksheet_id)._resolve_element()

    def _resolve_placement(self) -> _Placement:
        self._ensure_attached()
        placement = next(
            (item for item in _placements(self._resolve_worksheet_element()) if item.id == self._id),
            None,
        )
        if placement is None:
            self._detach()
            raise DetachedModelError(f"worksheet field is detached: {self._id}")
        return placement

    @property
    def id(self) -> str:
        self._resolve_placement()
        return self._id

    @property
    def field_id(self) -> str:
        placement = self._resolve_placement()
        return _field_details(
            self._context,
            self._resolve_worksheet_element(),
            placement.reference,
        )[1]

    @property
    def name(self) -> str:
        placement = self._resolve_placement()
        return _field_details(
            self._context,
            self._resolve_worksheet_element(),
            placement.reference,
        )[2]

    @property
    def datasource_id(self) -> str:
        placement = self._resolve_placement()
        return _field_details(
            self._context,
            self._resolve_worksheet_element(),
            placement.reference,
        )[0]

    @property
    def shelf(self) -> str | None:
        return self._resolve_placement().shelf

    @property
    def encoding(self) -> str | None:
        return self._resolve_placement().encoding

    @property
    def pane_id(self) -> str | None:
        return self._resolve_placement().pane_id

    @property
    def aggregation(self) -> str | None:
        return _aggregation_from_reference(self._resolve_placement().reference)

    @property
    def discrete(self) -> bool | None:
        return _discrete_from_reference(self._resolve_placement().reference)

    @property
    def table_calculation(self) -> str | None:
        reference = self._resolve_placement().reference
        match = _FIELD_REF.match(reference)
        if match is None or not match.group(2).startswith("usr:"):
            return None
        worksheet_el = self._resolve_worksheet_element()
        datasource_id, token = match.groups()
        instances = worksheet_el.xpath(
            ".//*[local-name()='datasource-dependencies'][@datasource=$datasource_id]"
            "/*[local-name()='column-instance'][@name=$name]",
            datasource_id=datasource_id,
            name=f"[{token}]",
        )
        if len(instances) != 1:
            return None
        table_calc = _direct_child(instances[0], "table-calc")
        instance_order = table_calc.get("ordering-type") if table_calc is not None else None
        return next(
            (
                name
                for name, (_, stored_instance_order) in _TABLE_CALCULATIONS.items()
                if stored_instance_order == instance_order
            ),
            None,
        )

    @property
    def date_level(self) -> str | None:
        match = _FIELD_REF.match(self._resolve_placement().reference)
        if match is None:
            return None
        prefix = match.group(2).split(":", 1)[0]
        return next(
            (name for name, (stored, _) in _DATE_LEVELS.items() if stored == prefix),
            None,
        )

    def update(
        self,
        *,
        aggregation: str | None | _UnsetType = UNSET,
        discrete: bool | None | _UnsetType = UNSET,
    ) -> TwbWorksheetField:
        placement = self._resolve_placement()
        if self.table_calculation is not None or self.date_level is not None:
            raise UnsupportedFeatureError("derived field placement updates are not supported")
        datasource_id, field_id, _, _, _ = _field_details(
            self._context,
            self._resolve_worksheet_element(),
            placement.reference,
        )
        datasource_hits = self._context.tree.getroot().xpath(
            "/workbook/datasources/datasource[@name=$datasource_id]",
            datasource_id=datasource_id,
        )
        if not datasource_hits:
            raise UnsupportedFeatureError("placement datasource definition is unavailable")
        fields = [
            TwbField(self._context, datasource_id, field_id)
            for column in datasource_hits[0].findall("./column")
            if column.get("name") == field_id
        ]
        if len(fields) != 1:
            raise UnsupportedFeatureError("placement field definition is unavailable")
        field = fields[0]

        effective_aggregation = self.aggregation if aggregation is UNSET else aggregation
        effective_discrete = self.discrete if discrete is UNSET else discrete
        reference = _build_reference(
            field,
            aggregation=effective_aggregation,
            discrete=effective_discrete,
        )
        if reference == placement.reference:
            return self

        worksheet_el = self._resolve_worksheet_element()
        updated = copy.deepcopy(worksheet_el)
        updated_placement = next(item for item in _placements(updated) if item.id == self._id)
        if updated_placement.shelf in _SHELVES:
            references = _shelf_references(updated_placement.source_el)
            references[updated_placement.token_index or 0] = reference
            updated_placement.source_el.text = _format_shelf_references(references)
        else:
            updated_placement.source_el.set("column", reference)
        _replace_if_changed(worksheet_el, updated, self._context)
        return self

    def delete(self) -> None:
        placement = self._resolve_placement()
        datasource_id, field_id, _, _, _ = _field_details(
            self._context,
            self._resolve_worksheet_element(),
            placement.reference,
        )
        worksheet_el = self._resolve_worksheet_element()
        updated = copy.deepcopy(worksheet_el)
        updated_placement = next(item for item in _placements(updated) if item.id == self._id)
        if updated_placement.shelf in _SHELVES:
            references = _shelf_references(updated_placement.source_el)
            references.pop(updated_placement.token_index or 0)
            if references:
                updated_placement.source_el.text = _format_shelf_references(references)
            else:
                parent = updated_placement.source_el.getparent()
                if parent is None:
                    raise DetachedModelError(f"worksheet field is detached: {self._id}")
                parent.remove(updated_placement.source_el)
        else:
            parent = updated_placement.source_el.getparent()
            if parent is None:
                raise DetachedModelError(f"worksheet field is detached: {self._id}")
            parent.remove(updated_placement.source_el)
        _remove_unused_dependency(updated, datasource_id, field_id)
        _replace_if_changed(worksheet_el, updated, self._context)
        self._detach()


def get_worksheets(
    context: WorkbookContext,
    *,
    id: str | None = None,
    name: str | None = None,
) -> list[TwbWorksheet]:
    _validate_get_args(id, name)
    result: list[TwbWorksheet] = []
    for worksheet_el in worksheet_elements(context.tree):
        worksheet_id = worksheet_el.get("name")
        if not worksheet_id:
            continue
        worksheet_name = _worksheet_display_name(worksheet_el)
        if _matches(model_id=worksheet_id, model_name=worksheet_name, id=id, name=name):
            result.append(TwbWorksheet(context, worksheet_id))
    return result


def create_worksheet(
    context: WorkbookContext,
    *,
    name: str,
    visible: bool = True,
) -> TwbWorksheet:
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    if not isinstance(visible, bool):
        raise TypeError("visible must be bool")
    if any(worksheet.get("name") == name for worksheet in worksheet_elements(context.tree)):
        raise ValueError(f"worksheet already exists: {name}")

    root = context.tree.getroot()
    if ET.QName(root).namespace is not None:
        raise UnsupportedFeatureError("namespaced workbook XML is not supported")
    updated_root = copy.deepcopy(root)
    worksheets_el = _direct_child(updated_root, "worksheets")
    if worksheets_el is None:
        worksheets_el = ET.Element("worksheets")
        dashboards_el = _direct_child(updated_root, "dashboards")
        if dashboards_el is None:
            updated_root.append(worksheets_el)
        else:
            updated_root.insert(updated_root.index(dashboards_el), worksheets_el)

    worksheet_el = ET.SubElement(worksheets_el, "worksheet", attrib={"name": name})
    table_el = ET.SubElement(worksheet_el, "table")
    view_el = ET.SubElement(table_el, "view")
    ET.SubElement(view_el, "datasources")
    ET.SubElement(view_el, "aggregation", attrib={"value": "true"})
    ET.SubElement(table_el, "style")
    panes_el = ET.SubElement(table_el, "panes")
    pane_el = ET.SubElement(
        panes_el,
        "pane",
        attrib={"id": "1", "selection-relaxation-option": "selection-relaxation-allow"},
    )
    pane_view = ET.SubElement(pane_el, "view")
    ET.SubElement(pane_view, "breakdown", attrib={"value": "auto"})
    ET.SubElement(pane_el, "mark", attrib={"class": "Automatic"})
    ET.SubElement(pane_el, "encodings")
    ET.SubElement(table_el, "rows")
    ET.SubElement(table_el, "cols")
    ET.SubElement(
        worksheet_el,
        "simple-id",
        attrib={"uuid": f"{{{str(uuid.uuid4()).upper()}}}"},
    )

    if not visible:
        windows_el = _direct_child(updated_root, "windows")
        if windows_el is None:
            windows_el = ET.Element("windows")
            updated_root.insert(0, windows_el)
        ET.SubElement(
            windows_el,
            "window",
            attrib={"class": "worksheet", "name": name, "hidden": "true"},
        )

    context.tree._setroot(updated_root)
    context.mark_dirty()
    return TwbWorksheet(context, name)
