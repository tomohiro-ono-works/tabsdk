"""E-2 の前提: フィルターの入口を `workbook.add_filter()` 1 つにまとめる。

旧 `TwbWorkbook.set_filter()` は「データソースフィルターを作り、使っている
全シートにスライスを足す」まとめ役だった。フィルターの入口は他にも
`worksheet.add_filter()` / `add_filter_slice()` / `container.add_filter()` と
散らばっていたので、**使う側の入口を 1 つにして種別は引数で選ぶ**形にした。

カードは新しく作らない。`add_filter()` が返したシェルフ上の配置を
`container.add_filter()` へ渡す。
"""

from __future__ import annotations

import pytest

from twbpatch import NotFoundError, TwbWorkbook


SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
"""


def _workbook(tmp_path, sheets=("売上シート",)):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "filter.twb"
    path.write_text(SOURCE, encoding="utf-8")
    workbook = TwbWorkbook.open(str(path))
    datasource = workbook.get_datasources(name="売上データ")[0]
    for name in sheets:
        workbook.draw_bar(
            datasource, name=name, item="地域", metric="売上"
        )
    return workbook


def _slices(workbook, sheet):
    return workbook.get_worksheets(id=sheet)[0]._resolve_element().xpath(
        ".//slices/column/text()"
    )


def _shared_view_filters(workbook):
    return workbook.tree.getroot().xpath("./shared-views/shared-view/filter")


# --- scope="worksheet"（既定） ------------------------------------------------


def test_a_worksheet_filter_is_placed_on_the_filters_shelf(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    placements = workbook.add_filter(("売上データ", "地域"))

    assert len(placements) == 1
    assert placements[0].shelf == "filters"
    assert placements[0].name == "地域"
    assert _shared_view_filters(workbook) == []


def test_the_result_can_go_straight_into_a_filter_card(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=1600, height=900)
    container = dashboard.create_container(direction="vertical")
    container.add_worksheet(workbook.get_worksheets()[0], show_title=False)

    placements = workbook.add_filter("地域")
    container.add_filter(placements[0], mode="checkdropdown", show_apply=True)

    controls = dashboard.get_filter_controls()
    assert [control.field for control in controls] == ["地域"]
    assert controls[0].show_apply is True
    assert controls[0].mode == "checkdropdown"


def test_every_sheet_using_the_datasource_is_covered(tmp_path) -> None:
    workbook = _workbook(tmp_path, sheets=("売上シート", "地域シート"))

    placements = workbook.add_filter("地域")

    assert {p._worksheet_id for p in placements} == {"売上シート", "地域シート"}


def test_the_target_sheets_can_be_named(tmp_path) -> None:
    workbook = _workbook(tmp_path, sheets=("売上シート", "地域シート"))

    placements = workbook.add_filter("地域", worksheets=["地域シート"])

    assert [p._worksheet_id for p in placements] == ["地域シート"]


def test_a_worksheet_object_can_be_passed(tmp_path) -> None:
    workbook = _workbook(tmp_path, sheets=("売上シート", "地域シート"))
    worksheet = workbook.get_worksheets(id="売上シート")[0]

    placements = workbook.add_filter("地域", worksheets=[worksheet])

    assert [p._worksheet_id for p in placements] == ["売上シート"]


# --- scope="datasource" -------------------------------------------------------


def test_a_datasource_filter_is_written_to_shared_views(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    placements = workbook.add_filter("地域", scope="datasource")

    # データソースフィルターはシェルフ上の配置を持たないのでカードにできない
    assert placements == []
    filters = _shared_view_filters(workbook)
    assert len(filters) == 1
    assert filters[0].get("class") == "categorical"
    assert filters[0].get("column") == "[ds1].[none:Region:nk]"


def test_a_datasource_filter_adds_a_slice_to_each_sheet(tmp_path) -> None:
    workbook = _workbook(tmp_path, sheets=("売上シート", "地域シート"))

    workbook.add_filter("地域", scope="datasource")

    assert _slices(workbook, "売上シート") == ["[ds1].[none:Region:nk]"]
    assert _slices(workbook, "地域シート") == ["[ds1].[none:Region:nk]"]


def test_a_datasource_filter_is_written_even_without_sheets(tmp_path) -> None:
    workbook = _workbook(tmp_path, sheets=())

    assert workbook.add_filter("地域", scope="datasource") == []
    assert len(_shared_view_filters(workbook)) == 1


# --- 異常系 -------------------------------------------------------------------


def test_an_unknown_scope_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="scope must be one of"):
        workbook.add_filter("地域", scope="dashboard")


def test_an_unknown_worksheet_name_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    with pytest.raises(NotFoundError, match="worksheet not found"):
        workbook.add_filter("地域", worksheets=["無いシート"])


def test_a_bare_name_needs_one_datasource(tmp_path) -> None:
    from twbpatch import AmbiguousCaptionError

    path = tmp_path / "two.twb"
    path.write_text(
        SOURCE.replace(
            "  </datasources>",
            """    <datasource name="ds2" caption="別データ">
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>""",
        ),
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))

    # データソースが 2 つあるので素の文字列では決まらない（仕様 §5.4a）
    with pytest.raises(AmbiguousCaptionError):
        workbook.add_filter("地域")


def test_worksheets_must_be_a_list(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    with pytest.raises(TypeError, match="worksheets must be a list"):
        workbook.add_filter("地域", worksheets="売上シート")
