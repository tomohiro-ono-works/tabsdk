from __future__ import annotations

from lxml import etree as ET


def parse_xml_text(xml_text: str) -> ET._ElementTree:
    parser = ET.XMLParser(remove_blank_text=True)
    root = ET.fromstring(xml_text.encode("utf-8"), parser=parser)
    return root.getroottree()


def tree_to_text(tree: ET._ElementTree) -> str:
    return ET.tostring(tree, pretty_print=True, encoding="utf-8", xml_declaration=True).decode("utf-8")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
