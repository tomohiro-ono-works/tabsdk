from __future__ import annotations

from lxml import etree as ET
from .errors import NotFoundError, AmbiguousCaptionError
from .models import TwbWorksheet


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


def _attrs(node: ET._Element) -> dict[str, str]:
    return {str(k): str(v) for k, v in node.attrib.items()}


def materialize_worksheet(ws_el: ET._Element) -> TwbWorksheet:
    name = ws_el.get("name") or ""
    caption = ws_el.get("caption") or name

    rows_text = _first_text(ws_el, ".//*[local-name()='rows']/text()")
    cols_text = _first_text(ws_el, ".//*[local-name()='cols']/text()")

    filters = [_attrs(f) for f in ws_el.xpath(".//*[local-name()='filter']")]

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
    )


def list_worksheets_from_tree(tree: ET._ElementTree) -> list[TwbWorksheet]:
    return [materialize_worksheet(ws) for ws in worksheet_elements(tree)]


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
    return materialize_worksheet(resolve_worksheet_el(tree, worksheet, by=by))
