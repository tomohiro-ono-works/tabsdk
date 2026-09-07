"""B-3 #20 / #21: 既存ダッシュボードの編集が対象コンテナの中だけに収まること。

仕様 §6.13。`copy.deepcopy` + `_replace_if_changed()` による部分置換なので、
**変更が対象コンテナ配下に限られる保証**と、**SDK が解釈しない属性・浮動ゾーン・
デバイスレイアウトが保たれる保証**が要る。既存テストは個々の要素を名指しで
確認していたが、それだと「見ていない場所が変わっていない」ことは言えない。

ここでは木全体で判定する。編集後の `<dashboard>` の対象ゾーンだけを編集前のものへ
差し戻し、それで編集前と完全一致するなら、**変更は対象ゾーンの中だけ**だったことになる。
"""

from __future__ import annotations

import copy

import pytest
from lxml import etree as ET

from twbpatch import TwbWorkbook


SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
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
    <worksheet name="SheetC">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name="Existing" caption="既存ダッシュボード" sdk-unknown="keep">
      <size sizing-mode="fixed" minwidth="1200" maxwidth="1200"
            minheight="800" maxheight="800" />
      <zones>
        <zone id="1" type-v2="layout-basic" param="horz" x="0" y="0"
              w="100000" h="100000" custom="keep">
          <zone id="2" name="SheetA" x="0" y="0" w="100000" h="100000"
                show-title="true" custom-child="keep" />
        </zone>
        <zone id="3" name="SheetB" x="10000" y="10000" w="25000" h="25000"
              floating-custom="keep" />
      </zones>
      <devicelayouts>
        <devicelayout name="phone">
          <zones>
            <zone id="phone-1" name="SheetA" x="0" y="0" w="100000" h="50000" />
          </zones>
        </devicelayout>
      </devicelayouts>
    </dashboard>
  </dashboards>
</workbook>
"""


def _workbook(tmp_path):
    path = tmp_path / "locality.twb"
    path.write_text(SOURCE, encoding="utf-8")
    return TwbWorkbook.open(str(path))


def _dashboard_el(workbook):
    return workbook.tree.getroot().xpath("/workbook/dashboards/dashboard")[0]


def _assert_only_zone_changed(workbook, before_el, zone_id: str) -> None:
    """対象ゾーンだけを編集前へ差し戻して、木全体が一致するかを見る。"""
    after_el = copy.deepcopy(_dashboard_el(workbook))
    # そもそも編集が起きていないと、この判定は素通りしてしまう
    assert ET.tostring(after_el) != ET.tostring(before_el), "編集が起きていない"
    target = after_el.xpath("./zones//zone[@id=$id]", id=zone_id)[0]
    original = copy.deepcopy(before_el.xpath("./zones//zone[@id=$id]", id=zone_id)[0])
    target.getparent().replace(target, original)
    assert ET.tostring(after_el) == ET.tostring(before_el)


def test_adding_a_worksheet_changes_only_the_target_container(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    before = copy.deepcopy(_dashboard_el(workbook))
    container = workbook.get_dashboards()[0].get_containers()[0]

    container.add_worksheet(workbook.get_worksheets(id="SheetC")[0], weight=1)

    _assert_only_zone_changed(workbook, before, "1")


def test_zone_update_changes_only_that_zone(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    before = copy.deepcopy(_dashboard_el(workbook))
    zone = workbook.get_dashboards()[0].get_zones(id="2")[0]

    zone.update(show_title=False)

    _assert_only_zone_changed(workbook, before, "2")


def test_the_floating_zone_is_untouched(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    floating_before = ET.tostring(
        _dashboard_el(workbook).xpath("./zones/zone[@id='3']")[0]
    )
    container = workbook.get_dashboards()[0].get_containers()[0]

    container.add_worksheet(workbook.get_worksheets(id="SheetC")[0], weight=1)

    after = _dashboard_el(workbook).xpath("./zones/zone[@id='3']")[0]
    assert ET.tostring(after) == floating_before


def test_the_device_layout_is_untouched(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    device_before = ET.tostring(_dashboard_el(workbook).xpath("./devicelayouts")[0])
    container = workbook.get_dashboards()[0].get_containers()[0]

    container.add_worksheet(workbook.get_worksheets(id="SheetC")[0], weight=1)

    after = _dashboard_el(workbook).xpath("./devicelayouts")[0]
    assert ET.tostring(after) == device_before


def test_attributes_the_sdk_does_not_interpret_survive(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    container = workbook.get_dashboards()[0].get_containers()[0]

    container.add_worksheet(workbook.get_worksheets(id="SheetC")[0], weight=1)

    dashboard_el = _dashboard_el(workbook)
    # ダッシュボード自身・対象コンテナ・その子・浮動ゾーンの、どれも保つ
    assert dashboard_el.get("sdk-unknown") == "keep"
    assert dashboard_el.xpath("string(./zones/zone[@id='1']/@custom)") == "keep"
    assert (
        dashboard_el.xpath("string(./zones/zone[@id='1']/zone[@id='2']/@custom-child)")
        == "keep"
    )
    assert dashboard_el.xpath("string(./zones/zone[@id='3']/@floating-custom)") == "keep"


def test_the_device_layout_zone_is_not_taken_for_a_dashboard_zone(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.get_dashboards()[0]

    # devicelayouts の中の zone は既定レイアウトの一覧に出てこない
    assert [zone.id for zone in dashboard.get_zones()] == ["2", "3"]


def test_only_the_window_changes_outside_the_dashboard(tmp_path) -> None:
    """ダッシュボードの外で変わってよいのは window だけ。"""
    workbook = _workbook(tmp_path)
    root_before = copy.deepcopy(workbook.tree.getroot())
    container = workbook.get_dashboards()[0].get_containers()[0]

    container.add_worksheet(workbook.get_worksheets(id="SheetC")[0], weight=1)

    after = copy.deepcopy(workbook.tree.getroot())
    # ダッシュボードと window を両方から外すと、残りは一致するはず
    for root in (after, root_before):
        for path in ("./dashboards", "./windows"):
            for element in root.xpath(path):
                root.remove(element)
    assert ET.tostring(after) == ET.tostring(root_before)
