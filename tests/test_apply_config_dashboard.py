"""設定画面が出す `dashboard` セクションを適用する。

画面の 1 エリア = 1 シートなので、`draw_*()` でシートを作ってから
`build_report()` で並べる 2 段になる。アクションはそのあとに張る。
"""

from __future__ import annotations

import pytest
import copy
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
      <column name="[Budget]" caption="予算"
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


def _template(tmp_path):
    from test_dashboard_layout_template import _layout_workbook, _template_root
    return _template_root(tmp_path, _layout_workbook(tmp_path))


def test_template_stacks_generated_charts_below_template(tmp_path):
    from test_dashboard_layout_template import _nodes
    baseline = _workbook(tmp_path)
    baseline.apply_config(_config())
    original = next(n for n in _nodes(baseline.get_dashboards()[0].layout) if n['kind'] == 'worksheet')
    workbook = _workbook(tmp_path)
    config = _config()
    config['design'].update(dashboard_template='sales', dashboard_template_dashboard='Source')
    workbook.apply_config(config, template_root=_template(tmp_path))
    dashboard = workbook.get_dashboards()[0]
    assert (dashboard.layout['width'], dashboard.layout['height']) == (1600, 1100)
    generated = next(n for n in _nodes(dashboard.layout) if n['kind'] == 'worksheet')
    for key in ('x', 'width', 'height'):
        assert generated[key] == pytest.approx(original[key], abs=0.02)
    assert generated['y'] == pytest.approx(original['y'] + 200, abs=0.02)
    assert any(r['text'] == 'グラフ' for n in _nodes(dashboard.layout) for r in n.get('text_runs', []))
    assert dashboard.get_actions()
    assert dashboard.get_worksheets()
    assert len(dashboard.get_containers()) == 1


def test_template_only_has_no_content_region(tmp_path):
    workbook = _workbook(tmp_path)
    workbook.apply_config({'design': {'dashboard_template': 'sales'},
                           'dashboard': {'name': 'Template only', 'rows': []}}, template_root=_template(tmp_path))
    layout = workbook.get_dashboards()[0].layout
    assert (layout['width'], layout['height']) == (1000, 200)
    assert not workbook.get_worksheets()


@pytest.mark.parametrize('with_content', [False, True])
def test_template_and_generated_content_save_with_validation(tmp_path, with_content):
    workbook = _workbook(tmp_path)
    config = _config() if with_content else {'design': {}, 'dashboard': {'name': 'Template only', 'rows': []}}
    config['design']['dashboard_template'] = 'sales'
    workbook.apply_config(config, template_root=_template(tmp_path))
    errors = [m.code for m in workbook.validate() if m.severity == 'error']
    assert errors == []
    output = tmp_path / 'validated.twb'
    workbook.save(str(output))
    assert TwbWorkbook.open(str(output)).get_dashboards()[0].layout == workbook.get_dashboards()[0].layout


def test_invalid_template_does_not_mutate_workbook(tmp_path):
    from lxml import etree as ET
    workbook = _workbook(tmp_path)
    before = ET.tostring(workbook.tree)
    config = _config()
    config['design']['dashboard_template'] = 'missing'
    with pytest.raises(ValueError):
        workbook.apply_config(config, template_root=tmp_path)
    assert ET.tostring(workbook.tree) == before


def test_template_stack_handles_different_widths_and_floating_nodes(tmp_path):
    from twbpatch.dashboard_layout import stack_dashboard_layouts
    from test_dashboard_layout_template import _layout_workbook, _nodes
    layout = _layout_workbook(tmp_path).get_dashboards()[0].layout
    small = dict(layout, width=600)
    combined = stack_dashboard_layouts(layout, small)
    assert (combined['width'], combined['height']) == (1000, 400)
    floating = [n for n in combined['nodes'] if n['placement'] == 'floating']
    assert [n['y'] for n in floating] == [10, 210]
    original = next(n for n in _nodes(layout) if n['kind'] == 'worksheet')
    sheets = [n for n in _nodes(combined) if n['kind'] == 'worksheet']
    assert [n['y'] for n in sheets] == [original['y'], original['y'] + 200]
    assert all(n['width'] == original['width'] for n in sheets)


def test_template_stack_preserves_dashboard_background_in_upper_region(tmp_path):
    from twbpatch.dashboard_layout import stack_dashboard_layouts
    from test_dashboard_layout_template import _layout_workbook, _nodes
    layout = _layout_workbook(tmp_path).get_dashboards()[0].layout
    layout['style']['dashboard'] = {'background-color': '#112233'}
    content = copy.deepcopy(layout)
    content['style']['dashboard'] = {'background-color': '#ffffff'}
    stacked = stack_dashboard_layouts(layout, content)
    upper = [n for n in _nodes(stacked) if n.get('style', {}).get('background_color') == '#112233']
    assert upper and upper[0]['y'] == 0 and upper[0]['height'] == 200
    layout['style'] = {'all': {'background-color': '#445566'}}
    stacked = stack_dashboard_layouts(layout, content)
    assert any(n.get('style', {}).get('background_color') == '#445566' for n in _nodes(stacked))
    assert all(n['attributes']['fixed-size'].isdigit() for n in _nodes(stacked)
               if 'fixed-size' in n.get('attributes', {}))


def test_template_stack_uses_integer_fixed_sizes(tmp_path):
    from twbpatch.dashboard_layout import stack_dashboard_layouts
    from test_dashboard_layout_template import _layout_workbook, _nodes
    layout = _layout_workbook(tmp_path).get_dashboards()[0].layout
    stacked = stack_dashboard_layouts(layout, layout)
    assert all(n['attributes']['fixed-size'].isdigit() for n in _nodes(stacked)
               if 'fixed-size' in n.get('attributes', {}))


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


def test_area_info_places_a_floating_icon_over_the_area(tmp_path) -> None:
    """エリアの `info:` は、build_report() が Tiled 配置を組んだ後にそのエリアの
    ゾーンの右上へ浮動でインフォメーションアイコンを重ねる（2026-09-23）。"""
    workbook = _workbook(tmp_path)
    config = _config()
    config["dashboard"]["rows"][1]["areas"][1]["info"] = {
        "text": "地域ごとの売上です",
        "icon": "quest",
        "heading": "補足",
    }

    workbook.apply_config(config)

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    zones = {zone.name: zone for zone in dashboard.get_zones()}
    main_zone = zones["地域別売上"]
    icon_zone = zones["info|地域別売上"]
    assert icon_zone.placement_mode == "floating"
    assert (icon_zone.width, icon_zone.height) == (30, 30)
    assert icon_zone.x == main_zone.x + main_zone.width - 30 - 4
    assert icon_zone.y == main_zone.y + 4
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_bar_dual_axis_comes_through_the_config(tmp_path) -> None:
    """棒グラフの項目なし・バーインバー・二重軸の折れ線が YAML から通ること
    （2026-09-22 追加）。画面は使わない引数を書かないので、無い前提で読む。
    """
    workbook = _workbook(tmp_path)
    config = _config()
    config["dashboard"]["rows"][1]["areas"] = [
        {
            "kind": "worksheet", "datasource": "売上データ", "sheet": "バーインバー",
            "chart": "draw_bar",
            "params": {"item": "地域", "metric": "売上", "sub_metric": "予算",
                       "bar_color": "@main_color"},
        },
        {
            "kind": "worksheet", "datasource": "売上データ", "sheet": "折れ線付き",
            "chart": "draw_bar",
            "params": {"item": "地域", "metric": "売上", "line_metric": "予算"},
        },
        {
            "kind": "worksheet", "datasource": "売上データ", "sheet": "三つとも",
            "chart": "draw_bar",
            "params": {"item": "地域", "metric": "売上", "sub_metric": "予算",
                       "line_metric": "予算"},
        },
        {
            "kind": "worksheet", "datasource": "売上データ", "sheet": "項目なし",
            "chart": "draw_bar", "params": {"metric": "売上"},
        },
    ]

    workbook.apply_config(config)

    def folds(sheet: str) -> list[tuple[str | None, str | None]]:
        return [
            (item.get("scope"), item.get("synchronized"))
            for item in workbook.tree.xpath(
                "/workbook/worksheets/worksheet[@name=$name]/table/style"
                "/style-rule[@element='axis']/encoding[@fold='true']",
                name=sheet,
            )
        ]

    assert folds("バーインバー") == [("cols", "true")]
    assert folds("折れ線付き") == [("cols", None)]
    assert folds("三つとも") == [("cols", None)]
    assert folds("項目なし") == []
    # 3 つそろうと棒はメジャーバリューにまとまる
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='三つとも']/table/cols)"
    ).startswith("([ds1].[Multiple Values] + ")
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='項目なし']/table/rows)"
    ) == ""
    assert [
        mark.get("class")
        for mark in workbook.tree.xpath(
            "/workbook/worksheets/worksheet[@name='折れ線付き']/table/panes/pane/mark"
        )
    ] == ["Bar", "Bar", "Line"]
    assert not [
        message for message in workbook.validate() if message.severity == "error"
    ]


def test_report_column_titles_are_added_as_floating_text(tmp_path) -> None:
    """帳票の消えた項目名だけを浮動テキストで補う（2026-09-22 追加）。

    **Tableau は行に置いた項目の名前は出すが、棒・色帯の列の名前だけ出さない。**
    その空いている分にだけ文字を置く（行に置いた項目の分まで置くと二重になる）。
    列幅は `draw_sheet()` が固定した概算で、置いたあと人が Tableau で直す前提。
    """
    workbook = _workbook(tmp_path)
    config = _config()
    config["dashboard"]["rows"] = [{
        "name": "1段目",
        "areas": [{
            "kind": "worksheet", "datasource": "売上データ", "sheet": "帳票",
            "chart": "draw_sheet",
            "params": {"items": ["地域", "売上"], "bar_metrics": ["予算"],
                       "color_metrics": ["予算"]},
        }],
    }]

    workbook.apply_config(config)

    texts = workbook.tree.xpath(
        "/workbook/dashboards/dashboard/zones/zone[@type-v2='text']"
        "/formatted-text/run"
    )
    # 出すのは棒 1 つと色帯 1 つだけ。行に置いた「地域」「売上」は Tableau が出す
    assert [run.text for run in texts] == ["予算", "予算"]
    zones = [run.getparent().getparent() for run in texts]
    assert [int(zone.get("x")) for zone in zones] == sorted(
        int(zone.get("x")) for zone in zones
    )
    assert len({zone.get("y") for zone in zones}) == 1
    # 列幅はゾーンの幅から余白を引いて列数で割った暫定値（2026-09-22 指定）
    sheet_zone = [z for z in workbook.get_dashboards()[0].get_zones()
                  if z.worksheet_id == "帳票"][0]
    from twbpatch.connected_dashboard import _raw_to_px

    width = (sheet_zone.width - 16) // 4  # 項目 2 + 棒 1 + 色帯 1
    assert _raw_to_px(int(zones[0].get("x")), 1600) == sheet_zone.x + 8 + width * 2
    assert _raw_to_px(int(zones[0].get("w")), 1600) == width
    # ヘッダーの帯へ重ねるため 25px 下げる。文字は 9px の細め（2026-09-22 指定）
    assert _raw_to_px(int(zones[0].get("y")), 900) == sheet_zone.y + 8 + 25
    run = texts[0]
    assert (run.get("fontsize"), run.get("bold")) == ("9", None)
    # 同じ幅をワークシートの列にも書くので、文字と実際の列が揃う
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='帳票']/table/style"
        "/style-rule[@element='header']/format[@attr='width']/@value"
    ) == [str(width), str(width)]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='帳票']/table/panes/pane"
        "/style/style-rule[@element='pane']/format[@attr='maxwidth']/@value"
    ) == [str(width), str(width)]
    assert not [
        message for message in workbook.validate() if message.severity == "error"
    ]


def test_filter_card_title_is_bold_and_size_10(tmp_path) -> None:
    """フィルタの名称は太字、文字の大きさは 10（2026-09-22 指定）。

    Tableau はフィルタカードの書式を、置いた先のダッシュボードではなく
    フィルタを持つワークシートの `<style-rule element='quick-filter-title'>` に
    書く（実ワークブックで確認）。
    """
    workbook = _workbook(tmp_path)
    workbook.apply_config(_config())

    rules = workbook.tree.xpath(
        "/workbook/worksheets/worksheet/table/style"
        "/style-rule[@element='quick-filter-title']"
    )
    assert [
        sorted((item.get("attr"), item.get("value")) for item in rule)
        for rule in rules
    ] == [[("font-size", "10"), ("font-weight", "bold")]]


def test_apply_config_accepts_yaml_text(tmp_path) -> None:
    path = tmp_path / "twbpatch_config.yaml"
    path.write_text(
        yaml.safe_dump(_config(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    workbook = _workbook(tmp_path)
    workbook.apply_config(path)

    assert workbook.get_dashboards(name="売上ダッシュボード")


def test_row_distribute_evenly_decides_whether_the_area_width_applies(tmp_path) -> None:
    """段の `distribute_evenly` で幅の割り方を選ぶ（2026-09-21 追加）。

    Tableau の「均等に配布」の段では、エリアごとの固定幅は読まれない
    （Tableau 自身もその組み合わせを書かない）。均等割りを選んだ段では幅を
    捨てて均等に、選ばなかった段では指定した px をそのまま幅にする。
    """
    canvas = 1600

    def widths(distribute: bool) -> list[int]:
        config = _config()
        row = config["dashboard"]["rows"][1]
        row["distribute_evenly"] = distribute
        row["areas"][1]["width"] = "300"
        workbook = _workbook(tmp_path)
        workbook.apply_config(config)
        dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
        root = dashboard.get_containers()[0].get_containers(name="売上ダッシュボード")[0]
        row_el = root.get_containers()[1]._resolve_element()
        return [
            round(int(zone.get("w") or 0) * canvas / 100000)
            for zone in row_el.xpath("./*[local-name()='zone']")
        ]

    # 均等割り: 600 と 300 は捨てられ、半分ずつになる（末尾に余りは出ない）
    assert widths(True) == [776, 776]
    # 幅を指定: px がそのまま通り、余りは末尾の空きゾーンが吸う
    assert widths(False) == [600, 300, 652]


def test_apply_config_rejects_a_non_boolean_distribute_evenly(tmp_path) -> None:
    config = _config()
    config["dashboard"]["rows"][1]["distribute_evenly"] = "yes"
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="distribute_evenly must be true or false"):
        workbook.apply_config(config)


def test_header_colors_and_the_canvas_come_from_the_design_rules(tmp_path) -> None:
    """ヘッダーの色はデザインルールを参照でき、台紙の色もそこから来る（2026-09-21 追加）。

    画面の既定は背景＝`@main_color`、文字＝`@background_color`。台紙の灰色は
    ライブラリ側の固定値だったので、`design.background_color` で変えられるようにした。
    """
    config = _config()
    config["design"]["background_color"] = "#eef1f6"
    config["dashboard"]["header"]["background_color"] = "@main_color"
    config["dashboard"]["header"]["font_color"] = "@background_color"
    workbook = _workbook(tmp_path)
    workbook.apply_config(config)

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    outer = dashboard.get_containers()[0]
    header = outer.get_zones()[0]
    content = outer.get_containers(name="売上ダッシュボード")[0]

    assert header.style["background_color"] == "#2f3b52"  # @main_color
    assert content.style["background_color"] == "#eef1f6"
    from lxml import etree as ET

    run = header._resolve_element().xpath(".//*[local-name()='run']")[0]
    assert run.get("fontcolor") == "#eef1f6"  # @background_color
    # 余りを埋める空きゾーンも台紙と同じ色にする（灰色が残らない）
    zones = ET.tostring(content._resolve_element(), encoding="unicode")
    assert "#f5f5f5" not in zones


def test_kpi_card_drops_the_params_of_the_other_mode(tmp_path) -> None:
    """KPI カードは選んだモードの引数だけを渡す（2026-09-21 追加）。

    画面は今はモードに合う引数だけを書き出すが、全部の引数を並べていた頃の
    YAML には `sub_metric` と `budget_metric` が両方入っている。`draw_card()` は
    両方渡されると例外にするので、受け手側で使わない方を落とす。
    """
    config = _config()
    area = config["dashboard"]["rows"][1]["areas"][0]
    area["params"].update(
        {
            "mode": "budget",
            "sub_metric": "売上",  # 予実比較モードでは使わない
            "budget_metric": "売上",
            "budget_threshold": "1",
        }
    )
    workbook = _workbook(tmp_path)
    workbook.apply_config(config)

    datasource = workbook.get_datasources(name="売上データ")[0]
    # 条件ごとに率と文言の 2 つ（2026-09-21）
    assert [
        field.name
        for field in datasource.get_fields()
        if field.name.startswith("カテゴリ別売上_")
    ] == [
        "カテゴリ別売上_達成",
        "カテゴリ別売上_達成判定",
        "カテゴリ別売上_未達",
        "カテゴリ別売上_未達判定",
    ]


def test_numeric_params_are_accepted_as_strings(tmp_path) -> None:
    """数の引数は文字列でも受ける（2026-09-21 追加）。

    画面は数の入力欄も文字列で書き出す（`opacity: "0.4"`）ため、そのまま渡すと
    `draw_*()` が型で弾いていた。どれが数かは `draw_*()` の注釈から読む。
    """
    config = _config()
    config["dashboard"]["rows"][1]["areas"].append(
        {
            "kind": "worksheet",
            "datasource": "売上データ",
            "sheet": "象限",
            "chart": "draw_quadrant",
            "params": {
                "item": "カテゴリ",
                "x_metric": "売上",
                "y_metric": "売上",
                "size_metric": "売上",
                "opacity": "0.4",
            },
        }
    )
    workbook = _workbook(tmp_path)
    workbook.apply_config(config)

    pane = workbook.get_worksheets(name="象限")[0].get_panes()[0]
    # XML は 0..255 で持つので、往復すると端数が出る
    assert round(pane.mark_opacity, 2) == 0.4

    config["dashboard"]["rows"][1]["areas"][-1]["params"]["opacity"] = "濃いめ"
    with pytest.raises(ValueError, match="opacity must be a number"):
        _workbook(tmp_path).apply_config(config)


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


# ---------------------------------------------------------------------------
# build_waterfall: 画面のグラフ種類の 1 つとして `chart:` に指定できること
# （2026-09-23）。`draw_` で始まらない名前を通すには config_apply.py 側の
# ホワイトリスト（_EXTRA_CHARTS）を通る必要がある。
# ---------------------------------------------------------------------------

_WATERFALL_ORDERS_OBJECT_ID = "Orders_E82A0D784F4E42B1A8CF60FF78680595"

_WATERFALL_SOURCE = f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <connection class="federated">
        <named-connections>
          <named-connection name="excel-direct.1wk7x6i16gwroz19147dy1u57n1l" caption="sample">
            <connection class="excel-direct" filename="C:/sample.xlsx" />
          </named-connection>
        </named-connections>
        <relation type="collection">
          <relation connection="excel-direct.1wk7x6i16gwroz19147dy1u57n1l" name="Orders" table="[Orders$]" type="table">
            <columns header="yes">
              <column datatype="real" name="Sales" ordinal="0" />
              <column datatype="real" name="Cost" ordinal="1" />
            </columns>
          </relation>
        </relation>
      </connection>
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Cost]" caption="コスト" datatype="real" role="measure" type="quantitative" />
      <extract count="-1" enabled="true" object-id="" units="records" user-specific="false">
        <connection class="hyper" dbname="C:/temp/extract.hyper" schema="Extract" tablename="Extract">
          <relation type="collection">
            <relation name="{_WATERFALL_ORDERS_OBJECT_ID}" table="[Extract].[{_WATERFALL_ORDERS_OBJECT_ID}]" type="table" />
          </relation>
          <cols>
            <map key="[Sales]" value="[{_WATERFALL_ORDERS_OBJECT_ID}].[Sales]" />
            <map key="[Cost]" value="[{_WATERFALL_ORDERS_OBJECT_ID}].[Cost]" />
          </cols>
        </connection>
      </extract>
      <object-graph>
        <objects>
          <object caption="Orders" id="{_WATERFALL_ORDERS_OBJECT_ID}">
            <properties context="">
              <relation connection="excel-direct.1wk7x6i16gwroz19147dy1u57n1l" name="Orders" table="[Orders$]" type="table">
                <columns header="yes">
                  <column datatype="real" name="Sales" ordinal="0" />
                  <column datatype="real" name="Cost" ordinal="1" />
                </columns>
              </relation>
            </properties>
          </object>
        </objects>
        <relationships />
      </object-graph>
    </datasource>
  </datasources>
  <worksheets />
</workbook>
"""


def _waterfall_config_workbook(tmp_path):
    path = tmp_path / "waterfall_report.twb"
    path.write_text(_WATERFALL_SOURCE, encoding="utf-8")
    return TwbWorkbook.open(str(path))


def test_apply_config_builds_a_waterfall_chart(tmp_path) -> None:
    """`chart: build_waterfall` を含む `dashboard` 節が最後まで通ること。"""
    workbook = _waterfall_config_workbook(tmp_path)
    config = _config()
    config["dashboard"]["rows"] = config["dashboard"]["rows"][1:]
    config["dashboard"]["rows"][0]["areas"] = [
        {
            "kind": "worksheet",
            "datasource": "売上データ",
            "sheet": "損益ウォーターフォール",
            "chart": "build_waterfall",
            "params": {
                "metrics": ["売上", "コスト"],
                "connectors": True,
                "landing": True,
            },
        },
    ]

    workbook.apply_config(config)

    dashboard = workbook.get_dashboards(name="売上ダッシュボード")[0]
    assert [worksheet.name for worksheet in dashboard.get_worksheets()] == [
        "損益ウォーターフォール",
    ]
    datasource = workbook.get_datasources(name="売上データ")[0]
    assert datasource.get_fields(name="連番")
    assert [f.name for f in datasource.get_fields() if f.name.startswith("損益ウォーターフォール_")] == [
        "損益ウォーターフォール_値",
        "損益ウォーターフォール_項目名",
        "損益ウォーターフォール_種別",
        "損益ウォーターフォール_サイズ",
    ]
