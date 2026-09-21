"""KPI ツリーダッシュボードの配置（backlog I-2、作業計画は docs/tasks/I2_kpi_tree.md）。

既にあるシート（通常は `draw_card()` で作った KPI カード）を親子関係のツリーとして受け取り、
左から右へ展開するタイル配置で並べる。KPI カード自体は作らない。

エッジ（線）は、座標だけを持つ .hyper（パッケージ同梱の assets/edge.hyper）をデータソースとして足し、親ノードごとに
折れ線のシートを作って描く。表の形は Tableau で手作りしたシートに合わせている: 線 E-k は
O(0,0) → P-k(1,k) → P2-k(2,k) の 3 点で、階段補間により「親から横 → 縦 → 子へ横」になる。
k は親の中心からの縦位置（ノードの高さの半分、75px 単位）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .connected import TwbDatasource, TwbField
from .connected_dashboard import (
    _CHART_ZONE_PADDING,
    _DEFAULT_REPORT_CONTENT_STYLE,
    _DEFAULT_REPORT_WORKSHEET_STYLE,
    TwbDashboard,
    TwbDashboardContainer,
    _scaled_spacing,
    _validate_spacing_scale,
)
from .connected_worksheet import (
    TwbWorksheet,
    _ensure_table,
    _ensure_table_style,
    _set_style_value,
)
from .context import validate_style_group

if TYPE_CHECKING:
    from .workbook import TwbWorkbook

_NODE_WIDTH = 200
_NODE_HEIGHT = 150
_ALIGNS = {"center", "top"}

# 見た目はダッシュボードタブ（build_report()）の KPI カードに揃える: 灰色の台紙に白いカードを余白付きで置く。
# 台紙は build_report() と同じく content_style= で上書きできる。台紙の外側・内側の余白の分だけ
# 中身が内へ寄るので、ダッシュボードはその分大きくする。
# ノードは KPI カードなので、内側の余白はダッシュボードタブの KPI カードと同じ 0。
_CARD_STYLE = {**_DEFAULT_REPORT_WORKSHEET_STYLE, "padding": _CHART_ZONE_PADDING["draw_card"]}
_SIDES = ("left", "right", "top", "bottom")

_EDGE_WIDTH = 60
_EDGE_DATASOURCE_NAME = "KPIツリーのエッジ"
#: パッケージに同梱したエッジの表（examples/edge.hyper と同じもの）。
_BUNDLED_EDGE_HYPER = Path(__file__).resolve().parent / "assets" / "edge.hyper"
#: 同梱の表を使うとき .twb から参照する名前。`save()` が .twb の隣（.twbx なら中）へ置く（2026-09-15）。
#: 利用者のファイルとぶつからない名前にする。
_BUNDLED_EDGE_FILENAME = "twbpatch_kpi_tree_edge.hyper"
_EDGE_FIELDS = [
    {"name": "edge", "datatype": "string", "role": "dimension"},
    {"name": "point", "datatype": "string", "role": "dimension"},
    {"name": "x", "datatype": "integer", "role": "measure"},
    {"name": "y", "datatype": "integer", "role": "measure"},
]
#: エッジの表が持つ k の上限（examples/edge.txt）。表を広げたら同時に変える。
_EDGE_MAX_OFFSET = 13
_EDGE_COLOR = "#666666"
_EDGE_SIZE = 0.29585635662078857


@dataclass
class KpiNode:
    """KPI ツリーの1ノード。`children` が空ならツリーの末端。"""

    worksheet: TwbWorksheet
    children: list[KpiNode] = field(default_factory=list)


def build_kpi_tree(
    workbook: TwbWorkbook,
    *,
    dashboard_name: str,
    root: KpiNode,
    align: str = "center",
    edges: bool = False,
    edge_hyper: str | None = None,
    content_style: dict[str, str | int | None] | None = None,
    spacing_scale: float = 1.0,
) -> TwbDashboard:
    _validate_spacing_scale(spacing_scale)
    if not isinstance(align, str) or align.lower() not in _ALIGNS:
        raise ValueError(f"align must be center or top: {align!r}")
    align = align.lower()
    if not isinstance(edges, bool):
        raise TypeError("edges must be bool")
    # edges=True でパスを渡さなければ同梱の表を使い、save() が .twb の隣へ置く。
    # edge_hyper を渡したときは、そのパスのファイルを利用者が用意する。
    if edges and edge_hyper is None:
        edge_hyper = _BUNDLED_EDGE_FILENAME
    tree_style = _tree_style(content_style)
    inset = {side: _inset(tree_style, side) for side in _SIDES}
    _validate_tree(workbook, root, set())
    _validate_dashboard_name(workbook, dashboard_name)
    if edge_hyper is not None:
        _validate_edges(workbook, root, align, edge_hyper)

    edge_fields = None if edge_hyper is None else _edge_fields(_edge_datasource(workbook, edge_hyper))
    depth = _depth(root)
    gap = 0 if edge_fields is None else _EDGE_WIDTH
    dashboard = workbook.create_dashboard(
        name=dashboard_name,
        width=depth * _NODE_WIDTH + (depth - 1) * gap + inset["left"] + inset["right"],
        height=_leaf_count(root) * _NODE_HEIGHT + inset["top"] + inset["bottom"],
    )
    row = dashboard.create_container(direction="horizontal")
    row.update(style=tree_style)
    _place(workbook, row, root, depth, align, edge_fields, _scaled_spacing(_CARD_STYLE, spacing_scale))
    background = tree_style.get("background_color")
    if edge_fields is not None and background is not None:
        for parent in _parents(root):
            _fill_background(workbook.get_worksheets(name=_edge_sheet_name(parent))[0], str(background))
    return dashboard


def _tree_style(content_style: dict[str, str | int | None] | None) -> dict[str, str | int | None]:
    """台紙の書式。`build_report()` と同じく既定に重ねる。XML を変える前に大きさの計算まで検証する。"""
    style: dict[str, str | int | None] = dict(_DEFAULT_REPORT_CONTENT_STYLE)
    if content_style is not None:
        style.update(validate_style_group("content_style", content_style))
    for name, value in style.items():
        if not name.replace("_", "").isalnum():
            raise ValueError(f"invalid style name: {name}")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int))):
            raise TypeError(f"style value must be str, int, or None: {name}")
    for side in _SIDES:
        _inset(style, side)
    return style


def _inset(style: dict[str, str | int | None], side: str) -> int:
    """台紙の 1 辺で、中身が内へ寄る幅（外側の余白 + 内側の余白）。"""
    total = 0
    for kind in ("margin", "padding"):
        value = style.get(f"{kind}_{side}", style.get(kind))
        if value is None:
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"content_style {kind} must be a whole number: {value!r}") from None
        if number < 0:
            raise ValueError(f"content_style {kind} must not be negative: {value!r}")
        total += number
    return total


def _validate_tree(workbook: TwbWorkbook, node: KpiNode, seen: set[str]) -> None:
    """XML を変える前に全ノードを検証する。同じシートの再登場で循環も止まる。"""
    if not isinstance(node, KpiNode):
        raise TypeError("tree nodes must be KpiNode")
    if not isinstance(node.worksheet, TwbWorksheet):
        raise TypeError("KpiNode.worksheet must be TwbWorksheet")
    if node.worksheet._context is not workbook._context:
        raise ValueError("worksheet must belong to the workbook")
    worksheet_id = node.worksheet.id
    if worksheet_id in seen:
        raise ValueError(f"worksheet appears more than once in the tree: {worksheet_id}")
    seen.add(worksheet_id)
    if not isinstance(node.children, list):
        raise TypeError("KpiNode.children must be a list")
    for child in node.children:
        _validate_tree(workbook, child, seen)


def _validate_dashboard_name(workbook: TwbWorkbook, name: str) -> None:
    """`create_dashboard()` と同じ検証。エッジ用データソースを作った後に失敗しないよう先に行う。"""
    if not isinstance(name, str):
        raise TypeError("dashboard_name must be a string")
    stripped = name.strip()
    if not stripped:
        raise ValueError("name must not be empty")
    if workbook.get_dashboards(id=stripped) or workbook.get_dashboards(name=stripped):
        raise ValueError(f"dashboard already exists: {stripped}")


def _validate_edges(workbook: TwbWorkbook, root: KpiNode, align: str, edge_hyper: str) -> None:
    if not isinstance(edge_hyper, str) or not edge_hyper.lower().endswith(".hyper"):
        raise ValueError("edge_hyper must be a .hyper file path")
    if align != "top":
        raise ValueError("edges can only be drawn with align='top'")
    existing = workbook.get_datasources(name=_EDGE_DATASOURCE_NAME)
    if existing:
        _edge_fields(existing[0])
        dbnames = existing[0]._resolve_element().xpath("./*[local-name()='extract']/*[local-name()='connection']/@dbname")
        if [str(value) for value in dbnames] != [edge_hyper]:
            raise ValueError(
                f"{_EDGE_DATASOURCE_NAME} already exists with a different .hyper path: {list(map(str, dbnames))}"
            )
    for parent in _parents(root):
        offsets = _edge_offsets(parent)
        if offsets[-1] > _EDGE_MAX_OFFSET:
            raise ValueError(
                f"too many leaves under {parent.worksheet.id} to draw edges "
                f"(offset {offsets[-1]} > {_EDGE_MAX_OFFSET})"
            )
        name = _edge_sheet_name(parent)
        if workbook.get_worksheets(name=name):
            raise ValueError(f"worksheet already exists: {name}")


def _edge_datasource(workbook: TwbWorkbook, edge_hyper: str) -> TwbDatasource:
    """ワークブックにあれば使い回し、無ければ .hyper から作る。"""
    existing = workbook.get_datasources(name=_EDGE_DATASOURCE_NAME)
    if existing:
        return existing[0]
    return workbook.create_hyper_datasource(
        name=_EDGE_DATASOURCE_NAME,
        path=edge_hyper,
        fields=[dict(item) for item in _EDGE_FIELDS],
    )


def _edge_fields(edges: TwbDatasource) -> dict[str, TwbField]:
    fields: dict[str, TwbField] = {}
    for item in _EDGE_FIELDS:
        column = item["name"]
        matches = edges.get_fields(id=f"[{column}]")
        if len(matches) != 1:
            raise ValueError(f"edge datasource needs a [{column}] column")
        fields[column] = matches[0]
    return fields


def _parents(node: KpiNode) -> list[KpiNode]:
    if not node.children:
        return []
    return [node, *(parent for child in node.children for parent in _parents(child))]


def _depth(node: KpiNode) -> int:
    return 1 + max((_depth(child) for child in node.children), default=0)


def _leaf_count(node: KpiNode) -> int:
    return sum(_leaf_count(child) for child in node.children) or 1


def _edge_offsets(node: KpiNode) -> list[int]:
    """上端揃えでの、親の中心から各子の中心までの縦位置（ノードの高さの半分単位）。"""
    offsets: list[int] = []
    leaves_before = 0
    for child in node.children:
        offsets.append(2 * leaves_before)
        leaves_before += _leaf_count(child)
    return offsets


def _edge_sheet_name(node: KpiNode) -> str:
    return f"エッジ|{node.worksheet.id}"


def _place(
    workbook: TwbWorkbook,
    row: TwbDashboardContainer,
    node: KpiNode,
    columns: int,
    align: str,
    edge_fields: dict[str, TwbField] | None,
    card_style: dict[str, str | int | None],
) -> None:
    """`row` は `columns` 列ぶんの幅、高さ 末端数 × ノードの高さ の横コンテナ。

    コンテナの最後の子は固定サイズでも残りいっぱいに伸びるため、カードや
    ノード列の後ろに伸びてよい空白を置いて大きさを保つ。
    """
    stretches = _leaf_count(node) > 1
    column = row.create_container(direction="vertical", fixed_size=_NODE_WIDTH)
    if align == "center" and stretches:
        column.add_spacer()
    card = column.add_worksheet(
        node.worksheet,
        fixed_size=_NODE_HEIGHT,
        # 文字が無くても、背景色があるタイトルは帯として出す（KPI カード）
        show_title=node.worksheet.title is not None
        or node.worksheet.title_style["background_color"] is not None,
    )
    card.update(style=dict(card_style))
    if stretches:
        column.add_spacer()

    if not node.children:
        if columns > 1:
            row.add_spacer()
        return
    if edge_fields is not None:
        row.add_worksheet(
            _draw_edge_sheet(workbook, node, edge_fields),
            fixed_size=_EDGE_WIDTH,
            show_title=False,
        )
    children = row.create_container(direction="vertical")
    for child in node.children:
        child_row = children.create_container(
            direction="horizontal",
            fixed_size=_leaf_count(child) * _NODE_HEIGHT,
        )
        _place(workbook, child_row, child, columns - 1, align, edge_fields, card_style)


def _draw_edge_sheet(
    workbook: TwbWorkbook,
    node: KpiNode,
    fields: dict[str, TwbField],
) -> TwbWorksheet:
    """親 1 つぶんのエッジ。軸の範囲は、シートの高さ（親の行）と y=0 が親の中心に来ることから決まる。"""
    sheet = workbook.create_worksheet(name=_edge_sheet_name(node), visible=False)
    y = sheet.add_field(field=fields["y"], shelf="rows", aggregation="sum", discrete=False)
    x = sheet.add_field(field=fields["x"], shelf="columns", aggregation="sum", discrete=False)
    pane = sheet.get_panes()[0]
    pane.add_field(field=fields["edge"], encoding="detail")
    pane.add_field(field=fields["point"], encoding="detail")
    pane.update(
        mark_type="line",
        mark_color=_EDGE_COLOR,
        mark_size=_EDGE_SIZE,
        mark_scaling=False,
        line_interpolation="step",
    )
    sheet.add_filter(field=fields["edge"])
    sheet.get_filters()[0].update(values=[f"E-{offset}" for offset in _edge_offsets(node)])
    for placement in (x, y):
        sheet.set_axis_visibility(field=placement, visible=False)
    sheet.set_axis_range(field=y, min_value=-1, max_value=2 * _leaf_count(node) - 1, reverse=True)
    sheet.set_axis_range(field=x, min_value=0, max_value=2)
    sheet.update(lines_visible=False)
    return sheet


def _fill_background(sheet: TwbWorksheet, color: str) -> None:
    """シートの背景は既定で白く、台紙の上で帯になる。透明（#00000000）を書いても Tableau Public では
    背景が残ったため、ワークシートとペインの両方を台紙と同じ色で塗る。"""
    style = _ensure_table_style(_ensure_table(sheet._resolve_element()))
    for element in ("pane", "table"):
        _set_style_value(style, element, "background-color", color)
    sheet._context.mark_dirty()


def bundled_attachments(root: object) -> list[tuple[str, Path]]:
    """`save()` が .twb と一緒に置くファイル。同梱のエッジの表を参照するデータソースがあるときだけ返す。

    保存のたびに XML から判定するので、KPI ツリーを作ったセッションに限らず、作った .twb を
    開き直して別の場所へ保存したときも .hyper が付いていく。
    """
    dbnames = root.xpath(  # type: ignore[attr-defined]
        "/workbook/datasources/datasource/*[local-name()='extract']/*[local-name()='connection']/@dbname"
    )
    if _BUNDLED_EDGE_FILENAME in {str(value) for value in dbnames}:
        return [(_BUNDLED_EDGE_FILENAME, _BUNDLED_EDGE_HYPER)]
    return []
