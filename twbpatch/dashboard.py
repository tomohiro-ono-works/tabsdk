from __future__ import annotations

from lxml import etree as ET
from .errors import NotFoundError, AmbiguousCaptionError
from .models import TwbDashboard, TwbWorksheet
from .worksheet import materialize_worksheet


def dashboard_elements(tree: ET._ElementTree) -> list[ET._Element]:
    return list(tree.getroot().xpath("/workbook/dashboards/dashboard"))


def _worksheet_name_set(tree: ET._ElementTree) -> set[str]:
    return set(str(x) for x in tree.getroot().xpath("/workbook/worksheets/worksheet/@name"))


def _worksheet_map(tree: ET._ElementTree) -> dict[str, ET._Element]:
    return {str(ws.get("name")): ws for ws in tree.getroot().xpath("/workbook/worksheets/worksheet") if ws.get("name")}


def materialize_dashboard(dash_el: ET._Element, worksheets_by_name: dict[str, ET._Element]) -> TwbDashboard:
    name = dash_el.get("name") or ""
    caption = dash_el.get("caption") or name
    linked: list[TwbWorksheet] = []
    seen: set[str] = set()

    # Tableau dashboard usually stores worksheet references in zone name attributes.
    for value in dash_el.xpath(".//@name"):
        ws_name = str(value)
        if ws_name in worksheets_by_name and ws_name not in seen:
            linked.append(materialize_worksheet(worksheets_by_name[ws_name]))
            seen.add(ws_name)

    return TwbDashboard(name=name, id=name, caption=caption, worksheets=linked)


def list_dashboards_from_tree(tree: ET._ElementTree) -> list[TwbDashboard]:
    worksheets_by_name = _worksheet_map(tree)
    return [materialize_dashboard(dash, worksheets_by_name) for dash in dashboard_elements(tree)]


def resolve_dashboard_el(tree: ET._ElementTree, dashboard: str, *, by: str = "auto") -> ET._Element:
    candidates = dashboard_elements(tree)
    if by not in {"auto", "caption", "name"}:
        raise ValueError("by must be 'auto', 'caption', or 'name'.")

    matched = [d for d in candidates if d.get("caption") == dashboard] if by in {"auto", "caption"} else []
    if not matched and by in {"auto", "name"}:
        matched = [d for d in candidates if d.get("name") == dashboard]
    if not matched:
        raise NotFoundError(f"dashboard not found: {dashboard}")
    if len(matched) > 1:
        raise AmbiguousCaptionError(f"dashboard is ambiguous: {dashboard}")
    return matched[0]


def get_dashboard_from_tree(tree: ET._ElementTree, dashboard: str, *, by: str = "auto") -> TwbDashboard:
    worksheets_by_name = _worksheet_map(tree)
    return materialize_dashboard(resolve_dashboard_el(tree, dashboard, by=by), worksheets_by_name)
