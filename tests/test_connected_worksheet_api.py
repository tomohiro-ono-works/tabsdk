from __future__ import annotations

from lxml import etree as ET
import pytest

from twbpatch import DetachedModelError, TwbWorkbook


def _write_workbook(tmp_path, filename: str = "worksheet.twb"):
    path = tmp_path / filename
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <windows>
    <window class="worksheet" name="Sheet1" hidden="false" />
  </windows>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Region]" caption="地域" datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="Sheet1" caption="売上シート">
      <table>
        <view>
          <datasource-dependencies datasource="ds1" />
        </view>
        <panes>
          <pane id="1">
            <mark class="Automatic" />
            <encodings />
          </pane>
        </panes>
      </table>
    </worksheet>
  </worksheets>
</workbook>
""",
        encoding="utf-8",
    )
    return path


def test_get_worksheets_and_panes_are_connected_lists(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))

    worksheets = workbook.get_worksheets()
    assert [(item.id, item.name, item.visible) for item in worksheets] == [
        ("Sheet1", "Sheet1", True),
    ]
    assert [item.id for item in workbook.get_worksheets(id="Sheet1")] == ["Sheet1"]
    assert [item.id for item in workbook.get_worksheets(name="Sheet1")] == ["Sheet1"]
    assert workbook.get_worksheets(name="missing") == []

    panes = worksheets[0].get_panes()
    assert [(item.id, item.name, item.mark_type) for item in panes] == [
        ("1", "1", "automatic"),
    ]
    assert [item.id for item in worksheets[0].get_panes(name="1")] == ["1"]

    with pytest.raises(ValueError, match="cannot be specified together"):
        workbook.get_worksheets(id="Sheet1", name="Sheet1")


def test_add_field_places_id_references_on_all_worksheet_shelves(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    sales = datasource.get_fields(name="売上")[0]
    region = datasource.get_fields(name="地域")[0]
    worksheet = workbook.get_worksheets()[0]

    rows = worksheet.add_field(field=sales, shelf="rows", aggregation="sum")
    columns = worksheet.add_field(field=region, shelf="columns", discrete=True)
    pages = worksheet.add_field(field=region, shelf="pages")
    filters = worksheet.add_field(field=region, shelf="filters")

    assert (rows.field_id, rows.name, rows.shelf, rows.aggregation, rows.discrete) == (
        "[Sales]",
        "売上",
        "rows",
        "sum",
        False,
    )
    assert (columns.field_id, columns.shelf, columns.discrete) == (
        "[Region]",
        "columns",
        True,
    )
    assert pages.shelf == "pages"
    assert filters.shelf == "filters"
    assert not hasattr(worksheet, "create_field")
    assert workbook.is_dirty is True

    worksheet_el = workbook.tree.getroot().xpath("/workbook/worksheets/worksheet")[0]
    assert worksheet_el.xpath("string(.//*[local-name()='rows'])") == "[ds1].[sum:Sales:qk]"
    assert worksheet_el.xpath("string(.//*[local-name()='cols'])") == "[ds1].[none:Region:nk]"
    assert worksheet_el.xpath("string(.//*[local-name()='pages'])") == "[ds1].[none:Region:nk]"
    assert worksheet_el.xpath("string(.//*[local-name()='filter']/@column)") == "[ds1].[none:Region:nk]"
    assert worksheet_el.xpath("string(./table/rows)") == "[ds1].[sum:Sales:qk]"
    assert worksheet_el.xpath("string(./table/cols)") == "[ds1].[none:Region:nk]"
    assert worksheet_el.xpath("string(./table/pages)") == "[ds1].[none:Region:nk]"
    assert not worksheet_el.xpath("./table/view/rows | ./table/view/cols | ./table/view/pages")
    dependency_ids = worksheet_el.xpath(
        ".//*[local-name()='datasource-dependencies']/*[local-name()='column']/@name"
    )
    assert dependency_ids == ["[Sales]", "[Region]"]
    instance_ids = worksheet_el.xpath(
        ".//*[local-name()='datasource-dependencies']/*[local-name()='column-instance']/@name"
    )
    assert instance_ids == ["[sum:Sales:qk]", "[none:Region:nk]"]


def test_workbook_set_filter_applies_to_all_worksheets_using_datasource(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources(name="売上データ")[0]
    second = workbook.create_worksheet(name="Sheet2")
    second.add_field(
        field=datasource.get_fields(name="売上")[0],
        shelf="rows",
        aggregation="sum",
    )
    unrelated = workbook.create_worksheet(name="Unrelated")

    assert workbook.set_filter(("売上データ", "地域")) is workbook
    assert workbook.set_filter(("売上データ", "地域")) is workbook

    shared_filters = workbook.tree.xpath(
        "/workbook/shared-views/shared-view[@name='ds1']/filter"
    )
    assert len(shared_filters) == 1
    assert shared_filters[0].attrib == {
        "class": "categorical",
        "column": "[ds1].[none:Region:nk]",
    }
    groupfilter = shared_filters[0].xpath("./groupfilter")[0]
    assert groupfilter.get("function") == "level-members"
    assert groupfilter.get("level") == "[none:Region:nk]"
    assert groupfilter.get(
        "{http://www.tableausoftware.com/xml/user}ui-enumeration"
    ) == "all"
    assert groupfilter.get(
        "{http://www.tableausoftware.com/xml/user}ui-marker"
    ) == "enumerate"
    for worksheet in [workbook.get_worksheets(name="Sheet1")[0], second]:
        assert worksheet.get_filters() == []
        view = worksheet._resolve_element().xpath("./table/view")[0]
        assert view.xpath("filter") == []
        assert view.xpath("slices/column/text()") == ["[ds1].[none:Region:nk]"]
    assert unrelated.get_filters() == []


def test_add_sort_creates_computed_sort_and_field_instances(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    sales = datasource.get_fields(name="売上")[0]
    region = datasource.get_fields(name="地域")[0]
    worksheet = workbook.get_worksheets()[0]

    assert worksheet.add_sort(field=region, by=sales) is worksheet

    worksheet_el = workbook.tree.xpath("/workbook/worksheets/worksheet")[0]
    sort = worksheet_el.xpath("./table/view/computed-sort")[0]
    assert sort.attrib == {
        "column": "[ds1].[none:Region:nk]",
        "direction": "DESC",
        "using": "[ds1].[sum:Sales:qk]",
    }
    assert worksheet_el.xpath(
        "./table/view/datasource-dependencies/column-instance/@name"
    ) == ["[none:Region:nk]", "[sum:Sales:qk]"]
    assert len(workbook.tree.xpath(
        "/workbook/document-format-change-manifest/SortTagCleanup"
    )) == 1
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_pane_updates_mark_and_adds_encodings(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    sales = datasource.get_fields(name="売上")[0]
    region = datasource.get_fields(name="地域")[0]
    pane = workbook.get_worksheets()[0].get_panes()[0]

    assert pane.update(mark_type="bar") is pane
    color = pane.add_field(field=region, encoding="color")
    label = pane.add_field(field=sales, encoding="label", aggregation="sum")
    angle = pane.add_field(field=sales, encoding="angle", aggregation="sum")

    assert pane.mark_type == "bar"
    assert (color.encoding, color.pane_id, color.field_id) == ("color", "1", "[Region]")
    assert (label.encoding, label.aggregation, label.field_id) == ("label", "sum", "[Sales]")
    assert (angle.encoding, angle.aggregation, angle.field_id) == ("angle", "sum", "[Sales]")
    assert [(item.encoding, item.name) for item in pane.get_fields()] == [
        ("color", "地域"),
        ("label", "売上"),
        ("angle", "売上"),
    ]

    pane_el = workbook.tree.getroot().xpath("//*[local-name()='pane'][@id='1']")[0]
    assert pane_el.xpath("string(./*[local-name()='mark']/@class)") == "Bar"
    assert pane_el.xpath("string(.//*[local-name()='color']/@column)") == "[ds1].[none:Region:nk]"
    assert pane_el.xpath("string(.//*[local-name()='text']/@column)") == "[ds1].[sum:Sales:qk]"
    assert pane_el.xpath("string(.//*[local-name()='wedge-size']/@column)") == "[ds1].[sum:Sales:qk]"
    pane.update(mark_type="pie")
    assert pane.mark_type == "pie"


def test_worksheet_field_update_and_delete_only_change_placement(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    sales = datasource.get_fields(name="売上")[0]
    worksheet = workbook.get_worksheets()[0]
    placement = worksheet.add_field(field=sales, shelf="rows", aggregation="sum")

    assert placement.update(aggregation="avg", discrete=True) is placement
    assert placement.aggregation == "avg"
    assert placement.discrete is True
    assert workbook.tree.getroot().xpath("string(//*[local-name()='rows'])") == "[ds1].[avg:Sales:nk]"

    placement.delete()
    with pytest.raises(DetachedModelError):
        _ = placement.name
    assert worksheet.get_fields() == []
    assert datasource.get_fields(id="[Sales]")[0].name == "売上"


def test_worksheet_update_renames_id_and_updates_window_visibility(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    worksheet = workbook.get_worksheets()[0]

    assert worksheet.update(name="主要指標", visible=False) is worksheet
    assert worksheet.id == "主要指標"
    assert worksheet.name == "主要指標"
    assert worksheet.visible is False

    assert workbook.get_worksheets(id="Sheet1") == []
    assert workbook.get_worksheets(name="主要指標")[0] is not worksheet
    with pytest.raises(TypeError, match="name must be a string"):
        worksheet.update(name=None)
    assert workbook.tree.getroot().xpath(
        "string(/workbook/windows/window[@class='worksheet'][@name='主要指標']/@hidden)"
    ) == "true"


def test_worksheet_rename_updates_dashboard_and_action_references(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    root = workbook.tree.getroot()
    dashboards = ET.SubElement(root, "dashboards")
    dashboard = ET.SubElement(dashboards, "dashboard", name="Dashboard1")
    zones = ET.SubElement(dashboard, "zones")
    ET.SubElement(zones, "zone", id="1", name="Sheet1")
    actions = ET.SubElement(root, "actions")
    action = ET.SubElement(actions, "action", name="[Action].[Select]")
    ET.SubElement(action, "source", worksheet="Sheet1")

    worksheet = workbook.get_worksheets(id="Sheet1")[0]
    worksheet.update(name="月次売上")

    assert (worksheet.id, worksheet.name) == ("月次売上", "月次売上")
    assert root is not workbook.tree.getroot()
    updated_root = workbook.tree.getroot()
    assert updated_root.xpath("string(/workbook/dashboards/dashboard/zones/zone/@name)") == "月次売上"
    assert updated_root.xpath("string(/workbook/actions/action/source/@worksheet)") == "月次売上"
    assert updated_root.xpath("string(/workbook/windows/window/@name)") == "月次売上"


def test_create_worksheet_builds_standard_empty_structure(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))

    worksheet = workbook.create_worksheet(name="新規シート", visible=False)

    assert (worksheet.id, worksheet.name, worksheet.visible) == (
        "新規シート",
        "新規シート",
        False,
    )
    assert [(pane.id, pane.mark_type) for pane in worksheet.get_panes()] == [
        ("1", "automatic")
    ]
    worksheet_el = workbook.tree.getroot().xpath(
        "/workbook/worksheets/worksheet[@name='新規シート']"
    )[0]
    assert worksheet_el.get("caption") is None
    assert len(worksheet_el.xpath("./table/view")) == 1
    assert len(worksheet_el.xpath("./table/view/datasources")) == 1
    assert len(worksheet_el.xpath("./table/view/aggregation[@value='true']")) == 1
    assert len(worksheet_el.xpath("./table/style")) == 1
    assert len(worksheet_el.xpath("./table/panes/pane/view/breakdown[@value='auto']")) == 1
    assert len(worksheet_el.xpath("./table/panes/pane[@id='1']/mark[@class='Automatic']")) == 1
    assert len(worksheet_el.xpath("./table/panes/pane[@id='1']/encodings")) == 1
    assert len(worksheet_el.xpath("./table/rows | ./table/cols")) == 2
    assert len(worksheet_el.xpath("./simple-id[starts-with(@uuid, '{')]")) == 1
    assert workbook.tree.getroot().xpath(
        "string(/workbook/windows/window[@name='新規シート']/@hidden)"
    ) == "true"

    before_duplicate = ET.tostring(workbook.tree.getroot())
    with pytest.raises(ValueError, match="already exists"):
        workbook.create_worksheet(name="新規シート")
    assert ET.tostring(workbook.tree.getroot()) == before_duplicate


def test_invalid_worksheet_operations_leave_xml_unchanged(tmp_path) -> None:
    first = TwbWorkbook.open(str(_write_workbook(tmp_path, "first.twb")))
    second = TwbWorkbook.open(str(_write_workbook(tmp_path, "second.twb")))
    worksheet = first.get_worksheets()[0]
    pane = worksheet.get_panes()[0]
    field = first.get_datasources()[0].get_fields()[0]
    foreign_field = second.get_datasources()[0].get_fields()[0]
    before = first.tree.getroot().getroottree().xpath("string(/workbook/worksheets/worksheet/@caption)")

    with pytest.raises(ValueError, match="unsupported shelf"):
        worksheet.add_field(field=field, shelf="invalid")
    with pytest.raises(ValueError, match="unsupported aggregation"):
        worksheet.add_field(field=field, shelf="rows", aggregation="median")
    with pytest.raises(ValueError, match="same workbook"):
        worksheet.add_field(field=foreign_field, shelf="rows")
    with pytest.raises(ValueError, match="unsupported encoding"):
        pane.add_field(field=field, encoding="invalid")
    with pytest.raises(ValueError, match="unsupported mark type"):
        pane.update(mark_type="hexbin")

    assert first.is_dirty is False
    assert first.tree.getroot().xpath("string(/workbook/worksheets/worksheet/@caption)") == before
    assert worksheet.get_fields() == []


def test_update_grand_totals_writes_shelf_attributes(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    worksheet = workbook.get_worksheets()[0]

    assert worksheet.grand_totals == {"row": None, "column": None}
    assert worksheet.update(grand_totals={"row": "bottom", "column": "right"}) is worksheet

    def shelf(tag: str) -> dict[str, str]:
        # update() は worksheet 要素ごと差し替えるため、都度取り直す。
        return dict(
            workbook.tree.xpath(f"/workbook/worksheets/worksheet/table/{tag}")[0].attrib
        )

    assert shelf("rows") == {"total": "true", "onTop": "false"}
    assert shelf("cols") == {"total": "true", "onLeft": "false"}
    assert worksheet.grand_totals == {"row": "bottom", "column": "right"}

    worksheet.update(grand_totals={"row": "top", "column": "left"})
    assert shelf("rows") == {"total": "true", "onTop": "true"}
    assert shelf("cols") == {"total": "true", "onLeft": "true"}
    assert worksheet.grand_totals == {"row": "top", "column": "left"}

    worksheet.update(grand_totals={"column": None})
    assert shelf("cols") == {}
    assert worksheet.grand_totals == {"row": "top", "column": None}
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_update_grand_totals_rejects_unknown_key_and_position(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    worksheet = workbook.get_worksheets()[0]

    with pytest.raises(ValueError):
        worksheet.update(grand_totals={"rows": "bottom"})
    with pytest.raises(ValueError):
        worksheet.update(grand_totals={"row": "left"})
    with pytest.raises(ValueError):
        worksheet.update(grand_totals={"column": "top"})
    with pytest.raises(TypeError):
        worksheet.update(grand_totals="bottom")

    # 検証で弾いた呼び出しは XML を変えない（仕様 §5.5）。
    assert workbook.tree.xpath("/workbook/worksheets/worksheet/table/rows") == []
    assert worksheet.grand_totals == {"row": None, "column": None}


def test_set_subtotal_visibility_adds_and_removes_subtotals(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.get_worksheets()[0]
    region = worksheet.add_field(field=datasource.get_fields(name="地域")[0], shelf="rows")

    def subtotal_columns() -> list[str]:
        return workbook.tree.xpath(
            "/workbook/worksheets/worksheet/table/subtotals/column/text()"
        )

    assert worksheet.set_subtotal_visibility(field=region) is worksheet
    assert subtotal_columns() == ["[ds1].[none:Region:nk]"]
    # <subtotals> は <table> 直下、rows / cols より後ろに置く（validator の要素順）。
    table = workbook.tree.xpath("/workbook/worksheets/worksheet/table")[0]
    names = [child.tag for child in table]
    assert names.index("subtotals") > names.index("rows")
    assert not [message for message in workbook.validate() if message.severity == "error"]

    # 二重に呼んでも column は増えない。
    worksheet.set_subtotal_visibility(field=region)
    assert subtotal_columns() == ["[ds1].[none:Region:nk]"]

    worksheet.set_subtotal_visibility(field=region, visible=False)
    assert workbook.tree.xpath("/workbook/worksheets/worksheet/table/subtotals") == []
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_set_subtotal_visibility_rejects_unusable_fields(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.get_worksheets()[0]
    filtered = worksheet.add_field(field=datasource.get_fields(name="地域")[0], shelf="filters")

    with pytest.raises(TypeError):
        worksheet.set_subtotal_visibility(field="地域")
    with pytest.raises(ValueError):
        worksheet.set_subtotal_visibility(field=filtered)
    assert workbook.tree.xpath("/workbook/worksheets/worksheet/table/subtotals") == []
