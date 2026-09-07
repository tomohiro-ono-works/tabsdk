"""B-2: `TwbWorksheet.set_axis_visibility()` を直接検証する。

`draw_card()` 経由でしか実行されておらず、引数の異常系が確かめられていなかった。
軸の表示は `<style><style-rule element="axis"><format attr="display">` に書かれる。
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "axis.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _sheet_with_fields(tmp_path):
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")
    rows = worksheet.add_field(
        field=datasource.get_fields(name="売上")[0], shelf="rows", aggregation="sum"
    )
    columns = worksheet.add_field(
        field=datasource.get_fields(name="カテゴリ")[0], shelf="columns"
    )
    return workbook, worksheet, rows, columns


def _axis_formats(worksheet):
    return worksheet._resolve_element().xpath(
        ".//style-rule[@element='axis']/format[@attr='display']"
    )


def test_hiding_an_axis_writes_display_false(tmp_path) -> None:
    workbook, worksheet, rows, _ = _sheet_with_fields(tmp_path)

    assert worksheet.set_axis_visibility(field=rows, visible=False) is worksheet

    formats = _axis_formats(worksheet)
    assert len(formats) == 1
    assert formats[0].get("value") == "false"
    assert formats[0].get("scope") == "rows"
    assert workbook.is_dirty is True


def test_the_scope_follows_the_shelf(tmp_path) -> None:
    _, worksheet, _, columns = _sheet_with_fields(tmp_path)

    worksheet.set_axis_visibility(field=columns, visible=False)

    # 列シェルフは XML では cols
    assert _axis_formats(worksheet)[0].get("scope") == "cols"


def test_showing_it_again_overwrites_the_same_entry(tmp_path) -> None:
    _, worksheet, rows, _ = _sheet_with_fields(tmp_path)

    worksheet.set_axis_visibility(field=rows, visible=False)
    worksheet.set_axis_visibility(field=rows, visible=True)

    formats = _axis_formats(worksheet)
    assert len(formats) == 1
    assert formats[0].get("value") == "true"


def test_each_shelf_gets_its_own_entry(tmp_path) -> None:
    _, worksheet, rows, columns = _sheet_with_fields(tmp_path)

    worksheet.set_axis_visibility(field=rows, visible=False)
    worksheet.set_axis_visibility(field=columns, visible=False)

    assert sorted(f.get("scope") for f in _axis_formats(worksheet)) == ["cols", "rows"]


def test_the_same_value_twice_is_a_no_op(tmp_path) -> None:
    workbook, worksheet, rows, _ = _sheet_with_fields(tmp_path)
    worksheet.set_axis_visibility(field=rows, visible=False)
    workbook.save(str(tmp_path / "saved.twb"))

    before = workbook.is_dirty
    worksheet.set_axis_visibility(field=rows, visible=False)

    assert workbook.is_dirty is before


def test_a_field_on_another_shelf_is_rejected(tmp_path) -> None:
    workbook, worksheet, _, _ = _sheet_with_fields(tmp_path)
    datasource = workbook.get_datasources()[0]
    filtered = worksheet.add_field(
        field=datasource.get_fields(name="カテゴリ")[0], shelf="filters"
    )

    with pytest.raises(ValueError, match="rows or columns"):
        worksheet.set_axis_visibility(field=filtered, visible=False)


def test_a_field_from_another_worksheet_is_rejected(tmp_path) -> None:
    workbook, worksheet, rows, _ = _sheet_with_fields(tmp_path)
    other = workbook.create_worksheet(name="別シート")

    with pytest.raises(ValueError, match="must belong to the worksheet"):
        other.set_axis_visibility(field=rows, visible=False)


def test_a_bare_field_is_rejected(tmp_path) -> None:
    workbook, worksheet, _, _ = _sheet_with_fields(tmp_path)
    field = workbook.get_datasources()[0].get_fields(name="売上")[0]

    # シェルフ上の配置（TwbWorksheetField）が要る。TwbField では位置が決まらない
    with pytest.raises(TypeError, match="TwbWorksheetField"):
        worksheet.set_axis_visibility(field=field, visible=False)


def test_visible_must_be_bool(tmp_path) -> None:
    _, worksheet, rows, _ = _sheet_with_fields(tmp_path)

    with pytest.raises(TypeError, match="visible must be bool"):
        worksheet.set_axis_visibility(field=rows, visible="false")
