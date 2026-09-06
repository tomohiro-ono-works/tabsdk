"""L-5: グループをクラス方式で作る。

XML の形は Tableau が保存した `.twb` から実測した（2026-09-07、
`workbook/hierarchy_group_sample.twb`）。`<group>` 要素ではなく、普通の
`<column>` に `<calculation class="categorical-bin">` を入れて書かれる。
表示名がそのまま内部 ID になり、`caption` は付かない。
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook, UnsupportedFeatureError


def _workbook(tmp_path):
    path = tmp_path / "group.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _datasource(workbook):
    return workbook.get_datasources()[0]


def test_create_group_matches_the_shape_tableau_writes(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)

    datasource.create_group(
        field="カテゴリ",
        groups={"家具と事務用品": ["Furniture", "Office Supplies"]},
    )

    column = datasource._resolve_element().xpath("./column[@name='[カテゴリ (グループ)]']")[0]
    assert column.attrib == {
        "datatype": "string",
        "name": "[カテゴリ (グループ)]",
        "role": "dimension",
        "type": "nominal",
    }
    # caption は付かない。表示名がそのまま内部 ID を兼ねる
    assert column.get("caption") is None

    calculation = column.find("./calculation")
    assert calculation.attrib == {
        "class": "categorical-bin",
        "column": "[Category]",
        "new-bin": "true",
    }
    bin_el = calculation.find("./bin")
    # グループ名もメンバーもダブルクォート込みの文字列
    assert bin_el.get("value") == '"家具と事務用品"'
    assert [value.text for value in bin_el] == ['"Furniture"', '"Office Supplies"']


def test_the_group_name_is_explicit_so_default_name_is_not_written(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    datasource.create_group(field="カテゴリ", groups={"家具": ["Furniture"]})

    bin_el = datasource._resolve_element().xpath(".//bin")[0]
    # default-name="true" は Tableau に名前を任せた印。こちらは必ず名前を受け取る
    assert bin_el.get("default-name") is None


def test_ungrouped_values_are_not_written(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    datasource.create_group(field="カテゴリ", groups={"家具": ["Furniture"]})

    # まとめなかった値は書かない。Tableau が単独の値として扱う
    assert len(datasource._resolve_element().xpath(".//bin")) == 1


def test_several_groups_become_several_bins(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    datasource.create_group(
        field="カテゴリ",
        groups={"家具": ["Furniture"], "事務用品と家電": ["Office Supplies", "Technology"]},
    )

    bins = datasource._resolve_element().xpath(".//bin")
    assert [b.get("value") for b in bins] == ['"家具"', '"事務用品と家電"']
    assert [len(b) for b in bins] == [1, 2]


def test_the_created_field_is_a_dimension_in_the_field_list(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)

    field = datasource.create_group(field="カテゴリ", groups={"家具": ["Furniture"]})

    assert field.id == "[カテゴリ (グループ)]"
    assert field.name == "カテゴリ (グループ)"
    assert field.role == "dimension"
    assert field.datatype == "string"
    assert workbook.is_dirty is True
    assert "カテゴリ (グループ)" in [f.name for f in datasource.get_fields()]


def test_the_name_can_be_given(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    field = datasource.create_group(
        field="カテゴリ", groups={"家具": ["Furniture"]}, name="商品区分"
    )

    assert field.id == "[商品区分]"
    assert field.name == "商品区分"


def test_the_group_can_go_into_a_folder(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))
    datasource.create_folder(name="Dim商品")

    field = datasource.create_group(
        field="カテゴリ", groups={"家具": ["Furniture"]}, folder="Dim商品"
    )

    assert field.folder is not None and field.folder.name == "Dim商品"


def test_a_field_object_can_be_passed(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))
    source = datasource.get_fields(name="カテゴリ")[0]

    datasource.create_group(field=source, groups={"家具": ["Furniture"]})

    calculation = datasource._resolve_element().xpath(".//calculation")[0]
    assert calculation.get("column") == "[Category]"


def test_a_measure_is_rejected(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    with pytest.raises(UnsupportedFeatureError, match="must be a string field"):
        datasource.create_group(field="売上", groups={"高": ["100"]})


def test_a_duplicate_field_name_is_rejected(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))
    datasource.create_group(field="カテゴリ", groups={"家具": ["Furniture"]})

    with pytest.raises(ValueError, match="field name already exists"):
        datasource.create_group(field="カテゴリ", groups={"家具": ["Furniture"]})


def test_a_value_in_two_groups_is_rejected(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    with pytest.raises(ValueError, match="in more than one group"):
        datasource.create_group(
            field="カテゴリ",
            groups={"家具": ["Furniture"], "まとめ": ["Furniture", "Technology"]},
        )


def test_an_empty_group_set_is_rejected(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    with pytest.raises(ValueError, match="non-empty dict"):
        datasource.create_group(field="カテゴリ", groups={})


def test_a_group_without_members_is_rejected(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    with pytest.raises(ValueError, match="at least one member"):
        datasource.create_group(field="カテゴリ", groups={"家具": []})


def test_a_quote_in_a_value_is_rejected(tmp_path) -> None:
    datasource = _datasource(_workbook(tmp_path))

    with pytest.raises(ValueError, match="must not contain a quote"):
        datasource.create_group(field="カテゴリ", groups={"家具": ['Fur"niture']})


def test_the_group_survives_a_round_trip(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    _datasource(workbook).create_group(
        field="カテゴリ", groups={"家具と事務用品": ["Furniture", "Office Supplies"]}
    )
    out = tmp_path / "out.twb"
    workbook.save(str(out))

    reopened = TwbWorkbook.open(str(out))
    field = _datasource(reopened).get_fields(name="カテゴリ (グループ)")[0]
    assert field.id == "[カテゴリ (グループ)]"
    bin_el = _datasource(reopened)._resolve_element().xpath(".//bin")[0]
    assert [value.text for value in bin_el] == ['"Furniture"', '"Office Supplies"']


def test_the_group_column_passes_validation_without_a_caption(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    _datasource(workbook).create_group(field="カテゴリ", groups={"家具": ["Furniture"]})

    # グループは formula を持たず caption も付かない。どちらも警告・エラーにしない
    assert [m.code for m in workbook.validate()] == []
    workbook.save(str(tmp_path / "out.twb"))
