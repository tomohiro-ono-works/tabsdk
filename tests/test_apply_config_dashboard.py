"""設定画面が出す `dashboard` セクションを適用する。

画面の 1 エリア = 1 シートなので、`draw_*()` でシートを作ってから
`build_report()` で並べる 2 段になる。アクションはそのあとに張る。
"""

from __future__ import annotations

import pytest
import yaml

from twbpatch import TwbWorkbook


SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
"""


def _workbook(tmp_path):
    path = tmp_path / "report.twb"
    path.write_text(SOURCE, encoding="utf-8")
    return TwbWorkbook.open(str(path))


def _config(**overrides):
    config = {
        "design": {
            "font": "Meiryo UI",
            "main_color": "#2f3b52",
            "spacing": "wide",
            "filter_apply_button": True,
        },
        "dashboard": {
            "name": "売上ダッシュボード",
            "width": "1600",
            "height": "900",
            "header": {
                "title": "月次レポート",
                "height": "44",
                "background_color": "#333333",
                "font_color": "#ffffff",
            },
            "rows": [
                {
                    "name": "上段",
                    "height": "50",
                    "areas": [
                        {
                            "kind": "filter",
                            "datasource": "売上データ",
                            "field": "地域",
                        }
                    ],
                },
                {
                    "name": "下段",
                    "height": "400",
                    "areas": [
                        {
                            "kind": "worksheet",
                            "datasource": "売上データ",
                            "width": "600",
                            "sheet": "カテゴリ別売上",
                            "chart": "draw_card",
                            "params": {
                                "main_metric": "売上",
                                "main_color": "@main_color",
                            },
                            "action": {
                                "type": "filter",
                                "target": "地域別売上",
                                "field": "カテゴリ",
                            },
                        },
                        {
                            "kind": "worksheet",
                            "datasource": "売上データ",
                            "sheet": "地域別売上",
                            "chart": "draw_bar",
                            "params": {"item": "地域", "metric": "売上"},
                        },
                    ],
                },
            ],
        },
    }
    config["dashboard"].update(overrides)
    return config


def test_apply_config_builds_the_whole_dashboard(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.apply_config(_config())

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    assert [worksheet.name for worksheet in dashboard.get_worksheets()] == [
        "カテゴリ別売上",
        "地域別売上",
    ]

    root = dashboard.get_containers()[0].get_containers(name="売上ダッシュボード")[0]
    rows = root.get_containers()
    assert [row.name for row in rows] == ["上段", "下段"]
    assert [row.fixed_size for row in rows] == [50, 400]
    assert [zone.kind for zone in rows[0].get_zones()] == ["filter"]

    # エリアの幅は 1 枚の列にして渡す
    assert [column.fixed_size for column in rows[1].get_containers()] == [600]


def test_apply_config_accepts_yaml_text(tmp_path) -> None:
    path = tmp_path / "twbpatch_config.yaml"
    path.write_text(
        yaml.safe_dump(_config(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    workbook = _workbook(tmp_path)
    workbook.apply_config(path)

    assert workbook.get_dashboards(name="売上ダッシュボード")


def test_apply_config_uses_the_header_title(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.apply_config(_config())

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    outer = dashboard.get_containers()[0]
    header = outer.get_zones()[0]
    # ダッシュボード名ではなくヘッダーの文言が入る
    assert header.text == "月次レポート"
    assert header.fixed_size == 44


def test_apply_config_resolves_design_tokens(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.apply_config(_config())

    worksheet = workbook.get_worksheets(name="カテゴリ別売上")[0]
    from lxml import etree as ET

    xml = ET.tostring(worksheet._resolve_element(), encoding="unicode")
    # @main_color がデザインルールの色コードへ置き換わる
    assert "#2f3b52" in xml
    assert "@main_color" not in xml


def test_apply_config_resolves_heatmap_design_tokens_for_crosstab(tmp_path) -> None:
    """`draw_crosstab` の min/mid/max_color はデザインルールの既定3色を
    `@min_color` 等で参照できる（2026-09-12 追加）。

    3色そろえるかゼロかしか許されない制約があるため、画面はグラフ選択時に
    自動でこの3トークンを参照させる（html_export.py の `defaultParamsFor()`）。
    ここでは Python 側の解決だけを検証する。
    """
    workbook = _workbook(tmp_path)
    config = _config()
    config["design"]["min_color"] = "#2166ac"
    config["design"]["mid_color"] = "#f7f7f7"
    config["design"]["max_color"] = "#b2182b"
    config["dashboard"]["rows"][1]["areas"].append(
        {
            "kind": "worksheet",
            "datasource": "売上データ",
            "sheet": "地域カテゴリ別ヒートマップ",
            "chart": "draw_crosstab",
            "params": {
                "x_item": "地域",
                "y_item": "カテゴリ",
                "color_metric": "売上",
                "label_metric": "売上",
                "min_color": "@min_color",
                "mid_color": "@mid_color",
                "max_color": "@max_color",
            },
        }
    )
    workbook.apply_config(config)

    # set_continuous_colors() は色をワークシート要素ではなく preferences の
    # color-palette へ書く（テスト対象は @トークンが実色へ解決されたかどうか）。
    from lxml import etree as ET

    root = workbook.tree.getroot()
    xml = ET.tostring(root, encoding="unicode")
    assert "#2166ac" in xml
    assert "#f7f7f7" in xml
    assert "#b2182b" in xml
    assert "@min_color" not in xml
    assert "@mid_color" not in xml
    assert "@max_color" not in xml


def test_apply_config_applies_the_filter_apply_button(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.apply_config(_config())

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    controls = dashboard.get_filter_controls()
    assert controls
    assert all(control.show_apply is True for control in controls)


def test_apply_config_creates_the_area_action(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.apply_config(_config())

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    actions = dashboard.get_actions()
    assert [action.type for action in actions] == ["filter"]
    assert actions[0].name == "カテゴリ別売上 で絞り込む"
    assert actions[0].source_worksheet_ids == ["カテゴリ別売上"]


def test_apply_config_creates_a_url_action(tmp_path) -> None:
    config = _config()
    config["dashboard"]["rows"][1]["areas"][0]["action"] = {
        "type": "url",
        "url": "https://example.com/",
    }
    workbook = _workbook(tmp_path)
    workbook.apply_config(config)

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    actions = dashboard.get_actions()
    assert [action.type for action in actions] == ["url"]
    assert actions[0].name == "カテゴリ別売上 からリンク"


def test_apply_config_names_rows_that_have_none(tmp_path) -> None:
    config = _config()
    for row in config["dashboard"]["rows"]:
        row["name"] = ""
    workbook = _workbook(tmp_path)
    workbook.apply_config(config)

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    root = dashboard.get_containers()[0].get_containers(name="売上ダッシュボード")[0]
    assert [row.name for row in root.get_containers()] == ["段1", "段2"]


def test_apply_config_rejects_an_unknown_design_token(tmp_path) -> None:
    config = _config()
    config["dashboard"]["rows"][1]["areas"][0]["params"]["main_color"] = "@accent"
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="unknown design token"):
        workbook.apply_config(config)


def test_apply_config_rejects_an_unknown_chart(tmp_path) -> None:
    config = _config()
    config["dashboard"]["rows"][1]["areas"][0]["chart"] = "draw_pie"
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="unknown chart"):
        workbook.apply_config(config)


def test_apply_config_rejects_an_unknown_area_kind(tmp_path) -> None:
    config = _config()
    config["dashboard"]["rows"][1]["areas"][0]["kind"] = "chart"
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="area kind must be one of"):
        workbook.apply_config(config)


def test_apply_config_rejects_a_bad_spacing(tmp_path) -> None:
    config = _config()
    config["design"]["spacing"] = "loose"
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="design.spacing must be one of"):
        workbook.apply_config(config)
