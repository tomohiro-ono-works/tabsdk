from __future__ import annotations

import inspect
import json

from lxml import etree as ET
import pytest

from twbpatch import DetachedModelError, ResourceInUseError, TwbWorkbook


def _write_workbook(tmp_path, *, include_action: bool = False):
    action_xml = ""
    if include_action:
        action_xml = """
  <actions>
    <action name="[Action].[Select]" caption="選択アクション">
      <activation type="on-select" />
      <source dashboard="Dashboard1" type="sheet" />
      <command command="filter"><target dashboard="Dashboard1" type="sheet" /></command>
    </action>
  </actions>"""
    path = tmp_path / ("action.twb" if include_action else "final.twb")
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
    <datasource name="Parameters">
      <column name="[Year]" caption="年度" datatype="integer" value="2026" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="Sheet1" caption="売上シート">
      <table><view /><panes><pane id="1"><mark class="Automatic" /></pane></panes></table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name="Dashboard1" caption="概要">
      <size sizing-mode="fixed" minwidth="1200" maxwidth="1200" minheight="800" maxheight="800" />
      <zones />
    </dashboard>
  </dashboards>{action_xml}
</workbook>
""",
        encoding="utf-8",
    )
    return path


def test_datasource_delete_requires_child_resources_to_be_deleted(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    field = datasource.get_fields()[0]
    before = ET.tostring(workbook.tree.getroot())

    with pytest.raises(ResourceInUseError) as caught:
        datasource.delete()
    assert caught.value.resource_type == "Datasource"
    assert caught.value.references[0].resource_type == "Field"
    assert caught.value.references[0].resource_id == "[Sales]"
    assert ET.tostring(workbook.tree.getroot()) == before

    field.delete()
    datasource.delete()
    with pytest.raises(DetachedModelError):
        _ = datasource.name
    assert workbook.get_datasources() == []
    assert workbook.get_parameters()[0].name == "年度"


def test_workbook_set_default_font_preserves_explicit_font_overrides(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    worksheet = workbook.tree.xpath("/workbook/worksheets/worksheet")[0]
    table = worksheet.find("./table")
    assert table is not None
    style = ET.Element("style")
    header = ET.SubElement(style, "style-rule", attrib={"element": "header"})
    ET.SubElement(
        header,
        "format",
        attrib={"attr": "font-family", "value": "Arial"},
    )
    table.insert(1, style)
    layout = ET.Element("layout-options")
    title = ET.SubElement(layout, "title")
    formatted = ET.SubElement(title, "formatted-text")
    ET.SubElement(formatted, "run", attrib={"fontname": "Courier"}).text = "個別"
    ET.SubElement(formatted, "run").text = "既定"
    worksheet.insert(0, layout)
    dashboard = workbook.get_dashboards()[0]
    dashboard.create_container().add_text("ダッシュボード")

    assert workbook.set_default_font() is workbook
    assert workbook.set_default_font() is workbook

    assert workbook.tree.xpath(
        "/workbook/style/style-rule[@element='all']"
        "/format[@attr='font-family']/@value"
    ) == ["Meiryo UI"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet/table/style"
        "/style-rule[@element='header']"
        "/format[@attr='font-family']/@value"
    ) == ["Arial"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet/layout-options/title"
        "/formatted-text/run/@fontname"
    ) == ["Courier"]
    assert workbook.tree.xpath(
        "/workbook/dashboards/dashboard/zones//formatted-text/run/@fontname"
    ) == []


def test_dashboard_delete_requires_zones_and_containers_to_be_removed(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.get_dashboards()[0]
    root = dashboard.create_container(direction="horizontal")
    zone = root.add_worksheet(workbook.get_worksheets()[0])
    before = ET.tostring(workbook.tree.getroot())

    with pytest.raises(ResourceInUseError) as caught:
        dashboard.delete()
    assert caught.value.resource_type == "Dashboard"
    assert {item.resource_type for item in caught.value.references} == {
        "DashboardContainer",
        "DashboardZone",
    }
    assert ET.tostring(workbook.tree.getroot()) == before

    zone.delete()
    root.delete()
    dashboard.delete()
    with pytest.raises(DetachedModelError):
        _ = dashboard.name
    assert workbook.get_dashboards() == []
    assert workbook.get_worksheets()[0].name == "Sheet1"


def test_new_dashboard_actions_use_id_and_name_without_caption(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path, include_action=True)))
    dashboard = workbook.get_dashboards()[0]
    action = dashboard.get_actions()[0]

    assert (action.id, action.name, action.type, action.activation, action.command) == (
        "[Action].[Select]",
        "選択アクション",
        "filter",
        "on-select",
        "filter",
    )
    assert not hasattr(action, "caption")
    with pytest.raises(ResourceInUseError) as caught:
        dashboard.delete()
    assert caught.value.references[0].resource_type == "DashboardAction"
    assert caught.value.references[0].resource_id == "[Action].[Select]"


def test_export_json_uses_new_names_and_contains_no_connected_context(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path, include_action=True)))
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.get_worksheets()[0]
    field = datasource.get_fields()[0]
    worksheet.add_field(field, shelf="rows", aggregation="sum")
    dashboard = workbook.get_dashboards()[0]
    dashboard.create_container(direction="horizontal").add_worksheet(worksheet)

    exported = workbook.export_json()
    assert set(exported) == {"datasources", "parameters", "worksheets", "dashboards"}
    assert exported["datasources"][0]["id"] == "ds1"
    assert exported["datasources"][0]["name"] == "売上データ"
    assert exported["datasources"][0]["fields"][0]["id"] == "[Sales]"
    assert "columns" not in exported["datasources"][0]
    assert exported["worksheets"][0]["fields"][0]["field_id"] == "[Sales]"
    assert exported["dashboards"][0]["worksheets"] == [
        {"id": "Sheet1", "name": "Sheet1"}
    ]
    assert exported["dashboards"][0]["actions"][0]["name"] == "選択アクション"

    def assert_public(value):
        if isinstance(value, dict):
            for key, item in value.items():
                assert key != "caption"
                assert not key.startswith("_")
                assert_public(item)
        elif isinstance(value, list):
            for item in value:
                assert_public(item)

    assert_public(exported)
    json.dumps(exported, ensure_ascii=False)


def test_new_api_signatures_and_models_follow_final_contract(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    field = datasource.get_fields()[0]
    worksheet = workbook.get_worksheets()[0]
    pane = worksheet.get_panes()[0]
    dashboard = workbook.get_dashboards()[0]
    parameter = workbook.get_parameters()[0]

    calls = [
        (workbook.get_datasources, workbook.get_datasources()),
        (workbook.get_parameters, workbook.get_parameters()),
        (workbook.get_worksheets, workbook.get_worksheets()),
        (workbook.get_dashboards, workbook.get_dashboards()),
        (workbook.get_unsupported_features, workbook.get_unsupported_features()),
        (datasource.get_fields, datasource.get_fields()),
        (datasource.get_folders, datasource.get_folders()),
        (worksheet.get_fields, worksheet.get_fields()),
        (worksheet.get_panes, worksheet.get_panes()),
        (pane.get_fields, pane.get_fields()),
        (dashboard.get_worksheets, dashboard.get_worksheets()),
        (dashboard.get_containers, dashboard.get_containers()),
        (dashboard.get_zones, dashboard.get_zones()),
    ]
    for method, result in calls:
        assert isinstance(result, list)
        parameters = inspect.signature(method).parameters
        assert "by" not in parameters
        assert "identifier" not in parameters

    for model in (datasource, field, worksheet, pane, dashboard, parameter):
        assert not hasattr(model, "caption")
        allowed_updates = {
            "update_table_style",
            "update_title_style",
            "update_customized_label",
            "update_style",
        }
        assert not {
            name for name in dir(model)
            if name.startswith("update_") and name not in allowed_updates
        }

    assert hasattr(workbook, "list_datasources")
    assert hasattr(workbook, "get_datasource")


def test_connected_edits_round_trip_through_save_and_reopen(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.get_worksheets()[0]
    worksheet.add_field(datasource.get_fields()[0], shelf="rows", aggregation="sum")
    dashboard = workbook.get_dashboards()[0]
    dashboard.create_container(direction="horizontal").add_worksheet(worksheet)
    output = tmp_path / "roundtrip.twb"

    workbook.save(str(output), validate=True)
    assert workbook.is_dirty is False

    reopened = TwbWorkbook.open(str(output))
    placement = reopened.get_worksheets()[0].get_fields()[0]
    zone = reopened.get_dashboards()[0].get_zones()[0]
    assert (placement.field_id, placement.shelf, placement.aggregation) == (
        "[Sales]",
        "rows",
        "sum",
    )
    assert (zone.name, zone.worksheet_id, zone.placement_mode) == (
        "Sheet1",
        "Sheet1",
        "tiled",
    )
