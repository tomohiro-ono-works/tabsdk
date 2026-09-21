import pytest

from twbpatch import NotFoundError, TwbWorkbook


DATASOURCE_ID = "federated.00vlmup0b8v7m212i5x9f03fouo2"
DATASOURCE_NAME = "Orders++ (sample_-_superstore)"


def _superstore_workbook(tmp_path):
    """実ワークブックを模した最小構成。

    データソースの `@name` は Tableau が実際に付ける `federated.xxx` 形式にしてある。
    `draw_*` が組み立てる参照文字列がこの形式を前提にしているため。
    """
    path = tmp_path / "superstore.twb"
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="{DATASOURCE_ID}" caption="{DATASOURCE_NAME}">
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Sub-Category]" caption="サブカテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Order Date]" caption="注文日" datatype="date" role="dimension" type="ordinal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_draw_methods_with_a_datasource_accept_plain_field_names(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    sheet = workbook.draw_sheet(
        datasource,
        name="API_一覧",
        items=["カテゴリ", "サブカテゴリ"],
    )
    bar = workbook.draw_bar(
        datasource,
        name="API_棒",
        item="サブカテゴリ",
        metric="売上",
    )
    card = workbook.draw_card(
        datasource,
        name="API_カード",
        main_metric="売上",
        sub_metric="利益",
    )

    assert {field.shelf for field in sheet.get_fields()} == {"rows"}
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='API_一覧']/table/rows)"
    ) == (
        f"[{DATASOURCE_ID}].[none:Category:nk]"
        f" / [{DATASOURCE_ID}].[none:Sub-Category:nk]"
    )
    assert bar.get_panes()[0].mark_type == "bar"
    assert card.get_panes()[0].mark_type == "automatic"
    assert card.get_panes()[0].customized_label == {
        "main_metric": "売上",
        "sub_metric": "利益",
        "main_color": "#602fff",
        "value_color": "#333333",
    }
    assert [field.encoding for field in card.get_fields()] == ["label", "label"]
    assert not [message for message in workbook.validate() if message.severity == "error"]

    with pytest.raises(NotFoundError, match="field not found"):
        workbook.draw_bar(
            datasource,
            name="API_不正",
            item="存在しない項目",
            metric="売上",
        )
    assert workbook.get_worksheets(name="API_不正") == []


def test_workbook_draw_methods_accept_datasource_field_tuples(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    datasource_name = DATASOURCE_NAME

    sheet = workbook.draw_sheet(
        name="API_タプル一覧",
        items=[
            (datasource_name, "カテゴリ"),
            (datasource_name, "サブカテゴリ"),
        ],
    )
    bar = workbook.draw_bar(
        name="API_タプル棒",
        item=(datasource_name, "サブカテゴリ"),
        metric=(datasource_name, "売上"),
    )
    card = workbook.draw_card(
        name="API_タプルカード",
        main_metric=(datasource_name, "売上"),
        sub_metric=(datasource_name, "利益"),
    )

    assert {field.shelf for field in sheet.get_fields()} == {"rows"}
    assert bar.get_panes()[0].mark_type == "bar"
    assert card.get_panes()[0].customized_label["main_metric"] == "売上"


def test_workbook_draw_bar_applies_bar_color(tmp_path) -> None:
    """`bar_color` を指定すると棒の色に反映される（2026-09-12 追加）。

    以前は draw_bar に色を指定する引数が無く、常に既定色で描画されていた。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    workbook.draw_bar(datasource, name="色指定なし", item="カテゴリ", metric="売上")
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='色指定なし']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-color']/@value"
    ) == []

    bar = workbook.draw_bar(
        datasource,
        name="色指定あり",
        item="カテゴリ",
        metric="売上",
        item_shelf="columns",
        bar_color="#602fff",
    )
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='色指定あり']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-color']/@value"
    ) == ["#602fff"]
    assert bar.get_panes()[0].mark_type == "bar"


def test_draw_card_aggregates_row_level_calculated_fields(tmp_path) -> None:
    """計算フィールドでも、式が集計関数を含まなければ通常どおり集計する
    （2026-09-12 追加）。

    以前は `field.is_calculated` だけを見て一律「集計済み扱い（derivation=User）」
    にしていたため、`IIF(...)` のような行レベルの式を持つ計算フィールドを指標に
    使うと、集計されずに明細がそのまま出てしまっていた。式が SUM/AVG/COUNT/COUNTD
    などの集計関数を含む場合だけ「集計済み」とみなし、含まない場合は通常のフィールドと
    同じ既定集計（SUM）を適用する。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="行レベル売上", formula="IIF(1=1, [Sales], 0)", datatype="real", role="measure"
    )
    datasource.create_calculated_field(
        name="集計済み利益", formula="SUM([Profit])", datatype="real", role="measure"
    )

    row_level = workbook.draw_card(datasource, name="行レベルカード", main_metric="行レベル売上")
    aggregated = workbook.draw_card(datasource, name="集計済みカード", main_metric="集計済み利益")

    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='行レベルカード']"
        "//column-instance/@derivation"
    ) == ["Sum"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='集計済みカード']"
        "//column-instance/@derivation"
    ) == ["User"]
    assert row_level.get_panes()[0].mark_type == "automatic"
    assert aggregated.get_panes()[0].mark_type == "automatic"


def test_workbook_draw_bar_resolves_fields_from_different_datasources(tmp_path) -> None:
    source = tmp_path / "multi-datasource.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="products" caption="商品データ">
      <column name="[Sub-Category]" caption="サブカテゴリ"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
    <datasource name="sales" caption="売上データ">
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))

    worksheet = workbook.draw_bar(
        name="データソース横断",
        item=("商品データ", "サブカテゴリ"),
        metric=("売上データ", "売上"),
    )

    assert worksheet.get_panes()[0].mark_type == "bar"
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='データソース横断']"
        "/table/view/datasources/datasource/@name"
    ) == ["products", "sales"]
    sort = workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='データソース横断']"
        "/table/view/computed-sort"
    )[0]
    assert sort.get("column").startswith("[products].")
    assert sort.get("using").startswith("[sales].")


def test_draw_card_title_bar_shows_background_without_text(tmp_path) -> None:
    """スコアカードのタイトルバーは帯（背景色）だけ表示し、文字は入れない
    （2026-09-12 変更）。

    以前はプレースホルダーとして "-" という文字を入れており、Tableau で
    実際に開くとタイトルバーにその文字が見えてしまっていた。
    """
    workbook = _superstore_workbook(tmp_path)
    card = workbook.draw_card(name="タイトル確認", main_metric="売上")

    assert card.title is None
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='タイトル確認']"
        "/layout-options/title/formatted-text/run)"
    ) == ""
    assert card.title_style["background_color"] == "#602fff"


def test_draw_card_chooses_aggregation_per_metric() -> None:
    workbook = TwbWorkbook.open("tests/sample_minimal.twb")
    datasource = workbook.get_datasources()[0]
    calculated = datasource.create_calculated_field(
        name="集計済み売上",
        formula="SUM([売上])",
        datatype="real",
    )

    card = workbook.draw_card(
        name="API_自動集計カード",
        main_metric=calculated,
        sub_metric=(datasource.name, "売上"),
    )

    assert {field.name: field.aggregation for field in card.get_fields()} == {
        "売上": "sum",
        "集計済み売上": "agg",
    }


def test_draw_quadrant_builds_scatter_medians_and_four_colors(tmp_path) -> None:
    source = tmp_path / "quadrant.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="商品データ">
      <column name="[Sub-Category]" caption="サブカテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Quantity]" caption="数量"
              datatype="integer" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))
    datasource = workbook.get_datasources()[0]
    profit_ratio = datasource.create_calculated_field(
        name="利益率",
        formula="SUM([利益]) / SUM([売上])",
        datatype="real",
    )
    product_count = datasource.create_calculated_field(
        name="商品数",
        formula="COUNTD([サブカテゴリ])",
        datatype="integer",
    )

    worksheet = workbook.draw_quadrant(
        name="商品ポジショニング",
        title="商品ポジショニングマップ",
        item=("商品データ", "サブカテゴリ"),
        x_metric=("商品データ", "売上"),
        y_metric=profit_ratio,
        size_metric=product_count,
        colors=("#111111", "#222222", "#333333", "#444444"),
    )

    assert worksheet.get_panes()[0].mark_type == "circle"
    assert worksheet.title == "商品ポジショニングマップ"
    assert {field.shelf: field.aggregation for field in worksheet.get_fields() if field.shelf} == {
        "columns": "sum",
        "rows": "agg",
    }
    assert next(field for field in worksheet.get_fields() if field.encoding == "size").aggregation == "agg"
    assert worksheet.get_panes()[0].mark_opacity == pytest.approx(0.6, abs=0.01)
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-transparency']/@value)"
    ) == "206"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/mark-sizing/@mark-sizing-setting)"
    ) == "marks-scaling-off"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='size']/@value)"
    ) == "4"
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/view/datasource-dependencies/column-instance"
        "[@column=$field]/@derivation",
        field=profit_ratio.id,
    ) == ["User"]
    color = next(field for field in worksheet.get_fields() if field.encoding == "color")
    assert color.table_calculation == "field"
    assert worksheet.get_panes()[0].get_categorical_colors(color) == {
        "1": "#111111",
        "2": "#222222",
        "3": "#333333",
        "4": "#444444",
    }
    datasource_color_ref = f"[usr:{color.field_id.strip('[]')}:nk:2]"
    assert workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$datasource]"
        "/column-instance[@name=$reference]/@column",
        datasource=datasource.id,
        reference=datasource_color_ref,
    ) == [color.field_id]
    datasource_palette = workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$datasource]"
        "/style/style-rule[@element='mark']"
        "/encoding[@attr='color'][@field=$reference]/map",
        datasource=datasource.id,
        reference=datasource_color_ref,
    )
    assert {
        mapping.findtext("bucket", "").strip('"'): mapping.get("to")
        for mapping in datasource_palette
    } == {
        "1": "#111111",
        "2": "#222222",
        "3": "#333333",
        "4": "#444444",
    }
    assert [line.formula for line in worksheet.get_reference_lines()] == [
        "median",
        "median",
        "median",
    ]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@z-order"
    ) == ["1", "1", "2"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@probability"
    ) == ["95", "95", "95"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@scope"
    ) == ["per-table", "per-table", "per-pane"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@label-type"
    ) == ["value", "value", "automatic"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@enable-instant-analytics"
    ) == ["true", "true", "true"]
    quadrant = workbook.get_datasources()[0].get_fields(name="商品ポジショニング_四象限")[0]
    assert "WINDOW_MEDIAN(SUM([Sales]))" in (quadrant.raw_formula or "")
    assert "WINDOW_MEDIAN([Calculation_" in (quadrant.raw_formula or "")
    assert quadrant.hidden is False
    assert workbook.tree.xpath(
        "string(/workbook/datasources/datasource/column[@name=$field]/@hidden)",
        field=quadrant.id,
    ) == ""
    assert quadrant.role == "measure"
    assert workbook.tree.xpath(
        "string(/workbook/datasources/datasource/column[@name=$field]"
        "/calculation/table-calc/@ordering-type)",
        field=quadrant.id,
    ) == "Rows"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/view/datasource-dependencies/column[@name=$field]"
        "/calculation/table-calc/@ordering-type)",
        field=quadrant.id,
    ) == "Rows"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/view/datasource-dependencies/column-instance[@column=$field]"
        "/table-calc/@ordering-field)",
        field=quadrant.id,
    ) == f"[{datasource.id}].{datasource.get_fields(name='サブカテゴリ')[0].id}"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_crosstab_uses_color_and_label_metrics(tmp_path) -> None:
    source = tmp_path / "crosstab.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Segment]" caption="顧客セグメント"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))

    worksheet = workbook.draw_crosstab(
        name="カテゴリ_顧客セグメント",
        x_item=("売上データ", "カテゴリ"),
        y_item=("売上データ", "顧客セグメント"),
        color_metric=("売上データ", "売上"),
        label_metric=("売上データ", "売上"),
        min_color="#FF007F",
        mid_color="#FFFFFF",
        max_color="#4400FF",
        title="カテゴリ・顧客セグメント別売上",
    )

    assert worksheet.get_panes()[0].mark_type == "square"
    assert worksheet.title == "カテゴリ・顧客セグメント別売上"
    assert [(field.name, field.shelf) for field in worksheet.get_fields() if field.shelf] == [
        ("顧客セグメント", "rows"),
        ("カテゴリ", "columns"),
    ]
    assert {
        (field.encoding, field.name, field.aggregation)
        for field in worksheet.get_fields()
        if field.encoding
    } == {
        ("color", "売上", "sum"),
        ("label", "売上", "sum"),
    }
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='カテゴリ_顧客セグメント']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-labels-show']/@value)"
    ) == "true"
    palette = workbook.tree.xpath(
        "/workbook/preferences/color-palette[@type='ordered-diverging']"
    )[0]
    assert [color.text for color in palette.findall("./color")] == [
        "#ff007f",
        "#ffffff",
        "#4400ff",
    ]
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='カテゴリ_顧客セグメント']"
        "/table/style/style-rule[@element='mark']"
        "/encoding[@attr='color']/@palette)"
    ) == palette.get("name")
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_card_treats_calculation_referencing_aggregated_calculation_as_aggregated(tmp_path) -> None:
    """集計済みの計算フィールドだけを参照する計算フィールドも、集計済みとして扱う（2026-09-20）。

    式に集計関数が無くても、参照先が集計済みなら SUM をかけると Tableau でエラーになる。
    行レベルの計算フィールド同士の式は従来どおり SUM をかける。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    for name, formula in [
        ("売上合計", "SUM([Sales])"),
        ("売上比", "[売上合計] / [売上合計]"),
        ("売上比の比", "[売上比] / 2"),
        ("行レベル", "[Sales] * 2"),
        ("行レベル比", "[行レベル] / 2"),
    ]:
        datasource.create_calculated_field(name=name, formula=formula, datatype="real", role="measure")

    def derivations(metric: str) -> list[str]:
        workbook.draw_card(datasource, name=f"カード|{metric}", main_metric=metric)
        return workbook.tree.xpath(
            f"/workbook/worksheets/worksheet[@name='カード|{metric}']//column-instance/@derivation"
        )

    assert derivations("売上合計") == ["User"]
    assert derivations("売上比") == ["User"]
    assert derivations("売上比の比") == ["User"]
    assert derivations("行レベル比") == ["Sum"]
