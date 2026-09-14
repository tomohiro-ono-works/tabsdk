from __future__ import annotations

import re
from collections import defaultdict
from lxml import etree as ET
from ..errors import AmbiguousFormulaReferenceError, NotFoundError
from .naming import normalize_column_name
from .xpath import metadata_column_records, metadata_text

_FIELD_REF = re.compile(r"\[([^\]]+)\]")


def build_caption_name_map(datasource_el: ET._Element) -> dict[str, str]:
    mapping: dict[str, str] = {}
    duplicates: dict[str, list[str]] = defaultdict(list)

    def add(key: str, name: str) -> None:
        key = key.strip()
        if not key:
            return
        if key in mapping and mapping[key] != name:
            duplicates[key].append(name)
        mapping[key] = name

    # metadata-record: <column> 要素を持たない未使用フィールドの基礎マッピング。
    # 一度もシェルフ等で使われていないフィールドはリネームされておらず <column> も
    # 無いため、これが無いと実データとして存在していても式内で参照できない。
    columns_with_name = {
        col.get("name") for col in datasource_el.findall("./column") if col.get("name")
    }
    for record in metadata_column_records(datasource_el):
        field_id = metadata_text(record, "local-name")
        if not field_id or field_id in columns_with_name:
            continue
        display = (
            field_id[1:-1]
            if field_id.startswith("[") and field_id.endswith("]")
            else field_id
        )
        add(display, field_id)
        add(field_id.strip("[]"), field_id)
        add(field_id, field_id)

    # column 要素: caption・リネーム後の表示名を持つフィールド。metadata 由来の
    # 値より優先する（リネーム後の表示名を正とする）。
    for col in datasource_el.findall("./column"):
        caption = col.get("caption")
        name = col.get("name")
        if not name:
            continue
        if caption:
            add(caption, name)
        add(name.strip("[]"), name)
        add(name, name)

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
