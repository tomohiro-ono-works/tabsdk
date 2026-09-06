"""J-5: ダッシュボードのフィルタに「適用」ボタンを付ける。

Tableau は付けるときだけ `zone[@type-v2='filter']` へ `show-apply="true"` を書き、
付けないときは属性ごと書かない（`workbook/RETAIL - POS` の .twb で実測）。
これまで読み取り専用（`TwbFilterControl.show_apply`）で、書く手段が無かった。
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook


_SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
"""


def _workbook(tmp_path):
    path = tmp_path / "filter.twb"
    path.write_text(_SOURCE, encoding="utf-8")
    return TwbWorkbook.open(str(path))


def _dashboard_with_filter(workbook, **kwargs):
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="Sheet1")
    worksheet.add_field(field=datasource.get_fields(name="売上")[0], shelf="rows")
    placement = worksheet.add_filter(field=datasource.get_fields(name="地域")[0])

    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")
    container.add_worksheet(worksheet, show_title=False)
    zone = container.add_filter(placement, **kwargs)
    return dashboard, zone


def _zone_el(workbook, zone_id):
    return workbook.tree.getroot().xpath(
        ".//*[local-name()='zone'][@id=$zone_id]", zone_id=zone_id
    )[0]


def test_add_filter_omits_the_attribute_by_default(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard, zone = _dashboard_with_filter(workbook)

    assert "show-apply" not in _zone_el(workbook, zone.id).attrib
    assert dashboard.get_filter_controls()[0].show_apply is None


def test_add_filter_writes_the_apply_button(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard, zone = _dashboard_with_filter(workbook, show_apply=True)

    assert _zone_el(workbook, zone.id).get("show-apply") == "true"
    assert dashboard.get_filter_controls()[0].show_apply is True


def test_update_turns_the_apply_button_on_and_off(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard, zone = _dashboard_with_filter(workbook)

    zone.update(show_apply=True)
    assert dashboard.get_filter_controls()[0].show_apply is True

    # 消すときは属性ごと消す。Tableau が既定で書かないため。
    zone.update(show_apply=False)
    assert "show-apply" not in _zone_el(workbook, zone.id).attrib
    assert dashboard.get_filter_controls()[0].show_apply is None


def test_update_rejects_show_apply_on_a_worksheet_zone(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard, _ = _dashboard_with_filter(workbook)

    worksheet_zone = [
        zone for zone in dashboard.get_zones() if zone.kind == "worksheet"
    ][0]
    with pytest.raises(ValueError, match="filter zones"):
        worksheet_zone.update(show_apply=True)


def test_update_rejects_a_non_bool(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    _, zone = _dashboard_with_filter(workbook)

    with pytest.raises(TypeError, match="show_apply must be bool"):
        zone.update(show_apply="true")


def _report_workbook(tmp_path):
    path = tmp_path / "report.twb"
    path.write_text(
        _SOURCE.replace(
            "<worksheets />",
            """<worksheets>
    <worksheet name="SheetA">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
  </worksheets>""",
        ),
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))
    workbook.set_filter(("売上データ", "地域"))
    return workbook


def test_build_report_applies_the_button_to_every_filter(tmp_path) -> None:
    workbook = _report_workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={"フィルタ": [("売上データ", "地域")], "本体": ["SheetA"]},
        filter_apply_button=True,
    )

    controls = dashboard.get_filter_controls()
    assert controls
    assert all(control.show_apply is True for control in controls)


def test_build_report_omits_the_button_by_default(tmp_path) -> None:
    workbook = _report_workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={"フィルタ": [("売上データ", "地域")], "本体": ["SheetA"]},
    )

    controls = dashboard.get_filter_controls()
    assert controls
    assert all(control.show_apply is None for control in controls)


def test_build_report_rejects_a_non_bool(tmp_path) -> None:
    workbook = _report_workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="filter_apply_button must be bool"):
        dashboard.build_report(
            dashboard_name="レポート",
            struct={"本体": ["SheetA"]},
            filter_apply_button="true",
        )
