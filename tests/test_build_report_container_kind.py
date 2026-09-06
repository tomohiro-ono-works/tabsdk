"""K-1: コンテナ名の文字列で挙動が変わるのをやめ、区分値 `kind` で制御する。

以前は `"フィルタ" in コンテナ名` で分岐していた。コンテナ名はダッシュボードに
表示される枠の名前でもあるため、名前を変えると挙動が変わり、グラフの枠に
「売上フィルタ状況」と付けると意図せずフィルタ置き場になっていた。

`kind` は省略できない。中身から推測する案も既定値を置く案も採らなかった。
どちらも「なぜこの枠がフィルタ置き場になったか」が呼び出し側から読めないため。
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


def _build(dashboard, struct, **kwargs):
    return dashboard.build_report(
        dashboard_name="レポート", struct=struct, **kwargs
    )


def test_kind_decides_the_container_not_the_name(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    _build(
        dashboard,
        {
            # 名前に「フィルタ」が無くてもフィルタ置き場
            "地域を選ぶ": {"kind": "filter", "items": [("売上データ", "地域")]},
            # 名前に「フィルタ」が入っていてもワークシート置き場
            "売上フィルタ状況": {"kind": "worksheet", "items": ["SheetA", "SheetB"]},
        },
    )

    root = _root(dashboard)
    selector = root.get_containers(name="地域を選ぶ")[0]
    assert [zone.kind for zone in selector.get_zones()] == ["filter"]
    assert selector.fixed_size == 50
    assert selector.distribute_evenly is False

    sheets = root.get_containers(name="売上フィルタ状況")[0]
    assert [zone.kind for zone in sheets.get_zones()] == ["worksheet", "worksheet"]
    assert sheets.fixed_size == 300


def test_container_sizes_still_overrides_the_default(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    _build(
        dashboard,
        {
            "地域を選ぶ": {"kind": "filter", "items": [("売上データ", "地域")]},
            "本体": {"kind": "worksheet", "items": ["SheetA"]},
        },
        container_sizes={"地域を選ぶ": 80, "本体": 420},
    )

    assert [item.fixed_size for item in _root(dashboard).get_containers()] == [80, 420]


def test_a_bare_list_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="container must be"):
        _build(dashboard, {"本体": ["SheetA"]})


def test_a_missing_kind_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="container kind is required"):
        _build(dashboard, {"本体": {"items": ["SheetA"]}})


def test_an_unknown_kind_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="container kind must be one of"):
        _build(dashboard, {"本体": {"kind": "chart", "items": ["SheetA"]}})


def test_an_unknown_container_key_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(ValueError, match="only kind and items"):
        _build(
            dashboard,
            {"本体": {"kind": "worksheet", "items": ["SheetA"], "height": 200}},
        )


def test_a_filter_container_rejects_worksheet_names(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="filter item must be"):
        _build(dashboard, {"地域を選ぶ": {"kind": "filter", "items": ["SheetA"]}})


def test_a_worksheet_container_rejects_filter_tuples(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="レポート")

    with pytest.raises(TypeError, match="worksheet container must contain"):
        _build(
            dashboard,
            {"本体": {"kind": "worksheet", "items": [("売上データ", "地域")]}},
        )
