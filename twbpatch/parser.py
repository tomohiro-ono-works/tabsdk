from __future__ import annotations

import os
import tempfile
import zipfile
from dataclasses import dataclass
from lxml import etree as ET
from .xml import parse_xml_text
from .errors import NotFoundError


@dataclass
class ParsedWorkbook:
    tree: ET._ElementTree
    source_path: str
    is_twbx: bool
    twb_inner_path: str | None = None
    extract_dir: str | None = None


def open_template_workbook_file(path: str) -> ParsedWorkbook:
    """Read only the workbook member, without extracting template packages."""
    from pathlib import PurePosixPath

    if path.lower().endswith('.twb'):
        with open(path, encoding='utf-8') as source:
            return ParsedWorkbook(_parse_template_xml(source.read()), path, False)
    if not path.lower().endswith('.twbx'):
        raise ValueError('template must be TWB or TWBX')
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        workbooks = [name for name in names if name.lower().endswith('.twb')]
        if len(workbooks) != 1:
            raise ValueError('template TWBX must contain exactly one TWB')
        member = workbooks[0]
        if PurePosixPath(member).is_absolute() or '\\' in member or ':' in member or '..' in member.split('/'):
            raise ValueError('invalid template workbook member path')
        return ParsedWorkbook(_parse_template_xml(package.read(member).decode('utf-8')), path, True, member)


def _parse_template_xml(text: str) -> ET._ElementTree:
    parser = ET.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
    root = ET.fromstring(text.encode('utf-8'), parser=parser)
    if root.tag != 'workbook' or root.getroottree().docinfo.doctype:
        raise ValueError('template must contain a workbook without a DTD')
    return root.getroottree()


def open_workbook_file(path: str) -> ParsedWorkbook:
    lower = path.lower()
    if lower.endswith(".twb"):
        with open(path, "r", encoding="utf-8") as f:
            return ParsedWorkbook(parse_xml_text(f.read()), path, False)
    if lower.endswith(".twbx"):
        extract_dir = tempfile.mkdtemp(prefix="twbpatch_")
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(extract_dir)
        twb_files: list[str] = []
        for root, _, files in os.walk(extract_dir):
            for file in files:
                if file.lower().endswith(".twb"):
                    twb_files.append(os.path.join(root, file))
        if not twb_files:
            raise NotFoundError(".twbx 内に .twb が見つかりません。")
        twb_path = twb_files[0]
        with open(twb_path, "r", encoding="utf-8") as f:
            tree = parse_xml_text(f.read())
        inner = os.path.relpath(twb_path, extract_dir)
        return ParsedWorkbook(tree, path, True, inner, extract_dir)
    raise ValueError("対応している拡張子は .twb / .twbx です。")
