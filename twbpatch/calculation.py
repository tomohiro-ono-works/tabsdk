from __future__ import annotations

from lxml import etree as ET
from .models import TwbColumn
from .errors import NotFoundError
from .domain.entities import make_calculated_element
from .domain.formula import build_caption_name_map, replace_formula_captions
from .domain.naming import gen_unique_name, normalize_column_name
from .domain.xpath import find_by_attr, find_last_sibling_of_type
from .column import formula_details_for_datasource, resolve_column_el


def normalize_formula_for_datasource(
    datasource_el: ET._Element,
    formula: str,
    *,
    formula_ref: str = "auto",
    strict: bool = False,
    ref_map: dict[str, str] | None = None,
) -> str:
    if formula_ref == "name":
        return formula
    if formula_ref not in {"auto", "caption"}:
        raise ValueError("formula_ref must be 'auto', 'caption', or 'name'.")
    mapping = build_caption_name_map(datasource_el)
    return replace_formula_captions(formula, mapping, strict=strict, ref_map=ref_map)


def normalize_number_format(number_format: str | None) -> str | None:
    if number_format is None:
        return None
    if number_format == "%":
        return "p0%"
    raise ValueError("number_format must be '%' or None")


def create_calculated_field_el(
    datasource_el: ET._Element,
    *,
    name: str | None,
    caption: str,
    formula: str,
    datatype: str = "real",
    role: str = "measure",
    discrete: bool | None = False,
    hidden: bool | None = False,
    number_format: str | None = None,
    formula_ref: str = "auto",
    strict: bool = False,
    ref_map: dict[str, str] | None = None,
) -> TwbColumn:
    tag_local = "column"
    formula_norm = normalize_formula_for_datasource(
        datasource_el, formula, formula_ref=formula_ref, strict=strict, ref_map=ref_map
    )
    used_name = normalize_column_name(name) if name else gen_unique_name(datasource_el, tag_local, caption, formula_norm)
    if find_by_attr(datasource_el, tag_local, "name", used_name) is not None:
        raise ValueError(f"calculated field name already exists: {used_name}")
    if caption and find_by_attr(datasource_el, tag_local, "caption", caption) is not None:
        raise ValueError(f"caption already exists: {caption}")

    element = make_calculated_element(
        tag_local,
        caption,
        formula_norm,
        used_name,
        datatype=datatype,
        role=role,
        discrete=discrete,
        hidden=hidden,
    )
    normalized_format = normalize_number_format(number_format)
    if normalized_format is not None:
        element.set("default-format", normalized_format)
    anchor = find_last_sibling_of_type(datasource_el, tag_local)
    if anchor is not None:
        anchor.addnext(element)
    else:
        datasource_el.insert(0, element)

    display_formula, referenced_columns = formula_details_for_datasource(formula_norm, datasource_el)
    return TwbColumn(
        name=used_name,
        id=used_name,
        caption=caption,
        datatype=datatype,
        role=role,
        discrete=discrete,
        hidden=bool(hidden),
        formula=display_formula,
        raw_formula=formula_norm,
        referenced_columns=referenced_columns,
    )


def update_formula_el(
    datasource_el: ET._Element,
    column: str,
    formula: str,
    *,
    by: str = "auto",
    formula_ref: str = "auto",
    strict: bool = False,
    ref_map: dict[str, str] | None = None,
) -> None:
    col = resolve_column_el(datasource_el, column, by=by)
    formula_norm = normalize_formula_for_datasource(
        datasource_el, formula, formula_ref=formula_ref, strict=strict, ref_map=ref_map
    )
    calc = col.find("./calculation")
    if calc is None:
        calc = ET.SubElement(col, "calculation")
        calc.set("class", "tableau")
    calc.set("formula", formula_norm)
