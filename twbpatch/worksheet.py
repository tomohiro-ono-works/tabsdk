from __future__ import annotations

from lxml import etree as ET
from .errors import NotFoundError, AmbiguousCaptionError
from .field_ref import attrs, build_column_index, resolve_field
from .models import TwbReferenceLine, TwbWorksheet, TwbWorksheetField
from .window import bool_attr, window_attrs_by_name
from .worksheet_field import build_datasource_labels, worksheet_fields_from_element


def worksheet_elements(tree: ET._ElementTree) -> list[ET._Element]:
    return list(tree.getroot().xpath("/workbook/worksheets/worksheet"))


def _text_tokens(value: str | None) -> list[str]:
    if not value:
        return []
    return [x for x in value.replace("\n", " ").split() if x]


def _first_text(node: ET._Element, xpath: str) -> str | None:
    hits = node.xpath(xpath)
    if not hits:
        return None
    value = hits[0]
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, ET._Element):
        return (value.text or "").strip()
    return str(value).strip()


def _raw_attrs(node: ET._Element) -> dict[str, str]:
    return {str(k): str(v) for k, v in node.attrib.items()}


def _reference_lines(
    ws_el: ET._Element,
    worksheet: str,
    *,
    columns: dict[tuple[str, str], ET._Element] | None = None,
) -> list[TwbReferenceLine]:
    lines: list[TwbReferenceLine] = []
    worksheet_id = ws_el.get("name")
    columns = columns or {}

    for refline in ws_el.xpath(".//*[local-name()='reference-line']"):
        axis_column = refline.get("axis-column")
        value_column = refline.get("value-column")
        axis_caption, axis_role = resolve_field(axis_column, columns)
        value_caption, value_role = resolve_field(value_column, columns)

        lines.append(
            TwbReferenceLine(
                worksheet=worksheet,
                worksheet_id=worksheet_id,
                id=refline.get("id"),
                axis_column=axis_column,
                axis_caption=axis_caption,
                axis_role=axis_role,
                value_column=value_column,
                value_caption=value_caption,
                value_role=value_role,
                formula=refline.get("formula"),
                scope=refline.get("scope"),
                label_type=refline.get("label-type"),
                tooltip_type=refline.get("tooltip-type"),
                attrs=attrs(refline),
            )
        )

    return lines


def materialize_worksheet(
    ws_el: ET._Element,
    *,
    window_attrs: dict[str, str] | None = None,
    columns: dict[tuple[str, str], ET._Element] | None = None,
    datasource_labels: dict[str, str] | None = None,
) -> TwbWorksheet:
    name = ws_el.get("name") or ""
    caption = ws_el.get("caption") or name
    hidden = bool(bool_attr((window_attrs or {}).get("hidden"), False))

    rows_text = _first_text(ws_el, ".//*[local-name()='rows']/text()")
    cols_text = _first_text(ws_el, ".//*[local-name()='cols']/text()")

    filters = [_raw_attrs(f) for f in ws_el.xpath(".//*[local-name()='filter']")]

    datasource_names: list[str] = []
    for ds_dep in ws_el.xpath(".//*[local-name()='datasource-dependencies']"):
        ds_name = ds_dep.get("datasource")
        if ds_name and ds_name not in datasource_names:
            datasource_names.append(ds_name)

    used_columns: list[str] = []
    for col in ws_el.xpath(".//*[local-name()='datasource-dependencies']/*[local-name()='column']"):
        col_name = col.get("name")
        if col_name and col_name not in used_columns:
            used_columns.append(col_name)

    return TwbWorksheet(
        name=name,
        id=name,
        caption=caption,
        rows=_text_tokens(rows_text),
        columns=_text_tokens(cols_text),
        filters=filters,
        datasource_names=datasource_names,
        used_columns=used_columns,
        reference_lines=_reference_lines(ws_el, caption, columns=columns),
        fields=worksheet_fields_from_element(
            ws_el,
            columns=columns,
            datasource_labels=datasource_labels,
        ),
        visible=not hidden,
    )


def list_worksheets_from_tree(tree: ET._ElementTree) -> list[TwbWorksheet]:
    windows = window_attrs_by_name(tree, "worksheet")
    columns = build_column_index(tree)
    datasource_labels = build_datasource_labels(tree)
    return [
        materialize_worksheet(
            ws,
            window_attrs=windows.get(ws.get("name") or ""),
            columns=columns,
            datasource_labels=datasource_labels,
        )
        for ws in worksheet_elements(tree)
    ]


def resolve_worksheet_el(tree: ET._ElementTree, worksheet: str, *, by: str = "auto") -> ET._Element:
    candidates = worksheet_elements(tree)
    if by not in {"auto", "caption", "name"}:
        raise ValueError("by must be 'auto', 'caption', or 'name'.")

    matched = [ws for ws in candidates if ws.get("caption") == worksheet] if by in {"auto", "caption"} else []
    if not matched and by in {"auto", "name"}:
        matched = [ws for ws in candidates if ws.get("name") == worksheet]
    if not matched:
        raise NotFoundError(f"worksheet not found: {worksheet}")
    if len(matched) > 1:
        raise AmbiguousCaptionError(f"worksheet is ambiguous: {worksheet}")
    return matched[0]


def get_worksheet_from_tree(tree: ET._ElementTree, worksheet: str, *, by: str = "auto") -> TwbWorksheet:
    ws_el = resolve_worksheet_el(tree, worksheet, by=by)
    windows = window_attrs_by_name(tree, "worksheet")
    columns = build_column_index(tree)
    return materialize_worksheet(
        ws_el,
        window_attrs=windows.get(ws_el.get("name") or ""),
        columns=columns,
        datasource_labels=build_datasource_labels(tree),
    )


def list_worksheet_fields_from_tree(
    tree: ET._ElementTree,
    worksheet: str | None = None,
    *,
    by: str = "auto",
    max_filter_value_chars: int = 40,
) -> list[TwbWorksheetField]:
    columns = build_column_index(tree)
    datasource_labels = build_datasource_labels(tree)
    worksheet_els = (
        [resolve_worksheet_el(tree, worksheet, by=by)]
        if worksheet is not None
        else worksheet_elements(tree)
    )
    fields: list[TwbWorksheetField] = []
    for ws_el in worksheet_els:
        fields.extend(
            worksheet_fields_from_element(
                ws_el,
                columns=columns,
                datasource_labels=datasource_labels,
                max_filter_value_chars=max_filter_value_chars,
            )
        )
    return fields


def list_reference_lines_from_tree(
    tree: ET._ElementTree,
    worksheet: str | None = None,
    *,
    by: str = "auto",
) -> list[TwbReferenceLine]:
    columns = build_column_index(tree)
    worksheet_els = [resolve_worksheet_el(tree, worksheet, by=by)] if worksheet is not None else worksheet_elements(tree)
    lines: list[TwbReferenceLine] = []

    for ws_el in worksheet_els:
        caption = ws_el.get("caption") or ws_el.get("name") or ""
        lines.extend(_reference_lines(ws_el, caption, columns=columns))

    return lines
