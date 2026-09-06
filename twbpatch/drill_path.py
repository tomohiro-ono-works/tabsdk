"""階層（ドリルパス）の XML を組み立てる。

構造は Tableau が保存した `.twb` から実測した（2026-09-07、
`workbook/hierarchy_group_sample.twb`）。

```xml
<drill-paths>
  <drill-path name="カテゴリ">
    <field>[Category]</field>
    <field>[Sub-Category]</field>
  </drill-path>
</drill-paths>
```

- `<drill-paths>` は `datasource` 直下。`column-instance` の後、`folders-common` の前
- `<drill-path>` の属性は `name` のみ。**表示名そのまま**で角括弧は付かない
- `<field>` は属性なし。テキストに**内部 ID を角括弧付き**で、ドリルの階層順に並べる
- フォルダへは `<folder-item name="階層名" type="drillpath">` で入る。
  **階層に入ったフィールドは個別の folder-item を持たなくなる**
"""

from __future__ import annotations

from lxml import etree as ET

#: `<drill-paths>` より前に来る要素。挿入位置の計算に使う。
_PRECEDING = (
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
)


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def drill_paths_element(datasource_el: ET._Element) -> ET._Element | None:
    return next(
        (child for child in datasource_el if _local_name(child) == "drill-paths"),
        None,
    )


def ensure_drill_paths_element(datasource_el: ET._Element) -> ET._Element:
    existing = drill_paths_element(datasource_el)
    if existing is not None:
        return existing
    container = ET.Element("drill-paths")
    insert_at = 0
    for index, child in enumerate(datasource_el):
        if _local_name(child) in _PRECEDING:
            insert_at = index + 1
    datasource_el.insert(insert_at, container)
    return container


def list_drill_path_elements(datasource_el: ET._Element) -> list[ET._Element]:
    container = drill_paths_element(datasource_el)
    if container is None:
        return []
    return [child for child in container if _local_name(child) == "drill-path"]


def find_drill_path_element(datasource_el: ET._Element, name: str) -> ET._Element | None:
    return next(
        (
            element
            for element in list_drill_path_elements(datasource_el)
            if element.get("name") == name
        ),
        None,
    )


def drill_path_field_ids(drill_path_el: ET._Element) -> list[str]:
    return [
        text
        for child in drill_path_el
        if _local_name(child) == "field" and (text := (child.text or "").strip())
    ]


def build_drill_path_element(name: str, field_ids: list[str]) -> ET._Element:
    element = ET.Element("drill-path", attrib={"name": name})
    for field_id in field_ids:
        ET.SubElement(element, "field").text = field_id
    return element


def set_drill_path_fields(drill_path_el: ET._Element, field_ids: list[str]) -> None:
    for child in list(drill_path_el):
        if _local_name(child) == "field":
            drill_path_el.remove(child)
    for field_id in field_ids:
        ET.SubElement(drill_path_el, "field").text = field_id


def remove_folder_items(datasource_el: ET._Element, names: list[str]) -> None:
    """指定した名前の `folder-item` を全フォルダから取り除く。

    階層へ入れたフィールドは個別の folder-item を持たなくなる（実測）。
    空になったフォルダは残す。Tableau も残すため。
    """
    wanted = set(names)
    for item in datasource_el.xpath(
        ".//*[local-name()='folder-item'][@name]"
    ):
        if item.get("name") in wanted:
            parent = item.getparent()
            if parent is not None:
                parent.remove(item)
