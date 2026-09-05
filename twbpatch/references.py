from __future__ import annotations

import re

from lxml import etree as ET

from .errors import ResourceReference
from .field_ref import field_name_from_token


_REFERENCE_RE = re.compile(r"\[([^\]]+)\]\.\[([^\]]+)\]|\[([^\]]+)\]")


def _local_name(element: ET._Element) -> str:
    return ET.QName(element).localname


def _field_token_matches(token: str, field_id: str) -> bool:
    field_token = field_name_from_token(token)
    target = field_id[1:-1] if field_id.startswith("[") and field_id.endswith("]") else field_id
    return field_token == target or field_token == field_id


def _owner(element: ET._Element) -> tuple[str, str]:
    nodes = [element, *element.iterancestors()]
    for local_name, resource_type in (
        ("action", "DashboardAction"),
        ("worksheet", "Worksheet"),
        ("dashboard", "Dashboard"),
    ):
        node = next((item for item in nodes if _local_name(item) == local_name), None)
        if node is not None:
            return resource_type, node.get("name") or ""
    for node in nodes:
        local_name = _local_name(node)
        if local_name == "folder":
            return "Folder", node.get("name") or ""
        if local_name == "column":
            return "Field", node.get("name") or ""
    return _local_name(element), element.get("id") or element.get("name") or ""


def _append_reference(
    result: list[ResourceReference],
    seen: set[tuple[str, str, str]],
    tree: ET._ElementTree,
    element: ET._Element,
    suffix: str,
) -> None:
    resource_type, resource_id = _owner(element)
    location = f"{tree.getpath(element)}{suffix}"
    key = resource_type, resource_id, location
    if key not in seen:
        seen.add(key)
        result.append(ResourceReference(resource_type, resource_id, location))


def _datasource_context(element: ET._Element) -> str | None:
    for node in [element, *element.iterancestors()]:
        local_name = _local_name(node)
        if local_name == "datasource-dependencies" and node.get("datasource"):
            return node.get("datasource")
        if local_name == "datasource" and node.get("name"):
            return node.get("name")
    return None


def _has_qualified_reference(
    value: str,
    datasource_labels: set[str],
    field_id: str,
) -> bool:
    for match in _REFERENCE_RE.finditer(value):
        datasource_token, qualified_field, _ = match.groups()
        if (
            datasource_token in datasource_labels
            and qualified_field is not None
            and _field_token_matches(qualified_field, field_id)
        ):
            return True
    return False


def _has_local_formula_reference(value: str, field_id: str) -> bool:
    for match in _REFERENCE_RE.finditer(value):
        datasource_token, _, local_field = match.groups()
        if datasource_token is None and local_field is not None and _field_token_matches(local_field, field_id):
            return True
    return False


def field_references(
    tree: ET._ElementTree,
    datasource_id: str,
    field_id: str,
) -> list[ResourceReference]:
    result: list[ResourceReference] = []
    seen: set[tuple[str, str, str]] = set()
    datasource_hits = tree.getroot().xpath(
        "/workbook/datasources/datasource[@name=$datasource_id]",
        datasource_id=datasource_id,
    )
    datasource_labels = {datasource_id}
    if datasource_hits and datasource_hits[0].get("caption"):
        datasource_labels.add(str(datasource_hits[0].get("caption")))

    for item in tree.getroot().xpath(
        "//*[local-name()='folder-item'][@name=$field_id]",
        field_id=field_id,
    ):
        datasource = next(
            (node for node in item.iterancestors() if _local_name(node) == "datasource"),
            None,
        )
        if datasource is not None and datasource.get("name") == datasource_id:
            _append_reference(result, seen, tree, item, "/@name")

    for dependency in tree.getroot().xpath(
        "//*[local-name()='datasource-dependencies'][@datasource=$datasource_id]",
        datasource_id=datasource_id,
    ):
        for column in dependency.xpath(
            "./*[local-name()='column'][@name=$field_id]",
            field_id=field_id,
        ):
            _append_reference(result, seen, tree, column, "/@name")

    for calculation in tree.getroot().xpath("//*[local-name()='calculation'][@formula]"):
        formula = calculation.get("formula") or ""
        if _has_qualified_reference(formula, datasource_labels, field_id) or (
            _datasource_context(calculation) == datasource_id
            and _has_local_formula_reference(formula, field_id)
        ):
            _append_reference(result, seen, tree, calculation, "/@formula")

    for element in tree.getroot().iter():
        for attribute, value in element.attrib.items():
            if _has_qualified_reference(str(value), datasource_labels, field_id):
                _append_reference(result, seen, tree, element, f"/@{str(attribute).split('}')[-1]}")
        if element.text and _has_qualified_reference(element.text, datasource_labels, field_id):
            _append_reference(result, seen, tree, element, "/text()")
    return result


def worksheet_references(tree: ET._ElementTree, worksheet_id: str) -> list[ResourceReference]:
    result: list[ResourceReference] = []
    seen: set[tuple[str, str, str]] = set()

    for zone in tree.getroot().xpath(
        "/workbook/dashboards/dashboard//*[local-name()='zone'][@name=$worksheet_id]",
        worksheet_id=worksheet_id,
    ):
        _append_reference(result, seen, tree, zone, "/@name")

    for action in tree.getroot().xpath("/workbook/actions/action"):
        for element in action.iterdescendants():
            for attribute, value in element.attrib.items():
                attr_name = str(attribute).split("}")[-1]
                if attr_name in {"name", "worksheet", "sheet"} and value == worksheet_id:
                    _append_reference(result, seen, tree, element, f"/@{attr_name}")
    return result


def datasource_references(tree: ET._ElementTree, datasource_id: str) -> list[ResourceReference]:
    result: list[ResourceReference] = []
    seen: set[tuple[str, str, str]] = set()
    datasource_hits = tree.getroot().xpath(
        "/workbook/datasources/datasource[@name=$datasource_id]",
        datasource_id=datasource_id,
    )
    labels = {datasource_id}
    target = datasource_hits[0] if datasource_hits else None
    if target is not None and target.get("caption"):
        labels.add(str(target.get("caption")))

    for dependency in tree.getroot().xpath(
        "//*[local-name()='datasource-dependencies'][@datasource=$datasource_id]",
        datasource_id=datasource_id,
    ):
        _append_reference(result, seen, tree, dependency, "/@datasource")

    for element in tree.getroot().iter():
        if target is not None and (element is target or target in element.iterancestors()):
            continue
        for attribute, value in element.attrib.items():
            if any(match.group(1) in labels for match in _REFERENCE_RE.finditer(str(value)) if match.group(1)):
                _append_reference(result, seen, tree, element, f"/@{str(attribute).split('}')[-1]}")
        if element.text and any(
            match.group(1) in labels
            for match in _REFERENCE_RE.finditer(element.text)
            if match.group(1)
        ):
            _append_reference(result, seen, tree, element, "/text()")
    return result


def dashboard_references(tree: ET._ElementTree, dashboard_id: str) -> list[ResourceReference]:
    result: list[ResourceReference] = []
    seen: set[tuple[str, str, str]] = set()
    dashboard_hits = tree.getroot().xpath(
        "/workbook/dashboards/dashboard[@name=$dashboard_id]",
        dashboard_id=dashboard_id,
    )
    if not dashboard_hits:
        return result
    dashboard_el = dashboard_hits[0]

    for zone in dashboard_el.xpath(".//*[local-name()='zone']"):
        resource_type = (
            "DashboardContainer"
            if (zone.get("type-v2") or zone.get("type")) in {"layout-basic", "layout-flow"}
            else "DashboardZone"
        )
        location = tree.getpath(zone)
        key = resource_type, zone.get("id") or "", location
        if key not in seen:
            seen.add(key)
            result.append(ResourceReference(resource_type, zone.get("id") or "", location))

    for action in tree.getroot().xpath("/workbook/actions/action"):
        linked = any(
            value == dashboard_id
            for element in [action, *action.iterdescendants()]
            for attribute, value in element.attrib.items()
            if str(attribute).split("}")[-1] == "dashboard"
        )
        if linked:
            _append_reference(result, seen, tree, action, "")
    return result
