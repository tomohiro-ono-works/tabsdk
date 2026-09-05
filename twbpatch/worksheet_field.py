from __future__ import annotations

import re

from lxml import etree as ET

from .field_ref import (
    FIELD_REF_RE,
    attr_by_local_name,
    attrs,
    build_column_index,
    clean_filter_value,
    field_name_from_token,
)
from .models import TwbWorksheetField


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


def build_datasource_labels(tree: ET._ElementTree) -> dict[str, str]:
    return {
        str(datasource.get("name")): datasource.get("caption") or datasource.get("name") or ""
        for datasource in tree.getroot().xpath("/workbook/datasources/datasource[@name]")
    }


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def _refs_from_text(value: str | None) -> list[str]:
    return FIELD_REF_RE.findall(value or "")


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


def _field_details(
    ref: str | None,
    columns: dict[tuple[str, str], ET._Element],
    datasource_labels: dict[str, str],
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    match = re.match(r"^\[([^\]]+)\]\.\[([^\]]+)\]$", ref or "")
    if not match:
        return ref, None, None, None, None

    datasource_id, token = match.groups()
    field_name = field_name_from_token(token)
    candidate_names = (
        [field_name, f"[{field_name}]"]
        if field_name.startswith(":")
        else [f"[{field_name}]", field_name]
    )
    column = next(
        (columns.get((datasource_id, name)) for name in candidate_names if columns.get((datasource_id, name)) is not None),
        None,
    )
    caption = column.get("caption") or field_name if column is not None else field_name
    role = column.get("role") if column is not None else None
    field_id = column.get("name") if column is not None else field_name
    return caption, role, datasource_labels.get(datasource_id, datasource_id), datasource_id, field_id


def _truncate(value: str | None, max_chars: int) -> str | None:
    if value is None or max_chars <= 0 or len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3] + "..."


def _filter_values(
    filter_el: ET._Element,
    max_chars: int,
    columns: dict[tuple[str, str], ET._Element],
    datasource_labels: dict[str, str],
) -> str | None:
    values: list[str] = []

    def append(value: str | None) -> None:
        if value is None:
            return
        cleaned = clean_filter_value(value)
        if re.match(r"^\[[^\]]+\]\.\[[^\]]+\]$", cleaned):
            cleaned = _field_details(cleaned, columns, datasource_labels)[0] or cleaned
        if cleaned and cleaned not in values:
            values.append(cleaned)

    for node in [filter_el, *filter_el.xpath(".//*[local-name()='groupfilter']")]:
        append(node.get("member"))
        append(node.get("value"))

        min_value = node.get("min")
        max_value = node.get("max")
        if min_value is not None or max_value is not None:
            append(f"{clean_filter_value(min_value or '')} - {clean_filter_value(max_value or '')}")

        if attr_by_local_name(node, "ui-enumeration") == "all":
            append("All")

    return _truncate(", ".join(values) if values else None, max_chars)


def _append_field(
    fields: list[TwbWorksheetField],
    *,
    worksheet: str,
    worksheet_id: str | None,
    category: str,
    type_: str,
    ref: str | None,
    source_el: ET._Element,
    columns: dict[tuple[str, str], ET._Element],
    datasource_labels: dict[str, str],
    values: str | None = None,
    pane_id: str | None = None,
    mark_type: str | None = None,
) -> None:
    caption, role, datasource, datasource_id, field_id = _field_details(ref, columns, datasource_labels)
    fields.append(
        TwbWorksheetField(
            worksheet=worksheet,
            worksheet_id=worksheet_id,
            type=type_,
            role=role,
            caption=caption,
            id=ref,
            values=values,
            category=category,
            aggregation=_aggregation_from_ref(ref),
            datasource=datasource,
            datasource_id=datasource_id,
            field_id=field_id,
            pane_id=pane_id,
            mark_type=mark_type,
            attrs=attrs(source_el),
        )
    )


def _append_shelf_fields(
    fields: list[TwbWorksheetField],
    ws_el: ET._Element,
    *,
    tag: str,
    category: str,
    type_: str,
    worksheet: str,
    worksheet_id: str | None,
    columns: dict[tuple[str, str], ET._Element],
    datasource_labels: dict[str, str],
) -> None:
    for shelf in ws_el.xpath(f".//*[local-name()='{tag}']"):
        refs = _refs_from_text("".join(shelf.itertext()))
        if shelf.get("column"):
            refs.append(shelf.get("column"))
        for ref in dict.fromkeys(refs):
            _append_field(
                fields,
                worksheet=worksheet,
                worksheet_id=worksheet_id,
                category=category,
                type_=type_,
                ref=ref,
                source_el=shelf,
                columns=columns,
                datasource_labels=datasource_labels,
            )


def worksheet_fields_from_element(
    ws_el: ET._Element,
    *,
    columns: dict[tuple[str, str], ET._Element] | None = None,
    datasource_labels: dict[str, str] | None = None,
    max_filter_value_chars: int = 40,
) -> list[TwbWorksheetField]:
    tree = ws_el.getroottree()
    columns = columns or build_column_index(tree)
    datasource_labels = datasource_labels or build_datasource_labels(tree)
    worksheet_id = ws_el.get("name")
    worksheet = ws_el.get("caption") or worksheet_id or ""
    fields: list[TwbWorksheetField] = []

    for filter_el in ws_el.xpath(".//*[local-name()='filter'][@column]"):
        _append_field(
            fields,
            worksheet=worksheet,
            worksheet_id=worksheet_id,
            category="フィルタ",
            type_="フィルタ",
            ref=filter_el.get("column"),
            source_el=filter_el,
            columns=columns,
            datasource_labels=datasource_labels,
            values=_filter_values(filter_el, max_filter_value_chars, columns, datasource_labels),
        )

    _append_shelf_fields(
        fields,
        ws_el,
        tag="rows",
        category="軸",
        type_="y軸",
        worksheet=worksheet,
        worksheet_id=worksheet_id,
        columns=columns,
        datasource_labels=datasource_labels,
    )
    _append_shelf_fields(
        fields,
        ws_el,
        tag="cols",
        category="軸",
        type_="x軸",
        worksheet=worksheet,
        worksheet_id=worksheet_id,
        columns=columns,
        datasource_labels=datasource_labels,
    )
    _append_shelf_fields(
        fields,
        ws_el,
        tag="pages",
        category="ページ",
        type_="ページ",
        worksheet=worksheet,
        worksheet_id=worksheet_id,
        columns=columns,
        datasource_labels=datasource_labels,
    )

    for pane in ws_el.xpath(".//*[local-name()='pane']"):
        pane_id = pane.get("id")
        marks = pane.xpath("./*[local-name()='mark']")
        mark_type = marks[0].get("class") if marks else None

        for attribute, type_ in (("x-axis-name", "x軸"), ("y-axis-name", "y軸")):
            if pane.get(attribute):
                _append_field(
                    fields,
                    worksheet=worksheet,
                    worksheet_id=worksheet_id,
                    category="軸",
                    type_=type_,
                    ref=pane.get(attribute),
                    source_el=pane,
                    columns=columns,
                    datasource_labels=datasource_labels,
                    pane_id=pane_id,
                    mark_type=mark_type,
                )

        for encoding in pane.xpath(".//*[local-name()='encodings']/*[@column]"):
            type_ = ENCODING_TYPE_LABELS.get(_local_name(encoding), _local_name(encoding))
            _append_field(
                fields,
                worksheet=worksheet,
                worksheet_id=worksheet_id,
                category="ペイン",
                type_=type_,
                ref=encoding.get("column"),
                source_el=encoding,
                columns=columns,
                datasource_labels=datasource_labels,
                pane_id=pane_id,
                mark_type=mark_type,
            )

        for other in pane.xpath(".//*[@column and not(ancestor::*[local-name()='encodings'])]"):
            _append_field(
                fields,
                worksheet=worksheet,
                worksheet_id=worksheet_id,
                category="その他",
                type_="その他",
                ref=other.get("column"),
                source_el=other,
                columns=columns,
                datasource_labels=datasource_labels,
                pane_id=pane_id,
                mark_type=mark_type,
            )

    _append_shelf_fields(
        fields,
        ws_el,
        tag="sort",
        category="ソート",
        type_="ソート",
        worksheet=worksheet,
        worksheet_id=worksheet_id,
        columns=columns,
        datasource_labels=datasource_labels,
    )
    return fields
