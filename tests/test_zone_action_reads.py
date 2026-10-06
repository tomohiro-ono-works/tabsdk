"""L-6: 旧 `list_dashboard_*()` にしかなかった読み取りを接続型モデルへ移す。

E-2 で旧 API を消したとき、この 2 つは「新 API に同じ情報を取る手段が無い」ために
残した（`docs/developer/backlog.md` L-6）。ここで埋めた分を固定する。

- ゾーン: raw 座標、入れ子の親子、キャンバス情報、任意サイズでの px 換算
- アクション: **除外リスト**。Tableau は対象シートを「除外するシート」で書く
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook


SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="元シート">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
    <worksheet name="先シート">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
    <worksheet name="無関係シート">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
  </worksheets>
</workbook>
"""


def _workbook(tmp_path):
    path = tmp_path / "zones.twb"
    path.write_text(SOURCE, encoding="utf-8")
    workbook = TwbWorkbook.open(str(path))
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=1000, height=800)
    container = dashboard.create_container(direction="vertical")
    for worksheet in workbook.get_worksheets():
        container.add_worksheet(worksheet, show_title=False)
    return workbook, dashboard, container


# --- ゾーン -------------------------------------------------------------------


def test_raw_coordinates_are_the_values_tableau_writes(tmp_path) -> None:
    _, dashboard, container = _workbook(tmp_path)
    zone = dashboard.get_zones()[0]

    element = zone._resolve_element()
    assert zone.x_raw == int(element.get("x"))
    assert zone.y_raw == int(element.get("y"))
    assert zone.width_raw == int(element.get("w"))
    assert zone.height_raw == int(element.get("h"))
    # raw はダッシュボードの幅を 100000 とした比率
    assert 0 <= zone.x_raw <= 100000


def test_pixel_values_follow_the_dashboard_size(tmp_path) -> None:
    _, dashboard, _ = _workbook(tmp_path)
    zone = dashboard.get_zones()[0]

    assert zone.dashboard_width_px == 1000
    assert zone.dashboard_height_px == 800
    assert zone.sizing_mode == "fixed"
    assert zone.x == round(zone.x_raw * 1000 / 100000)
    assert zone.height == round(zone.height_raw * 800 / 100000)


def test_to_px_converts_with_any_canvas(tmp_path) -> None:
    _, dashboard, _ = _workbook(tmp_path)
    zone = dashboard.get_zones()[0]

    x, y, width, height = zone.to_px(width=1200, height=900)

    assert x == round(zone.x_raw * 1200 / 100000)
    assert height == round(zone.height_raw * 900 / 100000)
    # 既定の px はダッシュボードのサイズ基準なので別の値になる
    assert (x, y, width, height) != (zone.x, zone.y, zone.width, zone.height)


def test_to_px_rejects_a_non_positive_canvas(tmp_path) -> None:
    _, dashboard, _ = _workbook(tmp_path)
    zone = dashboard.get_zones()[0]

    with pytest.raises(ValueError, match="width must be positive"):
        zone.to_px(width=0, height=900)


def test_the_nesting_is_readable(tmp_path) -> None:
    _, dashboard, container = _workbook(tmp_path)
    zone = dashboard.get_zones()[0]

    # コンテナは get_zones() に出てこないが、親としては参照できる
    assert zone.parent_id == container.id
    assert zone.depth == 1
    assert [z.parent_id for z in dashboard.get_zones()] == [container.id] * 3


def test_the_zone_knows_its_dashboard_and_raw_attributes(tmp_path) -> None:
    _, dashboard, container = _workbook(tmp_path)
    zone = dashboard.get_zones()[0]

    assert zone.dashboard_id == dashboard.id
    assert zone.attrs["id"] == zone.id
    assert zone.attrs["name"] == zone.worksheet_id


def test_filter_card_attributes_are_none_on_a_plain_zone(tmp_path) -> None:
    _, dashboard, _ = _workbook(tmp_path)
    zone = dashboard.get_zones()[0]

    assert zone.mode is None
    assert zone.show_apply is None
    assert zone.show_caption is None
    assert zone.is_fixed is None
    assert zone.url is None


# --- アクション ---------------------------------------------------------------


def _action(workbook, dashboard):
    return dashboard.create_action(
        kind="filter",
        name="地域で絞る",
        source="元シート",
        targets=["先シート"],
        field=("売上データ", "地域"),
    )


def test_the_excluded_sheets_are_readable(tmp_path) -> None:
    workbook, dashboard, _ = _workbook(tmp_path)
    action = _action(workbook, dashboard)

    # ソースは `<source worksheet="...">` に名指しで書かれるので除外は空
    assert action.source_worksheet_ids == ["元シート"]
    assert action.excluded_source_worksheet_ids == []

    # 対象は逆に「除外するシート」で書かれる（`<param name="exclude">`）。
    # `create_action()` はソースも対象に残すので、除外されるのは無関係シートだけ
    assert action.target_worksheet_ids == ["元シート", "先シート"]
    assert action.excluded_target_worksheet_ids == ["無関係シート"]


def test_the_action_knows_its_dashboards(tmp_path) -> None:
    workbook, dashboard, _ = _workbook(tmp_path)
    action = _action(workbook, dashboard)

    assert action.dashboard_id == dashboard.id
    assert action.source_dashboard_id == dashboard.id
    assert action.target_dashboard_id == dashboard.id
    assert action.source_type == "sheet"
    # 対象は `<target>` 要素ではなく command の param に入るので type は無い
    assert action.target_type is None


def test_the_raw_action_element_is_readable(tmp_path) -> None:
    workbook, dashboard, _ = _workbook(tmp_path)
    action = _action(workbook, dashboard)

    assert action.attrs["name"] == action.id
    assert action.details["tag"] == "action"
    assert isinstance(action.details.get("children"), list)


# --- ワークシート上の配置 -----------------------------------------------------


def test_a_placement_knows_its_worksheet_role_and_attributes(tmp_path) -> None:
    workbook, _, _ = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    # 既存シートは <panes> を持たないので、Pane が要る分は作ったシートで見る
    worksheet = workbook.create_worksheet(name="新シート")

    placement = worksheet.add_field(
        field=datasource.get_fields(name="地域")[0], shelf="rows"
    )

    assert placement.worksheet_id == "新シート"
    assert placement.role == "dimension"
    # シェルフは `<rows>` のテキストに参照を書くので属性を持たない
    assert placement.attrs == {}

    pane = worksheet.get_panes()[0]
    colored = pane.add_field(
        field=datasource.get_fields(name="地域")[0], encoding="color"
    )
    # エンコーディングは `<color column="...">` の形。種別はタグ名、属性は column
    assert colored.attrs == {"column": colored._resolve_placement().reference}
    assert colored.encoding == "color"
    assert colored.role == "dimension"
