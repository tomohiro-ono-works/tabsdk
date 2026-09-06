from __future__ import annotations

from lxml import etree as ET
import pytest

from twbpatch import (
    DetachedModelError,
    ResourceInUseError,
    TwbWorkbook,
    UnsupportedFeatureError,
)


def _write_workbook(tmp_path, *, existing_dashboard: bool = False):
    dashboard_xml = ""
    if existing_dashboard:
        dashboard_xml = """
  <dashboards>
    <dashboard name="Existing" caption="既存ダッシュボード">
      <size sizing-mode="fixed" minwidth="1200" maxwidth="1200" minheight="800" maxheight="800" />
      <zones>
        <zone id="1" type-v2="layout-basic" param="horz" x="0" y="0" w="100000" h="100000" custom="keep">
          <zone id="2" name="SheetA" x="0" y="0" w="100000" h="100000" show-title="true" custom-child="keep" />
        </zone>
        <zone id="3" name="SheetB" x="10000" y="10000" w="25000" h="25000" floating-custom="keep" />
      </zones>
      <devicelayouts>
        <devicelayout name="phone">
          <zones><zone id="phone-1" name="SheetA" x="0" y="0" w="100000" h="50000" /></zones>
        </devicelayout>
      </devicelayouts>
    </dashboard>
  </dashboards>"""
    path = tmp_path / ("existing.twb" if existing_dashboard else "dashboard.twb")
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <worksheets>
    <worksheet name="SheetA" caption="シートA" />
    <worksheet name="SheetB" caption="シートB" />
    <worksheet name="SheetC" caption="シートC" />
  </worksheets>{dashboard_xml}
</workbook>
""",
        encoding="utf-8",
    )
    return path


def test_create_dashboard_uses_fixed_1200_by_800_default(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))

    dashboard = workbook.create_dashboard(name="経営ダッシュボード")
    assert (dashboard.id, dashboard.name) == ("経営ダッシュボード", "経営ダッシュボード")
    assert (dashboard.sizing_mode, dashboard.width, dashboard.height) == ("fixed", 1200, 800)
    assert dashboard.visible is True
    assert [item.id for item in workbook.get_dashboards(name="経営ダッシュボード")] == [
        "経営ダッシュボード"
    ]
    assert workbook.is_dirty is True

    size = workbook.tree.getroot().xpath("/workbook/dashboards/dashboard/size")[0]
    assert size.attrib == {
        "sizing-mode": "fixed",
        "minwidth": "1200",
        "maxwidth": "1200",
        "minheight": "800",
        "maxheight": "800",
    }


def test_nested_tiled_containers_compute_coordinates_from_order_and_weight(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="経営ダッシュボード")
    worksheets = {item.id: item for item in workbook.get_worksheets()}
    root = dashboard.create_container(direction="horizontal")
    left = root.create_container(direction="vertical", order=0, weight=2)
    right = root.create_container(direction="vertical", order=1, weight=1)
    sheet_a = left.add_worksheet(worksheets["SheetA"], order=0, weight=1)
    sheet_b = left.add_worksheet(worksheets["SheetB"], order=1, weight=1)
    sheet_c = right.add_worksheet(worksheets["SheetC"], weight=1)

    assert (root.direction, root.order, root.weight) == ("horizontal", None, None)
    assert [(item.id, item.direction) for item in root.get_containers()] == [
        (left.id, "vertical"),
        (right.id, "vertical"),
    ]
    assert (left.order, left.weight, right.order, right.weight) == (0, 2.0, 1, 1.0)
    assert [item.name for item in dashboard.get_worksheets()] == ["SheetA", "SheetB", "SheetC"]
    assert [item.placement_mode for item in dashboard.get_zones()] == ["tiled", "tiled", "tiled"]

    zones = {
        zone.get("id"): tuple(int(zone.get(attr) or 0) for attr in ("x", "y", "w", "h"))
        for zone in workbook.tree.getroot().xpath("/workbook/dashboards/dashboard/zones//zone")
    }
    assert zones[root.id] == (0, 0, 100000, 100000)
    assert zones[left.id] == (0, 0, 66667, 100000)
    assert zones[right.id] == (66667, 0, 33333, 100000)
    assert zones[sheet_a.id] == (0, 0, 66667, 50000)
    assert zones[sheet_b.id] == (0, 50000, 66667, 50000)
    assert zones[sheet_c.id] == (66667, 0, 33333, 100000)


def test_build_report_creates_named_rows_and_resolves_worksheet_names(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    workbook.get_worksheets(name="SheetC")[0].update(title="表タイトル")
    dashboard = workbook.create_dashboard(name="経営ダッシュボード")

    result = dashboard.build_report(
        dashboard_name="経営ダッシュボード",
        struct={
            "フィルタコンテナ": [],
            "スコアカード": ["SheetA", "SheetB"],
            "表": ["SheetC"],
        },
    )

    outer = dashboard.get_containers()[0]
    root = outer.get_containers(name="経営ダッシュボード")[0]
    assert result is dashboard
    assert dashboard.name == "経営ダッシュボード"
    assert outer.direction == "vertical"
    assert [item.name for item in outer.get_containers()] == ["経営ダッシュボード"]
    assert [item.name for item in root.get_containers()] == [
        "フィルタコンテナ",
        "スコアカード",
        "表",
    ]
    assert outer.get_zones()[0].fixed_size == 43
    assert [item.fixed_size for item in root.get_containers()] == [50, 250, 300]
    assert outer.get_zones()[0].text == "経営ダッシュボード"
    assert root.get_containers()[0].get_zones() == []
    assert root.get_containers()[1].get_zones()[0].style == {
        "background_color": "#ffffff",
        "border_style": "none",
        "margin": "4",
        "padding": "16",
    }
    assert root.get_zones()[-1].kind == "spacer"
    assert [item.name for item in dashboard.get_worksheets()] == [
        "SheetA",
        "SheetB",
        "SheetC",
    ]
    assert root.get_containers(name="表")[0].get_zones()[0].show_title is True
    assert root.get_containers(name="スコアカード")[0].get_zones()[0].show_title is False
    assert "caption" not in dashboard._resolve_element().attrib


def test_build_report_places_vertical_worksheet_groups_in_columns(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="経営ダッシュボード")

    dashboard.build_report(
        dashboard_name="経営ダッシュボード",
        struct={
            "スコア・時系列コンテナ": [
                {"items": ["SheetA", "SheetB"], "fixed_size": 200},
                ["SheetC"],
            ],
        },
        container_sizes={"スコア・時系列コンテナ": 206},
        content_style={"padding": 16, "padding_top": 4},
    )

    outer = dashboard.get_containers()[0]
    content = outer.get_containers(name="経営ダッシュボード")[0]
    row = content.get_containers(name="スコア・時系列コンテナ")[0]
    columns = row.get_containers()
    assert row.fixed_size == 206
    assert row.distribute_evenly is True
    assert [column.direction for column in columns] == ["vertical", "vertical"]
    assert [column.distribute_evenly for column in columns] == [True, False]
    assert [column.fixed_size for column in columns] == [200, None]
    assert [[zone.name for zone in column.get_zones()] for column in columns] == [
        ["SheetA", "SheetB"],
        ["SheetC"],
    ]
    assert [zone.fixed_size for zone in columns[0].get_zones()] == [None, None]
    assert [zone.weight for zone in columns[0].get_zones()] == [1.0, 1.0]
    assert columns[0].get_zones()[0].style["padding_bottom"] == "0"
    assert columns[0].get_zones()[1].style["padding_top"] == "0"
    assert columns[0].get_zones()[0].style["margin_bottom"] == "0"
    assert columns[0].get_zones()[1].style["margin_top"] == "0"

    row_el = row._resolve_element()
    assert tuple(int(row_el.get(attr) or 0) for attr in ("x", "y", "w", "h")) == (
        1333,
        5875,
        97334,
        25750,
    )
    assert [
        tuple(int(zone.get(attr) or 0) for attr in ("x", "y", "w", "h"))
        for zone in row_el.xpath("./zone")
    ] == [
        (1333, 5875, 48667, 25750),
        (50000, 5875, 48667, 25750),
    ]


def test_build_report_places_filters_registered_by_workbook_set_filter(tmp_path) -> None:
    source = tmp_path / "filter-dashboard.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="SheetA">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
    <worksheet name="SheetB">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
  </worksheets>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))
    workbook.set_filter(("売上データ", "地域"))
    dashboard = workbook.create_dashboard(name="ダッシュボード")

    dashboard.build_report(
        dashboard_name="ダッシュボード",
        struct={
            "フィルタコンテナ": [("売上データ", "地域")],
            "グラフコンテナ": ["SheetA", "SheetB"],
        },
    )

    controls = dashboard.get_filter_controls()
    assert len(controls) == 1
    assert (controls[0].worksheet, controls[0].field, controls[0].mode) == (
        "SheetA",
        "地域",
        "checkdropdown",
    )
    assert controls[0].apply_scope == "data_source"
    assert controls[0].apply_scope_label == "このデータソースを使用するすべて"
    outer = dashboard.get_containers()[0]
    content = outer.get_containers(name="ダッシュボード")[0]
    filter_container = content.get_containers(name="フィルタコンテナ")[0]
    assert [zone.kind for zone in filter_container.get_zones()] == ["filter"]
    assert [
        [filter_.field for filter_ in worksheet.get_filters()]
        for worksheet in workbook.get_worksheets()
    ] == [[], []]
    assert [
        worksheet._resolve_element().xpath("./table/view/slices/column/text()")
        for worksheet in workbook.get_worksheets()
    ] == [
        ["[ds1].[none:Region:nk]"],
        ["[ds1].[none:Region:nk]"],
    ]


def test_build_report_resolves_all_worksheets_before_editing(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="Dashboard")

    with pytest.raises(ValueError, match="worksheet not found: 不明"):
        dashboard.build_report(
            dashboard_name="経営ダッシュボード",
            struct={"スコアカード": ["SheetA", "不明"]},
        )

    assert dashboard.name == "Dashboard"
    assert dashboard.get_containers() == []


def test_tiled_zone_update_and_delete_preserve_worksheet(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="Dashboard")
    worksheets = workbook.get_worksheets()
    root = dashboard.create_container(direction="horizontal")
    first = root.add_worksheet(worksheets[0], weight=2)
    second = root.add_worksheet(worksheets[1], weight=1)

    assert first.update(order=1, weight=3, show_title=False) is first
    assert (first.order, first.weight, first.show_title) == (1, 3.0, False)
    with pytest.raises(ValueError, match="do not accept x"):
        first.update(x=10)

    second.delete()
    with pytest.raises(DetachedModelError):
        _ = second.name
    assert [item.id for item in dashboard.get_worksheets()] == ["SheetA"]
    assert [item.id for item in workbook.get_worksheets()] == ["SheetA", "SheetB", "SheetC"]
    remaining = workbook.tree.getroot().xpath(
        f"/workbook/dashboards/dashboard/zones/zone/zone[@id='{first.id}']"
    )[0]
    assert tuple(remaining.get(attr) for attr in ("x", "y", "w", "h")) == (
        "0",
        "0",
        "100000",
        "100000",
    )


def test_floating_worksheet_uses_pixels_and_explicit_update_rules(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="Dashboard")
    worksheet = workbook.get_worksheets()[0]

    zone = dashboard.add_floating_worksheet(
        worksheet,
        x=120,
        y=80,
        width=600,
        height=400,
        show_title=True,
    )
    assert (zone.placement_mode, zone.x, zone.y, zone.width, zone.height) == (
        "floating",
        120,
        80,
        600,
        400,
    )
    assert zone.update(x=240, y=160, width=300, height=200, show_title=False) is zone
    assert (zone.x, zone.y, zone.width, zone.height, zone.show_title) == (240, 160, 300, 200, False)
    with pytest.raises(ValueError, match="do not accept order"):
        zone.update(order=0)

    zone_el = workbook.tree.getroot().xpath(
        f"/workbook/dashboards/dashboard/zones/zone[@id='{zone.id}']"
    )[0]
    assert tuple(zone_el.get(attr) for attr in ("x", "y", "w", "h")) == (
        "20000",
        "20000",
        "25000",
        "25000",
    )

    zone.delete()
    assert dashboard.get_zones() == []
    assert workbook.get_worksheets(id="SheetA")[0].name == "SheetA"


def test_automatic_dashboard_rejects_floating_pixel_layout(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="Automatic", sizing_mode="automatic")

    assert (dashboard.width, dashboard.height) == (None, None)
    with pytest.raises(UnsupportedFeatureError, match="fixed-size"):
        dashboard.add_floating_worksheet(workbook.get_worksheets()[0])
    assert dashboard.get_zones() == []


def test_existing_dashboard_edits_only_target_container_subtree(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path, existing_dashboard=True)))
    dashboard = workbook.get_dashboards()[0]
    root = dashboard.get_containers()[0]
    floating_before = ET.tostring(
        workbook.tree.getroot().xpath("/workbook/dashboards/dashboard/zones/zone[@id='3']")[0]
    )
    device_before = ET.tostring(
        workbook.tree.getroot().xpath("/workbook/dashboards/dashboard/devicelayouts")[0]
    )

    added = root.add_worksheet(workbook.get_worksheets(id="SheetC")[0], weight=1)
    dashboard_el = workbook.tree.getroot().xpath("/workbook/dashboards/dashboard")[0]
    assert dashboard_el.xpath("string(./zones/zone[@id='1']/@custom)") == "keep"
    assert dashboard_el.xpath("string(./zones/zone[@id='1']/zone[@id='2']/@custom-child)") == "keep"
    assert ET.tostring(dashboard_el.xpath("./zones/zone[@id='3']")[0]) == floating_before
    assert ET.tostring(dashboard_el.xpath("./devicelayouts")[0]) == device_before
    assert added.placement_mode == "tiled"
    assert [item.id for item in dashboard.get_zones()] == ["2", added.id, "3"]


def test_container_delete_blocks_children_with_structured_references(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="Dashboard")
    root = dashboard.create_container(direction="horizontal")
    zone = root.add_worksheet(workbook.get_worksheets()[0])
    before = ET.tostring(dashboard._resolve_element())

    with pytest.raises(ResourceInUseError) as caught:
        root.delete()
    assert caught.value.resource_type == "DashboardContainer"
    assert caught.value.resource_id == root.id
    assert caught.value.references[0].resource_id == zone.id
    assert "container" in caught.value.references[0].location
    assert ET.tostring(dashboard._resolve_element()) == before

    zone.delete()
    root.delete()
    with pytest.raises(DetachedModelError):
        _ = root.direction
    assert dashboard.get_containers() == []


def test_layout_flow_objects_fixed_sizes_and_styles(tmp_path) -> None:
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="サンプル", width=1000, height=800)
    worksheet = workbook.get_worksheets(id="SheetA")[0]

    root = dashboard.create_container(direction="vertical", friendly_name="contents")
    root.update(style={"background_color": "#f5f5f5", "border_style": "none"})
    header = root.create_container(
        direction="horizontal",
        fixed_size=40,
        friendly_name="header",
    )
    image = header.add_image(
        fixed_size=50,
        style={"margin": 0, "border_style": "none"},
    )
    text = header.add_text(
        "Dashboard",
        bold=True,
        font_size=12,
        style={"margin": 0},
    )
    main = root.create_container(direction="horizontal", friendly_name="main")
    spacer = main.add_spacer(
        fixed_size=6,
        style={"background_color": "#602fff", "margin": 4},
    )
    sheet = main.add_worksheet(
        worksheet,
        show_title=False,
    )
    sheet.update(style={"background_color": "#ffffff", "padding": 8})

    assert dashboard.get_containers(name="contents")[0].id == root.id
    assert (root.name, root.direction, root.style["background_color"]) == (
        "contents", "vertical", "#f5f5f5"
    )
    assert (header.fixed_size, header.name) == (40, "header")
    assert [(zone.kind, zone.fixed_size) for zone in dashboard.get_zones()] == [
        ("image", 50), ("text", None), ("spacer", 6), ("worksheet", None)
    ]
    assert text.text == "Dashboard"
    assert image.style["margin"] == "0"
    assert spacer.style["background_color"] == "#602fff"
    assert sheet.style["padding"] == "8"

    root_el = root._resolve_element()
    assert root_el.get("type-v2") == "layout-flow"
    assert header._resolve_element().get("h") == "5000"
    assert image._resolve_element().get("w") == "5000"
    assert text._resolve_element().get("w") == "95000"
    assert workbook.tree.xpath("string(/workbook/windows/window[@class='dashboard']/@name)") == "サンプル"
    window = workbook.tree.xpath("/workbook/windows/window[@class='dashboard']")[0]
    assert [ET.QName(child).localname for child in window] == [
        "viewpoints", "active", "simple-id"
    ]
    for container in workbook.tree.xpath(
        "/workbook/dashboards/dashboard/zones//zone[zone and zone-style]"
    ):
        names = [ET.QName(child).localname for child in container]
        assert max(index for index, name in enumerate(names) if name == "zone") < names.index(
            "zone-style"
        )
    assert workbook.tree.xpath("/workbook/dashboards/dashboard/simple-id")
    assert not [message for message in workbook.validate() if message.severity == "error"]
