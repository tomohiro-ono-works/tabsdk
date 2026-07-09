from __future__ import annotations

from lxml import etree as ET
from .naming import normalize_column_name


def tableau_type_from_discrete(discrete: bool | None) -> str:
    if discrete is True:
        return "nominal"
    if discrete is False:
        return "quantitative"
    return "nominal"


def make_calculated_element(
    tag_local: str,
    caption: str,
    formula: str,
    name: str,
    *,
    datatype: str = "real",
    role: str = "measure",
    discrete: bool | None = False,
    hidden: bool = False,
) -> ET._Element:
    attrib = {
        "caption": caption,
        "datatype": datatype,
        "hidden": "true" if hidden else "false",
        "name": normalize_column_name(name),
        "role": role,
        "type": tableau_type_from_discrete(discrete),
    }
    el = ET.Element(tag_local, attrib=attrib)
    calc = ET.SubElement(el, "calculation")
    calc.set("class", "tableau")
    calc.set("formula", formula)
    return el
