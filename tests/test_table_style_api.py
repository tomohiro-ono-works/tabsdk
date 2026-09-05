from __future__ import annotations

from twbpatch import TwbWorkbook, draw_sheet


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
    worksheet.add_field(datasource.get_fields(name="#")[0], shelf="rows")
    worksheet.add_field(datasource.get_fields(name="カテゴリ")[0], shelf="rows")

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
    worksheet = draw_sheet(workbook, datasource, name="一覧")
    worksheet.add_field(
        datasource.get_fields(name="#")[0],
        shelf="rows",
        table_calculation="table_down",
    )
    worksheet.add_field(datasource.get_fields(name="カテゴリ")[0], shelf="rows")

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


def test_draw_sheet_allows_omitted_and_empty_items(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]

    omitted = draw_sheet(workbook, datasource, name="項目省略")
    empty = draw_sheet(workbook, datasource, name="空配列", items=[])

    assert omitted.get_fields() == []
    assert empty.get_fields() == []
    assert omitted._resolve_element().xpath(".//*[local-name()='table-calc']") == []
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_index_uses_unspecified_table_calculation(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = draw_sheet(
        workbook,
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
    from twbpatch import draw_card

    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = draw_card(
        workbook,
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
    assert [(run.get("fontsize"), run.get("fontcolor")) for run in runs] == [
        ("12", "#602fff"), (None, None), ("18", "#333333"),
        (None, None), ("10", "#555555"),
    ]
    assert worksheet._resolve_element().xpath(
        "string(./table/panes/pane/style/style-rule[@element='cell']/"
        "format[@attr='text-align']/@value)"
    ) == "center"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_yoy_uses_continuous_month_date(tmp_path) -> None:
    from twbpatch import draw_yoy

    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = draw_yoy(
        workbook,
        datasource,
        name="時系列",
        item="注文日",
        metric="売上",
    )

    assert worksheet._resolve_element().xpath("string(./table/cols)") == (
        "[ds1].[tmn:Order Date:qk]"
    )
    date = worksheet.get_fields(name="注文日")[0]
    assert date.date_level == "month"
    assert date.discrete is False
    assert date.aggregation is None
    instance = worksheet._resolve_element().xpath(
        ".//*[local-name()='column-instance'][@column='[Order Date]']"
    )[0]
    assert instance.get("derivation") == "Month-Trunc"
    assert worksheet.get_panes()[0].mark_type == "line"
    assert not [message for message in workbook.validate() if message.severity == "error"]
