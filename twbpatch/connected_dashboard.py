from __future__ import annotations

import copy
import math
import re
import uuid
from typing import Any
from .dashboard_layout import DashboardLayout

from lxml import etree as ET

from .connected import TwbDatasource, get_datasources, get_display_name, _matches, _validate_get_args
from .connected_parameter import TwbParameter
from .field_ref import field_name_from_token
from .connected_worksheet import (
    TwbWorksheet,
    TwbWorksheetField,
    _ensure_manifest_feature,
    get_worksheets,
)
from .context import (
    UNSET,
    ConnectedModel,
    WorkbookContext,
    _UnsetType,
    validate_style_group as _validate_style_group,
    xml_equal,
)
from .action_writer import (
    ACTION_KINDS,
    ACTIVATIONS,
    CLEAR_SELECTIONS,
    build_filter_action,
    build_url_action,
    declare_field,
    ensure_actions_element,
    generate_action_name,
    resolve_action_element,
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
    "corner_radius": 8,
    "margin": 4,
    "padding": 16,
}
#: グラフの種類ごとの内側の余白（2026-09-21 決定）。種類は `draw_*` が
#: `WorkbookContext.chart_kinds` へ記録する。記録が無いシートは既定の 16。
_CHART_ZONE_PADDING = {
    "draw_card": 0,
    # 棒グラフは向きで種類名を分けている（下の _CHART_ZOOM 参照）が、余白は共通
    "draw_bar_h": 16,
    "draw_bar_v": 16,
    # クロス集計と散布図は 2026-09-21 に 0 から 16 へ変更
    "draw_crosstab": 16,
    "draw_quadrant": 16,
    "draw_sheet": 8,
    # ウォーターフォール（2026-09-23）。他のマーク系グラフと同じ内側の余白にそろえる
    "build_waterfall_chart": 16,
    # インフォメーション（2026-09-23）。実測した手作業の "info" シートは余白の無い
    # 小さいアイコンだけのゾーンだったので、KPI カードと同じ 0 にする
    "draw_info": 0,
}

# build_report() の段の高さの既定。段ごとの height= か container_sizes= で変える。
# 以前はコンテナ名に「フィルタ」「スコア」が含まれるかで 50 / 250 / 300 を切り替えて
# いたが、名前でも中身でも挙動を変えないと決めたため 1 つに統一した（K-1、2026-09-07）。
_CONTAINER_HEIGHT = 300

#: テキストの文字揃えと、Tableau が `run/@fontalignment` へ書く値
#: （2026-09-22 に実ダッシュボードで確認）。
_TEXT_ALIGNMENTS = {"left": "0", "center": "1", "right": "2"}

#: 帳票の項目名を浮動テキストで置くときの見た目（2026-09-22）。
#: 表ヘッダーと同じ薄い灰色に合わせる。
_SHEET_TITLE_HEIGHT = 20
#: 細めで小さく（2026-09-22 指定）。太字にはしない
_SHEET_TITLE_FONT_SIZE = 9
_SHEET_TITLE_PADDING = 8
_SHEET_TITLE_BACKGROUND = "#f0f0f0"
#: シートのタイトルが出ているときの、その帯の高さ（概算）。
_SHEET_TITLE_BAR_HEIGHT = 18
#: 四象限のパラメータコントロール（右上に浮動で横並び）の大きさと余白（px）。
#: RETAIL の実ダッシュボードのコントロールに近い値（概算、2026-09-24）。
_QUADRANT_CONTROL_WIDTH = 160
_QUADRANT_CONTROL_HEIGHT = 48
_QUADRANT_CONTROL_GAP = 4
_QUADRANT_CONTROL_MARGIN = 4
#: ヘッダーの帯へ重ねるための下げ幅。実際に Tableau で開いて合わせた値
#: （2026-09-22 指定）。
_SHEET_TITLE_Y_OFFSET = 25

#: ダッシュボードに置くフィルタカードの名称（タイトル）の書式（2026-09-22 指定）。
#: 太字で文字は 10。フィルタを持つワークシートの書式として書く
#: （`TwbWorksheet._apply_filter_title_style()`）。
_FILTER_TITLE_BOLD = True
_FILTER_TITLE_FONT_SIZE = 10


#: 角の丸みだけは、Tableau が接頭辞付きの要素名で書き、ファイル先頭の
#: `document-format-change-manifest` にも宣言を足す（2026-09-21 に実ファイルで確認）。
_FCP_FORMAT_FEATURES = {"corner-radius": "DashboardRoundedCorners"}


def _format_tag(attr: str) -> str:
    feature = _FCP_FORMAT_FEATURES.get(attr)
    return "format" if feature is None else f"_.fcp.{feature}.true...format"


def _format_attr(element: ET._Element) -> str | None:
    """`format` 要素なら `attr` を返す。接頭辞付きの要素名も同じ `format` として扱う。"""
    local = _local_name(element)
    if local == "format" or local.endswith("...format"):
        return element.get("attr")
    return None


def _scaled_spacing(style: dict[str, Any], scale: float) -> dict[str, Any]:
    """余白（margin / padding）だけを倍率で伸ばす。0 は 0 のまま。"""
    if scale == 1.0:
        return dict(style)
    return {
        name: round(value * scale)
        if isinstance(value, int) and not isinstance(value, bool)
        and (name == "margin" or name == "padding" or name.startswith(("margin_", "padding_")))
        else value
        for name, value in style.items()
    }


def _validate_spacing_scale(scale: float) -> None:
    if isinstance(scale, bool) or not isinstance(scale, (int, float)):
        raise TypeError("spacing_scale must be a number")
    if scale <= 0:
        raise ValueError("spacing_scale must be positive")


def _validate_border_color(color: str | None) -> None:
    if color is not None and (not isinstance(color, str) or not color.strip()):
        raise ValueError("border_color must be a non-empty string or None")


#: 枠線の太さ。Tableau が実ファイルへ書く値は 0 / 1 / 2 の整数で、2 が 1 段階太い
#: （2026-09-22 に実ワークブックで実測）。細すぎて見えないので 1 から 2 へ上げた。
_BORDER_WIDTH = 2


def _bordered(style: dict[str, Any], border_color: str | None) -> dict[str, Any]:
    """枠線は色を指定したときだけ引く。指定が無ければ既定どおり枠線なし。"""
    if border_color is None:
        return style
    return {
        **style,
        "border_style": "solid",
        "border_width": _BORDER_WIDTH,
        "border_color": border_color,
    }


def _worksheet_zone_style(
    context: WorkbookContext,
    sheet_name: str,
    spacing_scale: float,
    border_color: str | None = None,
) -> dict[str, Any]:
    style = dict(_DEFAULT_REPORT_WORKSHEET_STYLE)
    padding = _CHART_ZONE_PADDING.get(context.chart_kinds.get(sheet_name, ""))
    if padding is not None:
        style["padding"] = padding
    return _bordered(_scaled_spacing(style, spacing_scale), border_color)


def _local_name(element: ET._Element) -> str:
    return ET.QName(element).localname


def _direct_child(parent: ET._Element, local_name: str) -> ET._Element | None:
    return next((child for child in parent if _local_name(child) == local_name), None)


def _is_container(zone_el: ET._Element) -> bool:
    return (zone_el.get("type-v2") or zone_el.get("type")) in _CONTAINER_TYPES


ITEM_KINDS = ("worksheet", "filter")


def _worksheet_item(container_name: str, item: dict[str, Any]) -> tuple[str, Any]:
    """`kind="worksheet"` の項目を正規化する。

    `sheet` は 1 枚をそのまま段へ置く。`sheets` は縦に積んだ列にまとめる
    （1 枚でも列になる）。`fixed_size` は列の幅。
    """
    unknown = set(item) - {"kind", "sheet", "sheets", "fixed_size"}
    if unknown:
        raise ValueError(
            "worksheet item supports only sheet, sheets and fixed_size: " + container_name
        )
    if ("sheet" in item) == ("sheets" in item):
        raise ValueError(
            "worksheet item needs exactly one of sheet or sheets: " + container_name
        )
    fixed_size = item.get("fixed_size")
    if fixed_size is not None:
        _validate_fixed_size(fixed_size)
    if "sheet" in item:
        name = item["sheet"]
        if not isinstance(name, str) or not name.strip():
            raise TypeError("sheet must be a worksheet name: " + container_name)
        if fixed_size is not None:
            raise ValueError(
                "fixed_size applies to sheets, not sheet: " + container_name
            )
        return "worksheet", ([name], None, False)
    names = item["sheets"]
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(name, str) and name.strip() for name in names)
    ):
        raise TypeError("sheets must be worksheet names: " + container_name)
    return "worksheet", (list(names), fixed_size, True)


def _filter_item(container_name: str, item: dict[str, Any]) -> tuple[str, Any]:
    unknown = set(item) - {"kind", "field"}
    if unknown:
        raise ValueError("filter item supports only field: " + container_name)
    field = item.get("field")
    if (
        not isinstance(field, tuple)
        or len(field) != 2
        or not all(isinstance(value, str) and value.strip() for value in field)
    ):
        raise TypeError(
            'filter field must be ("datasource name", "field name"): ' + container_name
        )
    return "filter", field


def _container_spec(
    container_name: str, value: Any
) -> tuple[list[tuple[str, Any]], int | None, bool | None]:
    """`struct` の値から段の項目・高さ・幅の割り方を取り出す。

    **区分値 `kind` は項目ごとに持つ**（2026-09-07）。1 つの段にグラフとフィルタを
    混ぜられるようにするため。設定画面もエリアごとに種別を選ばせている。

    `distribute_evenly` は段の幅の割り方（2026-09-21）。`True` なら Tableau の
    「均等に配布」で、エリアごとの `fixed_size` は効かない（Tableau もこの組み合わせを
    書かない）。`False` なら `fixed_size` の px がそのまま幅になる。`None`（既定）は
    これまでどおり、幅指定が無くグラフが 2 つ以上並ぶときだけ均等割りにする。

    ```python
    struct={
        "上段": {
            "height": 50,
            "distribute_evenly": False,
            "items": [
                {"kind": "filter", "field": ("売上データ", "地域")},
                {"kind": "worksheet", "sheet": "売上推移"},
                {"kind": "worksheet", "sheets": ["A", "B"], "fixed_size": 200},
            ],
        },
    }
    ```

    以前はコンテナ名に「フィルタ」が含まれるかで決めていた（K-1）。名前は
    ダッシュボードに表示される枠の名前でもあるため、名前を変えると挙動が変わり、
    グラフの枠に「売上フィルタ状況」と付けると意図せずフィルタ置き場になっていた。
    中身から推測する案も採らない。**なぜそう置かれたかが呼び出し側から読めない。**
    """
    if not isinstance(value, dict):
        raise TypeError(
            'container must be {"items": [...]}: ' + container_name
        )
    unknown = set(value) - {"items", "height", "distribute_evenly"}
    if unknown:
        raise ValueError(
            "container supports only items, height and distribute_evenly: " + container_name
        )
    height = value.get("height")
    if height is not None:
        _validate_fixed_size(height)
    distribute_evenly = value.get("distribute_evenly")
    if distribute_evenly is not None and not isinstance(distribute_evenly, bool):
        raise TypeError("distribute_evenly must be bool or None: " + container_name)
    items = value.get("items", [])
    if not isinstance(items, list):
        raise TypeError("container items must be a list: " + container_name)

    normalized: list[tuple[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise TypeError(
                'item must be {"kind": ..., ...}: ' + container_name
            )
        kind = item.get("kind")
        if kind not in ITEM_KINDS:
            raise ValueError(
                f"item kind must be one of {ITEM_KINDS}: {container_name}"
            )
        if kind == "worksheet":
            normalized.append(_worksheet_item(container_name, item))
        else:
            normalized.append(_filter_item(container_name, item))
    return normalized, height, distribute_evenly


def _set_show_apply(zone_el: ET._Element, show_apply: bool) -> None:
    """フィルタ zone の「適用」ボタンを付け外しする。

    Tableau は付けるときだけ `show-apply="true"` を書き、付けないときは属性ごと
    書かない（実測: RETAIL - POS の .twb は 4 件すべて `"true"`、既定のフィルタには
    属性が無い）。読み取り側も「属性なし = None」を前提にしているため、
    `False` では属性を消す。
    """
    if not isinstance(show_apply, bool):
        raise TypeError("show_apply must be bool")
    if show_apply:
        zone_el.set("show-apply", "true")
    else:
        zone_el.attrib.pop("show-apply", None)


def _zone_kind(zone_el: ET._Element, worksheet_ids: set[str]) -> str:
    if _is_container(zone_el):
        return "container"
    zone_type = zone_el.get("type-v2") or zone_el.get("type") or ""
    if zone_el.get("name") in worksheet_ids and zone_type in {"", "worksheet"}:
        return "worksheet"
    return {
        "text": "text",
        "bitmap": "image",
        "empty": "spacer",
        "dashboard-object": "dashboard_object",
        "filter": "filter",
        "paramctrl": "parameter_control",
        "color": "legend", "size": "legend", "shape": "legend",
        "legend": "legend", "color-legend": "legend", "size-legend": "legend",
    }.get(zone_type, "unknown")


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
    if xml_equal(current, updated):
        return False
    parent = current.getparent()
    if parent is None:
        raise DetachedModelError("XML resource is detached")
    parent.replace(current, updated)
    context.mark_dirty()
    return True


def _bool_or_none(value: str | None) -> bool | None:
    """XML の真偽値属性。書かれていなければ `None`（既定に任せている印）。"""
    if value is None:
        return None
    return value.strip().lower() == "true"


def _int_attr(element: ET._Element, name: str, default: int = 0) -> int:
    try:
        return int(float(element.get(name) or default))
    except ValueError:
        return default


def _round(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _spacer_style(content_style: dict[str, Any]) -> dict[str, Any]:
    """余りを埋める空きゾーンの書式。台紙と同じ色にして見えなくする（2026-09-21）。"""
    return {
        "background_color": content_style.get("background_color")
        or _DEFAULT_REPORT_CONTENT_STYLE["background_color"],
        "border_style": "none",
        "margin": 0,
    }


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
        attr.replace("-", "_"): item.get("value") or ""
        for item in style
        for attr in [_format_attr(item)]
        if attr
    }


def _set_zone_styles(
    zone_el: ET._Element,
    styles: dict[str, str | int | None],
    context: WorkbookContext | None = None,
) -> None:
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
        matches = [item for item in style if _format_attr(item) == attr]
        if value is None:
            for item in matches:
                style.remove(item)
        elif matches:
            matches[0].set("value", str(value))
            for item in matches[1:]:
                style.remove(item)
        else:
            ET.SubElement(style, _format_tag(attr), attrib={"attr": attr, "value": str(value)})
            if context is not None and attr in _FCP_FORMAT_FEATURES:
                feature = _FCP_FORMAT_FEATURES[attr]
                _ensure_manifest_feature(context, f"_.fcp.{feature}.true...{feature}")
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

    def inset(kind: str, side: str) -> float:
        value = styles.get(f"{kind}_{side}", styles.get(kind, "0"))
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    # Tableau が保存した .twb では、子の位置は外側（margin）と内側（padding）の両方の分だけ内へ寄る。
    def padding(side: str) -> float:
        return inset("margin", side) + inset("padding", side)

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
        # 末尾は端数を吸って枠をぴったり埋める。ただし固定サイズの子は伸ばさない
        # （2026-09-21。伸ばしていたため、段に 1 つだけ置いた固定幅が効かなかった）。
        # 全部が固定サイズのときは吸わせる相手がいないので、今までどおり末尾が吸う。
        if index == len(children) - 1 and (zone_id not in fixed_sizes or not flexible):
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


#: グラフの種類ごとの表示倍率（2026-09-21）。帳票は列が右へ伸びて横スクロールに
#: なるため「幅を合わせる」。ほかは今までどおり「ビュー全体」。
#: 棒グラフは向きで分ける（2026-09-22）: 縦棒（item が列）は「高さを合わせる」、
#: 横棒（item が行、既定）は「幅を合わせる」。
#: 種類は `draw_*` が `WorkbookContext.chart_kinds` へ記録する（.twb には残らない）。
_CHART_ZOOM = {
    "draw_sheet": "fit-width",
    "draw_bar_h": "fit-width",
    "draw_bar_v": "fit-height",
}


def _ZOOM_TYPE(context: WorkbookContext, sheet_name: str) -> str:
    return _CHART_ZOOM.get(context.chart_kinds.get(sheet_name, ""), "entire-view")


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
        if _zone_kind(zone, worksheet_ids) == 'worksheet'
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
    attrib = {"class": "dashboard", "maximized": "true", "name": dashboard_id}
    # 表示・非表示は window にしか無い。作り直しで消さないよう引き継ぐ。
    if current is not None and current.get("hidden") is not None:
        attrib["hidden"] = current.get("hidden")
    window = ET.Element("window", attrib=attrib)
    viewpoints = ET.SubElement(window, "viewpoints")
    seen: set[str] = set()
    for zone in worksheet_zones:
        name = zone.get("name") or ""
        if name in seen:
            continue
        seen.add(name)
        viewpoint = ET.SubElement(viewpoints, "viewpoint", attrib={"name": name})
        ET.SubElement(viewpoint, "zoom", attrib={"type": _ZOOM_TYPE(context, name)})
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
    elif not xml_equal(current, window):
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
    def tag(self) -> str:
        return self._snapshot().tag

    def _field_name(self, reference: str | None) -> str | None:
        match = re.fullmatch(r"\[([^\]]+)\]\.\[([^\]]+)\]", reference or "")
        if match is None:
            return None
        datasource_id, token = match.groups()
        if datasource_id == "Parameters":
            return None
        try:
            datasource = TwbDatasource(self._context, datasource_id)
            for field_id in (f"[{token}]", f"[{field_name_from_token(token)}]"):
                fields = datasource.get_fields(id=field_id)
                if len(fields) == 1:
                    return fields[0].name
        except DetachedModelError:
            return None
        return None

    @property
    def field_mappings(self) -> list[dict[str, str | None]]:
        result: list[dict[str, str | None]] = []
        for item in self._snapshot().field_mappings:
            source = self._field_name(item.get("source_field"))
            target = self._field_name(item.get("target_field"))
            if source is not None and (item.get("target_field") is None or target is not None):
                result.append({"source_field": source, "target_field": target})
        return result

    @property
    def target_parameter_name(self) -> str | None:
        reference = self._snapshot().target_parameter_id
        match = re.fullmatch(r"\[Parameters\]\.\[(.+)\]", reference or "")
        if match is None:
            return None
        try:
            return TwbParameter(self._context, f"[{match.group(1)}]").name
        except DetachedModelError:
            return None

    @property
    def source_worksheet_ids(self) -> list[str]:
        return list(self._snapshot().source_worksheet_ids)

    @property
    def target_worksheet_ids(self) -> list[str]:
        return list(self._snapshot().target_worksheet_ids)

    @property
    def excluded_source_worksheet_ids(self) -> list[str]:
        """対象から外したシート。**Tableau は対象シートを除外リストで書く。**"""
        return list(self._snapshot().excluded_source_worksheet_ids)

    @property
    def excluded_target_worksheet_ids(self) -> list[str]:
        return list(self._snapshot().excluded_target_worksheet_ids)

    @property
    def dashboard_id(self) -> str | None:
        return self._snapshot().dashboard_id

    @property
    def source_type(self) -> str | None:
        return self._snapshot().source_type

    @property
    def target_type(self) -> str | None:
        return self._snapshot().target_type

    @property
    def source_dashboard_id(self) -> str | None:
        return self._snapshot().source_dashboard_id

    @property
    def target_dashboard_id(self) -> str | None:
        """別のダッシュボードを対象にできるので、source と別に持つ。"""
        return self._snapshot().target_dashboard_id

    @property
    def attrs(self) -> dict[str, str]:
        return dict(self._snapshot().attrs)

    @property
    def details(self) -> dict[str, object]:
        """`<action>` の中身をそのまま辞書にしたもの。属性と子要素を含む。"""
        return self._snapshot().details

    @property
    def links(self) -> list[dict[str, str]]:
        return [dict(item) for item in self._snapshot().links]

    @property
    def params(self) -> dict[str, str]:
        return dict(self._snapshot().params)

    def _resolve_element(self) -> ET._Element:
        if self.tag != "action":
            raise UnsupportedFeatureError("update/delete is not supported for this action type")
        return resolve_action_element(self._context.tree.getroot(), self._id)

    def update(
        self,
        *,
        name: str | _UnsetType = UNSET,
        activation: str | _UnsetType = UNSET,
        clear_selection: str | _UnsetType = UNSET,
        url: str | _UnsetType = UNSET,
    ) -> TwbDashboardAction:
        """自身のスカラー値を更新する。

        差し替えたいのが対象シートやフィールドの場合は、消して作り直す。
        組み立て直しになるため `update()` には含めない。
        """
        kind = self.type
        if activation is not UNSET and activation not in ACTIVATIONS:
            raise ValueError(f"activation must be one of {ACTIVATIONS}")
        if clear_selection is not UNSET:
            if clear_selection not in CLEAR_SELECTIONS:
                raise ValueError(
                    f"clear_selection must be one of {tuple(CLEAR_SELECTIONS)}"
                )
            if kind != "filter":
                raise ValueError("clear_selection is only available on filter actions")
        if url is not UNSET:
            if not isinstance(url, str) or not url.strip():
                raise ValueError("url must be a non-empty string")
            if kind != "url":
                raise ValueError("url is only available on url actions")
        if name is not UNSET and (not isinstance(name, str) or not name.strip()):
            raise ValueError("name must be a non-empty string")

        action_el = self._resolve_element()
        updated = copy.deepcopy(action_el)
        if name is not UNSET:
            updated.set("caption", name.strip())
        activation_el = _first_child(updated, "activation")
        if activation is not UNSET and activation_el is not None:
            activation_el.set("type", activation)
        if clear_selection is not UNSET and activation_el is not None:
            activation_el.set("auto-clear", CLEAR_SELECTIONS[clear_selection])
        for link in updated.xpath("./*[local-name()='link']"):
            if name is not UNSET and kind == "filter":
                link.set("caption", name.strip())
            if url is not UNSET:
                link.set("expression", url.strip())
        _replace_if_changed(action_el, updated, self._context)
        return self

    def delete(self) -> None:
        action_el = self._resolve_element()
        parent = action_el.getparent()
        if parent is None:
            raise DetachedModelError(f"dashboard action is detached: {self._id}")
        parent.remove(action_el)
        self._context.mark_dirty()
        self._detach()


def _first_child(parent: ET._Element, local_name: str) -> ET._Element | None:
    return next(
        (child for child in parent if ET.QName(child).localname == local_name), None
    )


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
    def layout(self) -> DashboardLayout:
        from .dashboard_layout_xml import read_dashboard_layout

        return read_dashboard_layout(self._context, self._resolve_element())

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

    def create_action(
        self,
        *,
        kind: str,
        name: str,
        source: str | list[str],
        targets: list[str] | None = None,
        field: tuple[str, str] | None = None,
        url: str | None = None,
        activation: str = "on-select",
        clear_selection: str = "show_all",
    ) -> TwbDashboardAction:
        """ダッシュボードアクションを 1 件作る。

        `source` と `targets` は**このダッシュボードに置かれているワークシート名**。
        XML では「除外するシート」で書かれるが、呼び出し側は含める側を渡す。

        - `kind="filter"`: `source` は 1 枚、`targets` と `field` が要る
        - `kind="url"`: `source` は 1 枚以上、`url` が要る

        `activation` は `on-select` / `on-hover` / `on-menu`。**実測できているのは
        `on-select` だけ**で、残り 2 つは Tableau で一般に使われる値。
        """
        if kind not in ACTION_KINDS:
            raise ValueError(f"kind must be one of {ACTION_KINDS}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        name = name.strip()
        if activation not in ACTIVATIONS:
            raise ValueError(f"activation must be one of {ACTIVATIONS}")
        if clear_selection not in CLEAR_SELECTIONS:
            raise ValueError(
                f"clear_selection must be one of {tuple(CLEAR_SELECTIONS)}"
            )

        placed = [worksheet.id for worksheet in self.get_worksheets()]
        sources = [source] if isinstance(source, str) else list(source)
        for worksheet in sources:
            if worksheet not in placed:
                raise ValueError(f"worksheet is not on this dashboard: {worksheet}")
        if not sources:
            raise ValueError("source must contain at least one worksheet")

        root = self._context.tree.getroot()
        actions_el = ensure_actions_element(root)
        if self.get_actions(name=name):
            raise ValueError(f"action name already exists: {name}")
        action_name = generate_action_name(actions_el)

        if kind == "filter":
            if len(sources) != 1:
                raise ValueError("a filter action takes exactly one source worksheet")
            if url is not None:
                raise ValueError("url is only available on url actions")
            if not targets:
                raise ValueError("a filter action needs at least one target worksheet")
            for worksheet in targets:
                if worksheet not in placed:
                    raise ValueError(f"worksheet is not on this dashboard: {worksheet}")
            datasource_el, column_el, reference = self._resolve_action_field(field)
            kept = set(sources) | set(targets)
            action_el = build_filter_action(
                name=action_name,
                caption=name,
                dashboard_name=self._id,
                source_worksheet=sources[0],
                excluded_targets=[
                    worksheet for worksheet in placed if worksheet not in kept
                ],
                field_reference=reference,
                activation=activation,
                clear_selection=clear_selection,
            )
            actions_el.append(action_el)
            declare_field(actions_el, datasource_el, column_el)
        else:
            if not isinstance(url, str) or not url.strip():
                raise ValueError("a url action needs a url")
            if targets or field is not None:
                raise ValueError("targets and field are only available on filter actions")
            action_el = build_url_action(
                name=action_name,
                caption=name,
                dashboard_name=self._id,
                url=url.strip(),
                excluded_sources=[
                    worksheet for worksheet in placed if worksheet not in set(sources)
                ],
                activation=activation,
            )
            actions_el.append(action_el)

        self._context.mark_dirty()
        return TwbDashboardAction(self._context, self._id, action_name)

    def _resolve_action_field(
        self, field: tuple[str, str] | None
    ) -> tuple[ET._Element, ET._Element, str]:
        """`("データソース名", "フィールド名")` を XML 要素と参照文字列へ解決する。

        「すべてのフィールド」は扱わない（利用者の想定から外れるため、2026-09-07 決定）。
        """
        if (
            not isinstance(field, tuple)
            or len(field) != 2
            or not all(isinstance(value, str) and value.strip() for value in field)
        ):
            raise TypeError('field must be ("datasource name", "field name")')
        datasource_name, field_name = field
        datasources = get_datasources(self._context, name=datasource_name)
        if len(datasources) != 1:
            raise ValueError(f"datasource not found or ambiguous: {datasource_name}")
        datasource = datasources[0]
        fields = datasource.get_fields(name=field_name)
        if len(fields) != 1:
            raise ValueError(f"field not found or ambiguous: {field_name}")
        datasource_el = datasource._resolve_element()
        columns = datasource_el.xpath(
            "./*[local-name()='column'][@name=$id]", id=fields[0].id
        )
        if not columns:
            raise ValueError(f"field has no column element: {field_name}")
        return datasource_el, columns[0], f"[{datasource.id}].{fields[0].id}"

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
        header_title: str | None = None,
        header_height: int = 43,
        header_background_color: str = "#c0c0c0",
        header_font_color: str = "#333333",
        filter_apply_button: bool = False,
        spacing_scale: float = 1.0,
        border_color: str | None = None,
    ) -> TwbDashboard:
        if not isinstance(filter_apply_button, bool):
            raise TypeError("filter_apply_button must be bool")
        _validate_spacing_scale(spacing_scale)
        _validate_border_color(border_color)
        if header_title is not None and not isinstance(header_title, str):
            raise TypeError("header_title must be a string or None")
        container_sizes = dict(container_sizes or {})
        for container_name, size in container_sizes.items():
            if not isinstance(container_name, str) or not container_name.strip():
                raise ValueError("container size names must be non-empty strings")
            _validate_fixed_size(size)
        _validate_fixed_size(header_height)

        sheet_names: list[str] = []
        filter_specs: list[tuple[str, str]] = []
        specs: dict[str, tuple[list[tuple[str, Any]], int | None, bool | None]] = {
            container_name: _container_spec(container_name, value)
            for container_name, value in struct.items()
        }
        for items, _, _ in specs.values():
            for kind, payload in items:
                if kind == "filter":
                    filter_specs.append(payload)
                else:
                    sheet_names.extend(payload[0])
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
            dashboard_name if header_title is None else header_title,
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
        pending_filters: list[tuple[TwbDashboardContainer, int, tuple[str, str]]] = []
        for container_name, (items, height, distribute_evenly) in specs.items():
            fixed_size = height
            if fixed_size is None:
                fixed_size = container_sizes.get(container_name, _CONTAINER_HEIGHT)
            worksheet_items = [item for kind, item in items if kind == "worksheet"]
            widths = [item[1] for item in worksheet_items]
            if distribute_evenly is None:
                # 既定の均等配分は「並べたワークシートが 2 つ以上あり、フィルタが無く、
                # 幅の指定が 1 つも無い」とき。フィルタは幅を食わせない（Tableau で
                # 作った既存レイアウトに合わせる）。均等配分の段では Tableau が
                # エリアごとの固定幅を見ないので、幅を指定したら均等配分はしない。
                distribute_evenly = (
                    len(worksheet_items) > 1
                    and len(worksheet_items) == len(items)
                    and not any(width is not None for width in widths)
                )
            container = root.create_container(
                direction="horizontal",
                fixed_size=fixed_size,
                friendly_name=container_name,
                distribute_evenly=distribute_evenly,
            )
            column_index = 0
            for index, (kind, payload) in enumerate(items):
                if kind == "filter":
                    # フィルタは全ワークシートを置き終えてから差し込む。参照先の
                    # シートがダッシュボードに載っていないと配置できないため。
                    pending_filters.append((container, index, payload))
                    continue

                names, group_fixed_size, grouped = payload
                target = container
                if grouped:
                    column_index += 1
                    target = container.create_container(
                        direction="vertical",
                        weight=1,
                        fixed_size=group_fixed_size,
                        friendly_name=f"{container_name}_{column_index}",
                        distribute_evenly=len(names) > 1,
                    )
                for sheet_index, sheet_name in enumerate(names):
                    zone = target.add_worksheet(
                        worksheets[sheet_name],
                        # 文字が無くても、背景色があるタイトルは帯として出す（KPI カード）
                        show_title=worksheets[sheet_name].title is not None
                        or worksheets[sheet_name].title_style["background_color"] is not None,
                        weight=1,
                    )
                    zone_style = _worksheet_zone_style(
                        self._context, sheet_name, spacing_scale, border_color
                    )
                    if grouped and len(names) > 1:
                        if sheet_index < len(names) - 1:
                            zone_style["padding_bottom"] = 0
                            zone_style["margin_bottom"] = 0
                        if sheet_index > 0:
                            zone_style["padding_top"] = 0
                            zone_style["margin_top"] = 0
                    zone.update(style=zone_style)
            # 幅を全部指定した段は、余りを吸う相手がいないと最後のエリアが
            # 伸びてしまう（段の並びの末尾と同じく、空きゾーンに吸わせる）。
            if (
                not distribute_evenly
                and worksheet_items
                and len(worksheet_items) == len(items)
                and all(width is not None for width in widths)
            ):
                container.add_spacer(style=_spacer_style(effective_content_style))

        for container, index, payload in pending_filters:
            worksheet, reference = filter_fields[payload]
            zone = container._add_filter_reference(
                worksheet, reference, order=index, show_apply=filter_apply_button
            )
            zone.update(
                style={
                    "background_color": "#ffffff",
                    "border_style": "none",
                    "margin": 4,
                    "padding": 4,
                }
            )
            worksheet._apply_filter_title_style(
                bold=_FILTER_TITLE_BOLD, font_size=_FILTER_TITLE_FONT_SIZE
            )
        root.add_spacer(style=_spacer_style(effective_content_style))
        self._add_sheet_column_titles()
        self._add_quadrant_parameter_controls()
        return self

    def _add_quadrant_parameter_controls(self) -> None:
        """四象限のフィルター用パラメータを、シートの右上へ浮動で横に並べる（2026-09-24）。

        左が中央比率、右が売上閾値。対象は `draw_quadrant()` で描いたシート
        （`{シート名}_中央比率` / `{シート名}_売上閾値` を持つもの）。
        """
        try:
            _canvas_or_error(self._resolve_element())
        except UnsupportedFeatureError:
            # 自動サイズのダッシュボードには浮動で置けない
            return
        for zone in self.get_zones():
            sheet = zone.worksheet_id or ""
            if self._context.chart_kinds.get(sheet) != "draw_quadrant":
                continue
            if zone.x is None or zone.y is None or zone.width is None:
                continue
            title_bar = _SHEET_TITLE_BAR_HEIGHT if zone.show_title else 0
            y = zone.y + title_bar + _QUADRANT_CONTROL_MARGIN
            right = zone.x + zone.width - _QUADRANT_CONTROL_MARGIN
            for index, suffix in enumerate(("売上閾値", "中央比率")):
                self.add_floating_parameter_control(
                    f"{sheet}_{suffix}",
                    x=right - (index + 1) * _QUADRANT_CONTROL_WIDTH - index * _QUADRANT_CONTROL_GAP,
                    y=y,
                    width=_QUADRANT_CONTROL_WIDTH,
                    height=_QUADRANT_CONTROL_HEIGHT,
                )

    def _add_sheet_column_titles(self) -> None:
        """帳票の消えた項目名を、浮動テキストでヘッダーの帯へ重ねる（2026-09-22）。

        **Tableau は行に置いた項目の名前は出すが、棒・色帯の列の名前だけ出さない。**
        その空いている分にだけ文字を置く。

        列幅は**ゾーンの幅から余白を引いて列数で割った暫定値**（2026-09-22 指定）。
        同じ幅をワークシートの列にも書き込むので、文字の位置と実際の列が揃う。
        **位置も幅も概算で、置いたあと Tableau で人が直す前提。**
        """
        columns = self._context.sheet_columns
        if not columns:
            return
        try:
            _canvas_or_error(self._resolve_element())
        except UnsupportedFeatureError:
            # 自動サイズのダッシュボードには浮動で置けない
            return
        for zone in self.get_zones():
            layout = columns.get(zone.worksheet_id or "")
            if layout is None or zone.x is None or zone.y is None or zone.width is None:
                continue
            items, titles = layout
            if not titles:
                continue
            inner = zone.width - _SHEET_TITLE_PADDING * 2
            width = max(1, int(inner / (len(items) + len(titles))))
            self._set_sheet_column_widths(zone.worksheet_id or "", items, titles, width)
            # ヘッダーの帯はシートのタイトルの下。タイトルが無ければその分は空けない
            title_bar = _SHEET_TITLE_BAR_HEIGHT if zone.show_title else 0
            offset = zone.x + _SHEET_TITLE_PADDING + len(items) * width
            for title in titles:
                self.add_floating_text(
                    title,
                    x=offset,
                    y=zone.y + _SHEET_TITLE_PADDING + title_bar + _SHEET_TITLE_Y_OFFSET,
                    width=width,
                    height=_SHEET_TITLE_HEIGHT,
                    font_size=_SHEET_TITLE_FONT_SIZE,
                    align="center",
                    style={"background_color": _SHEET_TITLE_BACKGROUND},
                )
                offset += width

    def _set_sheet_column_widths(
        self, sheet: str, items: list[str], titles: list[str], width: int
    ) -> None:
        """帳票の列幅を、浮動テキストと同じ暫定値でそろえる（2026-09-22）。

        行に置いた項目は表の列幅（`style-rule element="header"` の `width`）、
        棒・色帯の列はペインの `minwidth`/`maxwidth`。
        """
        matches = get_worksheets(self._context, name=sheet)
        if len(matches) != 1:
            return
        worksheet = matches[0]
        if items:
            worksheet._apply_header_widths({reference: width for reference in items})
        panes = worksheet.get_panes()
        # 軸が 2 本以上あると、先頭に軸名を持たない土台のペインが付く
        for pane in (panes[1:] if len(titles) > 1 else panes):
            pane._apply_pane_width(width)

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

    def add_floating_text(
        self,
        text: str,
        *,
        x: float = 0,
        y: float = 0,
        width: float = 200,
        height: float = 24,
        font_size: int = 12,
        font_color: str = "#333333",
        bold: bool = False,
        align: str = "left",
        style: dict[str, str | int] | None = None,
    ) -> TwbDashboardZone:
        """テキストを**浮動**でダッシュボードへ置く（2026-09-22 追加）。

        位置と大きさは px で受け、Tableau の座標（ダッシュボードの幅・高さを
        100000 とした比率）へ直して書く。`add_floating_worksheet()` と同じ扱いで、
        **固定サイズのダッシュボードでのみ使える**。

        Tableau は浮動のオブジェクトを、レイアウトのコンテナの中ではなく
        `<zones>` の直下へ `x` / `y` / `w` / `h` 付きで置く（実ダッシュボードで確認）。
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if isinstance(font_size, bool) or not isinstance(font_size, int) or font_size <= 0:
            raise ValueError("font_size must be a positive integer")
        if not isinstance(font_color, str) or not font_color.strip():
            raise ValueError("font_color must be a non-empty string")
        if not isinstance(bold, bool):
            raise TypeError("bold must be bool")
        if align not in _TEXT_ALIGNMENTS:
            raise ValueError("align must be left, center, or right")
        style = _validate_style_group("style", style)
        x = _validate_pixel(x, "x")
        y = _validate_pixel(y, "y")
        width = _validate_pixel(width, "width", positive=True)
        height = _validate_pixel(height, "height", positive=True)

        dashboard_el = self._resolve_element()
        canvas_width, canvas_height = _canvas_or_error(dashboard_el)
        updated = copy.deepcopy(dashboard_el)
        zones_el = _default_zones(updated, create=True)
        assert zones_el is not None
        zone_id = _next_zone_id(updated)
        zone_el = ET.Element(
            "zone",
            attrib={
                "forceUpdate": "true",
                "id": zone_id,
                "type-v2": "text",
                "x": str(_px_to_raw(x, canvas_width)),
                "y": str(_px_to_raw(y, canvas_height)),
                "w": str(_px_to_raw(width, canvas_width)),
                "h": str(_px_to_raw(height, canvas_height)),
            },
        )
        formatted = ET.SubElement(zone_el, "formatted-text")
        run_attrs = {
            "fontalignment": _TEXT_ALIGNMENTS[align],
            "fontcolor": font_color,
            "fontsize": str(font_size),
        }
        if bold:
            run_attrs["bold"] = "true"
        ET.SubElement(formatted, "run", attrib=run_attrs).text = text
        if style:
            _set_zone_styles(zone_el, style, self._context)
        zones_el.append(zone_el)
        _replace_if_changed(dashboard_el, updated, self._context)
        _sync_dashboard_window(self._context, self._id)
        return TwbDashboardZone(self._context, self._id, zone_id)

    def add_floating_parameter_control(
        self,
        parameter: str,
        *,
        x: float = 0,
        y: float = 0,
        width: float = 160,
        height: float = 48,
    ) -> TwbDashboardZone:
        """パラメータコントロールを**浮動**でダッシュボードへ置く（2026-09-24 追加）。

        `parameter` はパラメータ名。`<zones>` 直下へ `type-v2="paramctrl"`・
        `param="[Parameters].[…]"`・`mode="compact"` の zone を置く（RETAIL の
        実ダッシュボードで確認。`add_floating_text()` と同じ座標の扱い）。
        """
        from .connected_parameter import get_parameters

        matches = get_parameters(self._context, name=parameter)
        if len(matches) != 1:
            raise ValueError(f"parameter not found: {parameter}")
        x = _validate_pixel(x, "x")
        y = _validate_pixel(y, "y")
        width = _validate_pixel(width, "width", positive=True)
        height = _validate_pixel(height, "height", positive=True)

        dashboard_el = self._resolve_element()
        canvas_width, canvas_height = _canvas_or_error(dashboard_el)
        updated = copy.deepcopy(dashboard_el)
        zones_el = _default_zones(updated, create=True)
        assert zones_el is not None
        zone_id = _next_zone_id(updated)
        zones_el.append(
            ET.Element(
                "zone",
                attrib={
                    "id": zone_id,
                    "mode": "compact",
                    "param": f"[Parameters].{matches[0].id}",
                    "type-v2": "paramctrl",
                    "x": str(_px_to_raw(x, canvas_width)),
                    "y": str(_px_to_raw(y, canvas_height)),
                    "w": str(_px_to_raw(width, canvas_width)),
                    "h": str(_px_to_raw(height, canvas_height)),
                },
            )
        )
        _replace_if_changed(dashboard_el, updated, self._context)
        _sync_dashboard_window(self._context, self._id)
        return TwbDashboardZone(self._context, self._id, zone_id)

    def update(
        self,
        *,
        name: str | None | _UnsetType = UNSET,
        visible: bool | _UnsetType = UNSET,
        layout: DashboardLayout | _UnsetType = UNSET,
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
            elif name != get_display_name(updated_dashboard):
                updated_dashboard.set("caption", name)
        if layout is not UNSET:
            from .dashboard_layout_xml import write_dashboard_layout

            updated_context = WorkbookContext(ET.ElementTree(updated_root))
            write_dashboard_layout(updated_context, updated_dashboard, layout)
        if visible is not UNSET:
            windows = updated_root.xpath(
                "/workbook/windows/window[@class='dashboard'][@name=$id]",
                id=self._id,
            )
            if windows:
                windows[0].set("hidden", "false" if visible else "true")
            elif not visible:
                # window は `<viewpoints>` `<active>` `<simple-id>` を持たないと
                # Tableau の構造として成立しない（validator の
                # dashboard_window_structure）。中身は載っているワークシートから
                # 作るので、シートが 1 枚も無いダッシュボードは隠せない。
                raise UnsupportedFeatureError(
                    "dashboard needs at least one worksheet before it can be hidden:"
                    f" {self._id}"
                )
        if not xml_equal(root, updated_root):
            self._context.tree._setroot(updated_root)
            self._context.mark_dirty()
        if layout is not UNSET:
            from .dashboard_layout_xml import restore_layout_viewpoints

            self._context.layout_weights = {
                key: value for key, value in self._context.layout_weights.items() if key[0] != self._id
            }
            _sync_dashboard_window(self._context, self._id)
            restore_layout_viewpoints(self._context, self._id, layout)
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
        show_apply: bool = False,
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
            show_apply=show_apply,
            order=order,
            weight=weight,
        )

    def _add_filter_reference(
        self,
        worksheet: TwbWorksheet,
        reference: str,
        *,
        mode: str = "checkdropdown",
        show_apply: bool = False,
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
        _set_show_apply(child, show_apply)
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
            _set_zone_styles(child, style, self._context)
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
            _set_zone_styles(container, style, self._context)
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

    @property
    def x_raw(self) -> int:
        """Tableau が XML に書く座標。ダッシュボードの幅を 100000 とした比率。"""
        return _zone_rect(self._resolve_element())[0]

    @property
    def y_raw(self) -> int:
        return _zone_rect(self._resolve_element())[1]

    @property
    def width_raw(self) -> int:
        return _zone_rect(self._resolve_element())[2]

    @property
    def height_raw(self) -> int:
        return _zone_rect(self._resolve_element())[3]

    @property
    def dashboard_id(self) -> str:
        return self._dashboard_id

    @property
    def type(self) -> str | None:
        """XML の `type-v2`（無ければ `type`）。`kind` は SDK 側の区分値。"""
        element = self._resolve_element()
        return element.get("type-v2") or element.get("type")

    @property
    def param(self) -> str | None:
        """コンテナなら並べる向き（`horz` / `vert`）。"""
        return self._resolve_element().get("param")

    @property
    def mode(self) -> str | None:
        """フィルタカードの表示形式。ほかのゾーンでは `None`。"""
        return self._resolve_element().get("mode")

    @property
    def show_caption(self) -> bool | None:
        """フィルタカードの見出しを出すか。`show_title` とは別の属性（§3.2）。"""
        return _bool_or_none(self._resolve_element().get("show-caption"))

    @property
    def show_apply(self) -> bool | None:
        """フィルタカードの「適用」ボタンを出すか。"""
        return _bool_or_none(self._resolve_element().get("show-apply"))

    @property
    def url(self) -> str | None:
        """Web ページゾーンの URL。"""
        return self._resolve_element().get("url")

    @property
    def is_fixed(self) -> bool | None:
        return _bool_or_none(self._resolve_element().get("is-fixed"))

    @property
    def is_scaled(self) -> bool | None:
        return _bool_or_none(self._resolve_element().get("is-scaled"))

    @property
    def attrs(self) -> dict[str, str]:
        """`<zone>` の属性そのまま。上のプロパティに出ていないものも入る。"""
        return {str(key): str(value) for key, value in self._resolve_element().attrib.items()}

    @property
    def sizing_mode(self) -> str:
        """所属ダッシュボードの `sizing-mode`。座標の解釈がこれで変わる。"""
        return _dashboard_size(self._resolve_dashboard_element())[0]

    @property
    def dashboard_width_px(self) -> int | None:
        """px 換算の基準になるダッシュボードの幅。自動サイズなら `None`。"""
        return _dashboard_size(self._resolve_dashboard_element())[1]

    @property
    def dashboard_height_px(self) -> int | None:
        return _dashboard_size(self._resolve_dashboard_element())[2]

    def to_px(self, *, width: int, height: int) -> tuple[int, int, int, int]:
        """任意のキャンバスサイズで px 換算する。

        自動サイズのダッシュボードは基準の幅・高さを持たないため `x` などが
        `None` になる。表示したいサイズを渡せば raw 座標から換算できる。
        """
        canvas_width = _validate_pixel(width, "width", positive=True)
        canvas_height = _validate_pixel(height, "height", positive=True)
        x, y, zone_width, zone_height = _zone_rect(self._resolve_element())
        return (
            _raw_to_px(x, int(canvas_width)),
            _raw_to_px(y, int(canvas_height)),
            _raw_to_px(zone_width, int(canvas_width)),
            _raw_to_px(zone_height, int(canvas_height)),
        )

    @property
    def parent_id(self) -> str | None:
        """入れ子の親ゾーンの `id`。最上位なら `None`。"""
        element = self._resolve_element()
        parent = next(
            (item for item in element.iterancestors() if _local_name(item) == "zone"),
            None,
        )
        return parent.get("id") if parent is not None else None

    @property
    def depth(self) -> int:
        """入れ子の深さ。最上位は `0`。"""
        element = self._resolve_element()
        return sum(1 for item in element.iterancestors() if _local_name(item) == "zone")

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
        show_apply: bool | _UnsetType = UNSET,
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
        if show_apply is not UNSET:
            if not isinstance(show_apply, bool):
                raise TypeError("show_apply must be bool")
            if self.kind != "filter":
                raise ValueError("show_apply is only available on filter zones")
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
        if show_apply is not UNSET:
            _set_show_apply(zone, show_apply)
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
            _set_zone_styles(zone, style, self._context)
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
