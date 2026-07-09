from __future__ import annotations

from lxml import etree as ET
from .models import TwbValidationMessage
from .datasource import datasource_elements
from .unsupported import unsupported_features_from_tree


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def _folder_elements(datasource_el: ET._Element) -> list[ET._Element]:
    folders: list[ET._Element] = []
    for container in datasource_el:
        if _local_name(container) not in {"folders-common", "folders-parameters"}:
            continue
        folders.extend([child for child in container if _local_name(child) == "folder"])
    return folders


def validate_tree(tree: ET._ElementTree) -> list[TwbValidationMessage]:
    messages: list[TwbValidationMessage] = []
    for ds in datasource_elements(tree):
        ds_id = ds.get("caption") or ds.get("name")
        names: set[str] = set()
        for col in ds.findall("./column"):
            name = col.get("name")
            caption = col.get("caption")
            if not name:
                messages.append(TwbValidationMessage("error", "column_name_empty", "column name is empty", ds_id))
                continue
            if name in names:
                messages.append(TwbValidationMessage("error", "column_name_duplicate", f"column name duplicated: {name}", ds_id, name))
            names.add(name)
            if caption is None:
                messages.append(TwbValidationMessage("warning", "caption_empty", f"caption is empty: {name}", ds_id, name))
            calc = col.find("./calculation")
            if calc is not None and not (calc.get("formula") or "").strip():
                messages.append(TwbValidationMessage("error", "formula_empty", f"formula is empty: {name}", ds_id, name))
        for folder in _folder_elements(ds):
            for item in folder.findall("./folder-item"):
                item_name = item.get("name")
                if item_name and item_name not in names:
                    messages.append(TwbValidationMessage("warning", "folder_item_missing", f"folder-item references missing column: {item_name}", ds_id, item_name))
        for folder in ds.findall("./folder"):
            messages.append(TwbValidationMessage("error", "folder_invalid_location", "folder must be under folders-common or folders-parameters", ds_id, folder.get("name")))
    for uf in unsupported_features_from_tree(tree):
        messages.append(TwbValidationMessage(uf.severity, f"unsupported_{uf.feature}", uf.message, uf.datasource))
    return messages
