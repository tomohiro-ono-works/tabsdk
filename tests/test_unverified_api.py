"""B-1: 一度も呼ばれていなかった公開メソッドの動作確認。

「テストを書く」ではなく「動作を確認して、必要なら修正する」ためのテスト。
根拠: docs/developer/backlog.md B-1
"""

from __future__ import annotations

from lxml import etree as ET
import pytest

from twbpatch import TwbDashboardZone, TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "unverified.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _worksheet(workbook, name="Sheet1"):
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name=name)
    worksheet.add_field(field=datasource.get_fields(name="売上")[0], shelf="rows")
    return worksheet


def _view_children(worksheet):
    view = worksheet._resolve_element().xpath(".//*[local-name()='view']")[0]
    return [ET.QName(child).localname for child in view]


def _slice_columns(worksheet):
    return worksheet._resolve_element().xpath(
        ".//*[local-name()='slices']/*[local-name()='column']/text()"
    )


# --- TwbWorksheet.add_filter_slice ------------------------------------------


def test_add_filter_slice_registers_the_field_without_a_filter(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet = _worksheet(workbook)
    region = workbook.get_datasources()[0].get_fields(name="地域")[0]

    assert worksheet.add_filter_slice(field=region) is worksheet

    assert _slice_columns(worksheet) == ["[ds1].[none:Region:nk]"]
    # slice はフィルタそのものではないので、フィルタとしては現れない
    assert worksheet.get_filters() == []
    assert "filter" not in _view_children(worksheet)
    assert not [item for item in workbook.validate() if item.severity == "error"]


def test_add_filter_slice_replaces_an_existing_filter(tmp_path) -> None:
    """add_filter() 済みのフィールドに対しては、filter 要素を slice へ置き換える。"""
    workbook = _workbook(tmp_path)
    worksheet = _worksheet(workbook)
    region = workbook.get_datasources()[0].get_fields(name="地域")[0]
    worksheet.add_filter(field=region)
    assert [item.id for item in worksheet.get_filters()] == ["[ds1].[none:Region:nk]"]

    worksheet.add_filter_slice(field=region)

    assert worksheet.get_filters() == []
    assert _slice_columns(worksheet) == ["[ds1].[none:Region:nk]"]


def test_add_filter_slice_is_idempotent(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet = _worksheet(workbook)
    region = workbook.get_datasources()[0].get_fields(name="地域")[0]

    worksheet.add_filter_slice(field=region)
    worksheet.add_filter_slice(field=region)

    assert _slice_columns(worksheet) == ["[ds1].[none:Region:nk]"]


def test_add_filter_slice_rejects_a_field_from_another_workbook(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet = _worksheet(workbook)
    other_path = tmp_path / "other"
    other_path.mkdir()
    other = _workbook(other_path)
    other_region = other.get_datasources()[0].get_fields(name="地域")[0]

    with pytest.raises(ValueError):
        worksheet.add_filter_slice(field=other_region)


# --- TwbDashboardContainer.add_dashboard_object（削除済み）-------------------


def test_add_dashboard_object_is_gone(tmp_path) -> None:
    """add_spacer() と処理が同一で、これでしかできないことが無かったため削除した。

    空の枠は add_spacer()（`type-v2="empty"`）で置く。そちらは Tableau 実物との
    一致を確認済み。中身を持つダッシュボードオブジェクトが必要になったら、
    種類ごとに引数を設計して作り直す（I-3）。
    """
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")

    assert not hasattr(container, "add_dashboard_object")


def test_add_spacer_covers_the_empty_zone_case(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    _worksheet(workbook)
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")

    zone = container.add_spacer(
        fixed_size=60,
        friendly_name="ナビ",
        style={"background_color": "#333333"},
    )

    assert type(zone) is TwbDashboardZone
    assert zone.kind == "spacer"
    assert zone.friendly_name == "ナビ"
    assert zone.fixed_size == 60
    assert zone.style == {"background_color": "#333333"}

    element = dashboard._resolve_element().xpath(
        ".//*[local-name()='zone'][@id=$zone_id]", zone_id=zone.id
    )[0]
    assert element.get("type-v2") == "empty"
    assert element.get("is-fixed") == "true"
    assert [ET.QName(child).localname for child in element] == ["zone-style"]
    assert not [item for item in workbook.validate() if item.severity == "error"]


def test_add_spacer_places_zones_in_order(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    _worksheet(workbook)
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")

    first = container.add_spacer(friendly_name="1")
    second = container.add_spacer(friendly_name="2")
    inserted = container.add_spacer(friendly_name="0", order=0)

    assert [zone.friendly_name for zone in container.get_zones()] == ["0", "1", "2"]
    assert [zone.id for zone in container.get_zones()] == [inserted.id, first.id, second.id]


def test_spacer_zone_can_be_updated_and_deleted(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    _worksheet(workbook)
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")
    zone = container.add_spacer(friendly_name="ナビ")

    zone.update(friendly_name="ヘッダー", style={"border_style": "none"})
    assert zone.friendly_name == "ヘッダー"
    assert zone.style == {"border_style": "none"}

    zone.delete()
    assert container.get_zones() == []


# --- worksheet.update(name=...) の参照更新 ----------------------------------


def test_worksheet_rename_updates_every_reference(tmp_path) -> None:
    """§3.5: Worksheet の name 変更は内部 ID の変更なので、参照側も同時に直す。"""
    path = tmp_path / "rename.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="S1">
      <table>
        <view />
        <panes><pane id="1"><mark class="Automatic" /><encodings /></pane></panes>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name="D1">
      <zones><zone id="1" type-v2="layout-flow" param="vert">
        <zone id="2" name="S1" />
      </zone></zones>
    </dashboard>
  </dashboards>
  <windows>
    <window class="worksheet" name="S1" hidden="false" />
    <window class="dashboard" name="D1">
      <viewpoints><viewpoint name="S1" /></viewpoints>
    </window>
  </windows>
  <actions>
    <action name="A1"><source worksheet="S1" /><target worksheet="S1" /></action>
  </actions>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))
    workbook.get_worksheets()[0].update(name="RENAMED")
    root = workbook.tree.getroot()

    assert root.xpath("/workbook/worksheets/worksheet/@name") == ["RENAMED"]
    assert root.xpath("/workbook/windows/window[@class='worksheet']/@name") == ["RENAMED"]
    assert root.xpath("//*[local-name()='zone'][@name]/@name") == ["RENAMED"]
    assert root.xpath("//*[local-name()='viewpoint']/@name") == ["RENAMED"]
    assert root.xpath("/workbook/actions/action/source/@worksheet") == ["RENAMED"]
    assert root.xpath("/workbook/actions/action/target/@worksheet") == ["RENAMED"]
    # 旧 ID がどこにも残っていない
    assert root.xpath("//*[@name='S1']") == []
