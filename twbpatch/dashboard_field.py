from __future__ import annotations

import re

from lxml import etree as ET

from .dashboard import get_dashboard_from_tree, list_dashboards_from_tree
from .models import TwbWorksheetField


FIELD_REF_RE = re.compile(r"\[[^\]]+\]\.\[[^\]]+\]")

ENCODING_TYPE_LABELS = {
    "color": "色",
    "text": "ラベル",
    "tooltip": "ツールチップ",
    "size": "サイズ",
    "shape": "形状",
    "lod": "詳細",
    "detail": "詳細",
    "path": "パス",
    "angle": "角度",
}

AGGREGATION_LABELS = {
    "sum": "SUM",
    "avg": "AVG",
    "average": "AVG",
    "median": "MEDIAN",
    "min": "MIN",
    "max": "MAX",
    "cnt": "COUNT",
    "count": "COUNT",
    "ctd": "COUNTD",
    "countd": "COUNTD",
    "stdev": "STDEV",
    "stdevp": "STDEVP",
    "var": "VAR",
    "varp": "VARP",
}


def _worksheet_map(tree: ET._ElementTree) -> dict[str, ET._Element]:
    return {str(ws.get("name")): ws for ws in tree.getroot().xpath("/workbook/worksheets/worksheet") if ws.get("name")}


def _build_column_index(tree: ET._ElementTree) -> dict[tuple[str, str], ET._Element]:
    columns: dict[tuple[str, str], ET._Element] = {}

    for ds in tree.getroot().xpath("//*[local-name()='datasource'][@name]"):
        ds_name = ds.get("name")
        for col in ds.xpath(".//*[local-name()='column'][@name]"):
            columns[(ds_name, col.get("name"))] = col

    for dep in tree.getroot().xpath("//*[local-name()='datasource-dependencies'][@datasource]"):
        ds_name = dep.get("datasource")
        for col in dep.xpath("./*[local-name()='column'][@name]"):
            columns[(ds_name, col.get("name"))] = col

    return columns


def _field_name_from_token(token: str) -> str:
    if token.startswith(":"):
        return token
    parts = token.split(":")
    return parts[1] if len(parts) >= 3 else token


def _aggregation_from_ref(ref: str | None) -> str | None:
    match = re.match(r"^\[[^\]]+\]\.\[([^\]]+)\]$", ref or "")
    if not match:
        return None
    token = match.group(1)
    if token.startswith(":"):
        return None
    parts = token.split(":")
    if len(parts) < 3:
        return None
    return AGGREGATION_LABELS.get(parts[0].lower())


def _resolve_field(ref: str | None, columns: dict[tuple[str, str], ET._Element]) -> tuple[str | None, str | None]:
    match = re.match(r"^\[([^\]]+)\]\.\[([^\]]+)\]$", ref or "")
    if not match:
        return ref, None

    ds_name, token = match.groups()
    field_name = _field_name_from_token(token)
    candidate_names = [field_name, f"[{field_name}]"] if field_name.startswith(":") else [f"[{field_name}]", field_name]

    col = next((columns.get((ds_name, name)) for name in candidate_names if columns.get((ds_name, name)) is not None), None)
    if col is None:
        return field_name, None
    return col.get("caption") or field_name, col.get("role")


def _refs_from_text(value: str | None) -> list[str]:
    return FIELD_REF_RE.findall(value or "")


def _first_text(node: ET._Element, name: str) -> str | None:
    hits = node.xpath(f".//*[local-name()='{name}']/text()")
    return str(hits[0]) if hits else None


def _attr_by_local_name(node: ET._Element, name: str) -> str | None:
    for key, value in node.attrib.items():
        if str(key).split("}")[-1] == name:
            return str(value)
    return None


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def _clean_filter_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _truncate(value: str | None, max_chars: int) -> str | None:
    if value is None or max_chars <= 0 or len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3] + "..."


def _filter_values(filter_el: ET._Element, max_chars: int, columns: dict[tuple[str, str], ET._Element]) -> str | None:
    values: list[str] = []

    def append(value: str | None) -> None:
        if value is None:
            return
        cleaned = _clean_filter_value(value)
        if re.match(r"^\[[^\]]+\]\.\[[^\]]+\]$", cleaned):
            cleaned = _resolve_field(cleaned, columns)[0] or cleaned
        if cleaned and cleaned not in values:
            values.append(cleaned)

    for node in [filter_el, *filter_el.xpath(".//*[local-name()='groupfilter']")]:
        append(node.get("member"))
        append(node.get("value"))

        min_value = node.get("min")
        max_value = node.get("max")
        if min_value is not None or max_value is not None:
            append(f"{_clean_filter_value(min_value or '')} - {_clean_filter_value(max_value or '')}")

        if _attr_by_local_name(node, "ui-enumeration") == "all":
            append("All")

    return _truncate(", ".join(values) if values else None, max_chars)


def _append_field(
    fields: list[TwbWorksheetField],
    *,
    worksheet: str,
    category: str,
    type_: str,
    ref: str | None,
    columns: dict[tuple[str, str], ET._Element],
    values: str | None = None,
) -> None:
    caption, role = _resolve_field(ref, columns)
    fields.append(
        TwbWorksheetField(
            worksheet=worksheet,
            type=type_,
            role=role,
            caption=caption,
            id=ref,
            values=values,
            category=category,
            aggregation=_aggregation_from_ref(ref),
        )
    )


def list_dashboard_fields_from_tree(
    tree: ET._ElementTree,
    dashboard: str | None = None,
    *,
    by: str = "auto",
    max_filter_value_chars: int = 40,
) -> list[TwbWorksheetField]:
    dashboards = [get_dashboard_from_tree(tree, dashboard, by=by)] if dashboard is not None else list_dashboards_from_tree(tree)
    worksheets_by_name = _worksheet_map(tree)
    columns = _build_column_index(tree)
    fields: list[TwbWorksheetField] = []

    for dash in dashboards:
        for ws in dash.worksheets:
            ws_el = worksheets_by_name.get(ws.name)
            if ws_el is None:
                continue

            for filter_el in ws_el.xpath(".//*[local-name()='filter'][@column]"):
                _append_field(
                    fields,
                    worksheet=ws.caption or ws.name,
                    category="フィルタ",
                    type_="フィルタ",
                    ref=filter_el.get("column"),
                    columns=columns,
                    values=_filter_values(filter_el, max_filter_value_chars, columns),
                )

            for ref in _refs_from_text(_first_text(ws_el, "rows")):
                _append_field(fields, worksheet=ws.caption or ws.name, category="軸", type_="y軸", ref=ref, columns=columns)

            for ref in _refs_from_text(_first_text(ws_el, "cols")):
                _append_field(fields, worksheet=ws.caption or ws.name, category="軸", type_="x軸", ref=ref, columns=columns)

            for pane in ws_el.xpath(".//*[local-name()='pane']"):
                for attr, type_ in (("x-axis-name", "x軸"), ("y-axis-name", "y軸")):
                    if pane.get(attr):
                        _append_field(
                            fields,
                            worksheet=ws.caption or ws.name,
                            category="軸",
                            type_=type_,
                            ref=pane.get(attr),
                            columns=columns,
                        )

                for el in pane.xpath(".//*[local-name()='encodings']/*[@column]"):
                    type_ = ENCODING_TYPE_LABELS.get(_local_name(el), _local_name(el))
                    _append_field(fields, worksheet=ws.caption or ws.name, category="ペイン", type_=type_, ref=el.get("column"), columns=columns)

                for el in pane.xpath(".//*[@column and not(ancestor::*[local-name()='encodings'])]"):
                    _append_field(fields, worksheet=ws.caption or ws.name, category="その他", type_="その他", ref=el.get("column"), columns=columns)

    return fields
