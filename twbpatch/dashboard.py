from __future__ import annotations

from lxml import etree as ET
from .errors import NotFoundError, AmbiguousCaptionError
from .field_ref import build_column_index
from .models import TwbDashboard, TwbWorksheet
from .worksheet import materialize_worksheet
from .window import bool_attr, window_attrs_by_name


def dashboard_elements(tree: ET._ElementTree) -> list[ET._Element]:
    return list(tree.getroot().xpath("/workbook/dashboards/dashboard"))


def _worksheet_name_set(tree: ET._ElementTree) -> set[str]:
    return set(str(x) for x in tree.getroot().xpath("/workbook/worksheets/worksheet/@name"))


def _worksheet_map(tree: ET._ElementTree) -> dict[str, ET._Element]:
    return {str(ws.get("name")): ws for ws in tree.getroot().xpath("/workbook/worksheets/worksheet") if ws.get("name")}


def materialize_dashboard(
    dash_el: ET._Element,
    worksheets_by_name: dict[str, ET._Element],
    *,
    window_attrs: dict[str, str] | None = None,
    worksheet_windows: dict[str, dict[str, str]] | None = None,
    columns: dict[tuple[str, str], ET._Element] | None = None,
) -> TwbDashboard:
    name = dash_el.get("name") or ""
    caption = dash_el.get("caption") or name
    hidden = bool(bool_attr((window_attrs or {}).get("hidden"), False))
    linked: list[TwbWorksheet] = []
    seen: set[str] = set()
    worksheet_windows = worksheet_windows or {}
    columns = columns or {}

    # Tableau dashboard usually stores worksheet references in zone name attributes.
    for value in dash_el.xpath(".//@name"):
        ws_name = str(value)
        if ws_name in worksheets_by_name and ws_name not in seen:
            linked.append(
                materialize_worksheet(
                    worksheets_by_name[ws_name],
                    window_attrs=worksheet_windows.get(ws_name),
                    columns=columns,
                )
            )
            seen.add(ws_name)

    return TwbDashboard(
        name=name,
        id=name,
        caption=caption,
        worksheets=linked,
        visible=not hidden,
    )


def list_dashboards_from_tree(tree: ET._ElementTree) -> list[TwbDashboard]:
    worksheets_by_name = _worksheet_map(tree)
    dashboard_windows = window_attrs_by_name(tree, "dashboard")
    worksheet_windows = window_attrs_by_name(tree, "worksheet")
    columns = build_column_index(tree)
    return [
        materialize_dashboard(
            dash,
            worksheets_by_name,
            window_attrs=dashboard_windows.get(dash.get("name") or ""),
            worksheet_windows=worksheet_windows,
            columns=columns,
        )
        for dash in dashboard_elements(tree)
    ]


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
    dash_el = resolve_dashboard_el(tree, dashboard, by=by)
    return materialize_dashboard(
        dash_el,
        worksheets_by_name,
        window_attrs=window_attrs_by_name(tree, "dashboard").get(dash_el.get("name") or ""),
        worksheet_windows=window_attrs_by_name(tree, "worksheet"),
        columns=build_column_index(tree),
    )
