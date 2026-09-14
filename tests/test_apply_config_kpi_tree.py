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
    assert set(_card_zones(dashboard)) == {"売上", "利益", "地域数"}
    # 既定の余白は「多め」: 台紙の外側 8 + 内側 16 の分だけダッシュボードが広がる
    assert (dashboard.width, dashboard.height) == (400 + 2 * 24, 300 + 2 * 24)
    assert dashboard.get_containers()[0].style["padding"] == "16"
    zones = _card_zones(dashboard)
    assert (zones["売上"].x, zones["売上"].y) == (24, 24)
    assert (zones["利益"].x, zones["利益"].y) == (224, 24)
    assert (zones["地域数"].x, zones["地域数"].y) == (224, 174)

    # デザインルールの色の参照（@main_color）が実際の色コードになってカードに入る
    assert "#2f3b52" in ET.tostring(
        workbook.tree.xpath("/workbook/worksheets/worksheet[@name='売上']")[0], encoding="unicode"
    )


def test_kpi_tree_follows_design_spacing(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": {"main_color": "#2f3b52", "spacing": "narrow"}, "kpi_tree": _kpi_tree()})

    dashboard = workbook.get_dashboards(name="KPIツリー")[0]
    assert (dashboard.width, dashboard.height) == (400 + 2 * 12, 300 + 2 * 12)
    assert dashboard.get_containers()[0].style["margin"] == "4"


def test_kpi_tree_draws_edges_when_edge_hyper_is_given(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": DESIGN, "kpi_tree": _kpi_tree(edge_hyper="edge.hyper")})

    assert workbook.get_datasources(name="KPIツリーのエッジ")
    assert workbook.get_worksheets(name="エッジ|売上")


def test_kpi_tree_without_edge_hyper_draws_no_edges(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    workbook.apply_config({"design": DESIGN, "kpi_tree": _kpi_tree(edge_hyper="")})

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
