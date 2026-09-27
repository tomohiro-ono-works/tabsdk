"""K-1: コンテナ名の文字列で挙動が変わるのをやめ、区分値 `kind` で制御する。

以前は `"フィルタ" in コンテナ名` で分岐していた。コンテナ名はダッシュボードに
表示される枠の名前でもあるため、名前を変えると挙動が変わり、グラフの枠に
「売上フィルタ状況」と付けると意図せずフィルタ置き場になっていた。

`kind` は**項目ごと**に持つ。1 つの段にグラフとフィルタを混ぜられるようにするため
（設定画面もエリアごとに種別を選ばせている）。省略はできない。
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
    workbook.add_filter(("売上データ", "地域"), scope="datasource")
    return workbook


def _root(dashboard):
    return dashboard.get_containers()[0].get_containers(name="レポート")[0]


def _build(dashboard, struct, **kwargs):
    return dashboard.build_report(dashboard_name="レポート", struct=struct, **kwargs)


def test_one_row_can_hold_both_a_filter_and_a_chart(tmp_path) -> None:
    """画面はエリアごとに種別を選べる。受け手も同じ段に混ぜられること。"""
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    _build(
        dashboard,
        {
            "上段": {
                "items": [
                    {"kind": "filter", "field": ("売上データ", "地域")},
                    {"kind": "worksheet", "sheet": "SheetA"},
                ]
            },
            "下段": {"items": [{"kind": "worksheet", "sheet": "SheetB"}]},
        },
    )

    row = _root(dashboard).get_containers(name="上段")[0]
    # 並びは items の順どおり
    assert [zone.kind for zone in row.get_zones()] == ["filter", "worksheet"]
    # フィルタが居る段は均等配分しない
    assert row.distribute_evenly is False


def test_a_filter_keeps_its_place_when_it_comes_in_the_middle(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    _build(
        dashboard,
        {
            "上段": {
                "items": [
                    {"kind": "worksheet", "sheet": "SheetA"},
                    {"kind": "filter", "field": ("売上データ", "地域")},
                    {"kind": "worksheet", "sheet": "SheetB"},
                ]
            }
        },
    )

    row = _root(dashboard).get_containers(name="上段")[0]
    assert [zone.kind for zone in row.get_zones()] == [
        "worksheet",
        "filter",
        "worksheet",
    ]


def test_the_name_does_not_decide_anything(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    _build(
        dashboard,
        {
            "売上フィルタ状況": {
                "items": [
                    {"kind": "worksheet", "sheet": "SheetA"},
                    {"kind": "worksheet", "sheet": "SheetB"},
                ]
            }
        },
    )

    container = _root(dashboard).get_containers(name="売上フィルタ状況")[0]
    assert [zone.kind for zone in container.get_zones()] == ["worksheet", "worksheet"]
    assert container.fixed_size == 300
    assert container.distribute_evenly is True


def test_height_is_taken_from_the_container_then_container_sizes(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    _build(
        dashboard,
        {
            "上段": {"height": 50, "items": [{"kind": "worksheet", "sheet": "SheetA"}]},
            "下段": {"items": [{"kind": "worksheet", "sheet": "SheetB"}]},
        },
        container_sizes={"上段": 999, "下段": 420},
    )

    # height を書いた段は container_sizes より優先される
    assert [item.fixed_size for item in _root(dashboard).get_containers()] == [50, 420]


def test_a_bare_list_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="container must be"):
        _build(dashboard, {"上段": ["SheetA"]})


def test_an_item_without_a_kind_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="item kind must be one of"):
        _build(dashboard, {"上段": {"items": [{"sheet": "SheetA"}]}})


def test_an_unknown_item_kind_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="item kind must be one of"):
        _build(dashboard, {"上段": {"items": [{"kind": "chart", "sheet": "SheetA"}]}})


def test_an_unknown_container_key_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    # distribute_evenly は 2026-09-21 追加
    with pytest.raises(ValueError, match="only items, height and distribute_evenly"):
        _build(
            dashboard,
            {"上段": {"items": [{"kind": "worksheet", "sheet": "SheetA"}], "kind": "x"}},
        )


def test_sheet_and_sheets_are_mutually_exclusive(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="exactly one of sheet or sheets"):
        _build(
            dashboard,
            {"上段": {"items": [{"kind": "worksheet", "sheet": "A", "sheets": ["B"]}]}},
        )


def test_fixed_size_needs_sheets(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="fixed_size applies to sheets"):
        _build(
            dashboard,
            {
                "上段": {
                    "items": [
                        {"kind": "worksheet", "sheet": "SheetA", "fixed_size": 200}
                    ]
                }
            },
        )


def test_a_filter_item_needs_a_field(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="filter field must be"):
        _build(dashboard, {"上段": {"items": [{"kind": "filter"}]}})


def test_sheets_makes_a_column_even_for_one_sheet(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    _build(
        dashboard,
        {
            "上段": {
                "items": [
                    {"kind": "worksheet", "sheets": ["SheetA"], "fixed_size": 200},
                    {"kind": "worksheet", "sheet": "SheetB"},
                ]
            }
        },
    )

    row = _root(dashboard).get_containers(name="上段")[0]
    columns = row.get_containers()
    assert [column.fixed_size for column in columns] == [200]
    assert [zone.name for zone in columns[0].get_zones()] == ["SheetA"]
    # sheet= はそのまま段へ置かれる（列にしない）
    assert [zone.name for zone in row.get_zones()] == ["SheetB"]
