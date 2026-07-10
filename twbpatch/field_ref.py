from __future__ import annotations

import re

from lxml import etree as ET


FIELD_REF_RE = re.compile(r"\[[^\]]+\]\.\[[^\]]+\]")


def attrs(node: ET._Element) -> dict[str, str]:
    return {str(k).split("}")[-1]: str(v) for k, v in node.attrib.items()}


def attr_by_local_name(node: ET._Element, name: str) -> str | None:
    for key, value in node.attrib.items():
        if str(key).split("}")[-1] == name:
            return str(value)
    return None


def clean_filter_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def build_column_index(tree: ET._ElementTree) -> dict[tuple[str, str], ET._Element]:
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


def field_name_from_token(token: str) -> str:
    if token.startswith(":"):
        return token
    parts = token.split(":")
    return parts[1] if len(parts) >= 3 else token


def resolve_field(
    ref: str | None,
    columns: dict[tuple[str, str], ET._Element],
) -> tuple[str | None, str | None]:
    match = re.match(r"^\[([^\]]+)\]\.\[([^\]]+)\]$", ref or "")
    if not match:
        return ref, None

    ds_name, token = match.groups()
    field_name = field_name_from_token(token)
    candidate_names = (
        [field_name, f"[{field_name}]"]
        if field_name.startswith(":")
        else [f"[{field_name}]", field_name]
    )

    col = next(
        (columns.get((ds_name, name)) for name in candidate_names if columns.get((ds_name, name)) is not None),
        None,
    )
    if col is None:
        return field_name, None
    return col.get("caption") or field_name, col.get("role")
