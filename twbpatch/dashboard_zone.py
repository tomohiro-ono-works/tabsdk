from __future__ import annotations

import math

from lxml import etree as ET

from .field_ref import attrs
from .models import TwbDashboardZone
from .window import bool_attr


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def _int_attr(node: ET._Element, name: str) -> int | None:
    value = node.get(name)
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _round_half_away_from_zero(value: float) -> int:
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def _to_px(value: int | None, canvas_size: int | None) -> int | None:
    if value is None or canvas_size is None:
        return None
    return _round_half_away_from_zero(value * canvas_size / 100000)


def _size_element(owner: ET._Element) -> ET._Element | None:
    sizes = owner.xpath("./*[local-name()='size']")
    return sizes[0] if sizes else None


def _fixed_dimension(size_el: ET._Element | None, minimum: str, maximum: str) -> int | None:
    if size_el is None or size_el.get("sizing-mode") != "fixed":
        return None
    minimum_value = _int_attr(size_el, minimum)
    maximum_value = _int_attr(size_el, maximum)
    return minimum_value if minimum_value is not None else maximum_value


def _device_layout(zone: ET._Element, dashboard_el: ET._Element) -> ET._Element | None:
    for ancestor in zone.iterancestors():
        if ancestor is dashboard_el:
            return None
        local_name = _local_name(ancestor).lower().replace("-", "")
        if local_name in {"devicelayout", "devicelayoutitem"}:
            return ancestor
    return None


def _layout_name(device_layout: ET._Element | None) -> str:
    if device_layout is None:
        return "default"
    return (
        device_layout.get("name")
        or device_layout.get("device-type")
        or device_layout.get("type")
        or "device"
    )


def _zone_text(zone: ET._Element, zone_type: str | None) -> str | None:
    if zone_type not in {"text", "title"}:
        return None
    values = [str(value).strip() for value in zone.xpath("./*[not(local-name()='zone')]//text()")]
    text = " ".join(value for value in values if value)
    return text or None


def list_zones_from_dashboard(
    dashboard_el: ET._Element,
    *,
    width_px: int | None = None,
    height_px: int | None = None,
    include_device_layouts: bool = False,
) -> list[TwbDashboardZone]:
    tree = dashboard_el.getroottree()
    dashboard_id = dashboard_el.get("name")
    dashboard = dashboard_el.get("caption") or dashboard_id or ""
    worksheets = {
        str(worksheet.get("name")): worksheet.get("caption") or worksheet.get("name") or ""
        for worksheet in tree.getroot().xpath("/workbook/worksheets/worksheet[@name]")
    }
    dashboard_size = _size_element(dashboard_el)
    result: list[TwbDashboardZone] = []

    for zone in dashboard_el.xpath(".//*[local-name()='zone']"):
        device_layout = _device_layout(zone, dashboard_el)
        if device_layout is not None and not include_device_layouts:
            continue

        size_el = _size_element(device_layout) if device_layout is not None else dashboard_size
        if size_el is None:
            size_el = dashboard_size
        canvas_width = width_px if width_px is not None else _fixed_dimension(size_el, "minwidth", "maxwidth")
        canvas_height = height_px if height_px is not None else _fixed_dimension(size_el, "minheight", "maxheight")
        parent = next((item for item in zone.iterancestors() if _local_name(item) == "zone"), None)
        zone_name = zone.get("name")
        worksheet_id = zone_name if zone_name in worksheets else None
        zone_type = zone.get("type-v2") or zone.get("type")
        if zone_type is None and worksheet_id is not None:
            zone_type = "worksheet"
        x_raw = _int_attr(zone, "x")
        y_raw = _int_attr(zone, "y")
        width_raw = _int_attr(zone, "w")
        height_raw = _int_attr(zone, "h")

        result.append(
            TwbDashboardZone(
                dashboard=dashboard,
                dashboard_id=dashboard_id,
                id=zone.get("id"),
                parent_id=parent.get("id") if parent is not None else None,
                depth=sum(1 for item in zone.iterancestors() if _local_name(item) == "zone"),
                name=zone_name,
                type=zone_type,
                worksheet=worksheets.get(worksheet_id) if worksheet_id is not None else None,
                worksheet_id=worksheet_id,
                mode=zone.get("mode"),
                param=zone.get("param"),
                url=zone.get("url"),
                text=_zone_text(zone, zone_type),
                layout=_layout_name(device_layout),
                sizing_mode=size_el.get("sizing-mode") if size_el is not None else None,
                dashboard_width_px=canvas_width,
                dashboard_height_px=canvas_height,
                x_raw=x_raw,
                x_px=_to_px(x_raw, canvas_width),
                y_raw=y_raw,
                y_px=_to_px(y_raw, canvas_height),
                width_raw=width_raw,
                width_px=_to_px(width_raw, canvas_width),
                height_raw=height_raw,
                height_px=_to_px(height_raw, canvas_height),
                fixed_size=_int_attr(zone, "fixed-size"),
                is_fixed=bool_attr(zone.get("is-fixed"), None),
                is_scaled=bool_attr(zone.get("is-scaled"), None),
                show_title=bool_attr(zone.get("show-title"), None),
                show_caption=bool_attr(zone.get("show-caption"), None),
                show_apply=bool_attr(zone.get("show-apply"), None),
                attrs=attrs(zone),
            )
        )

    return result
