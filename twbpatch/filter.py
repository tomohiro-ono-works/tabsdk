from __future__ import annotations

from collections import Counter
import re

from lxml import etree as ET

from .dashboard import dashboard_elements, resolve_dashboard_el
from .field_ref import (
    attr_by_local_name,
    attrs,
    build_column_index,
    clean_filter_value,
    resolve_field,
)
from .models import TwbFilterControl, TwbWorksheetFilter
from .window import bool_attr
from .worksheet import resolve_worksheet_el, worksheet_elements


VALUE_SCOPE_LABELS = {
    "database": "データベース内のすべての値",
    "relevant": "関連値のみ",
    "hierarchy": "階層内のみ",
}

APPLY_SCOPE_LABELS = {
    "worksheet": "このワークシート",
    "selected_worksheets": "選択したワークシート",
    "data_source": "このデータソースを使用するすべて",
    "related_data_sources": "関連するデータソースを使用するすべて",
}


def _append_value(values: list[str], value: str | None, columns: dict[tuple[str, str], ET._Element]) -> None:
    if value is None:
        return
    cleaned = clean_filter_value(value)
    if re.match(r"^\[[^\]]+\]\.\[[^\]]+\]$", cleaned):
        cleaned = resolve_field(cleaned, columns)[0] or cleaned
    if cleaned and cleaned not in values:
        values.append(cleaned)


def _first_local_attr(nodes: list[ET._Element], name: str) -> str | None:
    for node in nodes:
        value = attr_by_local_name(node, name)
        if value is not None:
            return value
    return None


def _functions(nodes: list[ET._Element]) -> list[str]:
    functions: list[str] = []
    for node in nodes:
        function = node.get("function")
        if function and function not in functions:
            functions.append(function)
    return functions


def _selection_type(groupfilters: list[ET._Element], values: list[str], enumeration: str | None) -> str | None:
    if enumeration == "all" or "All" in values:
        return "all"
    if any(node.get("min") is not None or node.get("max") is not None for node in groupfilters):
        return "range"
    if any(node.get("function") == "end" for node in groupfilters):
        return next((node.get("end") for node in groupfilters if node.get("end")), "top")
    if len(values) == 1:
        return "single"
    if len(values) > 1:
        return "multiple"
    return enumeration


def _label(value: str | None, labels: dict[str, str]) -> str | None:
    if value is None:
        return None
    return labels.get(value, value)


def _value_scope(domain: str | None) -> str | None:
    return domain


def _normalize_apply_scope(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "this_worksheet": "worksheet",
        "worksheet": "worksheet",
        "selected_worksheets": "selected_worksheets",
        "selected_sheets": "selected_worksheets",
        "datasource": "data_source",
        "data_source": "data_source",
        "this_datasource": "data_source",
        "all_using_this_datasource": "data_source",
        "related_datasources": "related_data_sources",
        "related_data_sources": "related_data_sources",
        "all_using_related_datasources": "related_data_sources",
    }
    return aliases.get(normalized, normalized)


def _filter_group_counts(tree: ET._ElementTree) -> Counter[str]:
    return Counter(
        filter_el.get("filter-group")
        for filter_el in tree.getroot().xpath("//*[local-name()='filter'][@filter-group]")
        if filter_el.get("filter-group")
    )


def _has_ancestor(filter_el: ET._Element, local_name: str) -> bool:
    return any(ET.QName(node).localname == local_name for node in filter_el.iterancestors())


def _apply_scope(
    filter_el: ET._Element,
    groupfilters: list[ET._Element],
    filter_groups: Counter[str],
) -> str | None:
    raw_scope = (
        _first_local_attr([filter_el, *groupfilters], "apply-scope")
        or _first_local_attr([filter_el, *groupfilters], "filter-scope")
    )
    if raw_scope:
        return _normalize_apply_scope(raw_scope)

    if filter_el.get("filter-group") in filter_groups:
        return "selected_worksheets"
    if _has_ancestor(filter_el, "shared-view"):
        return "data_source"
    if _has_ancestor(filter_el, "worksheet"):
        return "worksheet"
    return None


def _materialize_filter(
    filter_el: ET._Element,
    worksheet: str,
    worksheet_id: str | None,
    columns: dict[tuple[str, str], ET._Element],
    filter_groups: Counter[str],
) -> TwbWorksheetFilter:
    groupfilters = list(filter_el.xpath(".//*[local-name()='groupfilter']"))
    field, role = resolve_field(filter_el.get("column"), columns)
    values: list[str] = []

    for node in [filter_el, *groupfilters]:
        _append_value(values, node.get("member"), columns)
        _append_value(values, node.get("value"), columns)

        min_value = node.get("min")
        max_value = node.get("max")
        if min_value is not None or max_value is not None:
            _append_value(
                values,
                f"{clean_filter_value(min_value or '')} - {clean_filter_value(max_value or '')}",
                columns,
            )

        if attr_by_local_name(node, "ui-enumeration") == "all":
            _append_value(values, "All", columns)

    domain = _first_local_attr([filter_el, *groupfilters], "ui-domain")
    enumeration = _first_local_attr([filter_el, *groupfilters], "ui-enumeration")
    value_scope = _value_scope(domain)
    apply_scope = _apply_scope(filter_el, groupfilters, filter_groups)

    return TwbWorksheetFilter(
        worksheet=worksheet,
        worksheet_id=worksheet_id,
        column=filter_el.get("column"),
        field=field,
        role=role,
        filter_class=filter_el.get("class"),
        filter_group=filter_el.get("filter-group"),
        domain=domain,
        enumeration=enumeration,
        value_scope=value_scope,
        value_scope_label=_label(value_scope, VALUE_SCOPE_LABELS),
        apply_scope=apply_scope,
        apply_scope_label=_label(apply_scope, APPLY_SCOPE_LABELS),
        selection_type=_selection_type(groupfilters, values, enumeration),
        values=values,
        functions=_functions(groupfilters),
        attrs=attrs(filter_el),
        groupfilter_attrs=[attrs(node) for node in groupfilters],
    )


def list_filters_from_tree(
    tree: ET._ElementTree,
    worksheet: str | None = None,
    *,
    by: str = "auto",
) -> list[TwbWorksheetFilter]:
    columns = build_column_index(tree)
    filter_groups = _filter_group_counts(tree)
    worksheet_els = (
        [resolve_worksheet_el(tree, worksheet, by=by)]
        if worksheet is not None
        else worksheet_elements(tree)
    )
    filters: list[TwbWorksheetFilter] = []

    for ws_el in worksheet_els:
        worksheet_id = ws_el.get("name")
        caption = ws_el.get("caption") or worksheet_id or ""
        for filter_el in ws_el.xpath(".//*[local-name()='filter']"):
            filters.append(_materialize_filter(filter_el, caption, worksheet_id, columns, filter_groups))

    return filters


def _all_filters_from_tree(
    tree: ET._ElementTree,
    columns: dict[tuple[str, str], ET._Element],
) -> list[TwbWorksheetFilter]:
    filters: list[TwbWorksheetFilter] = []
    filter_groups = _filter_group_counts(tree)

    for filter_el in tree.getroot().xpath("//*[local-name()='filter'][@column]"):
        worksheet_el = next(
            (node for node in filter_el.iterancestors() if ET.QName(node).localname == "worksheet"),
            None,
        )
        shared_view_el = next(
            (node for node in filter_el.iterancestors() if ET.QName(node).localname == "shared-view"),
            None,
        )
        owner_el = worksheet_el if worksheet_el is not None else shared_view_el
        owner_id = owner_el.get("name") if owner_el is not None else None
        owner = owner_el.get("caption") or owner_id or "" if owner_el is not None else ""
        filters.append(_materialize_filter(filter_el, owner, owner_id, columns, filter_groups))

    return filters


def _worksheet_map(tree: ET._ElementTree) -> dict[str, ET._Element]:
    return {str(ws.get("name")): ws for ws in tree.getroot().xpath("/workbook/worksheets/worksheet") if ws.get("name")}


def _filter_indexes(filters: list[TwbWorksheetFilter]) -> tuple[dict[tuple[str | None, str | None], TwbWorksheetFilter], dict[str | None, TwbWorksheetFilter]]:
    by_worksheet_and_column: dict[tuple[str | None, str | None], TwbWorksheetFilter] = {}
    by_column: dict[str | None, TwbWorksheetFilter] = {}

    for filter_ in filters:
        by_worksheet_and_column.setdefault((filter_.worksheet_id, filter_.column), filter_)
        by_column.setdefault(filter_.column, filter_)

    return by_worksheet_and_column, by_column


def _materialize_filter_control(
    zone: ET._Element,
    dashboard: str,
    dashboard_id: str | None,
    worksheets_by_name: dict[str, ET._Element],
    columns: dict[tuple[str, str], ET._Element],
    filters_by_worksheet_and_column: dict[tuple[str | None, str | None], TwbWorksheetFilter],
    filters_by_column: dict[str | None, TwbWorksheetFilter],
) -> TwbFilterControl:
    column = zone.get("param")
    field, role = resolve_field(column, columns)
    mode = zone.get("mode")
    worksheet_id = zone.get("name") if zone.get("name") in worksheets_by_name else None
    worksheet_el = worksheets_by_name.get(worksheet_id or "")
    worksheet = worksheet_el.get("caption") or worksheet_id if worksheet_el is not None else None
    filter_ = filters_by_worksheet_and_column.get((worksheet_id, column)) or filters_by_column.get(column)

    return TwbFilterControl(
        dashboard=dashboard,
        dashboard_id=dashboard_id,
        id=zone.get("id"),
        name=zone.get("custom-title") or zone.get("name"),
        worksheet=worksheet,
        worksheet_id=worksheet_id,
        column=column,
        field=field,
        role=role,
        mode=mode,
        filter_class=filter_.filter_class if filter_ is not None else None,
        domain=filter_.domain if filter_ is not None else None,
        enumeration=filter_.enumeration if filter_ is not None else None,
        value_scope=filter_.value_scope if filter_ is not None else None,
        value_scope_label=filter_.value_scope_label if filter_ is not None else None,
        apply_scope=filter_.apply_scope if filter_ is not None else None,
        apply_scope_label=filter_.apply_scope_label if filter_ is not None else None,
        selection_type=filter_.selection_type if filter_ is not None else None,
        values=filter_.values if filter_ is not None else [],
        show_apply=bool_attr(zone.get("show-apply"), None),
        show_title=bool_attr(zone.get("show-title"), None),
        show_caption=bool_attr(zone.get("show-caption"), None),
        x=zone.get("x"),
        y=zone.get("y"),
        width=zone.get("w"),
        height=zone.get("h"),
        attrs=attrs(zone),
    )


def list_dashboard_filter_controls_from_tree(
    tree: ET._ElementTree,
    dashboard: str | None = None,
    *,
    by: str = "auto",
) -> list[TwbFilterControl]:
    columns = build_column_index(tree)
    worksheets_by_name = _worksheet_map(tree)
    filters_by_worksheet_and_column, filters_by_column = _filter_indexes(_all_filters_from_tree(tree, columns))
    dashboard_els = (
        [resolve_dashboard_el(tree, dashboard, by=by)]
        if dashboard is not None
        else dashboard_elements(tree)
    )
    controls: list[TwbFilterControl] = []

    for dash_el in dashboard_els:
        dashboard_id = dash_el.get("name")
        dashboard_caption = dash_el.get("caption") or dashboard_id or ""
        for zone in dash_el.xpath(".//*[local-name()='zone'][@type-v2='filter']"):
            controls.append(
                _materialize_filter_control(
                    zone,
                    dashboard_caption,
                    dashboard_id,
                    worksheets_by_name,
                    columns,
                    filters_by_worksheet_and_column,
                    filters_by_column,
                )
            )

    return controls
