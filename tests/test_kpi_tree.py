import pytest

from twbpatch import KpiNode, TwbWorkbook


DATASOURCE_ID = "federated.00vlmup0b8v7m212i5x9f03fouo2"
DATASOURCE_NAME = "Orders++ (sample_-_superstore)"
EDGE_DATASOURCE_NAME = "KPIツリーのエッジ"
#: ダッシュボードタブと同じ台紙の外側の余白。ダッシュボードは上下左右にこの分だけ大きい。
FRAME = 8


def _superstore_workbook(tmp_path, filename="superstore.twb"):
    path = tmp_path / filename
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="{DATASOURCE_ID}" caption="{DATASOURCE_NAME}">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _card(workbook, name):
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    return workbook.draw_card(datasource, name=name, main_metric="売上")


def _sample_tree(workbook):
    """深さ 3・末端 3 のツリー。ツリーは 600 × 450、ダッシュボードは台紙の余白込みで 616 × 466。"""
    return KpiNode(_card(workbook, "売上"), [
        KpiNode(_card(workbook, "客数"), [
            KpiNode(_card(workbook, "新規客数")),
            KpiNode(_card(workbook, "リピート客数")),
        ]),
        KpiNode(_card(workbook, "客単価")),
    ])


def _all_zones(container):
    zones = list(container.get_zones())
    for child in container.get_containers():
        zones.extend(_all_zones(child))
    return zones


def _card_rects(dashboard):
    """台紙の余白（外側 8）を除いた、ツリー内の位置。"""
    return {
        zone.name: (zone.x - FRAME, zone.y - FRAME, zone.width, zone.height)
        for zone in _all_zones(dashboard.get_containers()[0])
        if zone.kind == "worksheet"
    }


def _axis_space(workbook, sheet_name):
    return [
        dict(item.attrib)
        for item in workbook.tree.xpath(
            "/workbook/worksheets/worksheet[@name=$name]/table/style"
            "/style-rule[@element='axis']/encoding[@attr='space']",
            name=sheet_name,
        )
    ]


def _no_errors(workbook):
    return not [message for message in workbook.validate() if message.severity == "error"]


def test_build_kpi_tree_sizes_dashboard_from_tree_shape(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)

    dashboard = workbook.build_kpi_tree(dashboard_name="KPIツリー", root=_sample_tree(workbook))

    assert dashboard.sizing_mode == "fixed"
    assert (dashboard.width, dashboard.height) == (600 + 2 * FRAME, 450 + 2 * FRAME)


def test_build_kpi_tree_places_single_node(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)

    dashboard = workbook.build_kpi_tree(
        dashboard_name="KPIツリー",
        root=KpiNode(_card(workbook, "売上")),
    )

    assert (dashboard.width, dashboard.height) == (200 + 2 * FRAME, 150 + 2 * FRAME)
    assert _card_rects(dashboard) == {"売上": (0, 0, 200, 150)}
    assert [zone.kind for zone in _all_zones(dashboard.get_containers()[0])] == ["worksheet"]
    assert _no_errors(workbook)


def test_build_kpi_tree_centers_parent_cards(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)

    dashboard = workbook.build_kpi_tree(dashboard_name="KPIツリー", root=_sample_tree(workbook))

    assert _card_rects(dashboard) == {
        "売上": (0, 150, 200, 150),
        "客数": (200, 75, 200, 150),
        "新規客数": (400, 0, 200, 150),
        "リピート客数": (400, 150, 200, 150),
        "客単価": (200, 300, 200, 150),
    }
    assert _no_errors(workbook)


def test_build_kpi_tree_aligns_parent_cards_to_top(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)

    dashboard = workbook.build_kpi_tree(
        dashboard_name="KPIツリー",
        root=_sample_tree(workbook),
        align="top",
    )

    assert _card_rects(dashboard) == {
        "売上": (0, 0, 200, 150),
        "客数": (200, 0, 200, 150),
        "新規客数": (400, 0, 200, 150),
        "リピート客数": (400, 150, 200, 150),
        "客単価": (200, 300, 200, 150),
    }
    assert _no_errors(workbook)


def test_build_kpi_tree_keeps_card_size_with_fixed_sizes_and_spacers(tmp_path) -> None:
    """コンテナの最後の子は残りいっぱいに伸びるため、空白で大きさを保っていること。"""
    workbook = _superstore_workbook(tmp_path)

    dashboard = workbook.build_kpi_tree(dashboard_name="KPIツリー", root=_sample_tree(workbook))

    zones = _all_zones(dashboard.get_containers()[0])
    assert {zone.fixed_size for zone in zones if zone.kind == "worksheet"} == {150}
    # 浅い枝の末端（客単価）の右側は空白で埋める
    spacers = {(zone.x - FRAME, zone.y - FRAME, zone.width, zone.height) for zone in zones if zone.kind == "spacer"}
    assert (400, 300, 200, 150) in spacers


def test_build_kpi_tree_styles_cards_like_dashboard_tab(tmp_path) -> None:
    """ダッシュボードタブ（build_report()）の KPI カードと同じ見た目: 灰色の台紙に白いカード、タイトルなし。"""
    workbook = _superstore_workbook(tmp_path)
    _card(workbook, "売上")
    tab = workbook.create_dashboard(name="タブ")
    tab.build_report(
        dashboard_name="タブ",
        struct={"段": {"items": [{"kind": "worksheet", "sheets": ["売上"]}]}},
    )
    tab_content = tab.get_containers()[0].get_containers(name="タブ")[0]
    [tab_card] = [zone for zone in _all_zones(tab_content) if zone.kind == "worksheet"]

    dashboard = workbook.build_kpi_tree(
        dashboard_name="KPIツリー",
        root=KpiNode(_card(workbook, "利益"), [KpiNode(_card(workbook, "客数"))]),
        align="top",
        edge_hyper="edge.hyper",
    )

    tree = dashboard.get_containers()[0]
    assert tree.style == tab_content.style
    cards = [zone for zone in _all_zones(tree) if zone.kind == "worksheet" and not zone.name.startswith("エッジ|")]
    assert [zone.style for zone in cards] == [tab_card.style, tab_card.style]
    assert [zone.show_title for zone in cards] == [tab_card.show_title, tab_card.show_title] == [False, False]
    # エッジのシートはワークシートとペインの背景を台紙と同じ色で塗る
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='エッジ|利益']/table/style"
        "/style-rule[@element='pane' or @element='table']/format[@attr='background-color']/@value"
    ) == [tab_content.style["background_color"]] * 2
    assert _no_errors(workbook)


def test_build_kpi_tree_rejects_invalid_input_without_changes(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    other = _superstore_workbook(tmp_path, "other.twb")
    card = _card(workbook, "売上")

    with pytest.raises(ValueError, match="more than once"):
        workbook.build_kpi_tree(
            dashboard_name="KPIツリー",
            root=KpiNode(card, [KpiNode(card)]),
        )
    with pytest.raises(ValueError, match="belong to the workbook"):
        workbook.build_kpi_tree(
            dashboard_name="KPIツリー",
            root=KpiNode(card, [KpiNode(_card(other, "別"))]),
        )
    with pytest.raises(ValueError, match="align"):
        workbook.build_kpi_tree(
            dashboard_name="KPIツリー",
            root=KpiNode(card),
            align="middle",
        )
    with pytest.raises(TypeError, match="KpiNode"):
        workbook.build_kpi_tree(dashboard_name="KPIツリー", root=card)

    assert workbook.get_dashboards(name="KPIツリー") == []


def test_build_kpi_tree_places_edge_sheets_between_parent_and_children(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)

    dashboard = workbook.build_kpi_tree(
        dashboard_name="KPIツリー",
        root=_sample_tree(workbook),
        align="top",
        edge_hyper="edge.hyper",
    )

    assert (dashboard.width, dashboard.height) == (720 + 2 * FRAME, 450 + 2 * FRAME)
    assert _card_rects(dashboard) == {
        "売上": (0, 0, 200, 150),
        "エッジ|売上": (200, 0, 60, 450),
        "客数": (260, 0, 200, 150),
        "エッジ|客数": (460, 0, 60, 300),
        "新規客数": (520, 0, 200, 150),
        "リピート客数": (520, 150, 200, 150),
        "客単価": (260, 300, 200, 150),
    }
    zones = _all_zones(dashboard.get_containers()[0])
    assert {zone.show_title for zone in zones if zone.name.startswith("エッジ|")} == {False}
    assert _no_errors(workbook)


def test_build_kpi_tree_creates_edge_datasource_from_hyper(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)

    workbook.build_kpi_tree(
        dashboard_name="KPIツリー",
        root=_sample_tree(workbook),
        align="top",
        edge_hyper="../examples/edge.hyper",
    )

    edges = workbook.get_datasources(name=EDGE_DATASOURCE_NAME)
    assert len(edges) == 1
    assert workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$name]/extract/connection/@dbname",
        name=edges[0].id,
    ) == ["../examples/edge.hyper"]


def test_build_kpi_tree_reuses_edge_datasource(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    first = KpiNode(_card(workbook, "売上"), [KpiNode(_card(workbook, "利益"))])
    second = KpiNode(_card(workbook, "売上2"), [KpiNode(_card(workbook, "利益2"))])

    workbook.build_kpi_tree(dashboard_name="ツリー1", root=first, align="top", edge_hyper="edge.hyper")
    workbook.build_kpi_tree(dashboard_name="ツリー2", root=second, align="top", edge_hyper="edge.hyper")

    assert len(workbook.get_datasources(name=EDGE_DATASOURCE_NAME)) == 1
    assert workbook.get_worksheets(name="エッジ|売上2")
    assert _no_errors(workbook)


def test_build_kpi_tree_edge_sheet_matches_hand_made_tableau_sheet(tmp_path) -> None:
    """Tableau で手作りしたエッジ用シート（2026-09-13 実測）と同じ設定になっていること。"""
    workbook = _superstore_workbook(tmp_path)
    workbook.build_kpi_tree(
        dashboard_name="KPIツリー",
        root=_sample_tree(workbook),
        align="top",
        edge_hyper="edge.hyper",
    )

    sheet = workbook.get_worksheets(name="エッジ|売上")[0]
    assert sheet.visible is False
    assert sheet.lines_visible is False
    assert {(field.shelf, field.name) for field in sheet.get_fields() if field.shelf in {"rows", "columns"}} == {
        ("rows", "y"),
        ("columns", "x"),
    }
    pane = sheet.get_panes()[0]
    assert pane.mark_type == "line"
    assert pane.line_interpolation == "step"
    assert [field.name for field in pane.get_fields()] == ["edge", "point"]
    # 客数（末端 2）が縦位置 0、客単価が 4
    assert sheet.get_filters()[0].values == ["E-0", "E-4"]
    assert workbook.get_worksheets(name="エッジ|客数")[0].get_filters()[0].values == ["E-0", "E-2"]
    # y は親の中心が 0、シートの高さは末端 3 つぶん（75px 単位で -1〜5）
    y_space, x_space = sorted(_axis_space(workbook, "エッジ|売上"), key=lambda item: item["scope"], reverse=True)
    assert (y_space["min"], y_space["max"], y_space["reverse"]) == ("-1", "5", "true")
    assert (x_space["min"], x_space["max"]) == ("0", "2")
    assert "reverse" not in x_space


def _snapshot(workbook):
    return (
        [datasource.id for datasource in workbook.get_datasources()],
        [sheet.name for sheet in workbook.get_worksheets()],
        [dashboard.name for dashboard in workbook.get_dashboards()],
    )


def test_build_kpi_tree_rejects_invalid_edges_without_changes(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    root = _sample_tree(workbook)
    wide = KpiNode(_card(workbook, "全体"), [KpiNode(_card(workbook, f"葉{index}")) for index in range(8)])
    workbook.create_dashboard(name="既存")
    before = _snapshot(workbook)

    with pytest.raises(ValueError, match="align='top'"):
        workbook.build_kpi_tree(dashboard_name="KPIツリー", root=root, edge_hyper="edge.hyper")
    with pytest.raises(ValueError, match=r"\.hyper"):
        workbook.build_kpi_tree(dashboard_name="KPIツリー", root=root, align="top", edge_hyper="edge.csv")
    with pytest.raises(ValueError, match="too many leaves"):
        workbook.build_kpi_tree(dashboard_name="KPIツリー", root=wide, align="top", edge_hyper="edge.hyper")
    # ダッシュボード名の重複は、エッジ用データソースを作る前に止める
    with pytest.raises(ValueError, match="dashboard already exists"):
        workbook.build_kpi_tree(dashboard_name="既存", root=root, align="top", edge_hyper="edge.hyper")
    assert _snapshot(workbook) == before

    workbook.create_worksheet(name="エッジ|売上")
    before = _snapshot(workbook)
    with pytest.raises(ValueError, match="worksheet already exists"):
        workbook.build_kpi_tree(dashboard_name="KPIツリー", root=root, align="top", edge_hyper="edge.hyper")
    assert _snapshot(workbook) == before


def test_build_kpi_tree_rejects_edge_datasource_with_other_hyper(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    first = KpiNode(_card(workbook, "売上"), [KpiNode(_card(workbook, "利益"))])
    workbook.build_kpi_tree(dashboard_name="ツリー1", root=first, align="top", edge_hyper="edge.hyper")
    second = KpiNode(_card(workbook, "売上2"), [KpiNode(_card(workbook, "利益2"))])
    before = _snapshot(workbook)

    with pytest.raises(ValueError, match="different .hyper path"):
        workbook.build_kpi_tree(dashboard_name="ツリー2", root=second, align="top", edge_hyper="other.hyper")

    assert _snapshot(workbook) == before
