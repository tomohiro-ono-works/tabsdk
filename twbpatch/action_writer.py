"""ダッシュボードアクションの XML を組み立てる。

構造は Tableau が保存した `.twb` から実測した（2026-09-07）。

- `<action>` は **`/workbook/actions` 直下**に置かれる。ダッシュボード配下ではない
- `<actions>` の中には、アクションが参照するデータソースと列の宣言も置かれる
- 名前は `[Action<連番>_<32 桁の 16 進大文字>]`
- **対象シートは「除外するシート」で書かれる。** フィルタは
  `<command><param name="exclude" value="シート名,...">`、URL は `<exclude-sheet>` の並び

実測できたのは実行方法 `on-select` と、選択解除時の `auto-clear="true"` だけ。
`on-hover` / `on-menu` は Tableau で一般に使われる値だが**未実測**。
"""

from __future__ import annotations

import uuid
from urllib.parse import quote

from lxml import etree as ET

from .errors import NotFoundError, UnsupportedFeatureError

ACTION_KINDS = ("filter", "url")

# 実行方法。`on-select` だけが実測済み。
ACTIVATIONS = ("on-select", "on-hover", "on-menu")

# 選択を解除したときの動作。フィルタアクションだけが持つ。
CLEAR_SELECTIONS = {"show_all": "true", "exclude": "false"}

_FILTER_COMMAND = "tsc:tsl-filter"


def _next_action_index(actions_el: ET._Element) -> int:
    """`[Action3_...]` の連番部分を採る。"""
    highest = 0
    for action in actions_el.xpath("./*[local-name()='action']"):
        name = (action.get("name") or "").strip("[]")
        head = name.split("_", 1)[0]
        if head.startswith("Action") and head[6:].isdigit():
            highest = max(highest, int(head[6:]))
    return highest + 1


def generate_action_name(actions_el: ET._Element) -> str:
    index = _next_action_index(actions_el)
    return f"[Action{index}_{uuid.uuid4().hex.upper()}]"


def ensure_actions_element(root: ET._Element) -> ET._Element:
    """`/workbook/actions` を返す。無ければ `<worksheets>` の直前に作る。"""
    existing = root.xpath("./*[local-name()='actions']")
    if existing:
        return existing[0]
    element = ET.Element("actions")
    insert_at = next(
        (
            index
            for index, child in enumerate(root)
            if ET.QName(child).localname in {"worksheets", "dashboards", "windows"}
        ),
        len(root),
    )
    root.insert(insert_at, element)
    return element


def declare_field(actions_el: ET._Element, datasource_el: ET._Element, column_el: ET._Element) -> None:
    """アクションが使うデータソースと列を `<actions>` 直下へ宣言する。

    Tableau が自動生成する部分。`<datasources>` と `<datasource-dependencies>` の
    2 つで、どちらも既にあれば足さない。
    """
    datasource_id = datasource_el.get("name") or ""
    declared = actions_el.xpath("./*[local-name()='datasources']")
    if declared:
        holder = declared[0]
    else:
        holder = ET.SubElement(actions_el, "datasources")
    if not holder.xpath("./*[local-name()='datasource'][@name=$id]", id=datasource_id):
        ET.SubElement(
            holder,
            "datasource",
            attrib={
                key: value
                for key, value in (
                    ("caption", datasource_el.get("caption")),
                    ("name", datasource_id),
                )
                if value
            },
        )

    dependencies = actions_el.xpath(
        "./*[local-name()='datasource-dependencies'][@datasource=$id]",
        id=datasource_id,
    )
    if dependencies:
        dependency = dependencies[0]
    else:
        dependency = ET.SubElement(
            actions_el, "datasource-dependencies", attrib={"datasource": datasource_id}
        )
    column_id = column_el.get("name") or ""
    if not dependency.xpath("./*[local-name()='column'][@name=$id]", id=column_id):
        copied = ET.SubElement(dependency, "column")
        for key in ("caption", "datatype", "name", "role", "type"):
            value = column_el.get(key)
            if value:
                copied.set(key, value)


def _filter_expression(dashboard_name: str, field_reference: str) -> str:
    """フィルタアクションの `<link expression>`。

    形は `tsl:<ダッシュボード名>?<フィールド>~s0=<<フィールド>~na>` で、
    ダッシュボード名とフィールド参照を URL エンコードしたもの。
    ソースとターゲットで同じフィールドを使う前提（画面もその形しか出さない）。
    """
    encoded_dashboard = quote(dashboard_name, safe="")
    encoded_field = quote(field_reference, safe="")
    return (
        f"tsl:{encoded_dashboard}?{encoded_field}~s0="
        f"<{field_reference}~na>"
    )


def build_filter_action(
    *,
    name: str,
    caption: str,
    dashboard_name: str,
    source_worksheet: str,
    excluded_targets: list[str],
    field_reference: str,
    activation: str,
    clear_selection: str,
) -> ET._Element:
    action = ET.Element("action", attrib={"caption": caption, "name": name})
    ET.SubElement(
        action,
        "activation",
        attrib={
            "auto-clear": CLEAR_SELECTIONS[clear_selection],
            "type": activation,
        },
    )
    ET.SubElement(
        action,
        "source",
        attrib={
            "dashboard": dashboard_name,
            "type": "sheet",
            "worksheet": source_worksheet,
        },
    )
    ET.SubElement(
        action,
        "link",
        attrib={
            "caption": caption,
            "delimiter": ",",
            "escape": "\\",
            "expression": _filter_expression(dashboard_name, field_reference),
            "include-null": "true",
            "multi-select": "true",
            "url-escape": "true",
        },
    )
    command = ET.SubElement(action, "command", attrib={"command": _FILTER_COMMAND})
    ET.SubElement(
        command,
        "param",
        attrib={"name": "exclude", "value": ",".join(excluded_targets)},
    )
    ET.SubElement(command, "param", attrib={"name": "target", "value": dashboard_name})
    return action


def build_url_action(
    *,
    name: str,
    caption: str,
    dashboard_name: str,
    url: str,
    excluded_sources: list[str],
    activation: str,
) -> ET._Element:
    action = ET.Element("action", attrib={"caption": caption, "name": name})
    ET.SubElement(action, "activation", attrib={"type": activation})
    source = ET.SubElement(
        action, "source", attrib={"dashboard": dashboard_name, "type": "sheet"}
    )
    for worksheet in excluded_sources:
        ET.SubElement(source, "exclude-sheet", attrib={"name": worksheet})
    ET.SubElement(action, "link", attrib={"caption": "", "expression": url})
    return action


def resolve_action_element(root: ET._Element, action_id: str) -> ET._Element:
    hits = root.xpath(
        "./*[local-name()='actions']/*[local-name()='action'][@name=$id]",
        id=action_id,
    )
    if not hits:
        newer = root.xpath(
            "./*[local-name()='actions']/*[local-name()='edit-parameter-action' or "
            "local-name()='edit-group-action' or local-name()='nav-action'][@name=$id]",
            id=action_id,
        )
        if newer:
            raise UnsupportedFeatureError("update/delete is not supported for this action type")
        raise NotFoundError(f"dashboard action not found: {action_id}")
    return hits[0]
