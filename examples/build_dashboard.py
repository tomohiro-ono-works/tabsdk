"""twbpatch の主要 API を一通り使うサンプル。

入力: examples/sample_ec.twb（リポジトリ同梱）
出力: outputs/example_dashboard.twb

    uv run --no-sync python examples/build_dashboard.py

このファイル 1 本で以下をカバーする。

1. フィールド整理     apply_field_config() による英名 → 和名・フォルダ分類
2. 計算フィールド     create_calculated_field(s) / create_yoy_calculated_fields()
3. グラフ生成         draw_* 7 種
4. 表スタイル         update(table_style=...) / set_title()
5. ダッシュボード     build_report() と create_container() の 2 通り
6. ペイン直接操作     draw_* に無いグラフ（円グラフ）を get_panes() で作る
                     フィールドは名前・タプル・オブジェクトのどれでも指定できる
"""

from __future__ import annotations

from pathlib import Path

from twbpatch import TwbWorkbook

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "examples" / "sample_ec.twb"
FIELD_CONFIG = ROOT / "examples" / "sample_ec_fields.yaml"
OUTPUT = ROOT / "outputs" / "example_dashboard.twb"

DATASOURCE = "EC Orders"
DASHBOARD = "ECサイト分析ダッシュボード"
YEAR_CATEGORY = "当年昨年区分"
YOY_METRICS = ("売上", "利益")


def main() -> None:
    workbook = TwbWorkbook.open(str(SOURCE))

    # 1. フィールド整理 -----------------------------------------------------
    # データソース → フォルダ → {英名: 和名} の 3 階層 YAML を一括で当てる。
    workbook.apply_field_config(FIELD_CONFIG)
    datasource = workbook.get_datasources(name=DATASOURCE)[0]

    # 2. 計算フィールド -----------------------------------------------------
    # 辞書で一括作成する形。値は式だけ、または (式, datatype) のタプル。
    datasource.create_calculated_fields(
        {
            "利益率": "SUM([利益]) / SUM([売上])",
            "注文数": "COUNTD([注文ID])",
            "1顧客あたり売上": "SUM([売上]) / COUNTD([顧客ID])",
        },
        folder="Measure",
    )
    # 帳票の連番列。discrete=True の index() が定番。
    datasource.create_calculated_field(
        name="#",
        formula="index()",
        datatype="integer",
        role="measure",
        discrete=True,
    )
    # 前年差の計算フィールド群。年区分のフィールドが前提になる。
    yoy_folder = datasource.create_folder(name="前年差")
    datasource.create_calculated_field(
        name=YEAR_CATEGORY,
        formula='IIF(YEAR([注文日]) = YEAR(TODAY()), "当年", "昨年")',
        datatype="string",
        role="dimension",
        discrete=True,
        folder=yoy_folder,
    )
    for metric in YOY_METRICS:
        datasource.create_yoy_calculated_fields(
            metric=metric,
            year_category=YEAR_CATEGORY,
            folder=yoy_folder,
        )

    # 3. グラフ生成（draw_* 7 種） -------------------------------------------
    # workbook のメソッド版は (データソース名, フィールド名) のタプルで項目を指定する。
    workbook.draw_card(
        name="スコアカード_売上",
        main_metric=(DATASOURCE, "売上"),
        sub_metric=(DATASOURCE, "利益"),
    )
    workbook.draw_yoy(
        name="時系列_売上",
        item=(DATASOURCE, "注文日"),
        metric=(DATASOURCE, "売上"),
    )
    workbook.draw_bar(
        name="サブカテゴリ別売上",
        item=(DATASOURCE, "サブカテゴリ"),
        metric=(DATASOURCE, "売上"),
    )
    workbook.draw_quadrant(
        name="サブカテゴリ_ポジショニング",
        title="サブカテゴリ別ポジショニング",
        item=(DATASOURCE, "サブカテゴリ"),
        x_metric=(DATASOURCE, "売上"),
        y_metric=(DATASOURCE, "利益率"),
        size_metric=(DATASOURCE, "数量"),
        colors=("#4400FF", "#FF007F", "#00C888", "#CCD500"),
        opacity=0.6,
    )
    workbook.draw_crosstab(
        name="カテゴリ_顧客セグメント_売上",
        title="カテゴリ・顧客セグメント別売上",
        x_item=(DATASOURCE, "カテゴリ"),
        y_item=(DATASOURCE, "顧客セグメント"),
        color_metric=(DATASOURCE, "売上"),
        label_metric=(DATASOURCE, "売上"),
        min_color="#FF007F",
        mid_color="#FFFFFF",
        max_color="#4400FF",
    )

    # 4. 表スタイル ---------------------------------------------------------
    report = workbook.draw_sheet(
        name="帳票",
        title="カテゴリ・サブカテゴリ別帳票",
        items=[
            (DATASOURCE, "#"),
            (DATASOURCE, "カテゴリ"),
            (DATASOURCE, "サブカテゴリ"),
        ],
    )
    report.update(
        table_style={
            "header_background": "#f5f5f5",
            "header_bold": True,
            "header_color": "#555555",
            "row_band": False,
            "column_widths": {"#": 36},
        }
    )

    # 前年差帳票。色分けは draw_colored_yoy_sheet が引数でまとめて受ける。
    yoy_report = workbook.draw_colored_yoy_sheet(
        name="前年差帳票",
        items=[
            (DATASOURCE, "#"),
            (DATASOURCE, "カテゴリ"),
            (DATASOURCE, "サブカテゴリ"),
        ],
        metrics=[(DATASOURCE, metric) for metric in YOY_METRICS],
        negative_color="#ff007f",
        positive_color="#602fff",
        ratio_color="#555555",
        mark_type="bar",
        axis_min=0,
        axis_max=1,
        show_axes=False,
        bar_opacity=0.0,
        index_partition_by=(DATASOURCE, "カテゴリ"),
    )
    yoy_report.update(title="カテゴリ・サブカテゴリ別 年前年差帳票")

    # 5. ペイン直接操作 -----------------------------------------------------
    # draw_* に円グラフは無いので、ペインの mark_type を直接変えて組む。
    # フィールドは名前でも (データソース名, フィールド名) でも TwbField でも指定できる。
    pie = workbook.create_worksheet(name="カテゴリ別売上_円")
    pane = pie.get_panes()[0]
    pane.update(mark_type="pie")
    pane.add_field(field=(DATASOURCE, "カテゴリ"), encoding="color", discrete=True)
    pane.add_field(field="カテゴリ", encoding="label", discrete=True)
    pane.add_field(field="売上", encoding="angle", aggregation="sum", discrete=False)

    # 6-a. build_report() によるダッシュボード ------------------------------
    # struct の値がそのまま配置になる。ネストした配列は横並びの行を作る。
    workbook.set_filter((DATASOURCE, "カテゴリ"))
    dashboard = workbook.create_dashboard(name=DASHBOARD, width=1169, height=1654)
    dashboard.build_report(
        dashboard_name=DASHBOARD,
        struct={
            "フィルタコンテナ": {
                "height": 50,
                "items": [{"kind": "filter", "field": (DATASOURCE, "カテゴリ")}],
            },
            "スコア・時系列コンテナ": {
                "items": [
                    {"kind": "worksheet", "sheets": ["スコアカード_売上", "時系列_売上"]},
                ],
            },
            "分析グラフコンテナ": {
                "items": [
                    {"kind": "worksheet", "sheet": "サブカテゴリ_ポジショニング"},
                    {"kind": "worksheet", "sheet": "カテゴリ_顧客セグメント_売上"},
                    {"kind": "worksheet", "sheet": "カテゴリ別売上_円"},
                ],
            },
            "帳票コンテナ": {
                "items": [
                    {"kind": "worksheet", "sheet": "帳票"},
                    {"kind": "worksheet", "sheet": "前年差帳票"},
                ],
            },
        },
        container_sizes={"スコア・時系列コンテナ": 206},
        content_style={
            "background_color": "#e6e6e6",
            "margin": 0,
            "padding": 16,
            "padding_top": 4,
        },
        header_height=44,
        header_background_color="#333333",
        header_font_color="#ffffff",
    )

    # 6-b. create_container() による手組みレイアウト -------------------------
    # build_report() を使わず 1 段ずつ組む場合。細部を指定したいときはこちら。
    manual = workbook.create_dashboard(name="手組みレイアウト", width=1169, height=600)
    root = manual.create_container(direction="vertical", friendly_name="contents")
    root.update(
        style={"background_color": "#f5f5f5", "border_style": "none", "margin": 8}
    )

    header = root.create_container(
        direction="horizontal", fixed_size=43, friendly_name="header"
    )
    header.update(style={"background_color": "#333333", "border_style": "none"})
    header.add_text(
        "  ECサイト分析",
        bold=True,
        fixed_size=None,
        style={"margin": 0, "border_style": "none"},
    )

    body = root.create_container(direction="vertical", friendly_name="body")
    body.update(style={"background_color": "#e6e6e6", "border_style": "none"})
    score_area = body.create_container(
        direction="horizontal", fixed_size=100, friendly_name="スコアエリア"
    )
    score_area.add_spacer(
        fixed_size=6,
        style={"background_color": "#602fff", "margin": 4, "margin_right": 0},
    )
    # add_worksheet() はシート名ではなく TwbWorksheet オブジェクトを受け取る。
    score_card = workbook.get_worksheets(name="スコアカード_売上")[0]
    card = score_area.add_worksheet(score_card, fixed_size=267, show_title=False)
    card.update(
        style={
            "background_color": "#ffffff",
            "border_style": "none",
            "margin": 4,
            "margin_left": 0,
            "margin_right": 8,
            "padding": 8,
        }
    )

    workbook.set_default_font()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(str(OUTPUT), validate=True, overwrite=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
