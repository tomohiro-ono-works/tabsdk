from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "table_style.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Index]" caption="#" datatype="integer" role="measure" type="quantitative">
        <calculation class="tableau" formula="index()" />
      </column>
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
      <column name="[Order Date]" caption="注文日" datatype="date" role="dimension" type="ordinal" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_get_and_update_table_style_round_trip(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")
    worksheet.add_field(field=datasource.get_fields(name="#")[0], shelf="rows")
    worksheet.add_field(field=datasource.get_fields(name="カテゴリ")[0], shelf="rows")

    assert worksheet.table_style == {
        "header_background": None,
        "header_bold": None,
        "header_color": None,
        "row_band": None,
        "column_widths": {},
    }
    assert worksheet.update(
        table_style={
            "header_background": "#f5f5f5",
            "header_bold": True,
            "header_color": "#555555",
            "row_band": False,
            "column_widths": {"#": 36},
        }
    ) is worksheet
    assert worksheet.table_style == {
        "header_background": "#f5f5f5",
        "header_bold": True,
        "header_color": "#555555",
        "row_band": False,
        "column_widths": {"#": 36},
    }

    style = workbook.tree.xpath("/workbook/worksheets/worksheet[@name='一覧']/table/style")[0]
    assert style.xpath("string(./style-rule[@element='header']/format[@attr='width']/@value)") == "36"
    assert style.xpath("string(./style-rule[@element='field-labels']/format[@attr='background-color']/@value)") == "#f5f5f5"
    assert style.xpath("string(./style-rule[@element='field-labels-decoration']/format[@attr='font-weight']/@value)") == "bold"
    assert style.xpath("string(./style-rule[@element='pane']/format[@attr='band-color']/@value)") == "#00000000"

    output = tmp_path / "styled.twb"
    workbook.save(str(output))
    assert TwbWorkbook.open(str(output)).get_worksheets(name="一覧")[0].table_style == worksheet.table_style


def test_worksheet_supports_explicit_table_down_calculation(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.draw_sheet(datasource, name="一覧")
    worksheet.add_field(
        field=datasource.get_fields(name="#")[0],
        shelf="rows",
        table_calculation="table_down",
    )
    worksheet.add_field(field=datasource.get_fields(name="カテゴリ")[0], shelf="rows")

    root = workbook.tree.getroot()
    calculation = root.xpath(
        "/workbook/worksheets/worksheet[@name='一覧']/table/view/"
        "datasource-dependencies/column[@caption='#']/calculation/table-calc"
    )[0]
    instance = root.xpath(
        "/workbook/worksheets/worksheet[@name='一覧']/table/view/"
        "datasource-dependencies/column-instance[@derivation='User']"
    )[0]
    assert calculation.get("ordering-type") == "Rows"
    assert instance.get("type") == "ordinal"
    assert instance.xpath("string(./table-calc/@ordering-type)") == "Columns"
    assert root.xpath("string(/workbook/worksheets/worksheet[@name='一覧']/table/rows)") == (
        "([ds1].[usr:Index:ok] / ([ds1].[none:Category:nk]))"
    )
    index_placement = worksheet.get_fields(name="#")[0]
    assert index_placement.table_calculation == "table_down"
    assert index_placement.discrete is True
    assert index_placement.aggregation is None
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_worksheet_supports_running_total(tmp_path) -> None:
    """累計（クイック表計算）。`examples/ウォーターフォール.twb` の手作業のシートを実測すると、

    別の計算フィールドではなく、行に置いたピル自体へ `<table-calc type="CumTotal">` が
    掛かっているだけだった（`[cum:usr:...:qk]` という参照）。
    """
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    amount = datasource.create_calculated_field(
        name="額", formula="SUM([売上]) - SUM([利益])", datatype="real", role="measure",
    )
    worksheet = workbook.create_worksheet(name="ウォーターフォール")

    worksheet.add_field(
        field=amount,
        shelf="rows",
        aggregation="agg",
        running_total=True,
    )

    token = amount.id[1:-1]  # 内部 id（[Calculation_xxx]）から角括弧を外す
    instance_name = f"[cum:usr:{token}:qk]"
    root = workbook.tree.getroot()
    assert root.xpath("string(/workbook/worksheets/worksheet[@name='ウォーターフォール']/table/rows)") == (
        f"[ds1].{instance_name}"
    )
    instance = root.xpath(
        "/workbook/worksheets/worksheet[@name='ウォーターフォール']/table/view/"
        "datasource-dependencies/column-instance[@name=$name]",
        name=instance_name,
    )[0]
    assert instance.get("derivation") == "User"
    assert instance.get("type") == "quantitative"
    table_calc = instance.find("table-calc")
    assert table_calc.get("type") == "CumTotal"
    assert table_calc.get("aggregation") == "Sum"
    assert table_calc.get("ordering-type") == "Rows"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_worksheet_supports_running_total_with_specific_dimensions(tmp_path) -> None:
    """「特定のディメンション」で累計の計算対象を明示する（2026-09-23、実機で確認）。

    `running_total_fields` を渡すと参照に `:2` が付き、`<table-calc ordering-type="Field">`
    の下へ対象の数だけ `<order field=...>` を並べる。物理フィールド（カテゴリ）は
    集計なし・不連続の通常のディメンション参照、計算フィールド（項目名）は素の
    `[id]` と、実機での書き方の違いをそのまま反映する。
    """
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    amount = datasource.create_calculated_field(
        name="額", formula="SUM([売上]) - SUM([利益])", datatype="real", role="measure",
    )
    label = datasource.create_calculated_field(
        name="項目名", formula='"売上"', datatype="string", role="dimension",
    )
    category = datasource.get_fields(name="カテゴリ")[0]
    worksheet = workbook.create_worksheet(name="ウォーターフォール")
    worksheet.add_field(field=category, shelf="columns", discrete=True)

    worksheet.add_field(
        field=amount,
        shelf="rows",
        aggregation="agg",
        running_total=True,
        running_total_fields=[category, label],
    )

    token = amount.id[1:-1]
    instance_name = f"[cum:usr:{token}:qk:2]"
    root = workbook.tree.getroot()
    assert root.xpath("string(/workbook/worksheets/worksheet[@name='ウォーターフォール']/table/rows)") == (
        f"[ds1].{instance_name}"
    )
    instance = root.xpath(
        "/workbook/worksheets/worksheet[@name='ウォーターフォール']/table/view/"
        "datasource-dependencies/column-instance[@name=$name]",
        name=instance_name,
    )[0]
    assert instance.get("derivation") == "User"
    assert instance.get("type") == "quantitative"
    table_calc = instance.find("table-calc")
    assert table_calc.get("type") == "CumTotal"
    assert table_calc.get("aggregation") == "Sum"
    assert table_calc.get("ordering-type") == "Field"
    orders = table_calc.findall("order")
    assert [order.get("field") for order in orders] == [
        "[ds1].[none:Category:nk]",
        f"[ds1].{label.id}",
    ]
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_running_total_rejects_unsupported_combinations(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")

    with pytest.raises(ValueError, match="running_total requires aggregation"):
        worksheet.add_field(
            field=datasource.get_fields(name="売上")[0], shelf="rows", running_total=True,
        )
    with pytest.raises(ValueError, match="running_total requires shelf rows or columns"):
        worksheet.add_field(
            field=datasource.get_fields(name="売上")[0],
            shelf="filters",
            aggregation="sum",
            running_total=True,
        )


def test_draw_sheet_allows_omitted_and_empty_items(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]

    omitted = workbook.draw_sheet(datasource, name="項目省略")
    empty = workbook.draw_sheet(datasource, name="空配列", items=[])

    assert omitted.get_fields() == []
    assert empty.get_fields() == []
    assert omitted._resolve_element().xpath(".//*[local-name()='table-calc']") == []
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_index_uses_unspecified_table_calculation(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.draw_sheet(
        datasource,
        name="既定表計算",
        items=["#", "カテゴリ"],
    )

    assert [field.name for field in worksheet.get_fields()] == ["#", "カテゴリ"]
    assert worksheet._resolve_element().xpath(".//*[local-name()='table-calc']") == []
    assert worksheet._resolve_element().xpath("string(./table/rows)") == (
        "([ds1].[usr:Index:ok] / ([ds1].[none:Category:nk]))"
    )
    instance = worksheet._resolve_element().xpath(
        ".//*[local-name()='column-instance'][@column='[Index]']"
    )[0]
    assert instance.get("derivation") == "User"
    assert instance.get("type") == "ordinal"


def test_draw_card_builds_formatted_main_and_sub_metrics(tmp_path) -> None:

    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.draw_card(
        datasource,
        name="カード",
        main_metric="売上",
        sub_metric="利益",
        main_color="#602fff",
    )

    pane = worksheet.get_panes()[0]
    assert pane.customized_label == {
        "main_metric": "売上",
        "sub_metric": "利益",
        "main_color": "#602fff",
        "value_color": "#333333",
    }
    assert worksheet.title_style == {
        "background_color": "#602fff",
        "border_width": "0",
        "border_style": "none",
    }
    runs = worksheet._resolve_element().xpath(
        "./table/panes/pane/customized-label/formatted-text/run"
    )
    # メイン指標は 16（2026-09-22 に 18 から変更）
    assert [(run.get("fontsize"), run.get("fontcolor")) for run in runs] == [
        ("12", "#602fff"), (None, None), ("16", "#333333"),
        (None, None), ("10", "#555555"),
    ]
    assert worksheet._resolve_element().xpath(
        "string(./table/panes/pane/style/style-rule[@element='cell']/"
        "format[@attr='text-align']/@value)"
    ) == "center"
    assert not [message for message in workbook.validate() if message.severity == "error"]


