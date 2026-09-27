"""設定画面が出す `kpi_tree` セクションを適用する。

ノードごとに `draw_card()` でカードを作ってから `build_kpi_tree()` で並べる 2 段になる。
"""

from __future__ import annotations

import logging

import pytest
from lxml import etree as ET

from twbpatch import TwbWorkbook


SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
"""

DESIGN = {"main_color": "#2f3b52"}


def _workbook(tmp_path):
    path = tmp_path / "tree.twb"
    path.write_text(SOURCE, encoding="utf-8")
    return TwbWorkbook.open(str(path))


def _kpi_tree(**overrides):
    kpi_tree = {
        "name": "KPIツリー",
        "datasource": "売上データ",
        "align": "top",
        "root": {
            "sheet": "売上",
            "params": {"main_metric": "売上", "sub_metric": "利益", "main_color": "@main_color"},
            "children": [
                {"sheet": "利益", "params": {"main_metric": "利益"}, "children": []},
                {"sheet": "地域数", "params": {"main_metric": "地域"}},
            ],
        },
    }
    kpi_tree.update(overrides)
    return kpi_tree


def _card_zones(dashboard):
    def walk(container):
        zones = [zone for zone in container.get_zones() if zone.kind == "worksheet"]
        for child in container.get_containers():
            zones.extend(walk(child))
        return zones

    return {zone.name: zone for zone in walk(dashboard.get_containers()[0])}


def test_kpi_tree_draws_cards_and_places_them(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": DESIGN, "kpi_tree": _kpi_tree()})

    dashboard = workbook.get_dashboards(name="KPIツリー")[0]
    # 上端揃えなのでエッジ（幅 60）も入る
    assert set(_card_zones(dashboard)) == {"売上", "エッジ|売上", "利益", "地域数"}
    # 既定の余白は「狭い」: 台紙の外側 4 + 内側 8 の分だけダッシュボードが広がる
    # （2026-09-21 に既定を wide から narrow へ変更）
    assert (dashboard.width, dashboard.height) == (400 + 60 + 2 * 12, 300 + 2 * 12)
    assert dashboard.get_containers()[0].style["padding"] == "8"
    zones = _card_zones(dashboard)
    assert (zones["売上"].x, zones["売上"].y) == (12, 12)
    assert (zones["利益"].x, zones["利益"].y) == (272, 12)
    assert (zones["地域数"].x, zones["地域数"].y) == (272, 162)

    # デザインルールの色の参照（@main_color）が実際の色コードになってカードに入る
    assert "#2f3b52" in ET.tostring(
        workbook.tree.xpath("/workbook/worksheets/worksheet[@name='売上']")[0], encoding="unicode"
    )


def test_kpi_tree_node_info_places_a_floating_icon_over_the_node(tmp_path) -> None:
    """ノードの `info:` は、build_kpi_tree() が並べた後にそのノードのゾームの右上へ
    浮動でインフォメーションアイコンを重ねる（2026-09-23）。"""
    workbook = _workbook(tmp_path)
    kpi_tree = _kpi_tree()
    kpi_tree["root"]["info"] = {"text": "全社の売上合計です", "icon": "info"}

    workbook.apply_config({"design": DESIGN, "kpi_tree": kpi_tree})

    dashboard = workbook.get_dashboards(name="KPIツリー")[0]
    zones = _card_zones(dashboard)
    all_zones = {zone.name: zone for zone in dashboard.get_zones()}
    icon_zone = all_zones["info|売上"]
    assert icon_zone.placement_mode == "floating"
    assert (icon_zone.width, icon_zone.height) == (30, 30)
    assert icon_zone.x == zones["売上"].x + zones["売上"].width - 30 - 4
    assert icon_zone.y == zones["売上"].y + 4
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_kpi_tree_follows_design_spacing(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": {"main_color": "#2f3b52", "spacing": "narrow"}, "kpi_tree": _kpi_tree()})

    dashboard = workbook.get_dashboards(name="KPIツリー")[0]
    assert (dashboard.width, dashboard.height) == (400 + 60 + 2 * 12, 300 + 2 * 12)
    assert dashboard.get_containers()[0].style["margin"] == "4"


def test_kpi_tree_draws_edges_with_the_bundled_hyper_when_aligned_to_top(tmp_path) -> None:
    """上端揃えならエッジを描く。.hyper は同梱のものを使い、YAML には書かない（2026-09-15）。"""
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": DESIGN, "kpi_tree": _kpi_tree(align="top")})

    edges = workbook.get_datasources(name="KPIツリーのエッジ")
    assert edges
    assert workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$name]/extract/connection/@dbname", name=edges[0].id
    ) == ["twbpatch_kpi_tree_edge.hyper"]
    assert workbook.get_worksheets(name="エッジ|売上")


def test_kpi_tree_aligned_to_center_draws_no_edges(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": DESIGN, "kpi_tree": _kpi_tree(align="center")})

    assert workbook.get_datasources(name="KPIツリーのエッジ") == []
    assert workbook.get_worksheets(name="エッジ|売上") == []


def test_dashboard_and_kpi_tree_make_two_dashboards(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = {
        "name": "売上ダッシュボード",
        "rows": [
            {
                "name": "段",
                "areas": [
                    {
                        "kind": "worksheet",
                        "datasource": "売上データ",
                        "sheet": "ダッシュボードの売上",
                        "chart": "draw_card",
                        "params": {"main_metric": "売上"},
                    }
                ],
            }
        ],
    }

    workbook.apply_config({"design": DESIGN, "dashboard": dashboard, "kpi_tree": _kpi_tree()})

    assert [item.name for item in workbook.get_dashboards()] == ["売上ダッシュボード", "KPIツリー"]


def test_design_colors_are_consumed_by_kpi_tree_alone(tmp_path, caplog) -> None:
    workbook = _workbook(tmp_path)

    with caplog.at_level(logging.WARNING):
        workbook.apply_config({"design": {"main_color": "#2f3b52", "spacing": "wide"}, "kpi_tree": _kpi_tree()})

    assert "main_color" not in caplog.text
    assert "spacing" not in caplog.text


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"name": ""}, "needs a name"),
        ({"datasource": None}, "needs a datasource"),
        ({"root": None}, "node must be a mapping"),
        ({"root": {"sheet": "売上", "params": {"main_metric": "売上"}, "children": "利益"}}, "children must be a list"),
    ],
)
def test_kpi_tree_rejects_malformed_section_before_drawing(tmp_path, override, message) -> None:
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match=message):
        workbook.apply_config({"design": DESIGN, "kpi_tree": _kpi_tree(**override)})

    assert workbook.get_worksheets() == []
    assert workbook.get_dashboards() == []


def test_kpi_tree_cards_have_no_inner_padding_and_rounded_corners(tmp_path) -> None:
    """ノードは KPI カードなので内側の余白は 0、角の丸みは 8（2026-09-21）。"""
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": {"main_color": "#2f3b52", "spacing": "narrow"}, "kpi_tree": _kpi_tree()})

    dashboard = workbook.get_dashboards(name="KPIツリー")[0]
    card = _card_zones(dashboard)["売上"]
    assert (card.style["padding"], card.style["margin"], card.style["corner_radius"]) == ("0", "4", "8")


def test_kpi_tree_scales_card_spacing_when_the_design_asks_for_wide(tmp_path) -> None:
    """余白「多め」ならカードの余白も 1.5 倍。0 は 0 のまま（2026-09-21）。"""
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": {"main_color": "#2f3b52", "spacing": "wide"}, "kpi_tree": _kpi_tree()})

    card = _card_zones(workbook.get_dashboards(name="KPIツリー")[0])["売上"]
    assert (card.style["margin"], card.style["padding"]) == ("6", "0")
