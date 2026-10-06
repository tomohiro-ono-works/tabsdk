from __future__ import annotations

import os
import zipfile
from pathlib import Path, PurePosixPath
from lxml import etree as ET
from .errors import SaveError
from .xml import tree_to_text, write_text


def validate_attachment_name(name: str) -> None:
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError(f"invalid attachment path: {name}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {'.', '..'} for part in name.split('/')):
        raise ValueError(f"invalid attachment path: {name}")


def _prepare_attachments(folder: str, attachments, overwrite: bool):
    root = Path(folder).resolve()
    copies = []
    seen = {}
    for name, source in attachments or []:
        validate_attachment_name(name)
        target = (root / name).resolve()
        if not target.is_relative_to(root):
            raise SaveError(f"同梱ファイルが保存領域の外を参照しています: {name}")
        parent = target.parent
        while parent.is_relative_to(root):
            if parent.exists() and not parent.is_dir():
                raise SaveError(f"同梱ファイルの保存先フォルダがファイルです: {parent}")
            if parent == root:
                break
            parent = parent.parent
        data = source if isinstance(source, bytes) else Path(source).read_bytes()
        if target in seen and seen[target] != data:
            raise SaveError(f"同梱ファイル名が重複しています: {name}")
        seen[target] = data
        if target.exists():
            if not target.is_file():
                raise SaveError(f"同梱ファイルの保存先がファイルではありません: {target}")
            if target.read_bytes() == data:
                continue
            if not overwrite:
                raise SaveError(f"同梱ファイルの保存先に別の内容のファイルがあります: {target}")
        copies.append((target, data))
    return copies


def _write_attachments(copies):
    for target, data in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def save_twb(
    tree: ET._ElementTree,
    path: str,
    *,
    overwrite: bool = False,
    attachments: list[tuple[str, Path | bytes]] | None = None,
) -> None:
    """`attachments` は .twb から相対パス（ファイル名）で参照する同梱ファイル。.twb の隣へ置く。"""
    if os.path.exists(path) and not overwrite:
        raise SaveError(f"保存先ファイルが既に存在します: {path}")
    # 書き込む前に置き場所を確かめる。途中で止まって .twb だけ書かれた状態にしない。
    folder = os.path.dirname(os.path.abspath(path))
    copies = _prepare_attachments(folder, attachments, overwrite)
    write_text(path, tree_to_text(tree))
    _write_attachments(copies)


def save_twbx(
    tree: ET._ElementTree,
    path: str,
    *,
    extract_dir: str,
    twb_inner_path: str,
    overwrite: bool = False,
    attachments: list[tuple[str, Path | bytes]] | None = None,
) -> None:
    """`attachments` はパッケージの中の .twb と同じフォルダへ入れる。"""
    if os.path.exists(path) and not overwrite:
        raise SaveError(f"保存先ファイルが既に存在します: {path}")
    twb_abs = os.path.join(extract_dir, twb_inner_path)
    copies = _prepare_attachments(os.path.dirname(twb_abs), attachments, overwrite)
    write_text(twb_abs, tree_to_text(tree))
    _write_attachments(copies)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(extract_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, extract_dir)
                zf.write(abs_path, rel_path)
