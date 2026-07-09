from __future__ import annotations

import hashlib
import time
from lxml import etree as ET
from .xpath import find_by_attr


def normalize_column_name(name: str) -> str:
    name = name.strip()
    if name.startswith("[") and name.endswith("]"):
        return name
    return f"[{name}]"


def gen_base_name(caption: str, formula: str) -> str:
    h = hashlib.sha1(f"{caption}|{formula}".encode("utf-8")).hexdigest()[:16]
    return f"[Calculation_{int(h, 16)}]"


def gen_unique_name(parent: ET._Element, tag_local: str, caption: str, formula: str) -> str:
    name = gen_base_name(caption, formula)
    if find_by_attr(parent, tag_local, "name", name) is None:
        return name
    attempt = 1
    while True:
        salt = f"{attempt}|{time.time_ns()}"
        h = hashlib.sha1(f"{caption}|{formula}|{salt}".encode("utf-8")).hexdigest()[:16]
        name = f"[Calculation_{int(h, 16)}]"
        if find_by_attr(parent, tag_local, "name", name) is None:
            return name
        attempt += 1
