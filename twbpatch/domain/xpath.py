from __future__ import annotations

from typing import Optional, Tuple, Union
from lxml import etree as ET
import re

ElementLike = Union[ET._ElementTree, ET._Element]


def get_tree(root: ElementLike) -> ET._ElementTree:
    return root.getroottree() if isinstance(root, ET._Element) else root


def split_parent_and_last_step(xpath: str) -> Tuple[str, str]:
    x = xpath.rstrip("/")
    i = x.rfind("/")
    return ("/", x or "") if i < 0 else (x[:i] or "/", x[i + 1 :])


def extract_local_from_step(step_expr: str) -> str:
    base = re.sub(r"\[.*\]$", "", step_expr)
    return base.split(":")[-1] if base else base


def xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ', "\'", '.join(f"'{p}'" for p in parts) + ")"


def build_ds_columns_xpath(datasource: str, *, attr: str = "caption") -> str:
    return f"/workbook/datasources/datasource[@{attr}={xpath_literal(datasource)}]/column"


def resolve_parent_generic(root: ElementLike, xpath: str, namespaces=None) -> Optional[ET._Element]:
    tree = get_tree(root)
    last_hit = tree.getroot().xpath(f"({xpath})[last()]", namespaces=namespaces)
    if last_hit and isinstance(last_hit[0], ET._Element):
        return last_hit[0].getparent()
    parent_xpath, _ = split_parent_and_last_step(xpath)
    last_parent = tree.getroot().xpath(f"({parent_xpath})[last()]", namespaces=namespaces)
    return last_parent[0] if last_parent and isinstance(last_parent[0], ET._Element) else None


def resolve_parent(root: ElementLike, parent_xpath: str, namespaces=None) -> Optional[ET._Element]:
    tree = get_tree(root)
    hits = tree.getroot().xpath(f"({parent_xpath})[last()]", namespaces=namespaces)
    return hits[0] if hits and isinstance(hits[0], ET._Element) else None


def find_last_sibling_of_type(parent: ET._Element, tag_local: str) -> Optional[ET._Element]:
    hits = parent.xpath("./*[local-name()=$n]", n=tag_local)
    return hits[-1] if hits else None


def find_by_attr(parent: ET._Element, tag_local: str, attr: str, value: str) -> Optional[ET._Element]:
    hits = parent.xpath(f"./*[local-name()=$n and @{attr}=$v]", n=tag_local, v=value)
    return hits[0] if hits else None


def children_by_local(parent: ET._Element, tag_local: str) -> list[ET._Element]:
    return list(parent.xpath("./*[local-name()=$n]", n=tag_local))


_METADATA_COLUMN_RECORDS_XPATH = (
    "./*[local-name()='connection']/*[local-name()='metadata-records']"
    "/*[local-name()='metadata-record' and @class='column']"
    " | ./*[local-name()='extract']/*[local-name()='connection']"
    "/*[local-name()='metadata-records']"
    "/*[local-name()='metadata-record' and @class='column']"
)


def metadata_column_records(datasource_el: ET._Element) -> list[ET._Element]:
    """データソース内の `metadata-record`（class='column'）を通常接続・抽出の両方から集める。

    一度もシェルフ等で使われていないフィールドは `<column>` 要素を持たないが、
    この metadata-record には必ず載る。
    """
    return list(datasource_el.xpath(_METADATA_COLUMN_RECORDS_XPATH))


def metadata_text(record: ET._Element, child_name: str) -> Optional[str]:
    for child in record:
        if ET.QName(child).localname == child_name:
            return child.text
    return None
