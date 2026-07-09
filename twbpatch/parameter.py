from __future__ import annotations

from lxml import etree as ET

from .models import TwbParameter


def _bool_attr(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() == "true"


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _parameters_datasource(tree: ET._ElementTree) -> ET._Element | None:
    hits = tree.getroot().xpath('/workbook/datasources/datasource[@name="Parameters"]')
    return hits[0] if hits else None


def _aliases(column_el: ET._Element) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for alias in column_el.xpath('./*[local-name()="aliases"]/*[local-name()="alias"]'):
        result.append({
            "value": _clean_value(alias.get("key")),
            "alias": alias.get("value"),
        })
    return result


def _allowable_values(column_el: ET._Element) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for member in column_el.xpath('./*[local-name()="members"]/*[local-name()="member"]'):
        result.append({
            "value": _clean_value(member.get("value")),
            "alias": member.get("alias"),
        })
    return result


def list_parameters_from_tree(tree: ET._ElementTree, *, include_hidden: bool = False) -> list[TwbParameter]:
    datasource_el = _parameters_datasource(tree)
    if datasource_el is None:
        return []

    parameters: list[TwbParameter] = []
    for col in datasource_el.findall("./column"):
        hidden = _bool_attr(col.get("hidden"), False)
        if hidden and not include_hidden:
            continue

        aliases = _aliases(col)
        allowable_values = _allowable_values(col)
        alias_by_value = {item["value"]: item["alias"] for item in [*aliases, *allowable_values]}
        value = _clean_value(col.get("value"))
        value_display = col.get("alias") or alias_by_value.get(value) or value
        name = col.get("name") or ""

        parameters.append(TwbParameter(
            name=name,
            id=name,
            caption=col.get("caption") or name,
            datatype=col.get("datatype"),
            value=value,
            value_display=value_display,
            domain_type=col.get("param-domain-type"),
            allowable_values=allowable_values,
            aliases=aliases,
            default_value_field=col.get("default-value-field"),
            hidden=hidden,
        ))

    return parameters
