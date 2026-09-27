"""A-2: フィルタ系 2 リソースの接続型モデル化。

根拠: docs/model_api_spec.md §11、docs/backlog.md A-2（2026-09-05 決定）
"""

from __future__ import annotations

import pytest

from twbpatch import (
    DetachedModelError,
    TwbDashboardZone,
    TwbFilterControl,
    TwbWorkbook,
    TwbWorksheetFilter,
)


def _workbook(tmp_path):
    path = tmp_path / "filter.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[連番]" caption="連番" datatype="integer" role="dimension" type="ordinal" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _worksheet_with_filter(workbook):
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="Sheet1")
    worksheet.add_field(field=datasource.get_fields(name="売上")[0], shelf="rows")
    placement = worksheet.add_filter(field=datasource.get_fields(name="地域")[0])
    return worksheet, placement


def test_get_filters_returns_connected_models(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, _ = _worksheet_with_filter(workbook)

    filters = worksheet.get_filters()
    assert [type(item) for item in filters] == [TwbWorksheetFilter]

    filter_ = filters[0]
    assert filter_.id == "[ds1].[none:Region:nk]"
    assert filter_.name == "地域"
    assert filter_.worksheet_id == "Sheet1"
    assert filter_.role == "dimension"
    assert filter_.filter_class == "categorical"

    assert [item.id for item in worksheet.get_filters(name="地域")] == [filter_.id]
    assert [item.id for item in worksheet.get_filters(id=filter_.id)] == [filter_.id]
    assert worksheet.get_filters(name="存在しない") == []
    with pytest.raises(ValueError, match="cannot be specified together"):
        worksheet.get_filters(id=filter_.id, name="地域")


def test_filter_update_replaces_selected_values(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, _ = _worksheet_with_filter(workbook)
    filter_ = worksheet.get_filters()[0]

    assert filter_.update(values=["東日本", "西日本"]) is filter_
    assert worksheet.get_filters()[0].values == ["東日本", "西日本"]

    # filter の直下に置ける groupfilter は 1 つだけ。複数の値は union で包む（Tableau の保存形。
    # 直下に並べると Tableau が読み込みを拒否する、2026-09-13）
    filter_el = worksheet._resolve_element().xpath(".//*[local-name()='filter']")[0]
    assert [child.get("function") for child in filter_el] == ["union"]
    assert filter_el[0].get("{http://www.tableausoftware.com/xml/user}ui-enumeration") == "inclusive"
    members = filter_el[0].xpath("./*[local-name()='groupfilter'][@function='member']")
    assert [item.get("member") for item in members] == ['"東日本"', '"西日本"']
    assert {item.get("level") for item in members} == {"[none:Region:nk]"}

    # 入れ替えであって追加ではない。1 つなら union で包まない
    filter_.update(values=["東日本"])
    assert worksheet.get_filters()[0].values == ["東日本"]
    filter_el = worksheet._resolve_element().xpath(".//*[local-name()='filter']")[0]
    assert [child.get("function") for child in filter_el] == ["member"]

    # 空リストは「すべての値」へ戻す
    filter_.update(values=[])
    assert worksheet.get_filters()[0].values == []
    assert worksheet._resolve_element().xpath(
        ".//*[local-name()='filter']/*[local-name()='groupfilter'][@function='level-members']"
    )


def test_filter_update_writes_integer_values_without_quotes(tmp_path) -> None:
    """`member` 属性は、文字列型なら引用符付き、整数型なら引用符なしで書く
    （2026-09-23 実測。整数型フィールドをダブルクォートで囲むと Tableau 側で
    実際の値と一致せず、フィルタが効かなかった）。
    """
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="Sheet1")
    worksheet.add_field(field=datasource.get_fields(name="売上")[0], shelf="rows")
    worksheet.add_filter(field=datasource.get_fields(name="連番")[0])
    filter_ = worksheet.get_filters()[0]

    filter_.update(values=["1", "2"])

    filter_el = worksheet._resolve_element().xpath(".//*[local-name()='filter']")[0]
    members = filter_el.xpath(".//*[local-name()='groupfilter'][@function='member']")
    assert [item.get("member") for item in members] == ["1", "2"]

    # 単一値でも引用符なし
    filter_.update(values=["1"])
    filter_el = worksheet._resolve_element().xpath(".//*[local-name()='filter']")[0]
    assert filter_el.xpath("./*[local-name()='groupfilter']")[0].get("member") == "1"


def test_filter_update_without_arguments_is_a_no_op(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, _ = _worksheet_with_filter(workbook)
    workbook.save(str(tmp_path / "saved.twb"), overwrite=True)
    assert workbook.is_dirty is False

    workbook.get_worksheets()[0].get_filters()[0].update()
    assert workbook.is_dirty is False


@pytest.mark.parametrize(
    "values, error",
    [("東日本", TypeError), ([1], TypeError), ([" "], ValueError)],
)
def test_filter_update_rejects_bad_values(tmp_path, values, error) -> None:
    workbook = _workbook(tmp_path)
    worksheet, _ = _worksheet_with_filter(workbook)
    with pytest.raises(error):
        worksheet.get_filters()[0].update(values=values)


def test_filter_delete_removes_element_and_detaches(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, _ = _worksheet_with_filter(workbook)
    filter_ = worksheet.get_filters()[0]

    assert filter_.delete() is None
    assert worksheet.get_filters() == []
    assert worksheet._resolve_element().xpath(".//*[local-name()='filter']") == []
    # add_filter() が置いた slices の参照も消える
    assert worksheet._resolve_element().xpath(
        ".//*[local-name()='slices']/*[local-name()='column']"
    ) == []

    with pytest.raises(DetachedModelError):
        filter_.values


def test_filter_control_is_a_dashboard_zone(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, placement = _worksheet_with_filter(workbook)
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")
    container.add_worksheet(worksheet, show_title=False)
    container.add_filter(field=placement)

    controls = dashboard.get_filter_controls()
    assert [type(item) for item in controls] == [TwbFilterControl]
    control = controls[0]
    assert isinstance(control, TwbDashboardZone)

    assert control.column == "[ds1].[none:Region:nk]"
    assert control.field == "地域"
    assert control.mode == "checkdropdown"
    assert control.worksheet == "Sheet1"
    assert control.kind == "filter"
    assert control.apply_scope == "worksheet"

    # 座標・スタイルの更新と削除は TwbDashboardZone から引き継ぐ
    control.update(style={"background_color": "#ffffff"}, show_title=False)
    assert control.style == {"background_color": "#ffffff"}
    assert control.show_title is False

    control.delete()
    assert dashboard.get_filter_controls() == []


def test_filter_control_rejects_a_non_filter_zone(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, _ = _worksheet_with_filter(workbook)
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")
    sheet_zone = container.add_worksheet(worksheet, show_title=False)

    control = TwbFilterControl(workbook._context, dashboard.id, sheet_zone.id)
    with pytest.raises(DetachedModelError, match="not a filter"):
        control.column
