"""A-8: フィールドを受け取る引数の書き味を固定する。

クラス方式（`worksheet.add_field()` など）も API 方式（`draw_*`）と同じく、
名前・タプル・`TwbField` の 3 通りで指定できる。引数はキーワード専用。
"""

from __future__ import annotations

import pytest

from twbpatch import AmbiguousCaptionError, NotFoundError, TwbWorkbook


def _single(tmp_path):
    path = tmp_path / "single.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _multi(tmp_path):
    path = tmp_path / "multi.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="a" caption="商品データ">
      <column name="[Name]" caption="名前" datatype="string" role="dimension" type="nominal" />
    </datasource>
    <datasource name="b" caption="売上データ">
      <column name="[Name]" caption="名前" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_three_ways_give_the_same_result(tmp_path) -> None:
    workbook = _single(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="S1")

    by_object = worksheet.add_field(
        field=datasource.get_fields(name="売上")[0], shelf="rows"
    )
    by_name = worksheet.add_field(field="地域", shelf="columns")
    by_tuple = worksheet.add_field(field=("売上データ", "地域"), shelf="pages")

    assert by_object.name == "売上"
    assert by_name.name == "地域"
    assert by_tuple.field_id == by_name.field_id


def test_every_method_accepts_a_name(tmp_path) -> None:
    """クラス方式のフィールド引数がすべて同じ書き味であることを固定する。"""
    workbook = _single(tmp_path)
    worksheet = workbook.create_worksheet(name="S1")

    worksheet.add_field(field="売上", shelf="rows")
    worksheet.add_field(field="地域", shelf="columns")
    worksheet.add_filter(field="地域")
    worksheet.add_sort(field="地域", by="売上")
    worksheet.get_panes()[0].add_field(field="地域", encoding="color", discrete=True)

    assert {item.name for item in worksheet.get_fields()} == {"売上", "地域"}
    assert [item.name for item in worksheet.get_filters()] == ["地域"]

    other = workbook.create_worksheet(name="S2")
    other.add_field(field="売上", shelf="rows")
    other.add_filter_slice(field="地域")
    assert other.get_filters() == []


def test_field_arguments_are_keyword_only(tmp_path) -> None:
    workbook = _single(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="S1")
    field = datasource.get_fields(name="売上")[0]

    with pytest.raises(TypeError, match="positional"):
        worksheet.add_field(field, shelf="rows")
    with pytest.raises(TypeError, match="positional"):
        worksheet.add_filter(field)


def test_a_name_uses_the_worksheet_dependency_as_context(tmp_path) -> None:
    """素の文字列は、そのシートが既に依存しているデータソースから探す。"""
    workbook = _multi(tmp_path)
    worksheet = workbook.create_worksheet(name="S1")

    # 依存がまだ無く、データソースが 2 つあるので決まらない
    with pytest.raises(AmbiguousCaptionError, match="specify it as"):
        worksheet.add_field(field="名前", shelf="rows")

    # タプルで 1 つ置くと、以降は名前で決まる
    worksheet.add_field(field=("売上データ", "売上"), shelf="rows")
    placement = worksheet.add_field(field="名前", shelf="columns")
    assert placement.datasource_id == "b"


def test_a_name_works_when_the_workbook_has_one_datasource(tmp_path) -> None:
    workbook = _single(tmp_path)
    worksheet = workbook.create_worksheet(name="S1")

    placement = worksheet.add_field(field="売上", shelf="rows")
    assert placement.name == "売上"


@pytest.mark.parametrize(
    "value, error",
    [
        ("存在しない", NotFoundError),
        ("   ", ValueError),
        (("存在しないデータソース", "売上"), NotFoundError),
        (("売上データ",), TypeError),
        (1, TypeError),
    ],
)
def test_bad_field_arguments(tmp_path, value, error) -> None:
    workbook = _single(tmp_path)
    worksheet = workbook.create_worksheet(name="S1")
    with pytest.raises(error):
        worksheet.add_field(field=value, shelf="rows")


def test_field_from_another_workbook_is_rejected(tmp_path) -> None:
    workbook = _single(tmp_path)
    other_path = tmp_path / "other"
    other_path.mkdir()
    other = _single(other_path)
    other_field = other.get_datasources()[0].get_fields(name="売上")[0]

    worksheet = workbook.create_worksheet(name="S1")
    with pytest.raises(ValueError, match="same workbook"):
        worksheet.add_field(field=other_field, shelf="rows")


def test_draw_methods_keep_accepting_the_same_three_forms(tmp_path) -> None:
    """API 方式の書き味は変わっていない。"""
    workbook = _single(tmp_path)
    datasource = workbook.get_datasources()[0]

    workbook.draw_bar(name="B1", item=("売上データ", "地域"), metric=("売上データ", "売上"))
    workbook.draw_bar(datasource, name="B2", item="地域", metric="売上")
    workbook.draw_bar(
        name="B3",
        item=datasource.get_fields(name="地域")[0],
        metric=datasource.get_fields(name="売上")[0],
    )

    assert [item.name for item in workbook.get_worksheets()] == ["B1", "B2", "B3"]
