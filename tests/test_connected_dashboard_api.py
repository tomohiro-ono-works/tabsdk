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
            "フィルタコンテナ": {"height": 50, "items": []},
            "スコアカード": {
                "items": [
                    {"kind": "worksheet", "sheet": "SheetA"},
                    {"kind": "worksheet", "sheet": "SheetB"},
                ]
            },
            "表": {"items": [{"kind": "worksheet", "sheet": "SheetC"}]},
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
    # 高さは kind から決まる。名前の「フィルタ」「スコア」は効かない（K-1、2026-09-07）
    assert [item.fixed_size for item in root.get_containers()] == [50, 300, 300]
    assert outer.get_zones()[0].text == "経営ダッシュボード"
    assert root.get_containers()[0].get_zones() == []
    # 角の丸みは Tableau が接頭辞付きの要素名で書く形式（2026-09-21）。
    # draw_* で描いていないシートなので、内側の余白はグラフ別ではなく既定の 16。
    assert root.get_containers()[1].get_zones()[0].style == {
        "background_color": "#ffffff",
        "border_style": "none",
        "corner_radius": "8",
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
            "スコア・時系列コンテナ": {
                "items": [
                    {"kind": "worksheet", "sheets": ["SheetA", "SheetB"], "fixed_size": 200},
                    {"kind": "worksheet", "sheets": ["SheetC"]},
                ],
            },
        },
        container_sizes={"スコア・時系列コンテナ": 206},
        content_style={"padding": 16, "padding_top": 4},
    )

    outer = dashboard.get_containers()[0]
    content = outer.get_containers(name="経営ダッシュボード")[0]
    row = content.get_containers(name="スコア・時系列コンテナ")[0]
    columns = row.get_containers()
    assert row.fixed_size == 206
    # 幅を指定した列があるので均等割りにしない（2026-09-21。均等割りの段では
    # Tableau がエリアごとの固定幅を見ないため、200 が捨てられていた）
    assert row.distribute_evenly is False
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

    # 中身のコンテナは既定の外側の余白 8 と内側の余白 16（上は 4）の両方の分だけ内へ寄る。
    row_el = row._resolve_element()
    assert tuple(int(row_el.get(attr) or 0) for attr in ("x", "y", "w", "h")) == (
        2000,
        6875,
        96000,
        25750,
    )
    assert [
        tuple(int(zone.get(attr) or 0) for attr in ("x", "y", "w", "h"))
        for zone in row_el.xpath("./zone")
    ] == [
        # 幅 200px は 200/1200 = 16667。残りは幅指定の無い列が取る（2026-09-21）
        (2000, 6875, 16667, 25750),
        (18667, 6875, 79333, 25750),
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
    workbook.add_filter(("売上データ", "地域"), scope="datasource")
    dashboard = workbook.create_dashboard(name="ダッシュボード")

    dashboard.build_report(
        dashboard_name="ダッシュボード",
        struct={
            "フィルタコンテナ": {
                "items": [{"kind": "filter", "field": ("売上データ", "地域")}]
            },
            "グラフコンテナ": {
                "items": [
                    {"kind": "worksheet", "sheet": "SheetA"},
                    {"kind": "worksheet", "sheet": "SheetB"},
                ]
            },
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
            struct={
                "スコアカード": {
                    "items": [
                        {"kind": "worksheet", "sheet": "SheetA"},
                        {"kind": "worksheet", "sheet": "不明"},
                    ]
                }
            },
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


def test_floating_text_is_placed_by_pixels(tmp_path) -> None:
    """テキストを浮動で置く（2026-09-22 追加）。

    Tableau は浮動のオブジェクトを、レイアウトのコンテナの中ではなく `<zones>` の
    直下へ `x` / `y` / `w` / `h` 付きで置く（実ダッシュボードで確認）。
    帳票の項目名のように、シートの外へ文字を重ねたいときに使う。
    """
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    dashboard = workbook.create_dashboard(name="Dashboard")

    zone = dashboard.add_floating_text(
        "売上",
        x=120,
        y=80,
        width=300,
        height=20,
        font_size=10,
        font_color="#333333",
        bold=True,
        align="center",
        style={"background_color": "#f0f0f0"},
    )

    assert (zone.placement_mode, zone.x, zone.y, zone.width, zone.height) == (
        "floating", 120, 80, 300, 20,
    )
    zone_el = workbook.tree.getroot().xpath(
        f"/workbook/dashboards/dashboard/zones/zone[@id='{zone.id}']"
    )[0]
    assert zone_el.get("type-v2") == "text"
    # 1200 x 800 の台紙に対する比率（幅も高さも 100000 とする）
    assert tuple(zone_el.get(attr) for attr in ("x", "y", "w", "h")) == (
        "10000", "10000", "25000", "2500",
    )
    run = zone_el.xpath("./formatted-text/run")[0]
    assert run.text == "売上"
    # 文字揃えは fontalignment（0=左 / 1=中央 / 2=右）
    assert (run.get("fontalignment"), run.get("fontsize"), run.get("bold")) == (
        "1", "10", "true",
    )
    assert zone_el.xpath(
        "./zone-style/format[@attr='background-color']/@value"
    ) == ["#f0f0f0"]

    with pytest.raises(ValueError, match="align must be"):
        dashboard.add_floating_text("x", align="middle")
    assert not [m for m in workbook.validate() if m.severity == "error"]


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


def _worksheet_zones(dashboard):
    def walk(container):
        zones = [zone for zone in container.get_zones() if zone.kind == "worksheet"]
        for child in container.get_containers():
            zones.extend(walk(child))
        return zones

    return walk(dashboard.get_containers()[0])


def _chart_workbook(tmp_path):
    """draw_*() でグラフを描ける最小のワークブック。手で作った SheetA も入れる。"""
    path = tmp_path / "charts.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="SheetA" caption="シートA" />
  </worksheets>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_build_report_uses_chart_specific_padding_and_rounded_corners(tmp_path) -> None:
    """ダッシュボードに置くときの内側の余白は、描いたグラフの種類ごとに変える（2026-09-21）。

    角の丸みは Tableau が接頭辞付きの要素名で書くので、宣言も一緒に足す。
    """
    workbook = _chart_workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    metric, item = "売上", "カテゴリ"
    workbook.draw_card(datasource, name="カード", main_metric=metric)
    workbook.draw_bar(datasource, name="棒", item=item, metric=metric)
    workbook.draw_sheet(datasource, name="帳票", items=[item])
    workbook.draw_crosstab(
        datasource, name="クロス", x_item=item, y_item=item,
        color_metric=metric, label_metric=metric,
    )
    dashboard = workbook.create_dashboard(name="D")

    dashboard.build_report(
        dashboard_name="D",
        struct={
            "段": {
                "items": [
                    {"kind": "worksheet", "sheets": ["カード"]},
                    {"kind": "worksheet", "sheets": ["棒"]},
                    {"kind": "worksheet", "sheets": ["帳票"]},
                    {"kind": "worksheet", "sheets": ["クロス"]},
                    {"kind": "worksheet", "sheets": ["SheetA"]},
                ]
            }
        },
    )

    zones = _worksheet_zones(dashboard)
    padding = {zone.name: zone.style["padding"] for zone in zones}
    # 手で作った SheetA は種類が分からないので既定の 16。
    # クロス集計と散布図は 2026-09-21 に 0 から 16 へ変更
    assert padding == {
        "カード": "0", "棒": "16", "帳票": "8", "クロス": "16", "SheetA": "16",
    }
    assert {zone.style["corner_radius"] for zone in zones} == {"8"}
    assert workbook.tree.xpath(
        "/workbook/document-format-change-manifest"
        "/*[local-name()='_.fcp.DashboardRoundedCorners.true...DashboardRoundedCorners']"
    )
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_report_scales_spacing_when_asked(tmp_path) -> None:
    """余白を「多め」にしたときは 1.5 倍。0 は 0 のまま（2026-09-21）。"""
    workbook = _chart_workbook(tmp_path)
    workbook.draw_card(workbook.get_datasources()[0], name="カード", main_metric="売上")
    dashboard = workbook.create_dashboard(name="D")

    dashboard.build_report(
        dashboard_name="D",
        struct={
            "段": {
                "items": [
                    {"kind": "worksheet", "sheets": ["カード"]},
                    {"kind": "worksheet", "sheets": ["SheetA"]},
                ]
            }
        },
        spacing_scale=1.5,
    )

    styles = {zone.name: zone.style for zone in _worksheet_zones(dashboard)}
    assert (styles["カード"]["margin"], styles["カード"]["padding"]) == ("6", "0")
    assert (styles["SheetA"]["margin"], styles["SheetA"]["padding"]) == ("6", "24")


def test_build_report_rejects_a_bad_spacing_scale(tmp_path) -> None:
    workbook = _chart_workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="D")
    struct = {"段": {"items": [{"kind": "worksheet", "sheets": ["SheetA"]}]}}

    with pytest.raises(ValueError, match="spacing_scale must be positive"):
        dashboard.build_report(dashboard_name="D", struct=struct, spacing_scale=0)
    with pytest.raises(TypeError, match="spacing_scale must be a number"):
        dashboard.build_report(dashboard_name="D", struct=struct, spacing_scale="wide")
    assert dashboard.get_containers() == []


def test_build_report_fits_the_sheet_chart_to_width(tmp_path) -> None:
    """帳票と横棒は「幅を合わせる」、縦棒は「高さを合わせる」で置く。

    帳票は列が右へ伸びるため、ビュー全体だと横スクロールになる。
    棒グラフは向きで表示倍率を分ける（2026-09-22）: item がロー（既定、横棒）なら
    幅を合わせる、item がカラム（縦棒）なら高さを合わせる。
    表示倍率はダッシュボードの window の viewpoint に書く。
    """
    workbook = _chart_workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    workbook.draw_sheet(datasource, name="帳票", items=["カテゴリ"])
    workbook.draw_bar(datasource, name="横棒", item="カテゴリ", metric="売上")
    workbook.draw_bar(
        datasource, name="縦棒", item="カテゴリ", metric="売上", item_shelf="columns"
    )
    dashboard = workbook.create_dashboard(name="D")

    dashboard.build_report(
        dashboard_name="D",
        struct={
            "段": {
                "items": [
                    {"kind": "worksheet", "sheet": "帳票"},
                    {"kind": "worksheet", "sheet": "横棒"},
                    {"kind": "worksheet", "sheet": "縦棒"},
                ]
            }
        },
    )

    assert [
        (viewpoint.get("name"), viewpoint[0].get("type"))
        for viewpoint in workbook.tree.xpath(
            "/workbook/windows/window[@class='dashboard']/viewpoints/viewpoint"
        )
    ] == [("帳票", "fit-width"), ("横棒", "fit-width"), ("縦棒", "fit-height")]


def test_floating_parameter_control_is_placed_by_pixels(tmp_path) -> None:
    """パラメータコントロールを浮動で置く（2026-09-24 追加）。

    RETAIL の実ダッシュボードの `type-v2="paramctrl"` に合わせ、
    `param="[Parameters].[…]"`・`mode="compact"` の zone を `<zones>` 直下へ置く。
    """
    workbook = TwbWorkbook.open(str(_write_workbook(tmp_path)))
    workbook.create_parameter(name="閾値", value=0.0, datatype="real")
    dashboard = workbook.create_dashboard(name="Dashboard")

    zone = dashboard.add_floating_parameter_control(
        "閾値", x=120, y=80, width=300, height=40
    )

    assert (zone.kind, zone.placement_mode, zone.x, zone.y, zone.width, zone.height) == (
        "parameter_control", "floating", 120, 80, 300, 40,
    )
    zone_el = workbook.tree.getroot().xpath(
        f"/workbook/dashboards/dashboard/zones/zone[@id='{zone.id}']"
    )[0]
    assert (zone_el.get("type-v2"), zone_el.get("param"), zone_el.get("mode")) == (
        "paramctrl", "[Parameters].[閾値]", "compact",
    )
    with pytest.raises(ValueError, match="parameter not found"):
        dashboard.add_floating_parameter_control("存在しない")
    assert not [m for m in workbook.validate() if m.severity == "error"]


def test_build_report_places_quadrant_parameters_at_the_top_right(tmp_path) -> None:
    """四象限のシートには、パラメータコントロールが右上へ浮動で横に並ぶ（2026-09-24）。
    左が中央比率、右が売上閾値。
    """
    workbook = _chart_workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    workbook.draw_quadrant(
        datasource, name="象限", item="カテゴリ", x_metric="売上",
        y_metric="売上", size_metric="売上",
    )
    dashboard = workbook.create_dashboard(name="D")

    dashboard.build_report(
        dashboard_name="D",
        struct={"段": {"items": [{"kind": "worksheet", "sheets": ["象限"]}]}},
    )

    sheet = next(zone for zone in dashboard.get_zones() if zone.worksheet_id == "象限")
    controls = {
        zone.get("param"): zone
        for zone in workbook.tree.xpath(
            "/workbook/dashboards/dashboard/zones/zone[@type-v2='paramctrl']"
        )
    }
    assert set(controls) == {"[Parameters].[象限_中央比率]", "[Parameters].[象限_売上閾値]"}
    center = controls["[Parameters].[象限_中央比率]"]
    threshold = controls["[Parameters].[象限_売上閾値]"]
    # 台紙の幅・高さに対する比率。中央比率が左、売上閾値が右で、y は同じ
    assert int(center.get("x")) < int(threshold.get("x"))
    assert center.get("y") == threshold.get("y")
    canvas_width = dashboard.width
    right_edge = (int(threshold.get("x")) + int(threshold.get("w"))) * canvas_width / 100000
    assert right_edge <= sheet.x + sheet.width
    assert sheet.x + sheet.width - right_edge < 10
    assert not [m for m in workbook.validate() if m.severity == "error"]
