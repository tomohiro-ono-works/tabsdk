from __future__ import annotations

from lxml import etree as ET
from .models import TwbFolder
from .column import resolve_column_el


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def _folder_containers(datasource_el: ET._Element) -> list[ET._Element]:
    return [
        child
        for child in datasource_el
        if _local_name(child) in {"folders-common", "folders-parameters"}
    ]


def _folder_elements(datasource_el: ET._Element) -> list[ET._Element]:
    folders: list[ET._Element] = []
    for container in _folder_containers(datasource_el):
        folders.extend([child for child in container if _local_name(child) == "folder"])
    return folders


def _ensure_folders_common(datasource_el: ET._Element) -> ET._Element:
    for child in datasource_el:
        if _local_name(child) == "folders-common":
            return child

    container = ET.Element("folders-common")
    preceding = {
        "repository-location",
        "connection",
        "utility-dimensions",
        "dimension",
        "overridable-settings",
        "aliases",
        "column",
        "column-instance",
        "group",
        "mapped-images",
        "drill-paths",
        "unlinked-server-hierarchies",
    }
    insert_at = 0
    for index, child in enumerate(datasource_el):
        if _local_name(child) in preceding:
            insert_at = index + 1
    datasource_el.insert(insert_at, container)
    return container


def _normalize_folder_el(folder_el: ET._Element) -> None:
    folder_el.attrib.pop("role", None)
    for item in folder_el.findall("./folder-item"):
        if item.get("type") is None:
            item.set("type", "field")


def _migrate_direct_folders(datasource_el: ET._Element) -> None:
    direct_folders = [child for child in datasource_el if _local_name(child) == "folder"]
    if not direct_folders:
        return
    container = _ensure_folders_common(datasource_el)
    for folder_el in direct_folders:
        _normalize_folder_el(folder_el)
        datasource_el.remove(folder_el)
        container.append(folder_el)


def list_folders_from_datasource(datasource_el: ET._Element) -> list[TwbFolder]:
    _migrate_direct_folders(datasource_el)
    folders: list[TwbFolder] = []
    for folder in _folder_elements(datasource_el):
        _normalize_folder_el(folder)
        name = folder.get("name")
        if not name:
            continue
        items = [item.get("name") for item in folder.findall("./folder-item") if item.get("name")]
        folders.append(TwbFolder(name=name, id=name, role=None, items=items))
    return folders


def _find_folder(datasource_el: ET._Element, folder: str, role: str | None = None) -> ET._Element | None:
    for el in _folder_elements(datasource_el):
        if el.get("name") == folder:
            return el
    return None


def move_column_to_folder_el(
    datasource_el: ET._Element,
    column: str,
    folder: str,
    *,
    by: str = "auto",
    role: str | None = None,
    create_if_missing: bool = True,
) -> None:
    _migrate_direct_folders(datasource_el)
    col = resolve_column_el(datasource_el, column, by=by)
    col_name = col.get("name")
    if not col_name:
        raise ValueError("column name is empty")
    folder_el = _find_folder(datasource_el, folder, role)
    if folder_el is None:
        if not create_if_missing:
            raise ValueError(f"folder not found: {folder}")
        folder_el = ET.Element("folder", attrib={"name": folder})
        _ensure_folders_common(datasource_el).append(folder_el)
    _normalize_folder_el(folder_el)
    for existing_folder in _folder_elements(datasource_el):
        for item in list(existing_folder.findall("./folder-item")):
            if item.get("name") == col_name and existing_folder is not folder_el:
                existing_folder.remove(item)
    for item in folder_el.findall("./folder-item"):
        if item.get("name") == col_name:
            return
    ET.SubElement(folder_el, "folder-item", attrib={"name": col_name, "type": "field"})


def remove_column_from_folder_el(
    datasource_el: ET._Element,
    column: str,
    *,
    by: str = "auto",
) -> None:
    _migrate_direct_folders(datasource_el)
    col = resolve_column_el(datasource_el, column, by=by)
    col_name = col.get("name")
    if not col_name:
        raise ValueError("column name is empty")
    for folder_el in _folder_elements(datasource_el):
        for item in list(folder_el.findall("./folder-item")):
            if item.get("name") == col_name:
                folder_el.remove(item)
