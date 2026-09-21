from __future__ import annotations

import filecmp
import os
import shutil
import zipfile
from pathlib import Path
from lxml import etree as ET
from .errors import SaveError
from .xml import tree_to_text, write_text


def save_twb(
    tree: ET._ElementTree,
    path: str,
    *,
    overwrite: bool = False,
    attachments: list[tuple[str, Path]] | None = None,
) -> None:
    """`attachments` は .twb から相対パス（ファイル名）で参照する同梱ファイル。.twb の隣へ置く。"""
    if os.path.exists(path) and not overwrite:
        raise SaveError(f"保存先ファイルが既に存在します: {path}")
    # 書き込む前に置き場所を確かめる。途中で止まって .twb だけ書かれた状態にしない。
    copies: list[tuple[Path, str]] = []
    folder = os.path.dirname(os.path.abspath(path))
    for name, source in attachments or []:
        target = os.path.join(folder, name)
        if os.path.exists(target):
            if filecmp.cmp(target, source, shallow=False):
                continue
            if not overwrite:
                raise SaveError(f"同梱ファイルの保存先に別の内容のファイルがあります: {target}")
        copies.append((source, target))
    write_text(path, tree_to_text(tree))
    for source, target in copies:
        shutil.copyfile(source, target)


def save_twbx(
    tree: ET._ElementTree,
    path: str,
    *,
    extract_dir: str,
    twb_inner_path: str,
    overwrite: bool = False,
    attachments: list[tuple[str, Path]] | None = None,
) -> None:
    """`attachments` はパッケージの中の .twb と同じフォルダへ入れる。"""
    if os.path.exists(path) and not overwrite:
        raise SaveError(f"保存先ファイルが既に存在します: {path}")
    twb_abs = os.path.join(extract_dir, twb_inner_path)
    write_text(twb_abs, tree_to_text(tree))
    for name, source in attachments or []:
        shutil.copyfile(source, os.path.join(os.path.dirname(twb_abs), name))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(extract_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, extract_dir)
                zf.write(abs_path, rel_path)
