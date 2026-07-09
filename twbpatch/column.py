from __future__ import annotations

import re

from lxml import etree as ET
from .errors import AmbiguousCaptionError, NotFoundError
from .models import TwbColumn


_FORMULA_REF_RE = re.compile(r"\[([^\]]+)\]\.\[([^\]]+)\]|\[([^\]]+)\]")


def _bool_attr(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() == "true"


def _discrete_from_type(value: str | None) -> bool | None:
    if value == "nominal":
        return True
    if value == "quantitative":
        return False
    return None


def _field_name_from_token(token: str) -> str:
    if token.startswith(":"):
        return token
    parts = token.split(":")
    return parts[1] if len(parts) >= 3 else token


def _build_datasource_lookup(tree: ET._ElementTree) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for ds in tree.getroot().xpath("/workbook/datasources/datasource[@name]"):
        name = ds.get("name")
        caption = ds.get("caption")
        if name:
            lookup[name] = name
        if caption and name:
            lookup[caption] = name
    return lookup


def _build_datasource_labels(tree: ET._ElementTree) -> dict[str, str]:
    labels: dict[str, str] = {}
    for ds in tree.getroot().xpath("/workbook/datasources/datasource[@name]"):
        name = ds.get("name")
        if name:
            labels[name] = ds.get("caption") or name
    return labels


def _build_column_index(tree: ET._ElementTree) -> dict[tuple[str, str], ET._Element]:
    columns: dict[tuple[str, str], ET._Element] = {}

    for ds in tree.getroot().xpath("/workbook/datasources/datasource[@name]"):
        ds_name = ds.get("name")
        for col in ds.xpath(".//*[local-name()='column'][@name]"):
            columns[(ds_name, col.get("name"))] = col

    for dep in tree.getroot().xpath("//*[local-name()='datasource-dependencies'][@datasource]"):
        ds_name = dep.get("datasource")
        for col in dep.xpath("./*[local-name()='column'][@name]"):
            columns[(ds_name, col.get("name"))] = col

    return columns


def _find_column(
    columns: dict[tuple[str, str], ET._Element],
    datasource: str | None,
    token: str,
) -> ET._Element | None:
    if datasource is None:
        return None

    field = _field_name_from_token(token)
    candidates = [field, f"[{field}]"] if field.startswith(":") else [f"[{field}]", field]
    return next((columns.get((datasource, name)) for name in candidates if columns.get((datasource, name)) is not None), None)


def _format_record(format_el: ET._Element) -> dict[str, str]:
    record: dict[str, str] = {str(k).split("}")[-1]: str(v) for k, v in format_el.attrib.items() if str(k).split("}")[-1] != "field"}
    parent = format_el.getparent()
    if parent is not None and ET.QName(parent).localname == "style-rule" and parent.get("element"):
        record["element"] = parent.get("element") or ""

    worksheet = next((node for node in format_el.iterancestors() if ET.QName(node).localname == "worksheet"), None)
    if worksheet is not None:
        record["worksheet"] = worksheet.get("caption") or worksheet.get("name") or ""

    return record


def _build_format_index(
    tree: ET._ElementTree,
    columns: dict[tuple[str, str], ET._Element],
) -> dict[tuple[str, str], list[dict[str, str]]]:
    formats: dict[tuple[str, str], list[dict[str, str]]] = {}
    for fmt in tree.getroot().xpath("//*[local-name()='format'][@field]"):
        match = re.match(r"^\[([^\]]+)\]\.\[([^\]]+)\]$", fmt.get("field") or "")
        if not match:
            continue
        ds_name, token = match.groups()
        col = _find_column(columns, ds_name, token)
        if col is None or col.get("name") is None:
            continue
        formats.setdefault((ds_name, col.get("name")), []).append(_format_record(fmt))
    return formats


def _column_caption(col: ET._Element, fallback: str) -> str:
    return col.get("caption") or (col.get("name") or fallback).strip("[]")


def _column_display_name(col: ET._Element) -> str:
    return (col.get("caption") or (col.get("name") or "").strip("[]")).strip()


def _folder_elements(datasource_el: ET._Element) -> list[ET._Element]:
    folders: list[ET._Element] = []
    for container in datasource_el:
        if ET.QName(container).localname not in {"folders-common", "folders-parameters"}:
            continue
        folders.extend([child for child in container if ET.QName(child).localname == "folder"])
    return folders


def _datasource_label(tree: ET._ElementTree, datasource: str) -> str:
    hits = tree.getroot().xpath("/workbook/datasources/datasource[@name=$name]", name=datasource)
    if not hits:
        return datasource
    return hits[0].get("caption") or hits[0].get("name") or datasource


def _resolve_formula_ref(
    match: re.Match[str],
    *,
    tree: ET._ElementTree,
    current_ds: str | None,
    datasource_lookup: dict[str, str],
    datasource_labels: dict[str, str],
    columns: dict[tuple[str, str], ET._Element],
) -> tuple[str, str]:
    qualified_ds = match.group(1)
    qualified_token = match.group(2)
    local_token = match.group(3)

    if qualified_ds is not None and qualified_token is not None:
        ds_name = datasource_lookup.get(qualified_ds, qualified_ds)
        col = _find_column(columns, ds_name, qualified_token)
        if col is None:
            return match.group(0), match.group(0)
        ds_label = datasource_labels.get(ds_name, ds_name)
        caption = _column_caption(col, qualified_token)
        return f"[{ds_label}].[{caption}]", f"{ds_label}.{caption}"

    col = _find_column(columns, current_ds, local_token)
    if col is None:
        return match.group(0), match.group(0)
    caption = _column_caption(col, local_token)
    return f"[{caption}]", caption


def _formula_context(
    datasource_el: ET._Element,
) -> tuple[ET._ElementTree, str | None, dict[str, str], dict[str, str], dict[tuple[str, str], ET._Element]]:
    tree = datasource_el.getroottree()
    return tree, datasource_el.get("name"), _build_datasource_lookup(tree), _build_datasource_labels(tree), _build_column_index(tree)


def _formula_details(
    formula: str | None,
    context: tuple[ET._ElementTree, str | None, dict[str, str], dict[str, str], dict[tuple[str, str], ET._Element]],
) -> tuple[str | None, list[str]]:
    if formula is None:
        return None, []

    tree, current_ds, datasource_lookup, datasource_labels, columns = context
    refs: list[str] = []

    def replace(match: re.Match[str]) -> str:
        display, ref = _resolve_formula_ref(
            match,
            tree=tree,
            current_ds=current_ds,
            datasource_lookup=datasource_lookup,
            datasource_labels=datasource_labels,
            columns=columns,
        )
        if ref not in refs:
            refs.append(ref)
        return display

    return _FORMULA_REF_RE.sub(replace, formula), refs


def formula_details_for_datasource(formula: str | None, datasource_el: ET._Element) -> tuple[str | None, list[str]]:
    return _formula_details(formula, _formula_context(datasource_el))


def list_columns_from_datasource(datasource_el: ET._Element) -> list[TwbColumn]:
    columns: list[TwbColumn] = []
    context = _formula_context(datasource_el)
    tree, current_ds, _, _, column_index = context
    format_index = _build_format_index(tree, column_index)
    folder_index: dict[str, str] = {}
    for folder in _folder_elements(datasource_el):
        folder_name = folder.get("name")
        if not folder_name:
            continue
        for item in folder.findall("./folder-item"):
            item_name = item.get("name")
            if item_name:
                folder_index[item_name] = folder_name
    for col in datasource_el.findall("./column"):
        calc = col.find("./calculation")
        raw_formula = calc.get("formula") if calc is not None else None
        formula, referenced_columns = _formula_details(raw_formula, context)
        name = col.get("name") or ""
        columns.append(TwbColumn(
            name=name,
            id=name,
            caption=_column_caption(col, name),
            datatype=col.get("datatype"),
            role=col.get("role"),
            discrete=_discrete_from_type(col.get("type")),
            hidden=_bool_attr(col.get("hidden"), False),
            formula=formula,
            raw_formula=raw_formula,
            referenced_columns=referenced_columns,
            format=[dict(item) for item in format_index.get((current_ds or "", name), [])],
            folder=folder_index.get(name),
        ))
    return columns


def resolve_column_el(datasource_el: ET._Element, column: str, *, by: str = "auto") -> ET._Element:
    cols = list(datasource_el.findall("./column"))
    if by not in {"auto", "caption", "name"}:
        raise ValueError("by must be 'auto', 'caption', or 'name'.")

    matched = [c for c in cols if c.get("caption") == column] if by in {"auto", "caption"} else []
    if not matched and by in {"auto", "name"}:
        target_names = {column, column if column.startswith("[") else f"[{column}]"}
        matched = [c for c in cols if c.get("name") in target_names]
    if not matched:
        raise NotFoundError(f"column not found: {column}")
    if len(matched) > 1:
        raise AmbiguousCaptionError(f"column is ambiguous: {column}")
    return matched[0]


def rename_column_el(datasource_el: ET._Element, column: str, caption: str, *, by: str = "auto") -> ET._Element:
    caption = caption.strip() if caption is not None else ""
    if not caption:
        raise ValueError("caption must not be empty")

    col = resolve_column_el(datasource_el, column, by=by)
    for other in datasource_el.findall("./column"):
        if other is not col and _column_display_name(other) == caption:
            raise ValueError(f"caption already exists: {caption}")

    col.set("caption", caption)
    return col


def reset_column_caption_el(datasource_el: ET._Element, column: str, *, by: str = "auto") -> ET._Element:
    col = resolve_column_el(datasource_el, column, by=by)
    if "caption" in col.attrib:
        del col.attrib["caption"]
    return col


def update_column_el(
    column_el: ET._Element,
    *,
    caption: str | None = None,
    role: str | None = None,
    discrete: bool | None = None,
    hidden: bool | None = None,
) -> None:
    if caption is not None:
        column_el.set("caption", caption)
    if role is not None:
        column_el.set("role", role)
    if discrete is not None:
        column_el.set("type", "nominal" if discrete else "quantitative")
    if hidden is not None:
        column_el.set("hidden", "true" if hidden else "false")
