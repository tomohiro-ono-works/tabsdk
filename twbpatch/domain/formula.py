from __future__ import annotations

import re
from collections import defaultdict
from lxml import etree as ET
from ..errors import AmbiguousFormulaReferenceError, NotFoundError
from .naming import normalize_column_name

_FIELD_REF = re.compile(r"\[([^\]]+)\]")


def build_caption_name_map(datasource_el: ET._Element) -> dict[str, str]:
    mapping: dict[str, str] = {}
    duplicates: dict[str, list[str]] = defaultdict(list)
    for col in datasource_el.findall("./column"):
        caption = col.get("caption")
        name = col.get("name")
        if not name:
            continue
        if caption:
            key = caption.strip()
            if key in mapping and mapping[key] != name:
                duplicates[key].append(name)
            mapping[key] = name
        mapping[name.strip("[]")] = name
        mapping[name] = name
    if duplicates:
        keys = ", ".join(sorted(duplicates.keys()))
        raise AmbiguousFormulaReferenceError(f"ambiguous formula reference: {keys}")
    return mapping


def replace_formula_captions(
    formula: str,
    caption_to_name: dict[str, str],
    *,
    strict: bool = False,
    ref_map: dict[str, str] | None = None,
) -> str:
    explicit = {k: normalize_column_name(v) for k, v in (ref_map or {}).items()}

    def repl(match: re.Match[str]) -> str:
        ref = match.group(1)
        if ref in explicit:
            return explicit[ref]
        name = caption_to_name.get(ref) or caption_to_name.get(f"[{ref}]")
        if name:
            return normalize_column_name(name)
        if strict:
            raise NotFoundError(f"formula reference not found: {ref}")
        return match.group(0)

    return _FIELD_REF.sub(repl, formula)
