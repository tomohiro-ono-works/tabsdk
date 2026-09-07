"""B-3 #41: 新旧 API の XML 出力が同等であることを確かめる。

仕様 §11 の移行規約で旧 API は当面残る。**同じ操作なら同じ XML が出る**ことが
前提だが、突き合わせる比較テストが無く `/spec-conformance` が「要目視」と判定していた。

同じワークブックを 2 つ開き、片方に旧 API、もう片方に新 API を適用して、
`ET.tostring()` の一致を見る。
"""

from __future__ import annotations

from lxml import etree as ET

from twbpatch import TwbWorkbook


SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="粗利" datatype="real" role="measure"
              type="quantitative">
        <calculation class="tableau" formula="[Sales] * 0.3" />
      </column>
      <folders-common>
        <folder name="指標" />
      </folders-common>
    </datasource>
  </datasources>
</workbook>
"""


def _pair(tmp_path):
    """同じ中身のワークブックを 2 つ開く。片方が旧 API、片方が新 API。"""
    old_path = tmp_path / "old.twb"
    new_path = tmp_path / "new.twb"
    for path in (old_path, new_path):
        path.write_text(SOURCE, encoding="utf-8")
    return TwbWorkbook.open(str(old_path)), TwbWorkbook.open(str(new_path))


def _xml(workbook) -> bytes:
    return ET.tostring(workbook.tree.getroot())


def _assert_same(old, new) -> None:
    assert _xml(old) == _xml(new)


def test_the_two_workbooks_start_identical(tmp_path) -> None:
    old, new = _pair(tmp_path)

    _assert_same(old, new)


def test_renaming_a_field(tmp_path) -> None:
    old, new = _pair(tmp_path)

    old.rename_field("売上データ", "売上", "売上高")
    new.get_datasources()[0].get_fields(name="売上")[0].update(name="売上高")

    _assert_same(old, new)


def test_resetting_a_caption(tmp_path) -> None:
    old, new = _pair(tmp_path)

    old.reset_field_caption("売上データ", "売上")
    new.get_datasources()[0].get_fields(name="売上")[0].update(name=None)

    _assert_same(old, new)


def test_updating_a_formula(tmp_path) -> None:
    old, new = _pair(tmp_path)

    old.update_formula("売上データ", "粗利", "[Sales] * 0.4")
    new.get_datasources()[0].get_fields(name="粗利")[0].update(formula="[Sales] * 0.4")

    _assert_same(old, new)


def test_moving_a_field_to_a_folder(tmp_path) -> None:
    old, new = _pair(tmp_path)

    old.move_field_to_folder("売上データ", "売上", "指標")
    new.get_datasources()[0].get_fields(name="売上")[0].move_to_folder("指標")

    _assert_same(old, new)


def test_creating_a_calculated_field(tmp_path) -> None:
    old, new = _pair(tmp_path)

    old.create_calculated_field(
        "売上データ", "利益率", "[Profit] / [Sales]", number_format="%"
    )
    new.get_datasources()[0].create_calculated_field(
        name="利益率", formula="[Profit] / [Sales]", number_format="%"
    )

    _assert_same(old, new)


def test_creating_a_calculated_field_into_a_folder(tmp_path) -> None:
    old, new = _pair(tmp_path)

    old.create_calculated_field(
        "売上データ", "利益率", "[Profit] / [Sales]", folder="指標"
    )
    new.get_datasources()[0].create_calculated_field(
        name="利益率", formula="[Profit] / [Sales]", folder="指標"
    )

    _assert_same(old, new)


def test_the_same_edits_in_a_row(tmp_path) -> None:
    """1 操作ずつでなく続けて掛けても、途中の順序差が残らないこと。"""
    old, new = _pair(tmp_path)

    old.rename_field("売上データ", "売上", "売上高")
    old.move_field_to_folder("売上データ", "売上高", "指標")
    old.create_calculated_field("売上データ", "利益率", "[Profit] / [Sales]")

    datasource = new.get_datasources()[0]
    field = datasource.get_fields(name="売上")[0]
    field.update(name="売上高")
    field.move_to_folder("指標")
    datasource.create_calculated_field(name="利益率", formula="[Profit] / [Sales]")

    _assert_same(old, new)
