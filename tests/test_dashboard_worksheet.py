from twbpatch import TwbWorkbook


def test_list_dashboards_includes_caption_and_worksheets(tmp_path):
    twb = tmp_path / "dashboard.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
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
    assert [worksheet.caption for worksheet in dashboards[0].worksheets] == ["Sales Sheet"]


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
            <groupfilter function="member" member="&quot;[ds1].[none:Sales:qk]&quot;" />
            <groupfilter function="member" member="&quot;[ds1].[none:LocalCalc:qk]&quot;" />
          </filter>
          <rows>[ds1].[none:LocalCalc:qk]</rows>
          <cols>[ds1].[none:Sales:qk]</cols>
        </view>
        <panes>
          <pane x-axis-name="[ds1].[none:Region:nk]">
            <encodings>
              <color column="[ds1].[none:Region:nk]" />
              <text column="[ds1].[none:Sales:qk]" />
            </encodings>
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

    assert ("Sheet 1", "フィルタ", "dimension", "Sales Region", "North, South") in [
        (f.worksheet, f.type, f.role, f.caption, f.values) for f in fields
    ]
    assert ("Sheet 1", "フィルタ", None, ":Measure Names", "Sales Amount, Local Calc") in [
        (f.worksheet, f.type, f.role, f.caption, f.values) for f in fields
    ]
    assert ("Sheet 1", "行", "measure", "Local Calc") in [(f.worksheet, f.type, f.role, f.caption) for f in fields]
    assert ("Sheet 1", "列", "measure", "Sales Amount") in [(f.worksheet, f.type, f.role, f.caption) for f in fields]
    assert ("Sheet 1", "ペイン", "dimension", "Sales Region") in [(f.worksheet, f.type, f.role, f.caption) for f in fields]
    assert ("Sheet 1", "色", "dimension", "Sales Region") in [(f.worksheet, f.type, f.role, f.caption) for f in fields]
    assert ("Sheet 1", "ラベル", "measure", "Sales Amount") in [(f.worksheet, f.type, f.role, f.caption) for f in fields]

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
