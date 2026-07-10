from __future__ import annotations

from lxml import etree as ET


def bool_attr(value: str | None, default: bool | None = False) -> bool | None:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes"}


def window_attrs_by_name(tree: ET._ElementTree, class_name: str) -> dict[str, dict[str, str]]:
    attrs: dict[str, dict[str, str]] = {}
    for window in tree.getroot().xpath(f"/workbook/windows/window[@class='{class_name}'][@name]"):
        name = window.get("name")
        if name:
            attrs[str(name)] = {str(k): str(v) for k, v in window.attrib.items()}
    return attrs
