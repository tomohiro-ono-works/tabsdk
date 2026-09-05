from __future__ import annotations

from lxml import etree as ET
import pytest

from twbpatch import DetachedModelError, ResourceInUseError, TwbWorkbook


def _write_fields_workbook(tmp_path, *, with_formula: bool = False):
    calculation = (
        '<column name="[Calc]" caption="計算" datatype="real" role="measure">'
        '<calculation class="tableau" formula="[Sales] * 2" />'
        "</column>"
        if with_formula
        else ""
    )
    path = tmp_path / ("formula.twb" if with_formula else "fields.twb")
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      {calculation}
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="Sheet1" caption="売上シート">
      <table><view /><panes><pane id="1"><mark class="Automatic" /></pane></panes></table>
    </worksheet>
  </worksheets>
</workbook>
""",
        encoding="utf-8",
    )
    return path


def _write_parameter_workbook(tmp_path):
    path = tmp_path / "parameters.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Calc]" caption="計算" datatype="integer" role="measure">
        <calculation class="tableau" formula="[Parameters].[Current Year]" />
      </column>
    </datasource>
    <datasource name="Parameters">
      <column name="[Current Year]" caption="年度" datatype="integer" param-domain-type="list" role="measure" value="2026">
        <members>
          <member value="2025" alias="FY2025" />
          <member value="2026" alias="FY2026" />
        </members>
      </column>
      <column name="[Internal]" caption="内部" datatype="integer" hidden="true" value="1" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return path


def test_field_delete_blocks_formula_reference_without_mutation(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_fields_workbook(tmp_path, with_formula=True)))
    datasource = workbook.get_datasources()[0]
    sales = datasource.get_fields(id="[Sales]")[0]
    before = ET.tostring(workbook.tree.getroot())

    with pytest.raises(ResourceInUseError) as caught:
        sales.delete()
    assert caught.value.resource_type == "Field"
    assert caught.value.resource_id == "[Sales]"
    assert [(item.resource_type, item.resource_id) for item in caught.value.references] == [
        ("Field", "[Calc]"),
    ]
    assert "@formula" in caught.value.references[0].location
    assert ET.tostring(workbook.tree.getroot()) == before
    assert workbook.is_dirty is False
    assert sales.name == "売上"

    calculated = datasource.get_fields(id="[Calc]")[0]
    calculated.delete()
    sales.delete()
    with pytest.raises(DetachedModelError):
        _ = sales.name
    assert datasource.get_fields() == []


def test_folder_delete_requires_explicit_field_removal(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_fields_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    field = datasource.get_fields()[0]
    folder = datasource.create_folder(name="KPI")
    field.move_to_folder(folder)
    before = ET.tostring(workbook.tree.getroot())

    with pytest.raises(ResourceInUseError) as caught:
        folder.delete()
    assert caught.value.references[0].resource_type == "Field"
    assert caught.value.references[0].resource_id == "[Sales]"
    assert ET.tostring(workbook.tree.getroot()) == before

    field.remove_from_folder()
    folder.delete()
    with pytest.raises(DetachedModelError):
        _ = folder.name
    assert datasource.get_folders() == []
    assert datasource.get_fields()[0].id == "[Sales]"


def test_placement_delete_removes_unused_dependency_before_field_delete(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_fields_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    field = datasource.get_fields()[0]
    worksheet = workbook.get_worksheets()[0]
    placement = worksheet.add_field(field, shelf="rows", aggregation="sum")

    with pytest.raises(ResourceInUseError) as caught:
        field.delete()
    assert {item.resource_type for item in caught.value.references} == {"Worksheet"}

    placement.delete()
    dependency_columns = workbook.tree.getroot().xpath(
        "/workbook/worksheets/worksheet//*[local-name()='datasource-dependencies']"
        "/*[local-name()='column']/@name"
    )
    assert dependency_columns == []
    field.delete()
    assert datasource.get_fields() == []


def test_parameter_get_update_and_reference_safe_delete(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_parameter_workbook(tmp_path)))
    parameters = workbook.get_parameters()
    assert [(item.id, item.name, item.value, item.value_display) for item in parameters] == [
        ("[Current Year]", "年度", "2026", "FY2026"),
    ]
    assert len(workbook.get_parameters(include_hidden=True)) == 2
    parameter = workbook.get_parameters(name="年度")[0]
    assert parameter.allowable_values == [
        {"value": "2025", "alias": "FY2025"},
        {"value": "2026", "alias": "FY2026"},
    ]

    parameter.update(value=2025)
    assert (parameter.value, parameter.value_display) == ("2025", "FY2025")
    before_invalid = ET.tostring(workbook.tree.getroot())
    with pytest.raises(ValueError, match="not allowed"):
        parameter.update(value=2030)
    assert ET.tostring(workbook.tree.getroot()) == before_invalid

    hidden = workbook.get_parameters(id="[Internal]", include_hidden=True)[0]
    with pytest.raises(ValueError, match="allow_hidden"):
        hidden.update(value=2)
    hidden.update(value=2, allow_hidden=True)
    assert hidden.value == "2"

    with pytest.raises(ResourceInUseError) as caught:
        parameter.delete()
    assert caught.value.references[0].resource_id == "[Calc]"
    workbook.get_datasources()[0].get_fields(id="[Calc]")[0].delete()
    parameter.delete()
    assert workbook.get_parameters(name="年度") == []


def test_create_list_parameter_uses_name_based_id_and_display_aliases(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_parameter_workbook(tmp_path)))

    parameter = workbook.create_parameter(
        name="対象年度",
        value=2025,
        datatype="integer",
        domain_type="list",
        allowable_values={2024: "FY2024", 2025: "FY2025"},
    )

    assert (parameter.id, parameter.name, parameter.value, parameter.value_display) == (
        "[対象年度]",
        "対象年度",
        "2025",
        "FY2025",
    )
    assert parameter.allowable_values == [
        {"value": "2024", "alias": "FY2024"},
        {"value": "2025", "alias": "FY2025"},
    ]
    parameter.update(value=2024)
    assert (parameter.value, parameter.value_display) == ("2024", "FY2024")
    parameter_el = workbook.tree.getroot().xpath(
        "/workbook/datasources/datasource[@name='Parameters']/column[@name='[対象年度]']"
    )[0]
    assert parameter_el.get("value") == "2024"
    assert parameter_el.xpath("string(./calculation/@formula)") == "2024"


def test_create_parameter_lazily_adds_parameters_datasource(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_fields_workbook(tmp_path)))

    parameter = workbook.create_parameter(name="地域", value="東日本")

    assert (parameter.id, parameter.name, parameter.value) == ("[地域]", "地域", "東日本")
    datasource_el = workbook.tree.getroot().xpath(
        "/workbook/datasources/datasource[@name='Parameters']"
    )[0]
    assert datasource_el.attrib == {
        "name": "Parameters",
        "caption": "Parameters",
        "hasconnection": "false",
        "inline": "true",
    }
    parameter_el = datasource_el.xpath("./column[@name='[地域]']")[0]
    assert parameter_el.get("value") == '"東日本"'
    assert parameter_el.xpath("string(./calculation/@formula)") == '"東日本"'


def test_create_range_parameter_validates_before_mutating_xml(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_fields_workbook(tmp_path, with_formula=True)))

    parameter = workbook.create_parameter(
        name="閾値",
        value=5,
        datatype="integer",
        domain_type="range",
        min_value=1,
        max_value=10,
        step_size=2,
    )
    assert (parameter.min_value, parameter.max_value, parameter.step_size) == ("1", "10", "2")

    invalid = TwbWorkbook.open(str(_write_fields_workbook(tmp_path)))
    before = ET.tostring(invalid.tree.getroot())
    with pytest.raises(ValueError, match="within the parameter range"):
        invalid.create_parameter(
            name="範囲外",
            value=11,
            datatype="integer",
            domain_type="range",
            min_value=1,
            max_value=10,
        )
    assert ET.tostring(invalid.tree.getroot()) == before
    assert invalid.is_dirty is False


def test_created_worksheet_and_parameter_round_trip(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_fields_workbook(tmp_path)))
    workbook.create_worksheet(name="分析シート")
    workbook.create_parameter(
        name="表示年度",
        value=2026,
        datatype="integer",
        domain_type="list",
        allowable_values={2025: "FY2025", 2026: "FY2026"},
    )
    output = tmp_path / "created-roundtrip.twb"

    workbook.save(str(output), validate=True)
    reopened = TwbWorkbook.open(str(output))

    assert [(item.id, item.name) for item in reopened.get_worksheets(name="分析シート")] == [
        ("分析シート", "分析シート")
    ]
    parameter = reopened.get_parameters(name="表示年度")[0]
    assert (parameter.id, parameter.value, parameter.value_display) == (
        "[表示年度]",
        "2026",
        "FY2026",
    )


def test_worksheet_delete_blocks_dashboard_zone_then_removes_window(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_fields_workbook(tmp_path)))
    worksheet = workbook.get_worksheets()[0]
    dashboard = workbook.create_dashboard(name="Dashboard")
    zone = dashboard.create_container(direction="horizontal").add_worksheet(worksheet)
    before = ET.tostring(workbook.tree.getroot())

    with pytest.raises(ResourceInUseError) as caught:
        worksheet.delete()
    assert caught.value.resource_type == "Worksheet"
    assert caught.value.references[0].resource_type == "Dashboard"
    assert ET.tostring(workbook.tree.getroot()) == before

    zone.delete()
    worksheet.delete()
    with pytest.raises(DetachedModelError):
        _ = worksheet.name
    assert workbook.get_worksheets() == []
