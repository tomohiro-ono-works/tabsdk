"""K-1: コンテナ名の文字列で挙動が変わるのをやめ、区分値で制御する。

以前は `"フィルタ" in コンテナ名` で分岐していた。コンテナ名はダッシュボードに
表示される枠の名前でもあるため、名前を変えると挙動が変わり、グラフの枠に
「売上フィルタ状況」と付けると意図せずフィルタ置き場になっていた。

今は `{"kind": "filter", "items": [...]}` と明示する。
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


def _root(dashboard):
    return dashboard.get_containers()[0].get_containers(name="レポート")[0]


def test_kind_filter_places_filters_whatever_the_name_is(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={
            "地域を選ぶ": {"kind": "filter", "items": [("売上データ", "地域")]},
            "本体": {"kind": "worksheet", "items": ["SheetA", "SheetB"]},
        },
    )

    selector = _root(dashboard).get_containers(name="地域を選ぶ")[0]
    assert [zone.kind for zone in selector.get_zones()] == ["filter"]
    assert selector.fixed_size == 50
    assert selector.distribute_evenly is False


def test_a_name_containing_filter_is_just_a_name(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={"売上フィルタ状況": ["SheetA", "SheetB"]},
    )

    container = _root(dashboard).get_containers(name="売上フィルタ状況")[0]
    assert [zone.kind for zone in container.get_zones()] == ["worksheet", "worksheet"]
    assert container.fixed_size == 300


def test_a_bare_list_is_a_worksheet_container(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={"本体": ["SheetA"]},
    )

    container = _root(dashboard).get_containers(name="本体")[0]
    assert [zone.kind for zone in container.get_zones()] == ["worksheet"]


def test_container_sizes_still_overrides_the_default(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    dashboard.build_report(
        dashboard_name="レポート",
        struct={
            "地域を選ぶ": {"kind": "filter", "items": [("売上データ", "地域")]},
            "本体": ["SheetA"],
        },
        container_sizes={"地域を選ぶ": 80, "本体": 420},
    )

    assert [item.fixed_size for item in _root(dashboard).get_containers()] == [80, 420]


def test_filters_without_a_kind_are_rejected_with_a_hint(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="filters need an explicit kind"):
        dashboard.build_report(
            dashboard_name="レポート",
            struct={"地域を選ぶ": [("売上データ", "地域")]},
        )


def test_an_unknown_kind_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="container kind must be one of"):
        dashboard.build_report(
            dashboard_name="レポート",
            struct={"本体": {"kind": "chart", "items": ["SheetA"]}},
        )


def test_an_unknown_container_key_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="only kind and items"):
        dashboard.build_report(
            dashboard_name="レポート",
            struct={"本体": {"kind": "worksheet", "items": ["SheetA"], "height": 200}},
        )


def test_a_filter_container_still_rejects_worksheet_names(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="filter item must be"):
        dashboard.build_report(
            dashboard_name="レポート",
            struct={"地域を選ぶ": {"kind": "filter", "items": ["SheetA"]}},
        )
