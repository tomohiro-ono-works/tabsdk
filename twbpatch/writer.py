from __future__ import annotations

import os
import zipfile
from lxml import etree as ET
from .errors import SaveError
from .xml import tree_to_text, write_text


def save_twb(tree: ET._ElementTree, path: str, *, overwrite: bool = False) -> None:
    if os.path.exists(path) and not overwrite:
        raise SaveError(f"保存先ファイルが既に存在します: {path}")
    write_text(path, tree_to_text(tree))


def save_twbx(
    tree: ET._ElementTree,
    path: str,
    *,
    extract_dir: str,
    twb_inner_path: str,
    overwrite: bool = False,
) -> None:
    if os.path.exists(path) and not overwrite:
        raise SaveError(f"保存先ファイルが既に存在します: {path}")
    twb_abs = os.path.join(extract_dir, twb_inner_path)
    write_text(twb_abs, tree_to_text(tree))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(extract_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, extract_dir)
                zf.write(abs_path, rel_path)
