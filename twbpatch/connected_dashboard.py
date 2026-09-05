from __future__ import annotations

import copy
import math
import uuid
from typing import Any

from lxml import etree as ET

from .connected import get_datasources, get_display_name, _matches, _validate_get_args
from .connected_worksheet import TwbWorksheet, TwbWorksheetField, get_worksheets
from .context import (
    UNSET,
    ConnectedModel,
    WorkbookContext,
    _UnsetType,
    validate_style_group as _validate_style_group,
)
from .dashboard import dashboard_elements
from .dashboard_action import list_actions_from_tree
from .errors import (
    DetachedModelError,
    ResourceInUseError,
    ResourceReference,
    UnsupportedFeatureError,
)
from .filter import list_dashboard_filter_controls_from_tree
from .references import dashboard_references


_DIRECTIONS = {"horizontal": "horz", "vertical": "vert"}
_CONTAINER_TYPES = {"layout-basic", "layout-flow"}
_DEFAULT_REPORT_CONTENT_STYLE = {
    "background_color": "#f5f5f5",
    "border_style": "none",
    "margin": 8,
}
_DEFAULT_REPORT_WORKSHEET_STYLE = {
    "background_color": "#ffffff",
    "border_style": "none",
    "margin": 4,
    "padding": 16,
}


def _local_name(element: ET._Element) -> str:
    return ET.QName(element).localname


def _direct_child(parent: ET._Element, local_name: str) -> ET._Element | None:
    return next((child for child in parent if _local_name(child) == local_name), None)


def _is_container(zone_el: ET._Element) -> bool:
    return (zone_el.get("type-v2") or zone_el.get("type")) in _CONTAINER_TYPES


def _zone_kind(zone_el: ET._Element, worksheet_ids: set[str]) -> str:
    if _is_container(zone_el):
        return "container"
    if (zone_el.get("type-v2") or zone_el.get("type")) == "filter":
        return "filter"
    if zone_el.get("name") in worksheet_ids:
        return "worksheet"
    return {
        "text": "text",
        "bitmap": "image",
        "empty": "spacer",
        "dashboard-object": "dashboard_object",
        "filter": "filter",
    }.get(zone_el.get("type-v2") or zone_el.get("type") or "", "unknown")


def _direct_zones(parent: ET._Element) -> list[ET._Element]:
    return [child for child in parent if _local_name(child) == "zone"]


def _default_zones(dashboard_el: ET._Element, *, create: bool = False) -> ET._Element | None:
    zones = [child for child in dashboard_el if _local_name(child) == "zones"]
    if len(zones) > 1:
        raise UnsupportedFeatureError("dashboard has multiple default zones elements")
    if zones:
        return zones[0]
    if not create:
        return None
    zones_el = ET.Element("zones")
    device_layouts = _direct_child(dashboard_el, "devicelayouts")
    if device_layouts is None:
        dashboard_el.append(zones_el)
    else:
        dashboard_el.insert(dashboard_el.index(device_layouts), zones_el)
    return zones_el


def _default_zone_elements(dashboard_el: ET._Element) -> list[ET._Element]:
    zones_el = _default_zones(dashboard_el)
    if zones_el is None:
        return []
    return [
        element
        for element in zones_el.iter()
        if element is not zones_el and _local_name(element) == "zone"
    ]


def _resolve_zone(dashboard_el: ET._Element, zone_id: str) -> ET._Element:
    hits = [zone for zone in _default_zone_elements(dashboard_el) if zone.get("id") == zone_id]
    if len(hits) != 1:
        raise DetachedModelError(f"dashboard zone is detached: {zone_id}")
    return hits[0]


def _replace_if_changed(
    current: ET._Element,
    updated: ET._Element,
    context: WorkbookContext,
) -> bool:
    if ET.tostring(current) == ET.tostring(updated):
        return False
    parent = current.getparent()
    if parent is None:
        raise DetachedModelError("XML resource is detached")
    parent.replace(current, updated)
    context.mark_dirty()
    return True


def _int_attr(element: ET._Element, name: str, default: int = 0) -> int:
    try:
        return int(float(element.get(name) or default))
    except ValueError:
        return default


def _round(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _validate_fixed_size(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("fixed_size must be a positive integer or None")
    return value


def _set_fixed_size(zone_el: ET._Element, value: int | None) -> None:
    if value is None:
        zone_el.attrib.pop("fixed-size", None)
        zone_el.attrib.pop("is-fixed", None)
    else:
        zone_el.set("fixed-size", str(value))
        zone_el.set("is-fixed", "true")


def _zone_style_values(zone_el: ET._Element) -> dict[str, str]:
    style = _direct_child(zone_el, "zone-style")
    if style is None:
        return {}
    return {
        (item.get("attr") or "").replace("-", "_"): item.get("value") or ""
        for item in style
        if _local_name(item) == "format" and item.get("attr")
    }


def _set_zone_styles(zone_el: ET._Element, styles: dict[str, str | int | None]) -> None:
    for name, value in styles.items():
        if not isinstance(name, str) or not name or not name.replace("_", "").isalnum():
            raise ValueError(f"invalid style name: {name}")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int))):
            raise TypeError(f"style value must be str, int, or None: {name}")
    style = _direct_child(zone_el, "zone-style")
    if style is None and any(value is not None for value in styles.values()):
        style = ET.SubElement(zone_el, "zone-style")
    if style is None:
        return
    for name, value in styles.items():
        attr = name.replace("_", "-")
        matches = style.xpath("./*[local-name()='format'][@attr=$attr]", attr=attr)
        if value is None:
            for item in matches:
                style.remove(item)
        elif matches:
            matches[0].set("value", str(value))
            for item in matches[1:]:
                style.remove(item)
        else:
            ET.SubElement(style, "format", attrib={"attr": attr, "value": str(value)})
    if not len(style):
        zone_el.remove(style)


def _dashboard_size(dashboard_el: ET._Element) -> tuple[str, int | None, int | None]:
    size_el = _direct_child(dashboard_el, "size")
    if size_el is None:
        return "automatic", None, None
    sizing_mode = size_el.get("sizing-mode") or "automatic"
    if sizing_mode != "fixed":
        return sizing_mode, None, None
    width = _int_attr(size_el, "minwidth") or _int_attr(size_el, "maxwidth") or None
    height = _int_attr(size_el, "minheight") or _int_attr(size_el, "maxheight") or None
    return sizing_mode, width, height


def _zone_rect(zone_el: ET._Element) -> tuple[int, int, int, int]:
    return (
        _int_attr(zone_el, "x"),
        _int_attr(zone_el, "y"),
        _int_attr(zone_el, "w", 100000),
        _int_attr(zone_el, "h", 100000),
    )


def _container_direction(container_el: ET._Element) -> str:
    param = (container_el.get("param") or "").lower()
    if param in {"horz", "horizontal"}:
        return "horizontal"
    if param in {"vert", "vertical"}:
        return "vertical"

    children = _direct_zones(container_el)
    if len(children) >= 2:
        x_values = [_int_attr(child, "x") for child in children]
        y_values = [_int_attr(child, "y") for child in children]
        if max(x_values) - min(x_values) >= max(y_values) - min(y_values):
            return "horizontal"
        return "vertical"
    return "horizontal"


def _weight_key(dashboard_id: str, zone_el: ET._Element) -> tuple[str, str]:
    zone_id = zone_el.get("id")
    if not zone_id:
        raise UnsupportedFeatureError("dashboard zone has no id")
    return dashboard_id, zone_id


def _derived_weights(
    dashboard_id: str,
    container_el: ET._Element,
    weights: dict[tuple[str, str], float],
) -> dict[str, float]:
    children = _direct_zones(container_el)
    if not children:
        return {}
    if container_el.get("layout-strategy-id") == "distribute-evenly":
        return {
            child.get("id") or "": 1.0
            for child in children
            if child.get("id")
        }
    direction = _container_direction(container_el)
    dimensions = [max(1, _int_attr(child, "w" if direction == "horizontal" else "h", 1)) for child in children]
    minimum = min(dimensions)
    result: dict[str, float] = {}
    for child, dimension in zip(children, dimensions):
        zone_id = child.get("id")
        if not zone_id:
            raise UnsupportedFeatureError("dashboard zone has no id")
        stored = weights.get((dashboard_id, zone_id))
        result[zone_id] = stored if stored is not None else dimension / minimum
    return result


def _content_rect(
    container_el: ET._Element,
    dashboard_el: ET._Element | None,
) -> tuple[int, int, int, int]:
    x, y, width, height = _zone_rect(container_el)
    if dashboard_el is None:
        return x, y, width, height
    _, canvas_width, canvas_height = _dashboard_size(dashboard_el)
    if canvas_width is None or canvas_height is None:
        return x, y, width, height

    styles = _zone_style_values(container_el)

    def padding(side: str) -> float:
        value = styles.get(f"padding_{side}", styles.get("padding", "0"))
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    left = _px_to_raw(padding("left"), canvas_width)
    right = _px_to_raw(padding("right"), canvas_width)
    top = _px_to_raw(padding("top"), canvas_height)
    bottom = _px_to_raw(padding("bottom"), canvas_height)
    return (
        x + left,
        y + top,
        max(0, width - left - right),
        max(0, height - top - bottom),
    )


def _layout_container(
    dashboard_id: str,
    container_el: ET._Element,
    weights: dict[tuple[str, str], float],
) -> None:
    children = _direct_zones(container_el)
    if not children:
        return
    direction = _container_direction(container_el)
    dashboard_el = next(
        (item for item in container_el.iterancestors() if _local_name(item) == "dashboard"),
        None,
    )
    x, y, width, height = _content_rect(container_el, dashboard_el)
    axis_size = width if direction == "horizontal" else height
    canvas = None
    if dashboard_el is not None:
        _, canvas_width, canvas_height = _dashboard_size(dashboard_el)
        canvas = canvas_width if direction == "horizontal" else canvas_height

    distribute_evenly = container_el.get("layout-strategy-id") == "distribute-evenly"
    fixed_sizes: dict[str, int] = {}
    flexible = []
    for child in children:
        zone_id = child.get("id")
        if not zone_id:
            raise UnsupportedFeatureError("dashboard zone has no id")
        fixed_px = (
            0
            if distribute_evenly
            else _int_attr(child, "fixed-size")
            if child.get("is-fixed") == "true"
            else 0
        )
        if fixed_px and canvas:
            fixed_sizes[zone_id] = _px_to_raw(fixed_px, canvas)
        else:
            flexible.append(child)

    remaining = max(0, axis_size - sum(fixed_sizes.values()))
    child_weights = (
        {child.get("id") or "": 1.0 for child in children}
        if distribute_evenly
        else _derived_weights(dashboard_id, container_el, weights)
    )
    flexible_total = sum(child_weights[child.get("id") or ""] for child in flexible)
    if flexible and flexible_total <= 0:
        raise ValueError("container weights must be positive")

    sizes: dict[str, int] = dict(fixed_sizes)
    flexible_consumed = 0
    accumulated_weight = 0.0
    for index, child in enumerate(flexible):
        zone_id = child.get("id") or ""
        accumulated_weight += child_weights[zone_id]
        boundary = remaining if index == len(flexible) - 1 else _round(
            remaining * accumulated_weight / flexible_total
        )
        sizes[zone_id] = max(0, boundary - flexible_consumed)
        flexible_consumed = boundary
    if not flexible and children:
        last_id = children[-1].get("id") or ""
        sizes[last_id] = sizes.get(last_id, 0) + max(0, axis_size - sum(sizes.values()))

    consumed = 0
    for index, child in enumerate(children):
        zone_id = child.get("id")
        if not zone_id:
            raise UnsupportedFeatureError("dashboard zone has no id")
        child_axis_size = sizes.get(zone_id, 0)
        if index == len(children) - 1:
            child_axis_size = max(0, axis_size - consumed)
        if zone_id not in fixed_sizes:
            weights[(dashboard_id, zone_id)] = child_weights[zone_id]
        if direction == "horizontal":
            child.set("x", str(x + consumed))
            child.set("y", str(y))
            child.set("w", str(child_axis_size))
            child.set("h", str(height))
        else:
            child.set("x", str(x))
            child.set("y", str(y + consumed))
            child.set("w", str(width))
            child.set("h", str(child_axis_size))
        consumed += child_axis_size
        if _is_container(child):
            _layout_container(dashboard_id, child, weights)


def _insert_zone(parent: ET._Element, zone_el: ET._Element, order: int | None) -> None:
    zones = _direct_zones(parent)
    if order is None:
        order = len(zones)
    if isinstance(order, bool) or not isinstance(order, int):
        raise TypeError("order must be an integer or None")
    if order < 0 or order > len(zones):
        raise ValueError(f"order is out of range: {order}")
    if order == len(zones):
        if zones:
            zones[-1].addnext(zone_el)
        else:
            trailing = next(
                (
                    child
                    for child in parent
                    if _local_name(child) in {"flipboard", "button", "zone-style"}
                ),
                None,
            )
            parent.insert(parent.index(trailing) if trailing is not None else len(parent), zone_el)
    else:
        zones[order].addprevious(zone_el)


def _move_zone(parent: ET._Element, zone_el: ET._Element, order: int) -> None:
    zones = _direct_zones(parent)
    if isinstance(order, bool) or not isinstance(order, int):
        raise TypeError("order must be an integer")
    if order < 0 or order >= len(zones):
        raise ValueError(f"order is out of range: {order}")
    current = zones.index(zone_el)
    if current == order:
        return
    parent.remove(zone_el)
    _insert_zone(parent, zone_el, order)


def _validate_weight(weight: float) -> float:
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise TypeError("weight must be a number")
    value = float(weight)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("weight must be positive")
    return value


def _next_zone_id(dashboard_el: ET._Element) -> str:
    used = {str(value) for value in dashboard_el.xpath(".//*[local-name()='zone']/@id")}
    numeric = [int(value) for value in used if value.isdigit()]
    candidate = max(numeric, default=0) + 1
    while str(candidate) in used:
        candidate += 1
    return str(candidate)


def _sync_dashboard_window(context: WorkbookContext, dashboard_id: str) -> None:
    root = context.tree.getroot()
    dashboards = root.xpath(
        "/workbook/dashboards/dashboard[@name=$dashboard_id]",
        dashboard_id=dashboard_id,
    )
    if not dashboards:
        return
    worksheet_ids = _worksheet_names(context)
    worksheet_zones = [
        zone
        for zone in _default_zone_elements(dashboards[0])
        if zone.get("name") in worksheet_ids
    ]
    windows_el = _direct_child(root, "windows")
    windows = [] if windows_el is None else windows_el.xpath(
        "./*[local-name()='window'][@class='dashboard'][@name=$dashboard_id]",
        dashboard_id=dashboard_id,
    )
    if not worksheet_zones:
        if windows:
            windows_el.remove(windows[0])
            context.mark_dirty()
        return
    if windows_el is None:
        windows_el = ET.Element("windows")
        root.insert(0, windows_el)
    current = windows[0] if windows else None
    simple_id = None if current is None else _direct_child(current, "simple-id")
    window = ET.Element(
        "window",
        attrib={"class": "dashboard", "maximized": "true", "name": dashboard_id},
    )
    viewpoints = ET.SubElement(window, "viewpoints")
    seen: set[str] = set()
    for zone in worksheet_zones:
        name = zone.get("name") or ""
        if name in seen:
            continue
        seen.add(name)
        viewpoint = ET.SubElement(viewpoints, "viewpoint", attrib={"name": name})
        ET.SubElement(viewpoint, "zoom", attrib={"type": "entire-view"})
    ET.SubElement(window, "active", attrib={"id": worksheet_zones[0].get("id") or "1"})
    ET.SubElement(
        window,
        "simple-id",
        attrib={
            "uuid": simple_id.get("uuid")
            if simple_id is not None and simple_id.get("uuid")
            else f"{{{str(uuid.uuid4()).upper()}}}",
        },
    )
    if current is None:
        windows_el.append(window)
        context.mark_dirty()
    elif ET.tostring(current) != ET.tostring(window):
        windows_el.replace(current, window)
        context.mark_dirty()


def _worksheet_names(context: WorkbookContext) -> dict[str, str]:
    return {
        str(element.get("name")): str(element.get("name"))
        for element in context.tree.getroot().xpath("/workbook/worksheets/worksheet[@name]")
    }


def _zone_display_name(context: WorkbookContext, zone_el: ET._Element) -> str:
    zone_name = zone_el.get("name")
    worksheets = _worksheet_names(context)
    if zone_name in worksheets:
        return worksheets[zone_name]
    return zone_el.get("friendly-name") or zone_name or zone_el.get("id") or ""


def _validate_worksheet(worksheet: TwbWorksheet, context: WorkbookContext) -> None:
    if not isinstance(worksheet, TwbWorksheet):
        raise TypeError("worksheet must be TwbWorksheet")
    worksheet._ensure_attached()
    worksheet._resolve_element()
    if worksheet._context is not context:
        raise ValueError("worksheet must belong to the same workbook")


def _contains_worksheet(dashboard_el: ET._Element, worksheet_id: str) -> bool:
    return any(zone.get("name") == worksheet_id for zone in _default_zone_elements(dashboard_el))


def _canvas_or_error(dashboard_el: ET._Element) -> tuple[int, int]:
    sizing_mode, width, height = _dashboard_size(dashboard_el)
    if sizing_mode != "fixed" or width is None or height is None:
        raise UnsupportedFeatureError("floating pixel layout requires a fixed-size dashboard")
    return width, height


def _px_to_raw(value: float, canvas: int) -> int:
    return _round(value * 100000 / canvas)


def _raw_to_px(value: int, canvas: int) -> int:
    return _round(value * canvas / 100000)


def _validate_pixel(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        requirement = "positive" if positive else "zero or greater"
        raise ValueError(f"{name} must be {requirement}")
    return result


class TwbDashboardAction(ConnectedModel):
    def __init__(self, context: WorkbookContext, dashboard_id: str, action_id: str):
        super().__init__(context)
        self._dashboard_id = dashboard_id
        self._id = action_id

    def _snapshot(self) -> Any:
        self._ensure_attached()
        dashboard = TwbDashboard(self._context, self._dashboard_id)._resolve_element()
        matches = [
            action
            for action in list_actions_from_tree(self._context.tree, dashboard)
            if action.id == self._id
        ]
        if len(matches) != 1:
            self._detach()
            raise DetachedModelError(f"dashboard action is detached: {self._id}")
        return matches[0]

    @property
    def id(self) -> str:
        self._snapshot()
        return self._id

    @property
    def name(self) -> str:
        action = self._snapshot()
        return action.caption or action.id or self._id

    @property
    def type(self) -> str | None:
        return self._snapshot().type

    @property
    def activation(self) -> str | None:
        return self._snapshot().activation

    @property
    def command(self) -> str | None:
        return self._snapshot().command

    @property
    def source_worksheet_ids(self) -> list[str]:
        return list(self._snapshot().source_worksheet_ids)

    @property
    def target_worksheet_ids(self) -> list[str]:
        return list(self._snapshot().target_worksheet_ids)

    @property
    def links(self) -> list[dict[str, str]]:
        return [dict(item) for item in self._snapshot().links]

    @property
    def params(self) -> dict[str, str]:
        return dict(self._snapshot().params)


class TwbDashboard(ConnectedModel):
    def __init__(self, context: WorkbookContext, dashboard_id: str):
        super().__init__(context)
        self._id = dashboard_id

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        hits = self._context.tree.getroot().xpath(
            "/workbook/dashboards/dashboard[@name=$id]",
            id=self._id,
        )
        if not hits:
            self._detach()
            raise DetachedModelError(f"dashboard is detached: {self._id}")
        return hits[0]

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        return get_display_name(self._resolve_element())

    @property
    def sizing_mode(self) -> str:
        return _dashboard_size(self._resolve_element())[0]

    @property
    def width(self) -> int | None:
        return _dashboard_size(self._resolve_element())[1]

    @property
    def height(self) -> int | None:
        return _dashboard_size(self._resolve_element())[2]

    @property
    def visible(self) -> bool:
        self._resolve_element()
        windows = self._context.tree.getroot().xpath(
            "/workbook/windows/window[@class='dashboard'][@name=$id]",
            id=self._id,
        )
        return not windows or (windows[0].get("hidden") or "false").lower() != "true"

    def get_worksheets(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbWorksheet]:
        _validate_get_args(id, name)
        worksheet_ids: list[str] = []
        known = _worksheet_names(self._context)
        for zone in _default_zone_elements(self._resolve_element()):
            worksheet_id = zone.get("name")
            if worksheet_id in known and worksheet_id not in worksheet_ids:
                worksheet_ids.append(worksheet_id)
        by_id = {worksheet.id: worksheet for worksheet in get_worksheets(self._context)}
        return [
            worksheet
            for worksheet_id in worksheet_ids
            if (worksheet := by_id.get(worksheet_id)) is not None
            and _matches(model_id=worksheet.id, model_name=worksheet.name, id=id, name=name)
        ]

    def get_fields(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbWorksheetField]:
        _validate_get_args(id, name)
        fields = [field for worksheet in self.get_worksheets() for field in worksheet.get_fields()]
        return [
            field
            for field in fields
            if _matches(model_id=field.id, model_name=field.name, id=id, name=name)
        ]

    def get_containers(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbDashboardContainer]:
        _validate_get_args(id, name)
        zones_el = _default_zones(self._resolve_element())
        if zones_el is None:
            return []
        result: list[TwbDashboardContainer] = []
        for zone_el in _direct_zones(zones_el):
            if not _is_container(zone_el) or not zone_el.get("id"):
                continue
            zone_id = str(zone_el.get("id"))
            zone_name = zone_el.get("friendly-name") or zone_id
            if _matches(model_id=zone_id, model_name=zone_name, id=id, name=name):
                result.append(TwbDashboardContainer(self._context, self._id, zone_id))
        return result

    def get_zones(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbDashboardZone]:
        _validate_get_args(id, name)
        result: list[TwbDashboardZone] = []
        for zone_el in _default_zone_elements(self._resolve_element()):
            zone_id = zone_el.get("id")
            if _is_container(zone_el) or not zone_id:
                continue
            zone_name = _zone_display_name(self._context, zone_el)
            if _matches(model_id=zone_id, model_name=zone_name, id=id, name=name):
                result.append(TwbDashboardZone(self._context, self._id, zone_id))
        return result

    def get_actions(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbDashboardAction]:
        _validate_get_args(id, name)
        actions = list_actions_from_tree(self._context.tree, self._resolve_element())
        result: list[TwbDashboardAction] = []
        for action in actions:
            if not action.id:
                continue
            model = TwbDashboardAction(self._context, self._id, action.id)
            if _matches(model_id=model.id, model_name=model.name, id=id, name=name):
                result.append(model)
        return result

    def get_filter_controls(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list["TwbFilterControl"]:
        _validate_get_args(id, name)
        controls = list_dashboard_filter_controls_from_tree(
            self._context.tree,
            self._id,
            by="name",
        )
        return [
            TwbFilterControl(self._context, self._id, control.id or "")
            for control in controls
            if control.id
            and _matches(
                model_id=control.id,
                model_name=control.name or control.id,
                id=id,
                name=name,
            )
        ]

    def build_report(
        self,
        *,
        dashboard_name: str,
        struct: dict[
            str,
            list[str | tuple[str, str] | list[str] | dict[str, Any]],
        ],
        container_sizes: dict[str, int] | None = None,
        content_style: dict[str, str | int | None] | None = None,
        header_height: int = 43,
        header_background_color: str = "#c0c0c0",
        header_font_color: str = "#333333",
    ) -> TwbDashboard:
        container_sizes = dict(container_sizes or {})
        for container_name, size in container_sizes.items():
            if not isinstance(container_name, str) or not container_name.strip():
                raise ValueError("container size names must be non-empty strings")
            _validate_fixed_size(size)
        _validate_fixed_size(header_height)

        sheet_names: list[str] = []
        filter_specs: list[tuple[str, str]] = []
        worksheet_groups: dict[str, list[tuple[list[str], int | None]] | None] = {}
        for container_name, items in struct.items():
            if "フィルタ" in container_name:
                for item in items:
                    if (
                        not isinstance(item, tuple)
                        or len(item) != 2
                        or not all(isinstance(value, str) and value.strip() for value in item)
                    ):
                        raise TypeError(
                            "filter item must be (datasource name, field name)"
                        )
                    filter_specs.append(item)
            else:
                if all(isinstance(item, str) and item.strip() for item in items):
                    names = [item for item in items if isinstance(item, str)]
                    worksheet_groups[container_name] = None
                    sheet_names.extend(names)
                    continue
                groups: list[tuple[list[str], int | None]] = []
                for item in items:
                    fixed_size = None
                    if isinstance(item, list):
                        names = item
                    elif isinstance(item, dict):
                        if set(item) - {"items", "fixed_size"}:
                            raise ValueError(
                                "worksheet group supports only items and fixed_size"
                            )
                        names = item.get("items")
                        fixed_size = item.get("fixed_size")
                        if fixed_size is not None:
                            _validate_fixed_size(fixed_size)
                    else:
                        raise TypeError(
                            "worksheet container must contain names or worksheet groups"
                        )
                    if (
                        not isinstance(names, list)
                        or not names
                        or not all(
                            isinstance(name, str) and name.strip()
                            for name in names
                        )
                    ):
                        raise TypeError(
                            "worksheet group items must be worksheet names"
                        )
                    groups.append((names, fixed_size))
                    sheet_names.extend(names)
                worksheet_groups[container_name] = groups
        if len(sheet_names) != len(set(sheet_names)):
            raise ValueError("a worksheet can be placed only once on a dashboard")
        if len(filter_specs) != len(set(filter_specs)):
            raise ValueError("a filter can be placed only once on a dashboard")

        worksheets: dict[str, TwbWorksheet] = {}
        for sheet_name in sheet_names:
            matches = get_worksheets(self._context, name=sheet_name)
            if len(matches) != 1:
                raise ValueError(f"worksheet not found: {sheet_name}")
            worksheets[sheet_name] = matches[0]

        filter_fields: dict[tuple[str, str], tuple[TwbWorksheet, str]] = {}
        for datasource_name, field_name in filter_specs:
            datasource_matches = get_datasources(self._context, name=datasource_name)
            if len(datasource_matches) != 1:
                raise ValueError(f"datasource not found or ambiguous: {datasource_name}")
            datasource = datasource_matches[0]
            fields = datasource.get_fields(name=field_name)
            if len(fields) != 1:
                raise ValueError(f"filter field not found or ambiguous: {field_name}")
            reference = (
                f"[{datasource.id}].[none:{fields[0].id.strip('[]')}:nk]"
            )
            worksheet = next(
                (
                    worksheets[sheet_name]
                    for sheet_name in sheet_names
                    if worksheets[sheet_name]._resolve_element().xpath(
                        ".//*[local-name()='slices']"
                        "/*[local-name()='column'][text()=$reference]",
                        reference=reference,
                    )
                ),
                None,
            )
            if worksheet is None:
                raise ValueError(
                    f"filter is not set: ({datasource_name}, {field_name})"
                )
            filter_fields[(datasource_name, field_name)] = (worksheet, reference)

        if self.name != dashboard_name:
            raise ValueError(
                f"dashboard name does not match: expected {self.name}, got {dashboard_name}"
            )
        outer = self.create_container(
            direction="vertical",
            friendly_name=f"{dashboard_name}_外枠",
        )
        outer.add_text(
            dashboard_name,
            fixed_size=header_height,
            friendly_name="ヘッダー",
            font_size=16,
            font_color=header_font_color,
            bold=True,
            style={
                "background_color": header_background_color,
                "border_style": "none",
                "margin": 0,
                "padding": 8,
            },
        )
        root = outer.create_container(
            direction="vertical",
            friendly_name=dashboard_name,
        )
        effective_content_style = dict(_DEFAULT_REPORT_CONTENT_STYLE)
        effective_content_style.update(content_style or {})
        root.update(style=effective_content_style)
        filter_containers: dict[str, TwbDashboardContainer] = {}
        for container_name, items in struct.items():
            fixed_size = container_sizes.get(
                container_name,
                50
                if "フィルタ" in container_name
                else 250
                if "スコア" in container_name
                else 300,
            )
            groups = None if "フィルタ" in container_name else worksheet_groups[container_name]
            item_count = len(groups) if groups is not None else len(items)
            container = root.create_container(
                direction="horizontal",
                fixed_size=fixed_size,
                friendly_name=container_name,
                distribute_evenly=(
                    "フィルタ" not in container_name and item_count > 1
                ),
            )
            if "フィルタ" in container_name:
                filter_containers[container_name] = container
                continue
            if groups is None:
                groups = [([item for item in items if isinstance(item, str)], None)]
            for index, (group, group_fixed_size) in enumerate(groups):
                target = container
                if worksheet_groups[container_name] is not None:
                    target = container.create_container(
                        direction="vertical",
                        weight=1,
                        fixed_size=group_fixed_size,
                        friendly_name=f"{container_name}_{index + 1}",
                        distribute_evenly=len(group) > 1,
                    )
                for sheet_index, sheet_name in enumerate(group):
                    zone = target.add_worksheet(
                        worksheets[sheet_name],
                        show_title=worksheets[sheet_name].title is not None,
                        weight=1,
                    )
                    zone_style = dict(_DEFAULT_REPORT_WORKSHEET_STYLE)
                    if worksheet_groups[container_name] is not None and len(group) > 1:
                        if sheet_index < len(group) - 1:
                            zone_style["padding_bottom"] = 0
                            zone_style["margin_bottom"] = 0
                        if sheet_index > 0:
                            zone_style["padding_top"] = 0
                            zone_style["margin_top"] = 0
                    zone.update(style=zone_style)
        for container_name, items in struct.items():
            if container_name not in filter_containers:
                continue
            container = filter_containers[container_name]
            for item in items:
                assert isinstance(item, tuple)
                worksheet, reference = filter_fields[item]
                zone = container._add_filter_reference(worksheet, reference)
                zone.update(
                    style={
                        "background_color": "#ffffff",
                        "border_style": "none",
                        "margin": 4,
                        "padding": 4,
                    }
                )
        root.add_spacer(
            style={"background_color": "#f5f5f5", "border_style": "none", "margin": 0}
        )
        return self

    def create_container(
        self,
        *,
        direction: str = "horizontal",
        friendly_name: str | None = None,
        distribute_evenly: bool = False,
    ) -> TwbDashboardContainer:
        direction = direction.lower()
        if direction not in _DIRECTIONS:
            raise ValueError(f"unsupported direction: {direction}")
        if not isinstance(distribute_evenly, bool):
            raise TypeError("distribute_evenly must be bool")
        dashboard_el = self._resolve_element()
        zones_el = _default_zones(dashboard_el)
        if zones_el is not None and any(_is_container(zone) for zone in _direct_zones(zones_el)):
            raise ValueError("dashboard already has a root tiled container")

        updated = copy.deepcopy(dashboard_el)
        updated_zones = _default_zones(updated, create=True)
        assert updated_zones is not None
        zone_id = _next_zone_id(updated)
        container_el = ET.Element(
            "zone",
            attrib={
                "id": zone_id,
                "type-v2": "layout-flow",
                "param": _DIRECTIONS[direction],
                "x": "0",
                "y": "0",
                "w": "100000",
                "h": "100000",
            },
        )
        if friendly_name is not None:
            container_el.set("friendly-name", friendly_name)
        if distribute_evenly:
            container_el.set("layout-strategy-id", "distribute-evenly")
        _insert_zone(updated_zones, container_el, 0)
        _replace_if_changed(dashboard_el, updated, self._context)
        return TwbDashboardContainer(self._context, self._id, zone_id)

    def add_floating_worksheet(
        self,
        worksheet: TwbWorksheet,
        *,
        x: float = 0,
        y: float = 0,
        width: float = 600,
        height: float = 400,
        show_title: bool = True,
    ) -> TwbDashboardZone:
        _validate_worksheet(worksheet, self._context)
        if not isinstance(show_title, bool):
            raise TypeError("show_title must be bool")
        x = _validate_pixel(x, "x")
        y = _validate_pixel(y, "y")
        width = _validate_pixel(width, "width", positive=True)
        height = _validate_pixel(height, "height", positive=True)
        dashboard_el = self._resolve_element()
        if _contains_worksheet(dashboard_el, worksheet.id):
            raise ValueError(f"worksheet is already placed on dashboard: {worksheet.id}")
        canvas_width, canvas_height = _canvas_or_error(dashboard_el)

        updated = copy.deepcopy(dashboard_el)
        zones_el = _default_zones(updated, create=True)
        assert zones_el is not None
        zone_id = _next_zone_id(updated)
        zone_el = ET.Element(
            "zone",
            attrib={
                "id": zone_id,
                "name": worksheet.id,
                "x": str(_px_to_raw(x, canvas_width)),
                "y": str(_px_to_raw(y, canvas_height)),
                "w": str(_px_to_raw(width, canvas_width)),
                "h": str(_px_to_raw(height, canvas_height)),
                "show-title": "true" if show_title else "false",
            },
        )
        zones_el.append(zone_el)
        _replace_if_changed(dashboard_el, updated, self._context)
        _sync_dashboard_window(self._context, self._id)
        return TwbDashboardZone(self._context, self._id, zone_id)

    def update(
        self,
        *,
        name: str | None | _UnsetType = UNSET,
        visible: bool | _UnsetType = UNSET,
    ) -> TwbDashboard:
        dashboard_el = self._resolve_element()
        if name is not UNSET and name is not None:
            name = name.strip()
            if not name:
                raise ValueError("name must not be empty")
            for other in dashboard_elements(self._context.tree):
                if other is not dashboard_el and get_display_name(other) == name:
                    raise ValueError(f"dashboard name already exists: {name}")
        if visible is not UNSET and not isinstance(visible, bool):
            raise TypeError("visible must be bool")

        root = self._context.tree.getroot()
        updated_root = copy.deepcopy(root)
        updated_dashboard = updated_root.xpath(
            "/workbook/dashboards/dashboard[@name=$id]",
            id=self._id,
        )[0]
        if name is not UNSET:
            if name is None:
                updated_dashboard.attrib.pop("caption", None)
            else:
                updated_dashboard.set("caption", name)
        if visible is not UNSET:
            windows = updated_root.xpath(
                "/workbook/windows/window[@class='dashboard'][@name=$id]",
                id=self._id,
            )
            if windows:
                windows[0].set("hidden", "false" if visible else "true")
            elif not visible:
                windows_el = _direct_child(updated_root, "windows")
                if windows_el is None:
                    windows_el = ET.Element("windows")
                    updated_root.insert(0, windows_el)
                ET.SubElement(
                    windows_el,
                    "window",
                    attrib={"class": "dashboard", "name": self._id, "hidden": "true"},
                )
        if ET.tostring(root) != ET.tostring(updated_root):
            self._context.tree._setroot(updated_root)
            self._context.mark_dirty()
        return self

    def delete(self) -> None:
        self._resolve_element()
        references = dashboard_references(self._context.tree, self._id)
        if references:
            raise ResourceInUseError("Dashboard", self._id, references)

        root = self._context.tree.getroot()
        updated_root = copy.deepcopy(root)
        dashboards = updated_root.xpath(
            "/workbook/dashboards/dashboard[@name=$id]",
            id=self._id,
        )
        if len(dashboards) != 1 or dashboards[0].getparent() is None:
            raise DetachedModelError(f"dashboard is detached: {self._id}")
        dashboards[0].getparent().remove(dashboards[0])
        for window in updated_root.xpath(
            "/workbook/windows/window[@class='dashboard'][@name=$id]",
            id=self._id,
        ):
            parent = window.getparent()
            if parent is not None:
                parent.remove(window)
        self._context.tree._setroot(updated_root)
        self._context.mark_dirty()
        self._detach()


class TwbDashboardContainer(ConnectedModel):
    def __init__(self, context: WorkbookContext, dashboard_id: str, container_id: str):
        super().__init__(context)
        self._dashboard_id = dashboard_id
        self._id = container_id

    def _resolve_dashboard_element(self) -> ET._Element:
        return TwbDashboard(self._context, self._dashboard_id)._resolve_element()

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        zone_el = _resolve_zone(self._resolve_dashboard_element(), self._id)
        if not _is_container(zone_el):
            self._detach()
            raise DetachedModelError(f"dashboard container is detached: {self._id}")
        return zone_el

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        return self._resolve_element().get("friendly-name") or self.id

    @property
    def friendly_name(self) -> str | None:
        return self._resolve_element().get("friendly-name")

    @property
    def fixed_size(self) -> int | None:
        value = self._resolve_element().get("fixed-size")
        return int(value) if value and value.isdigit() else None

    @property
    def hidden(self) -> bool:
        return (self._resolve_element().get("hidden-by-user") or "false").lower() == "true"

    @property
    def style(self) -> dict[str, str]:
        """ゾーンスタイル。`update(style=...)` と対になる。"""
        return _zone_style_values(self._resolve_element())

    @property
    def direction(self) -> str:
        return _container_direction(self._resolve_element())

    @property
    def distribute_evenly(self) -> bool:
        return self._resolve_element().get("layout-strategy-id") == "distribute-evenly"

    @property
    def order(self) -> int | None:
        element = self._resolve_element()
        parent = element.getparent()
        if parent is None or _local_name(parent) == "zones":
            return None
        return _direct_zones(parent).index(element)

    @property
    def weight(self) -> float | None:
        element = self._resolve_element()
        parent = element.getparent()
        if parent is None or _local_name(parent) == "zones":
            return None
        return _derived_weights(
            self._dashboard_id,
            parent,
            self._context.layout_weights,
        )[self._id]

    def get_containers(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbDashboardContainer]:
        _validate_get_args(id, name)
        result: list[TwbDashboardContainer] = []
        for child in _direct_zones(self._resolve_element()):
            child_id = child.get("id")
            if not _is_container(child) or not child_id:
                continue
            child_name = child.get("friendly-name") or child_id
            if _matches(model_id=child_id, model_name=child_name, id=id, name=name):
                result.append(TwbDashboardContainer(self._context, self._dashboard_id, child_id))
        return result

    def get_zones(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> list[TwbDashboardZone]:
        _validate_get_args(id, name)
        result: list[TwbDashboardZone] = []
        for child in _direct_zones(self._resolve_element()):
            child_id = child.get("id")
            if _is_container(child) or not child_id:
                continue
            child_name = _zone_display_name(self._context, child)
            if _matches(model_id=child_id, model_name=child_name, id=id, name=name):
                result.append(TwbDashboardZone(self._context, self._dashboard_id, child_id))
        return result

    def create_container(
        self,
        *,
        direction: str = "vertical",
        order: int | None = None,
        weight: float = 1,
        fixed_size: int | None = None,
        friendly_name: str | None = None,
        hidden: bool = False,
        distribute_evenly: bool = False,
    ) -> TwbDashboardContainer:
        direction = direction.lower()
        if direction not in _DIRECTIONS:
            raise ValueError(f"unsupported direction: {direction}")
        weight = _validate_weight(weight)
        fixed_size = _validate_fixed_size(fixed_size)
        if not isinstance(hidden, bool):
            raise TypeError("hidden must be bool")
        if not isinstance(distribute_evenly, bool):
            raise TypeError("distribute_evenly must be bool")
        dashboard_el = self._resolve_dashboard_element()
        updated = copy.deepcopy(dashboard_el)
        parent = _resolve_zone(updated, self._id)
        zone_id = _next_zone_id(updated)
        child = ET.Element(
            "zone",
            attrib={"id": zone_id, "type-v2": "layout-flow", "param": _DIRECTIONS[direction]},
        )
        if friendly_name is not None:
            child.set("friendly-name", friendly_name)
        if distribute_evenly:
            child.set("layout-strategy-id", "distribute-evenly")
        _set_fixed_size(child, fixed_size)
        if hidden:
            child.set("hidden-by-user", "true")
        _insert_zone(parent, child, order)
        weights = dict(self._context.layout_weights)
        weights[(self._dashboard_id, zone_id)] = weight
        _layout_container(self._dashboard_id, parent, weights)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        return TwbDashboardContainer(self._context, self._dashboard_id, zone_id)

    def add_worksheet(
        self,
        worksheet: TwbWorksheet,
        *,
        order: int | None = None,
        weight: float = 1,
        show_title: bool = True,
        fixed_size: int | None = None,
        friendly_name: str | None = None,
    ) -> TwbDashboardZone:
        _validate_worksheet(worksheet, self._context)
        weight = _validate_weight(weight)
        fixed_size = _validate_fixed_size(fixed_size)
        if not isinstance(show_title, bool):
            raise TypeError("show_title must be bool")
        dashboard_el = self._resolve_dashboard_element()
        if _contains_worksheet(dashboard_el, worksheet.id):
            raise ValueError(f"worksheet is already placed on dashboard: {worksheet.id}")
        updated = copy.deepcopy(dashboard_el)
        parent = _resolve_zone(updated, self._id)
        zone_id = _next_zone_id(updated)
        child = ET.Element(
            "zone",
            attrib={
                "id": zone_id,
                "name": worksheet.id,
                "show-title": "true" if show_title else "false",
            },
        )
        if friendly_name is not None:
            child.set("friendly-name", friendly_name)
        _set_fixed_size(child, fixed_size)
        _insert_zone(parent, child, order)
        weights = dict(self._context.layout_weights)
        weights[(self._dashboard_id, zone_id)] = weight
        _layout_container(self._dashboard_id, parent, weights)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        _sync_dashboard_window(self._context, self._dashboard_id)
        return TwbDashboardZone(self._context, self._dashboard_id, zone_id)

    def add_filter(
        self,
        field: TwbWorksheetField,
        *,
        mode: str = "checkdropdown",
        order: int | None = None,
        weight: float = 1,
    ) -> TwbDashboardZone:
        if not isinstance(field, TwbWorksheetField):
            raise TypeError("field must be TwbWorksheetField")
        if field._context is not self._context or field.shelf != "filters":
            raise ValueError("field must be a worksheet filter in the same workbook")
        if mode not in {"dropdown", "checkdropdown", "list", "compact"}:
            raise ValueError(f"unsupported filter mode: {mode}")
        reference = field._resolve_placement().reference
        return self._add_filter_reference(
            TwbWorksheet(self._context, field._worksheet_id),
            reference,
            mode=mode,
            order=order,
            weight=weight,
        )

    def _add_filter_reference(
        self,
        worksheet: TwbWorksheet,
        reference: str,
        *,
        mode: str = "checkdropdown",
        order: int | None = None,
        weight: float = 1,
    ) -> TwbDashboardZone:
        _validate_worksheet(worksheet, self._context)
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("reference must be a non-empty string")
        if mode not in {"dropdown", "checkdropdown", "list", "compact"}:
            raise ValueError(f"unsupported filter mode: {mode}")
        weight = _validate_weight(weight)

        dashboard_el = self._resolve_dashboard_element()
        if not _contains_worksheet(dashboard_el, worksheet.id):
            raise ValueError("filter worksheet must be placed on the dashboard")
        if dashboard_el.xpath(
            ".//*[local-name()='zone'][@type-v2='filter'][@param=$reference]",
            reference=reference,
        ):
            raise ValueError(f"filter is already placed on dashboard: {reference}")

        updated = copy.deepcopy(dashboard_el)
        parent = _resolve_zone(updated, self._id)
        zone_id = _next_zone_id(updated)
        child = ET.Element(
            "zone",
            attrib={
                "id": zone_id,
                "type-v2": "filter",
                "name": worksheet.id,
                "param": reference,
                "mode": mode,
            },
        )
        _insert_zone(parent, child, order)
        weights = dict(self._context.layout_weights)
        weights[(self._dashboard_id, zone_id)] = weight
        _layout_container(self._dashboard_id, parent, weights)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        return TwbDashboardZone(self._context, self._dashboard_id, zone_id)

    def _add_object(
        self,
        *,
        type_v2: str,
        order: int | None,
        weight: float,
        fixed_size: int | None,
        friendly_name: str | None,
        style: dict[str, str | int] | None,
        text: str | None = None,
        font_size: int = 12,
        font_color: str = "#333333",
        bold: bool = False,
    ) -> TwbDashboardZone:
        weight = _validate_weight(weight)
        fixed_size = _validate_fixed_size(fixed_size)
        dashboard_el = self._resolve_dashboard_element()
        updated = copy.deepcopy(dashboard_el)
        parent = _resolve_zone(updated, self._id)
        zone_id = _next_zone_id(updated)
        child = ET.Element("zone", attrib={"id": zone_id, "type-v2": type_v2})
        if friendly_name is not None:
            child.set("friendly-name", friendly_name)
        _set_fixed_size(child, fixed_size)
        if type_v2 == "bitmap":
            child.set("is-centered", "0")
        if text is not None:
            child.set("forceUpdate", "true")
            formatted = ET.SubElement(child, "formatted-text")
            attrs = {"fontsize": str(font_size), "fontcolor": font_color}
            if bold:
                attrs["bold"] = "true"
            ET.SubElement(formatted, "run", attrib=attrs).text = text
        if style:
            _set_zone_styles(child, style)
        _insert_zone(parent, child, order)
        weights = dict(self._context.layout_weights)
        weights[(self._dashboard_id, zone_id)] = weight
        _layout_container(self._dashboard_id, parent, weights)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        return TwbDashboardZone(self._context, self._dashboard_id, zone_id)

    def add_text(
        self,
        text: str,
        *,
        order: int | None = None,
        weight: float = 1,
        fixed_size: int | None = None,
        friendly_name: str | None = None,
        font_size: int = 12,
        font_color: str = "#333333",
        bold: bool = False,
        style: dict[str, str | int] | None = None,
    ) -> TwbDashboardZone:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if isinstance(font_size, bool) or not isinstance(font_size, int) or font_size <= 0:
            raise ValueError("font_size must be a positive integer")
        return self._add_object(
            type_v2="text", order=order, weight=weight, fixed_size=fixed_size,
            friendly_name=friendly_name, style=style, text=text,
            font_size=font_size, font_color=font_color, bold=bold,
        )

    def add_image(
        self,
        *,
        order: int | None = None,
        weight: float = 1,
        fixed_size: int | None = None,
        friendly_name: str | None = None,
        style: dict[str, str | int] | None = None,
    ) -> TwbDashboardZone:
        return self._add_object(
            type_v2="bitmap", order=order, weight=weight, fixed_size=fixed_size,
            friendly_name=friendly_name, style=style,
        )

    def add_spacer(
        self,
        *,
        order: int | None = None,
        weight: float = 1,
        fixed_size: int | None = None,
        friendly_name: str | None = None,
        style: dict[str, str | int] | None = None,
    ) -> TwbDashboardZone:
        return self._add_object(
            type_v2="empty", order=order, weight=weight, fixed_size=fixed_size,
            friendly_name=friendly_name, style=style,
        )

    def update(
        self,
        *,
        direction: str | _UnsetType = UNSET,
        order: int | _UnsetType = UNSET,
        weight: float | _UnsetType = UNSET,
        fixed_size: int | None | _UnsetType = UNSET,
        friendly_name: str | None | _UnsetType = UNSET,
        hidden: bool | _UnsetType = UNSET,
        distribute_evenly: bool | _UnsetType = UNSET,
        style: dict[str, str | int | None] | _UnsetType = UNSET,
    ) -> TwbDashboardContainer:
        style = _validate_style_group("style", style)
        if direction is not UNSET:
            if not isinstance(direction, str):
                raise TypeError("direction must be a string")
            direction = direction.lower()
            if direction not in _DIRECTIONS:
                raise ValueError(f"unsupported direction: {direction}")
        if weight is not UNSET:
            weight = _validate_weight(weight)
        if fixed_size is not UNSET:
            fixed_size = _validate_fixed_size(fixed_size)
        if hidden is not UNSET and not isinstance(hidden, bool):
            raise TypeError("hidden must be bool")
        if distribute_evenly is not UNSET and not isinstance(distribute_evenly, bool):
            raise TypeError("distribute_evenly must be bool")

        dashboard_el = self._resolve_dashboard_element()
        current = self._resolve_element()
        current_parent = current.getparent()
        if current_parent is None:
            raise DetachedModelError(f"dashboard container is detached: {self._id}")
        is_root = _local_name(current_parent) == "zones"
        if is_root and (order is not UNSET or weight is not UNSET):
            raise ValueError("root container has no order or weight")

        updated = copy.deepcopy(dashboard_el)
        container = _resolve_zone(updated, self._id)
        parent = container.getparent()
        assert parent is not None
        weights = dict(self._context.layout_weights)
        if direction is not UNSET:
            container.set("param", _DIRECTIONS[direction])
        if fixed_size is not UNSET:
            _set_fixed_size(container, fixed_size)
        if friendly_name is not UNSET:
            if friendly_name is None:
                container.attrib.pop("friendly-name", None)
            else:
                container.set("friendly-name", friendly_name)
        if hidden is not UNSET:
            if hidden:
                container.set("hidden-by-user", "true")
            else:
                container.attrib.pop("hidden-by-user", None)
        if distribute_evenly is not UNSET:
            if distribute_evenly:
                container.set("layout-strategy-id", "distribute-evenly")
            else:
                container.attrib.pop("layout-strategy-id", None)
        if style is not UNSET:
            _set_zone_styles(container, style)
            _layout_container(self._dashboard_id, container, weights)
        if not is_root:
            if order is not UNSET:
                _move_zone(parent, container, order)
            if weight is not UNSET:
                weights[(self._dashboard_id, self._id)] = weight
            _layout_container(self._dashboard_id, parent, weights)
        elif direction is not UNSET or distribute_evenly is not UNSET:
            _layout_container(self._dashboard_id, container, weights)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        return self

    def delete(self) -> None:
        container = self._resolve_element()
        children = _direct_zones(container)
        if children:
            references = [
                ResourceReference(
                    resource_type="DashboardContainer" if _is_container(child) else "DashboardZone",
                    resource_id=child.get("id") or "",
                    location=f"dashboard:{self._dashboard_id}/container:{self._id}",
                )
                for child in children
            ]
            raise ResourceInUseError("DashboardContainer", self._id, references)

        dashboard_el = self._resolve_dashboard_element()
        updated = copy.deepcopy(dashboard_el)
        target = _resolve_zone(updated, self._id)
        parent = target.getparent()
        if parent is None:
            raise DetachedModelError(f"dashboard container is detached: {self._id}")
        parent.remove(target)
        weights = dict(self._context.layout_weights)
        weights.pop((self._dashboard_id, self._id), None)
        if _local_name(parent) == "zone" and _is_container(parent):
            _layout_container(self._dashboard_id, parent, weights)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        self._detach()


class TwbDashboardZone(ConnectedModel):
    def __init__(self, context: WorkbookContext, dashboard_id: str, zone_id: str):
        super().__init__(context)
        self._dashboard_id = dashboard_id
        self._id = zone_id

    def _resolve_dashboard_element(self) -> ET._Element:
        return TwbDashboard(self._context, self._dashboard_id)._resolve_element()

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        zone_el = _resolve_zone(self._resolve_dashboard_element(), self._id)
        if _is_container(zone_el):
            self._detach()
            raise DetachedModelError(f"dashboard zone is detached: {self._id}")
        return zone_el

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        return _zone_display_name(self._context, self._resolve_element())

    @property
    def kind(self) -> str:
        return _zone_kind(self._resolve_element(), set(_worksheet_names(self._context)))

    @property
    def friendly_name(self) -> str | None:
        return self._resolve_element().get("friendly-name")

    @property
    def fixed_size(self) -> int | None:
        value = self._resolve_element().get("fixed-size")
        return int(value) if value and value.isdigit() else None

    @property
    def hidden(self) -> bool:
        return (self._resolve_element().get("hidden-by-user") or "false").lower() == "true"

    @property
    def text(self) -> str | None:
        formatted = _direct_child(self._resolve_element(), "formatted-text")
        return None if formatted is None else "".join(formatted.itertext())

    @property
    def style(self) -> dict[str, str]:
        """ゾーンスタイル。`update(style=...)` と対になる。"""
        return _zone_style_values(self._resolve_element())

    @property
    def worksheet_id(self) -> str | None:
        zone_name = self._resolve_element().get("name")
        return zone_name if zone_name in _worksheet_names(self._context) else None

    @property
    def placement_mode(self) -> str:
        parent = self._resolve_element().getparent()
        return "tiled" if parent is not None and _local_name(parent) == "zone" and _is_container(parent) else "floating"

    @property
    def order(self) -> int | None:
        element = self._resolve_element()
        parent = element.getparent()
        if self.placement_mode != "tiled" or parent is None:
            return None
        return _direct_zones(parent).index(element)

    @property
    def weight(self) -> float | None:
        element = self._resolve_element()
        parent = element.getparent()
        if self.placement_mode != "tiled" or parent is None:
            return None
        return _derived_weights(
            self._dashboard_id,
            parent,
            self._context.layout_weights,
        )[self._id]

    @property
    def show_title(self) -> bool | None:
        value = self._resolve_element().get("show-title")
        return None if value is None else value.lower() == "true"

    def _pixel_rect(self) -> tuple[int | None, int | None, int | None, int | None]:
        dashboard_el = self._resolve_dashboard_element()
        _, width, height = _dashboard_size(dashboard_el)
        if width is None or height is None:
            return None, None, None, None
        x, y, zone_width, zone_height = _zone_rect(self._resolve_element())
        return (
            _raw_to_px(x, width),
            _raw_to_px(y, height),
            _raw_to_px(zone_width, width),
            _raw_to_px(zone_height, height),
        )

    @property
    def x(self) -> int | None:
        return self._pixel_rect()[0]

    @property
    def y(self) -> int | None:
        return self._pixel_rect()[1]

    @property
    def width(self) -> int | None:
        return self._pixel_rect()[2]

    @property
    def height(self) -> int | None:
        return self._pixel_rect()[3]

    def update(
        self,
        *,
        order: int | _UnsetType = UNSET,
        weight: float | _UnsetType = UNSET,
        x: float | _UnsetType = UNSET,
        y: float | _UnsetType = UNSET,
        width: float | _UnsetType = UNSET,
        height: float | _UnsetType = UNSET,
        show_title: bool | _UnsetType = UNSET,
        fixed_size: int | None | _UnsetType = UNSET,
        friendly_name: str | None | _UnsetType = UNSET,
        hidden: bool | _UnsetType = UNSET,
        style: dict[str, str | int | None] | _UnsetType = UNSET,
    ) -> TwbDashboardZone:
        style = _validate_style_group("style", style)
        mode = self.placement_mode
        coordinate_values = (x, y, width, height)
        if mode == "tiled" and any(value is not UNSET for value in coordinate_values):
            raise ValueError("tiled zones do not accept x, y, width, or height")
        if mode == "floating" and (order is not UNSET or weight is not UNSET):
            raise ValueError("floating zones do not accept order or weight")
        if weight is not UNSET:
            weight = _validate_weight(weight)
        if fixed_size is not UNSET:
            fixed_size = _validate_fixed_size(fixed_size)
        if show_title is not UNSET and not isinstance(show_title, bool):
            raise TypeError("show_title must be bool")
        if hidden is not UNSET and not isinstance(hidden, bool):
            raise TypeError("hidden must be bool")

        dashboard_el = self._resolve_dashboard_element()
        canvas_width: int | None = None
        canvas_height: int | None = None
        if mode == "floating" and any(value is not UNSET for value in coordinate_values):
            canvas_width, canvas_height = _canvas_or_error(dashboard_el)
            if x is not UNSET:
                x = _validate_pixel(x, "x")
            if y is not UNSET:
                y = _validate_pixel(y, "y")
            if width is not UNSET:
                width = _validate_pixel(width, "width", positive=True)
            if height is not UNSET:
                height = _validate_pixel(height, "height", positive=True)

        updated = copy.deepcopy(dashboard_el)
        zone = _resolve_zone(updated, self._id)
        parent = zone.getparent()
        if parent is None:
            raise DetachedModelError(f"dashboard zone is detached: {self._id}")
        weights = dict(self._context.layout_weights)
        if mode == "tiled":
            if order is not UNSET:
                _move_zone(parent, zone, order)
            if weight is not UNSET:
                weights[(self._dashboard_id, self._id)] = weight
            if fixed_size is not UNSET:
                _set_fixed_size(zone, fixed_size)
            _layout_container(self._dashboard_id, parent, weights)
        else:
            if fixed_size is not UNSET:
                raise ValueError("floating zones do not accept fixed_size")
            assert canvas_width is not None or all(value is UNSET for value in coordinate_values)
            if x is not UNSET:
                zone.set("x", str(_px_to_raw(x, canvas_width or 1)))
            if y is not UNSET:
                zone.set("y", str(_px_to_raw(y, canvas_height or 1)))
            if width is not UNSET:
                zone.set("w", str(_px_to_raw(width, canvas_width or 1)))
            if height is not UNSET:
                zone.set("h", str(_px_to_raw(height, canvas_height or 1)))
        if show_title is not UNSET:
            zone.set("show-title", "true" if show_title else "false")
        if friendly_name is not UNSET:
            if friendly_name is None:
                zone.attrib.pop("friendly-name", None)
            else:
                zone.set("friendly-name", friendly_name)
        if hidden is not UNSET:
            if hidden:
                zone.set("hidden-by-user", "true")
            else:
                zone.attrib.pop("hidden-by-user", None)
        if style is not UNSET:
            _set_zone_styles(zone, style)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        return self

    def delete(self) -> None:
        mode = self.placement_mode
        was_worksheet = self.worksheet_id is not None
        dashboard_el = self._resolve_dashboard_element()
        updated = copy.deepcopy(dashboard_el)
        zone = _resolve_zone(updated, self._id)
        parent = zone.getparent()
        if parent is None:
            raise DetachedModelError(f"dashboard zone is detached: {self._id}")
        parent.remove(zone)
        weights = dict(self._context.layout_weights)
        weights.pop((self._dashboard_id, self._id), None)
        if mode == "tiled":
            _layout_container(self._dashboard_id, parent, weights)
        _replace_if_changed(dashboard_el, updated, self._context)
        self._context.layout_weights = weights
        if was_worksheet:
            _sync_dashboard_window(self._context, self._dashboard_id)
        self._detach()


class TwbFilterControl(TwbDashboardZone):
    """ダッシュボードに置かれたフィルタ（`zone[@type-v2='filter']`）。

    XML 上は Zone そのものなので、座標・スタイル・表示/非表示の `update()` と
    `delete()` は `TwbDashboardZone` から引き継ぐ。ここで足すのは、
    どのフィールドのフィルタかという読み取りだけ。
    """

    def _resolve_element(self) -> ET._Element:
        zone_el = super()._resolve_element()
        if (zone_el.get("type-v2") or zone_el.get("type")) != "filter":
            self._detach()
            raise DetachedModelError(f"dashboard zone is not a filter: {self._id}")
        return zone_el

    @property
    def column(self) -> str | None:
        """フィルタ対象の XML 内部参照。"""
        return self._resolve_element().get("param")

    @property
    def field(self) -> str | None:
        """フィルタ対象の解決済みフィールド名。"""
        return self._filter_snapshot("field")

    @property
    def role(self) -> str | None:
        return self._filter_snapshot("role")

    @property
    def mode(self) -> str | None:
        """表示形式（`checkdropdown` など）。"""
        return self._resolve_element().get("mode")

    @property
    def worksheet(self) -> str | None:
        """フィルタの出どころになっているワークシートの表示名。"""
        return self._filter_snapshot("worksheet")

    @property
    def show_apply(self) -> bool | None:
        return self._filter_snapshot("show_apply")

    @property
    def show_caption(self) -> bool | None:
        return self._filter_snapshot("show_caption")

    # 以下は参照先のワークシートフィルタ由来の読み取り。
    # 変更は TwbWorksheetFilter 側で行う。

    @property
    def filter_class(self) -> str | None:
        return self._filter_snapshot("filter_class")

    @property
    def domain(self) -> str | None:
        return self._filter_snapshot("domain")

    @property
    def enumeration(self) -> str | None:
        return self._filter_snapshot("enumeration")

    @property
    def value_scope(self) -> str | None:
        return self._filter_snapshot("value_scope")

    @property
    def value_scope_label(self) -> str | None:
        return self._filter_snapshot("value_scope_label")

    @property
    def apply_scope(self) -> str | None:
        return self._filter_snapshot("apply_scope")

    @property
    def apply_scope_label(self) -> str | None:
        return self._filter_snapshot("apply_scope_label")

    @property
    def selection_type(self) -> str | None:
        return self._filter_snapshot("selection_type")

    @property
    def values(self) -> list[str]:
        return self._filter_snapshot("values") or []

    def _filter_snapshot(self, attribute: str) -> Any:
        column = self.column
        if column is None:
            return None
        for control in list_dashboard_filter_controls_from_tree(
            self._context.tree,
            self._dashboard_id,
            by="name",
        ):
            if control.id == self._id:
                return getattr(control, attribute)
        return None


def get_dashboards(
    context: WorkbookContext,
    *,
    id: str | None = None,
    name: str | None = None,
) -> list[TwbDashboard]:
    _validate_get_args(id, name)
    result: list[TwbDashboard] = []
    for dashboard_el in dashboard_elements(context.tree):
        dashboard_id = dashboard_el.get("name")
        if not dashboard_id:
            continue
        dashboard_name = get_display_name(dashboard_el)
        if _matches(model_id=dashboard_id, model_name=dashboard_name, id=id, name=name):
            result.append(TwbDashboard(context, dashboard_id))
    return result


def create_dashboard(
    context: WorkbookContext,
    *,
    name: str,
    width: int = 1200,
    height: int = 800,
    sizing_mode: str = "fixed",
) -> TwbDashboard:
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    if any(
        element.get("name") == name or get_display_name(element) == name
        for element in dashboard_elements(context.tree)
    ):
        raise ValueError(f"dashboard already exists: {name}")
    sizing_mode = sizing_mode.lower()
    if sizing_mode not in {"fixed", "automatic"}:
        raise ValueError(f"unsupported sizing mode: {sizing_mode}")
    if sizing_mode == "fixed":
        if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
            raise ValueError("width must be a positive integer")
        if isinstance(height, bool) or not isinstance(height, int) or height <= 0:
            raise ValueError("height must be a positive integer")

    root = context.tree.getroot()
    dashboards_el = _direct_child(root, "dashboards")
    if dashboards_el is None:
        dashboards_el = ET.Element("dashboards")
        worksheets_el = _direct_child(root, "worksheets")
        if worksheets_el is None:
            root.append(dashboards_el)
        else:
            root.insert(root.index(worksheets_el) + 1, dashboards_el)
    dashboard_el = ET.SubElement(dashboards_el, "dashboard", attrib={"name": name})
    ET.SubElement(dashboard_el, "style")
    size_attrs = {"sizing-mode": sizing_mode}
    if sizing_mode == "fixed":
        size_attrs.update(
            {
                "minwidth": str(width),
                "maxwidth": str(width),
                "minheight": str(height),
                "maxheight": str(height),
            }
        )
    ET.SubElement(dashboard_el, "size", attrib=size_attrs)
    ET.SubElement(dashboard_el, "zones")
    ET.SubElement(
        dashboard_el,
        "simple-id",
        attrib={"uuid": f"{{{str(uuid.uuid4()).upper()}}}"},
    )
    context.mark_dirty()
    return TwbDashboard(context, name)
