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
    yoy = workbook.draw_yoy(
        datasource,
        name="API_前年比",
        item="注文日",
        metric="売上",
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
    assert yoy.get_panes()[0].mark_type == "line"
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
    yoy = workbook.draw_yoy(
        name="API_タプル前年比",
        item=(datasource_name, "注文日"),
        metric=(datasource_name, "売上"),
        color="#602FFF",
        show_axes=False,
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
    assert yoy.get_panes()[0].mark_type == "line"
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='API_タプル前年比']"
        "/table/style/style-rule[@element='axis']"
        "/format[@attr='display']/@value"
    ) == ["false", "false"]
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='API_タプル前年比']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-color']/@value)"
    ) == "#602fff"
    assert bar.get_panes()[0].mark_type == "bar"
    assert card.get_panes()[0].customized_label["main_metric"] == "売上"


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


def test_draw_colored_yoy_sheet_builds_fixed_hidden_bar_axes_per_metric(tmp_path) -> None:
    source = tmp_path / "colored-yoy.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Index]" caption="#" datatype="integer" role="measure" type="quantitative">
        <calculation class="tableau" formula="index()" />
      </column>
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="粗利" datatype="real" role="measure" type="quantitative" />
      <column name="[YearCategory]" caption="当年昨年区分" datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))
    datasource = workbook.get_datasources()[0]
    datasource.create_yoy_calculated_fields(metric="売上", year_category="当年昨年区分")
    datasource.create_yoy_calculated_fields(metric="粗利", year_category="当年昨年区分")

    worksheet = workbook.draw_colored_yoy_sheet(
        name="前年差帳票",
        items=[("売上データ", "#"), ("売上データ", "カテゴリ")],
        metrics=[("売上データ", "売上"), ("売上データ", "粗利")],
        negative_color="#FF007F",
        positive_color="#602FFF",
        ratio_color="#555555",
        mark_type="bar",
        bar_color="#4E79A7",
        axis_min=0,
        axis_max=1,
        show_axes=False,
        bar_opacity=0.0,
        index_partition_by=("売上データ", "カテゴリ"),
    )

    assert worksheet.name == "前年差帳票"
    assert [(field.name, field.shelf) for field in worksheet.get_fields() if field.shelf] == [
        ("#", "rows"),
        ("カテゴリ", "rows"),
        ("帳票配置用_MIN1", "columns"),
        ("帳票配置用_MIN1", "columns"),
    ]
    assert worksheet.get_fields(name="#")[0].table_calculation == "table_down"
    assert worksheet._resolve_element().xpath("string(./table/cols)").count("+") == 1
    panes = worksheet.get_panes()
    assert len(panes) == 3
    assert [
        [field.name for field in pane.get_fields()]
        for pane in panes[1:]
    ] == [
        ["売上|昨年差<0", "売上|昨年差>=0", "売上比|昨年比"],
        ["粗利|昨年差<0", "粗利|昨年差>=0", "粗利比|昨年比"],
    ]
    assert [pane.mark_type for pane in panes] == ["bar", "bar", "bar"]
    axis_encodings = worksheet._resolve_element().xpath(
        "./table/style/style-rule[@element='axis']/encoding[@attr='space']"
    )
    assert [
        f"{encoding.get('class')}:{encoding.get('min')}:"
        f"{encoding.get('max')}:{encoding.get('range-type')}"
        for encoding in axis_encodings
    ] == ["0:0:1:fixed", "1:0:1:fixed"]
    assert worksheet._resolve_element().xpath(
        "./table/style/style-rule[@element='axis']/format[@attr='display']/@value"
    ) == ["false", "false"]
    assert worksheet._resolve_element().xpath(
        "./table/panes/pane[position() > 1]/style/style-rule[@element='mark']"
        "/format[@attr='mark-color']/@value"
    ) == ["#4e79a7", "#4e79a7"]
    assert worksheet._resolve_element().xpath(
        "./table/panes/pane[position() > 1]/style/style-rule[@element='mark']"
        "/format[@attr='mark-transparency']/@value"
    ) == ["0", "0"]
    assert worksheet._resolve_element().xpath("string(./table/rows)").endswith(
        ".[none:Category:nk]))"
    )
    assert ":ok:2]" in worksheet._resolve_element().xpath("string(./table/rows)")
    assert worksheet._resolve_element().xpath(
        "string(./table/view/slices/column)"
    ).endswith(".[none:Category:nk]")
    labels = worksheet._resolve_element().xpath(
        "./table/panes/pane[position() > 1]/customized-label/formatted-text"
    )
    assert [[(run.get("fontcolor"), run.get("fontsize")) for run in label] for label in labels] == [
        [("#ff007f", None), ("#602fff", None), ("#555555", "7")],
        [("#ff007f", None), ("#602fff", None), ("#555555", "7")],
    ]
    assert worksheet.table_style == {
        "header_background": "#f5f5f5",
        "header_bold": True,
        "header_color": "#555555",
        "row_band": False,
        "column_widths": {"#": 36},
    }
    assert not [message for message in workbook.validate() if message.severity == "error"]


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
