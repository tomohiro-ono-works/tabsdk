from twbpatch import TwbWorkbook


def test_list_dashboards_includes_caption_and_worksheets(tmp_path):
    twb = tmp_path / "dashboard.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <windows>
    <window class="dashboard" name="Dashboard 1" />
    <window class="worksheet" name="Sheet 1" hidden="true" />
  </windows>
  <worksheets>
    <worksheet name="Sheet 1" caption="Sales Sheet">
      <table>
        <view>
          <datasource-dependencies datasource="ds1">
            <column name="[Sales]" />
          </datasource-dependencies>
        </view>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name="Dashboard 1" caption="Executive Dashboard">
      <zones>
        <zone name="Sheet 1" />
      </zones>
    </dashboard>
  </dashboards>
</workbook>
""",
        encoding="utf-8",
    )

    wb = TwbWorkbook.open(str(twb))
    dashboards = wb.list_dashboards()

    assert len(dashboards) == 1
    assert dashboards[0].caption == "Executive Dashboard"
    assert dashboards[0].visible is True
    assert [worksheet.caption for worksheet in dashboards[0].worksheets] == ["Sales Sheet"]
    assert dashboards[0].worksheets[0].visible is False

    worksheets = wb.list_worksheets()
    assert worksheets[0].visible is False


def test_list_reference_lines_returns_worksheet_lines(tmp_path):
    twb = tmp_path / "reference_lines.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1">
      <column name="[Date]" caption="Order Date" role="dimension" />
      <column name="[Sales]" caption="Sales Amount" role="measure" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="Sheet 1" caption="Sales Sheet">
      <table>
        <panes>
          <pane>
            <reference-line
              id="refline0"
              axis-column="[ds1].[none:Date:ok]"
              value-column="[ds1].[none:Sales:qk]"
              formula="average"
              scope="per-table"
              label-type="value" />
          </pane>
        </panes>
      </table>
    </worksheet>
  </worksheets>
</workbook>
""",
        encoding="utf-8",
    )

    wb = TwbWorkbook.open(str(twb))
    lines = wb.list_reference_lines("Sales Sheet")

    assert len(lines) == 1
    assert lines[0].worksheet == "Sales Sheet"
    assert lines[0].id == "refline0"
    assert lines[0].axis_caption == "Order Date"
    assert lines[0].value_caption == "Sales Amount"
    assert lines[0].formula == "average"
    assert lines[0].scope == "per-table"
    assert wb.get_worksheet("Sales Sheet").reference_lines[0].value_caption == "Sales Amount"


def test_list_filters_and_dashboard_filter_controls_include_ui_metadata(tmp_path):
    twb = tmp_path / "filters.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook xmlns:user="http://www.tableausoftware.com/xml/user">
  <datasources>
    <datasource name="ds1">
      <column name="[Region]" caption="Sales Region" role="dimension" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="Sheet 1" caption="Filter Sheet">
      <table>
        <view>
          <filter class="categorical" column="[ds1].[none:Region:nk]" filter-group="1">
            <groupfilter
              function="member"
              level="[none:Region:nk]"
              member="&quot;North&quot;"
              user:ui-domain="relevant"
              user:ui-enumeration="inclusive"
              user:ui-marker="enumerate" />
          </filter>
        </view>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name="Dashboard 1" caption="Sales Dashboard">
      <zones>
        <zone id="1" type-v2="filter" name="Sheet 1" param="[ds1].[none:Region:nk]" mode="dropdown" show-apply="true" x="1" y="2" w="3" h="4" />
        <zone id="2" type-v2="filter" name="Sheet 1" param="[ds1].[none:Region:nk]" mode="checkdropdown" />
      </zones>
    </dashboard>
  </dashboards>
</workbook>
""",
        encoding="utf-8",
    )

    wb = TwbWorkbook.open(str(twb))
    filters = wb.list_filters("Filter Sheet")

    assert len(filters) == 1
    assert filters[0].worksheet == "Filter Sheet"
    assert filters[0].field == "Sales Region"
    assert filters[0].domain == "relevant"
    assert filters[0].value_scope == "relevant"
    assert filters[0].value_scope_label == "関連値のみ"
    assert filters[0].apply_scope == "selected_worksheets"
    assert filters[0].apply_scope_label == "選択したワークシート"
    assert filters[0].enumeration == "inclusive"
    assert filters[0].selection_type == "single"
    assert filters[0].values == ["North"]

    controls = wb.list_dashboard_filter_controls("Sales Dashboard")
    assert [c.mode for c in controls] == ["dropdown", "checkdropdown"]
    assert controls[0].dashboard == "Sales Dashboard"
    assert controls[0].worksheet == "Filter Sheet"
    assert controls[0].field == "Sales Region"
    assert controls[0].domain == "relevant"
    assert controls[0].value_scope == "relevant"
    assert controls[0].value_scope_label == "関連値のみ"
    assert controls[0].apply_scope == "selected_worksheets"
    assert controls[0].apply_scope_label == "選択したワークシート"
    assert controls[0].selection_type == "single"
    assert controls[0].values == ["North"]
    assert controls[0].show_apply is True
    assert controls[0].width == "3"


def test_list_dashboard_fields_resolves_caption_and_role(tmp_path):
    twb = tmp_path / "dashboard_fields.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="Source">
      <column name="[Sales]" caption="Sales Amount" role="measure" />
      <column name="[Region]" caption="Sales Region" role="dimension" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="Sheet 1">
      <table>
        <view>
          <datasource-dependencies datasource="ds1">
            <column name="[LocalCalc]" caption="Local Calc" role="measure" />
          </datasource-dependencies>
          <filter column="[ds1].[none:Region:nk]">
            <groupfilter function="member" member="&quot;North&quot;" />
            <groupfilter function="member" member="&quot;South&quot;" />
          </filter>
          <filter column="[ds1].[:Measure Names]">
            <groupfilter function="member" member="&quot;[ds1].[sum:Sales:qk]&quot;" />
            <groupfilter function="member" member="&quot;[ds1].[cnt:LocalCalc:qk]&quot;" />
          </filter>
          <rows>[ds1].[cnt:LocalCalc:qk]</rows>
          <cols>[ds1].[sum:Sales:qk]</cols>
        </view>
        <panes>
          <pane x-axis-name="[ds1].[none:Region:nk]">
            <encodings>
              <color column="[ds1].[none:Region:nk]" />
              <text column="[ds1].[sum:Sales:qk]" />
            </encodings>
            <custom column="[ds1].[none:Region:nk]" />
          </pane>
        </panes>
        <style>
          <style-rule element="cell">
            <format attr="text-format" field="[ds1].[none:Sales:qk]" value="n#,##0" />
          </style-rule>
        </style>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name="Dashboard 1">
      <zones>
        <zone name="Sheet 1" />
      </zones>
    </dashboard>
  </dashboards>
</workbook>
""",
        encoding="utf-8",
    )

    wb = TwbWorkbook.open(str(twb))
    fields = wb.list_dashboard_fields("Dashboard 1")

    assert ("Sheet 1", "フィルタ", "フィルタ", "dimension", "Sales Region", "North, South") in [
        (f.worksheet, f.category, f.type, f.role, f.caption, f.values) for f in fields
    ]
    assert ("Sheet 1", "フィルタ", "フィルタ", None, ":Measure Names", "Sales Amount, Local Calc") in [
        (f.worksheet, f.category, f.type, f.role, f.caption, f.values) for f in fields
    ]
    assert ("Sheet 1", "軸", "y軸", "measure", "Local Calc") in [
        (f.worksheet, f.category, f.type, f.role, f.caption) for f in fields
    ]
    assert ("Sheet 1", "軸", "x軸", "measure", "Sales Amount") in [
        (f.worksheet, f.category, f.type, f.role, f.caption) for f in fields
    ]
    assert ("Sheet 1", "軸", "x軸", "dimension", "Sales Region") in [
        (f.worksheet, f.category, f.type, f.role, f.caption) for f in fields
    ]
    assert ("Sheet 1", "ペイン", "色", "dimension", "Sales Region") in [
        (f.worksheet, f.category, f.type, f.role, f.caption) for f in fields
    ]
    assert ("Sheet 1", "ペイン", "ラベル", "measure", "Sales Amount") in [
        (f.worksheet, f.category, f.type, f.role, f.caption) for f in fields
    ]
    assert ("Sheet 1", "y軸", "Local Calc", "COUNT") in [
        (f.worksheet, f.type, f.caption, f.aggregation) for f in fields
    ]
    assert ("Sheet 1", "x軸", "Sales Amount", "SUM") in [
        (f.worksheet, f.type, f.caption, f.aggregation) for f in fields
    ]
    assert ("Sheet 1", "ラベル", "Sales Amount", "SUM") in [
        (f.worksheet, f.type, f.caption, f.aggregation) for f in fields
    ]
    assert ("Sheet 1", "その他", "その他", "dimension", "Sales Region") in [
        (f.worksheet, f.category, f.type, f.role, f.caption) for f in fields
    ]

    sales = next(col for ds in wb.list_datasources() for col in ds.columns if col.caption == "Sales Amount")
    assert {"attr": "text-format", "value": "n#,##0", "element": "cell", "worksheet": "Sheet 1"} in sales.format

    short_fields = wb.list_dashboard_fields("Dashboard 1", max_filter_value_chars=10)
    assert next(f for f in short_fields if f.type == "フィルタ").values == "North, ..."


def test_list_datasources_adds_display_formula(tmp_path):
    twb = tmp_path / "formula.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="Source">
      <column name="[Sales]" caption="Sales Amount" role="measure" />
      <column name="[Calc]" caption="Calc Field" role="measure">
        <calculation class="tableau" formula="[Sales] + [Parameters].[Current Year]" />
      </column>
    </datasource>
    <datasource name="Parameters">
      <column name="[Current Year]" caption="Current Year" datatype="integer" param-domain-type="list" role="measure" value="2026">
        <members>
          <member value="2025" alias="FY2025" />
          <member value="2026" alias="FY2026" />
        </members>
      </column>
      <column name="[Internal]" caption="Internal" hidden="true" value="1" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )

    wb = TwbWorkbook.open(str(twb))
    datasources = wb.list_datasources()
    calc = next(col for ds in datasources if ds.name == "ds1" for col in ds.columns if col.caption == "Calc Field")
    parameters = wb.list_parameters()

    assert [ds.name for ds in datasources] == ["ds1"]
    assert len(parameters) == 1
    assert parameters[0].caption == "Current Year"
    assert parameters[0].value == "2026"
    assert parameters[0].value_display == "FY2026"
    assert parameters[0].allowable_values == [{"value": "2025", "alias": "FY2025"}, {"value": "2026", "alias": "FY2026"}]
    assert len(wb.list_parameters(include_hidden=True)) == 2
    assert calc.formula == "[Sales Amount] + [Parameters].[Current Year]"
    assert calc.raw_formula == "[Sales] + [Parameters].[Current Year]"
    assert calc.referenced_columns == ["Sales Amount", "Parameters.Current Year"]
