"""設定画面の KPI ツリータブ（html_kpi_tree.py、計画は docs/developer/tasks/I2_kpi_tree.md のステップ 4）。

既存の画面のテストと同じく、出力した HTML の文字列で確かめる。
"""

from __future__ import annotations

import json
import re

from twbpatch import TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def _html(tmp_path) -> str:
    return TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")


def _section(html: str) -> str:
    start = html.index('<section id="tab-kpi-tree">')
    return html[start:html.index("</section>", start)]


def test_kpi_tree_tab_has_the_approved_settings(tmp_path) -> None:
    html = _html(tmp_path)
    section = _section(html)

    assert '<input type="text" id="kt-name" value="KPI ツリー">' in section
    assert '<select id="kt-datasource"></select>' in section
    # 既定は上端揃え（上端ならエッジを描く）。エッジの .hyper は画面で指定しない（2026-09-15）
    assert '<button type="button" data-align="center">中央</button>' in section
    assert '<button type="button" data-align="top" class="on">上端</button>' in section
    assert 'const KT = { root: null, align: "top" };' in html
    assert "kt-edge-hyper" not in html
    assert "edge_hyper" not in html
    assert 'id="kt-root"' in section
    assert 'id="kt-yaml"' in section
    # ノードの幅・アクションとダッシュボードの幅 × 高さは持たない（大きさはツリーの形から決まる）
    assert "幅 (px)" not in section
    assert "高さ (px)" not in section
    assert "アクション" not in section


def test_kpi_tree_node_inputs_come_from_draw_card_signature(tmp_path) -> None:
    """ノードの入力欄は手で書かず、draw_card の実引数（DRAW_SPECS）から作る。"""
    html = _html(tmp_path)
    specs = json.loads(
        re.search(r'id="draw-specs">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</")
    )

    assert {spec["name"] for spec in specs["draw_card"]["params"]} >= {"main_metric", "sub_metric", "main_color"}
    # モードで使わない引数は出さない（2026-09-21。ダッシュボードタブと同じ）
    assert 'const specs = visibleParams(node, "draw_card");' in html
    assert "required.map(spec => paramControl(node, spec))" in html
    assert "optional.map(spec => paramControl(node, spec))" in html
    assert 'chart: "draw_card"' in html
    # ノードごとのアクション設定は持たない（D3）
    script = html[html.index("const KT = {"):]
    assert "action" not in script


def test_kpi_tree_editor_supports_add_remove_duplicate_and_drag(tmp_path) -> None:
    html = _html(tmp_path)

    assert 'class: "kt-edge-add", title: "子を追加", text: "＋"' in html
    assert 'title: isRoot ? "ツリーを削除" : "このノードと配下を削除"' in html
    assert 'title: "このノードを配下ごと複製"' in html
    assert 'attachGrip(grip, card, () => ({ kind: "kpi-node", node: node }))' in html
    assert 'return ratio < 0.25 ? "before" : ratio > 0.75 ? "after" : "into";' in html
    # 縦線はカードの中心を実測して引く。タブを開いたときにも引き直す
    assert "function drawKpiEdges()" in html
    assert "requestAnimationFrame(drawKpiEdges)" in html
    assert ".kt-tree.kt-align-top .kt-child-row.kt-first { padding-top: 0; }" in html


def test_kpi_tree_yaml_matches_the_receiver(tmp_path) -> None:
    html = _html(tmp_path)

    assert 'let out = "kpi_tree:\\n";' in html
    assert 'out += "  align: " + yamlKey(KT.align) + "\\n";' in html
    assert 'out += "  root:\\n" + kpiNodeYaml(KT.root, "    ");' in html
    # カードの引数はダッシュボードタブと同じ書き出し（主な色の複製もここ）
    assert 'out += paramsYaml("draw_card", node.params, pad);' in html
    assert 'out += paramsYaml(area.chart, area.params, "          ");' in html


def test_kpi_tree_yaml_in_the_screen_format_builds_a_workbook(tmp_path) -> None:
    """画面の kpiTreeYaml() が出す形（字下げ・children のリスト・色の複製）を受け手が読めること。"""
    source = tmp_path / "tree.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    config = tmp_path / "twbpatch_kpi_tree.yaml"
    config.write_text(
        """# twbpatch 設定ファイル（design / datasources / kpi_tree）
design:
  main_color: "#2f3b52"
  spacing: "wide"

datasources:
  {}

kpi_tree:
  name: "KPI ツリー"
  datasource: "売上データ"
  align: "top"
  root:
    sheet: "スコア|売上"
    params:
      main_metric: "売上"
      main_color: "@main_color"
      value_color: "@main_color"
      title_background_color: "@main_color"
    children:
      - sheet: "スコア|利益"
        params:
          main_metric: "利益"
      - sheet: "スコア|売上 (2)"
        params:
          main_metric: "売上"
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))

    workbook.apply_config(str(config))

    assert [item.name for item in workbook.get_dashboards()] == ["KPI ツリー"]
    assert workbook.get_worksheets(name="スコア|売上 (2)")
    assert workbook.get_worksheets(name="エッジ|スコア|売上")
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_kpi_tree_validates_before_download(tmp_path) -> None:
    html = _html(tmp_path)

    assert "function validateKpiTree()" in html
    assert 'if (!KT.root) return ["KPI ツリー: ノードがありません"];' in html
    assert 'errors.push(label + ": シート名が空")' in html
    # エッジは上端揃えのときだけ描くので、末端数の上限もそのときだけ見る
    assert 'const edges = KT.align === "top";' in html
    assert "if (edges && node.children.length) {" in html
    assert "const KPI_EDGE_MAX_OFFSET = 13;" in html
    # シート名・ダッシュボード名の重複は、ツリーの中・ダッシュボードタブ・.twb に既にあるものを見る
    assert 'duplicateSheetErrors(sheets, dashboardSheetNames(null), "ダッシュボードタブ")' in html
    assert 'duplicateSheetErrors(sheets, kpiTreeSheetNames(null), "KPI ツリータブ")' in html
    assert "(DATA.dashboards || []).some(db => db.name === name)" in html


def test_sheet_names_are_numbered_on_collision(tmp_path) -> None:
    """名前が重複したら画面で「 (2)」を付ける（2026-09-14）。受け手では付けない。"""
    html = _html(tmp_path)

    assert "function uniqueName(base, used)" in html
    assert 'const stem = base.replace(/ \\(\\d+\\)$/, "");' in html
    assert 'return stem + " (" + n + ")";' in html
    assert 'base + "_" + n' not in html
    # 重複を見る相手は両タブと .twb に既にあるシート
    # （2026-09-21: 読み込んだ設定 YAML が作るシートは除くので existingSheetNames() 経由）
    assert "const used = existingSheetNames();" in html
    assert "function existingSheetNames()" in html
    assert "kpiTreeSheetNames(except).forEach(name => used.add(name));" in html
    # 複製したエリア・ノードにも番号を付ける
    assert "if (copy.sheet) copy.sheet = uniqueName(copy.sheet, usedSheetNames(copy));" in html
    assert "if (item.sheet) item.sheet = uniqueName(item.sheet, usedSheetNames(item));" in html
