from __future__ import annotations

from lxml import etree as ET

from .dashboard import dashboard_elements, resolve_dashboard_el
from .field_ref import build_column_index
from .models import TwbWorksheetField
from .worksheet_field import build_datasource_labels, worksheet_fields_from_element


def _worksheet_map(tree: ET._ElementTree) -> dict[str, ET._Element]:
    return {
        str(worksheet.get("name")): worksheet
        for worksheet in tree.getroot().xpath("/workbook/worksheets/worksheet")
        if worksheet.get("name")
    }


def list_dashboard_fields_from_tree(
    tree: ET._ElementTree,
    dashboard: str | None = None,
    *,
    by: str = "auto",
    max_filter_value_chars: int = 40,
) -> list[TwbWorksheetField]:
    dashboard_els = (
        [resolve_dashboard_el(tree, dashboard, by=by)]
        if dashboard is not None
        else dashboard_elements(tree)
    )
    worksheets_by_name = _worksheet_map(tree)
    columns = build_column_index(tree)
    datasource_labels = build_datasource_labels(tree)
    fields: list[TwbWorksheetField] = []

    for dashboard_el in dashboard_els:
        seen: set[str] = set()
        for value in dashboard_el.xpath(".//@name"):
            worksheet_name = str(value)
            if worksheet_name in seen:
                continue
            worksheet_el = worksheets_by_name.get(worksheet_name)
            if worksheet_el is None:
                continue
            seen.add(worksheet_name)
            fields.extend(
                worksheet_fields_from_element(
                    worksheet_el,
                    columns=columns,
                    datasource_labels=datasource_labels,
                    max_filter_value_chars=max_filter_value_chars,
                )
            )

    return fields
