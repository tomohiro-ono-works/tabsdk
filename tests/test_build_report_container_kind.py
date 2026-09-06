"""K-1: コンテナ名の文字列でフィルタ置き場かどうかが決まるのをやめる。

以前は `"フィルタ" in コンテナ名` で分岐していた。コンテナ名はダッシュボードに
表示される枠の名前でもあるため、名前を変えると挙動が変わり、グラフの枠に
「売上フィルタ状況」と付けると意図せずフィルタ置き場になっていた。

今は中身で判別する。フィルタは `("データソース名", "フィールド名")` のタプル、
グラフはシート名の文字列。
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "report.twb"
    path.write_text(
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
    workbook = TwbWorkbook.open(str(path))
    workbook.set_filter(("売上データ", "地域"))
    return workbook


def test_a_container_of_tuples_is_a_filter_container_whatever_its_name(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={
            "地域を選ぶ": [("売上データ", "地域")],  # 名前に「フィルタ」は無い
            "本体": ["SheetA", "SheetB"],
        },
    )

    root = dashboard.get_containers()[0].get_containers(name="レポート")[0]
    selector = root.get_containers(name="地域を選ぶ")[0]
    assert [zone.kind for zone in selector.get_zones()] == ["filter"]
    assert selector.fixed_size == 50
    assert selector.distribute_evenly is False


def test_a_container_of_names_is_not_a_filter_container_whatever_its_name(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={"売上フィルタ状況": ["SheetA", "SheetB"]},  # 名前に「フィルタ」が入る
    )

    root = dashboard.get_containers()[0].get_containers(name="レポート")[0]
    container = root.get_containers(name="売上フィルタ状況")[0]
    assert [zone.kind for zone in container.get_zones()] == ["worksheet", "worksheet"]
    assert container.fixed_size == 300


def test_container_sizes_still_overrides_the_default(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={
            "地域を選ぶ": [("売上データ", "地域")],
            "本体": ["SheetA"],
        },
        container_sizes={"地域を選ぶ": 80, "本体": 420},
    )

    root = dashboard.get_containers()[0].get_containers(name="レポート")[0]
    assert [item.fixed_size for item in root.get_containers()] == [80, 420]


def test_mixing_filters_and_worksheets_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="mixes filters and worksheets"):
        dashboard.build_report(
            dashboard_name="レポート",
            struct={"混在": [("売上データ", "地域"), "SheetA"]},
        )
