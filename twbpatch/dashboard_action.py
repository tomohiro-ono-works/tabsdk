from __future__ import annotations

from lxml import etree as ET

from .field_ref import attrs
from .models import TwbDashboardAction


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def _element_record(node: ET._Element) -> dict[str, object]:
    record: dict[str, object] = {"tag": _local_name(node), "attrs": attrs(node)}
    text = (node.text or "").strip()
    if text:
        record["text"] = text
    children = [_element_record(child) for child in node]
    if children:
        record["children"] = children
    return record


def _first(node: ET._Element, xpath: str) -> ET._Element | None:
    matches = node.xpath(xpath)
    return matches[0] if matches else None


def _action_type(command: str | None, links: list[ET._Element]) -> str | None:
    """アクションの種別を決める。

    URL アクションには `<command>` が無く、`<link expression>` に URL が直接入る
    （Tableau が保存した .twb で実測 2026-09-07）。`command` だけを見ていると
    種別が `None` になっていた。
    """
    if not command:
        expressions = [link.get("expression") or "" for link in links]
        if expressions and not any(
            value.startswith("tsl:") for value in expressions
        ):
            return "url"
    return _normalized_action_type(command)


def _normalized_action_type(command: str | None) -> str | None:
    value = (command or "").lower()
    if "filter" in value:
        return "filter"
    if "highlight" in value:
        return "highlight"
    if "url" in value:
        return "url"
    if "sheet" in value or "navigate" in value:
        return "navigation"
    if "parameter" in value:
        return "parameter"
    if "set" in value:
        return "set"
    return command


def _identifier(value: str | None, candidates: dict[str, str]) -> str | None:
    if value is None:
        return None
    if value in candidates:
        return value
    unwrapped = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    return unwrapped if unwrapped in candidates else value


def _dashboard_indexes(
    tree: ET._ElementTree,
) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    worksheet_labels = {
        str(worksheet.get("name")): worksheet.get("caption") or worksheet.get("name") or ""
        for worksheet in tree.getroot().xpath("/workbook/worksheets/worksheet[@name]")
    }
    dashboard_labels: dict[str, str] = {}
    dashboard_worksheets: dict[str, list[str]] = {}
    for dashboard in tree.getroot().xpath("/workbook/dashboards/dashboard[@name]"):
        dashboard_id = str(dashboard.get("name"))
        dashboard_labels[dashboard_id] = dashboard.get("caption") or dashboard_id
        seen: set[str] = set()
        dashboard_worksheets[dashboard_id] = []
        for value in dashboard.xpath(".//@name"):
            worksheet_id = str(value)
            if worksheet_id in worksheet_labels and worksheet_id not in seen:
                dashboard_worksheets[dashboard_id].append(worksheet_id)
                seen.add(worksheet_id)
    return dashboard_labels, worksheet_labels, dashboard_worksheets


def _excluded_sheet_ids(owner: ET._Element | None) -> list[str]:
    if owner is None:
        return []
    values: list[str] = []
    for node in owner.xpath("./*[local-name()='exclude-sheet']"):
        value = node.get("name") or node.get("sheet") or node.get("worksheet")
        if value and value not in values:
            values.append(value)
    return values


def _explicit_sheet_ids(owner: ET._Element | None, worksheet_labels: dict[str, str]) -> list[str]:
    if owner is None:
        return []
    values: list[str] = []
    for attribute in ("worksheet", "sheet", "name"):
        value = owner.get(attribute)
        if value in worksheet_labels and value not in values:
            values.append(value)
    for node in owner.xpath("./*[local-name()='include-sheet']"):
        value = node.get("name") or node.get("sheet") or node.get("worksheet")
        if value in worksheet_labels and value not in values:
            values.append(value)
    return values


def _sheet_ids(
    owner: ET._Element | None,
    dashboard_id: str | None,
    worksheet_labels: dict[str, str],
    dashboard_worksheets: dict[str, list[str]],
    excluded: list[str],
) -> list[str]:
    explicit = _explicit_sheet_ids(owner, worksheet_labels)
    candidates = explicit or dashboard_worksheets.get(dashboard_id or "", [])
    return [worksheet_id for worksheet_id in candidates if worksheet_id not in excluded]


def _materialize_action(
    action: ET._Element,
    dashboard_labels: dict[str, str],
    worksheet_labels: dict[str, str],
    dashboard_worksheets: dict[str, list[str]],
) -> TwbDashboardAction:
    activation = _first(action, "./*[local-name()='activation']")
    source = _first(action, "./*[local-name()='source']")
    command_el = _first(action, "./*[local-name()='command']")
    target = _first(command_el, "./*[local-name()='target']") if command_el is not None else None
    command = command_el.get("command") if command_el is not None else None
    link_els = action.xpath(".//*[local-name()='link']")

    source_dashboard_id = _identifier(source.get("dashboard") if source is not None else None, dashboard_labels)
    excluded_source_ids = _excluded_sheet_ids(source)
    source_ids = _sheet_ids(source, source_dashboard_id, worksheet_labels, dashboard_worksheets, excluded_source_ids)

    links = [attrs(link) for link in link_els]
    params: dict[str, str] = {}
    for param in action.xpath(".//*[local-name()='param']"):
        name = param.get("name")
        if name:
            params[name] = param.get("value") or (param.text or "").strip()

    # ターゲットは `<target>` 要素ではなく `<command>` の param に入る。
    # 対象シートは「除外するシート名」のカンマ区切りで書かれる（実測 2026-09-07）。
    target_dashboard_id = _identifier(
        target.get("dashboard")
        if target is not None
        else params.get("target"),
        dashboard_labels,
    )
    excluded_target_ids = _excluded_sheet_ids(target)
    if not excluded_target_ids and params.get("exclude"):
        excluded_target_ids = [
            value.strip() for value in params["exclude"].split(",") if value.strip()
        ]
    target_ids = _sheet_ids(
        target, target_dashboard_id, worksheet_labels, dashboard_worksheets, excluded_target_ids
    )

    return TwbDashboardAction(
        dashboard=dashboard_labels.get(source_dashboard_id, source_dashboard_id),
        dashboard_id=source_dashboard_id,
        id=action.get("name") or action.get("id"),
        caption=action.get("caption") or action.get("name"),
        type=_action_type(command, link_els),
        activation=activation.get("type") if activation is not None else None,
        command=command,
        source_type=source.get("type") if source is not None else None,
        source_dashboard=dashboard_labels.get(source_dashboard_id, source_dashboard_id),
        source_dashboard_id=source_dashboard_id,
        source_worksheets=[worksheet_labels.get(value, value) for value in source_ids],
        source_worksheet_ids=source_ids,
        excluded_source_worksheets=[worksheet_labels.get(value, value) for value in excluded_source_ids],
        excluded_source_worksheet_ids=excluded_source_ids,
        target_type=target.get("type") if target is not None else None,
        target_dashboard=dashboard_labels.get(target_dashboard_id, target_dashboard_id),
        target_dashboard_id=target_dashboard_id,
        target_worksheets=[worksheet_labels.get(value, value) for value in target_ids],
        target_worksheet_ids=target_ids,
        excluded_target_worksheets=[worksheet_labels.get(value, value) for value in excluded_target_ids],
        excluded_target_worksheet_ids=excluded_target_ids,
        links=links,
        params=params,
        attrs=attrs(action),
        details=_element_record(action),
    )


def list_actions_from_tree(
    tree: ET._ElementTree,
    dashboard_el: ET._Element | None = None,
) -> list[TwbDashboardAction]:
    dashboard_labels, worksheet_labels, dashboard_worksheets = _dashboard_indexes(tree)
    actions = [
        _materialize_action(action, dashboard_labels, worksheet_labels, dashboard_worksheets)
        for action in tree.getroot().xpath("//*[local-name()='actions']/*[local-name()='action']")
    ]
    if dashboard_el is None:
        return actions

    dashboard_id = dashboard_el.get("name")
    sheet_ids = set(dashboard_worksheets.get(dashboard_id or "", []))
    return [
        action
        for action in actions
        if action.source_dashboard_id == dashboard_id
        or bool(sheet_ids.intersection(action.source_worksheet_ids))
    ]
