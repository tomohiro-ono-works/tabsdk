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


def _first_out_of_order(parent: ET._Element, order: tuple[str, ...]) -> str | None:
    ranks = {name: index for index, name in enumerate(order)}
    last_rank = -1
    for child in parent:
        name = _local_name(child)
        if name not in ranks:
            continue
        if ranks[name] < last_rank:
            return name
        last_rank = ranks[name]
    return None


_DATASOURCE_ORDER = (
    "repository-location", "connection", "utility-dimensions", "dimension",
    "overridable-settings", "aliases", "column", "column-instance", "group",
    "mapped-images", "drill-paths", "unlinked-server-hierarchies",
    "folders-common", "folders-parameters", "actions", "calculated-members",
    "extract", "layout", "style", "semantic-values", "date-options",
    "default-date-format", "default-sorts", "field-sort-info",
    "datasource-dependencies", "explainability", "filter", "object-graph",
)
_VIEW_ORDER = (
    "datasources", "mapsources", "datasource-dependencies", "filter",
    "computed-sort", "sort", "perspectives", "slices", "aggregation",
)
_TABLE_ORDER = (
    "view", "style", "panes", "mark-layout", "rows", "cols",
    "table-calc-densification", "pages", "join-lod-include-overrides",
    "join-lod-exclude-overrides", "subtotals", "table-calculations",
    "show-full-range", "consider-zeros-empty", "percentages", "mark-labels",
    "annotations", "page-trail-options", "trail-overrides", "tooltip-style",
    "forecast-specification",
)
_PANE_ORDER = (
    "view", "mark", "mark-sizing", "encodings", "label-data", "dropline",
    "trendline", "reference-line", "customized-tooltip", "customized-label",
    "style",
)
_DASHBOARD_ZONE_ORDER = (
    "formatted-text", "layout-cache", "zone", "flipboard", "button", "zone-style",
)
_DASHBOARD_WINDOW_ORDER = ("viewpoints", "active", "device-preview", "simple-id")


def validate_tree(tree: ET._ElementTree) -> list[TwbValidationMessage]:
    messages: list[TwbValidationMessage] = []
    for ds in datasource_elements(tree):
        ds_id = ds.get("caption") or ds.get("name")
        invalid = _first_out_of_order(ds, _DATASOURCE_ORDER)
        if invalid:
            messages.append(TwbValidationMessage(
                "error",
                "datasource_element_order",
                f"datasource element is out of order: {invalid}",
                ds_id,
            ))
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
            calc = col.find("./calculation")
            # グループ（categorical-bin）は formula を持たず、caption も付かない。
            # Tableau は表示名をそのまま name に書く（実測、backlog L-5）。
            is_group = calc is not None and calc.get("class") == "categorical-bin"
            if caption is None and not is_group:
                messages.append(TwbValidationMessage("warning", "caption_empty", f"caption is empty: {name}", ds_id, name))
            if calc is not None and not is_group and not (calc.get("formula") or "").strip():
                messages.append(TwbValidationMessage("error", "formula_empty", f"formula is empty: {name}", ds_id, name))
        # 階層はフォルダへ type="drillpath" で入り、name は drill-path の表示名
        # （角括弧なし）。列名と照合すると必ず外れるため、階層名も参照集合へ入れる。
        drill_names = {
            str(path.get("name"))
            for path in ds.xpath("./*[local-name()='drill-paths']/*[local-name()='drill-path'][@name]")
        }
        for folder in _folder_elements(ds):
            for item in folder.findall("./folder-item"):
                item_name = item.get("name")
                if item.get("type") == "drillpath":
                    if item_name and item_name not in drill_names:
                        messages.append(TwbValidationMessage("warning", "folder_item_missing", f"folder-item references missing drill path: {item_name}", ds_id, item_name))
                    continue
                if item_name and item_name not in names:
                    messages.append(TwbValidationMessage("warning", "folder_item_missing", f"folder-item references missing column: {item_name}", ds_id, item_name))
        for folder in ds.findall("./folder"):
            messages.append(TwbValidationMessage("error", "folder_invalid_location", "folder must be under folders-common or folders-parameters", ds_id, folder.get("name")))
    for worksheet in tree.xpath("/workbook/worksheets/worksheet"):
        worksheet_id = worksheet.get("name")
        if worksheet.xpath("./table/view/computed-sort") and not tree.xpath(
            "/workbook/document-format-change-manifest/SortTagCleanup"
        ):
            messages.append(TwbValidationMessage(
                "error",
                "computed_sort_manifest_missing",
                "computed-sort requires SortTagCleanup in document-format-change-manifest",
                worksheet_id,
            ))
        for element, order, code in [
            *[(view, _VIEW_ORDER, "worksheet_view_element_order") for view in worksheet.xpath("./table/view")],
            *[(table, _TABLE_ORDER, "worksheet_table_element_order") for table in worksheet.xpath("./table")],
            *[(pane, _PANE_ORDER, "worksheet_pane_element_order") for pane in worksheet.xpath("./table/panes/pane")],
        ]:
            invalid = _first_out_of_order(element, order)
            if invalid:
                messages.append(TwbValidationMessage(
                    "error", code, f"worksheet element is out of order: {invalid}", worksheet_id,
                ))
        for angle in worksheet.xpath(".//encodings/angle"):
            messages.append(TwbValidationMessage(
                "error", "worksheet_invalid_encoding", "pie angle must use wedge-size", worksheet_id,
            ))
    for dashboard in tree.xpath("/workbook/dashboards/dashboard"):
        dashboard_id = dashboard.get("name")
        for zone in dashboard.xpath(".//*[local-name()='zone']"):
            invalid = _first_out_of_order(zone, _DASHBOARD_ZONE_ORDER)
            if invalid:
                messages.append(TwbValidationMessage(
                    "error",
                    "dashboard_zone_element_order",
                    f"dashboard zone element is out of order: {invalid}",
                    dashboard_id,
                    zone.get("id"),
                ))
    for window in tree.xpath("/workbook/windows/window[@class='dashboard']"):
        dashboard_id = window.get("name")
        invalid = _first_out_of_order(window, _DASHBOARD_WINDOW_ORDER)
        children = {_local_name(child) for child in window}
        missing = {"viewpoints", "active", "simple-id"} - children
        if invalid or missing:
            detail = (
                f"element is out of order: {invalid}"
                if invalid
                else f"required elements are missing: {sorted(missing)}"
            )
            messages.append(TwbValidationMessage(
                "error",
                "dashboard_window_structure",
                f"dashboard window structure is invalid: {detail}",
                dashboard_id,
            ))
    for uf in unsupported_features_from_tree(tree):
        messages.append(TwbValidationMessage(uf.severity, f"unsupported_{uf.feature}", uf.message, uf.datasource))
    return messages
