"""L-2: 階層（ドリルパス）をクラス方式で作る。

XML の形は Tableau が保存した `.twb` から実測した（2026-09-07、
`workbook/hierarchy_group_sample.twb`）。`<drill-paths>` は datasource 直下で、
`<field>` のテキストに内部 ID を階層順に並べる。
"""

from __future__ import annotations

import pytest
from lxml import etree as ET

from twbpatch import DetachedModelError, TwbDrillPath, TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "drill.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sub-Category]" caption="サブカテゴリ"
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


def test_create_drill_path_matches_the_shape_tableau_writes(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)

    path = datasource.create_drill_path(
        name="商品階層", fields=["カテゴリ", "サブカテゴリ"]
    )

    assert isinstance(path, TwbDrillPath)
    element = datasource._resolve_element().xpath("./drill-paths/drill-path")[0]
    assert element.attrib == {"name": "商品階層"}
    # <field> は属性なし。テキストに内部 ID を階層順で並べる
    assert [child.tag for child in element] == ["field", "field"]
    assert [child.text for child in element] == ["[Category]", "[Sub-Category]"]
    assert not any(child.attrib for child in element)


def test_drill_paths_element_sits_before_folders(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    datasource.create_folder(name="Dim商品")

    datasource.create_drill_path(name="商品階層", fields=["カテゴリ", "サブカテゴリ"])

    order = [ET.QName(child).localname for child in datasource._resolve_element()]
    assert order.index("drill-paths") < order.index("folders-common")
    assert order.index("column") < order.index("drill-paths")


def test_id_and_name_are_the_same(tmp_path) -> None:
    """`<drill-path>` は name しか持たない。表示名が識別子を兼ねる。"""
    workbook = _workbook(tmp_path)
    path = _datasource(workbook).create_drill_path(
        name="商品階層", fields=["カテゴリ", "サブカテゴリ"]
    )

    assert path.id == "商品階層"
    assert path.name == path.id


def test_get_drill_paths_filters_by_name(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    datasource.create_drill_path(name="商品階層", fields=["カテゴリ", "サブカテゴリ"])
    datasource.create_drill_path(name="地域階層", fields=["地域", "カテゴリ"])

    assert [p.name for p in datasource.get_drill_paths()] == ["商品階層", "地域階層"]
    assert [p.name for p in datasource.get_drill_paths(name="地域階層")] == ["地域階層"]
    assert datasource.get_drill_paths(name="無い") == []

    with pytest.raises(ValueError, match="cannot be specified together"):
        datasource.get_drill_paths(id="商品階層", name="商品階層")


def test_get_fields_keeps_the_drill_order(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    # XML の出現順は カテゴリ → サブカテゴリ。階層は逆順で作る
    path = datasource.create_drill_path(
        name="商品階層", fields=["サブカテゴリ", "カテゴリ"]
    )

    assert [field.name for field in path.get_fields()] == ["サブカテゴリ", "カテゴリ"]
    assert path.field_ids == ["[Sub-Category]", "[Category]"]


def test_folder_keeps_the_hierarchy_not_its_fields(tmp_path) -> None:
    """階層に入れたフィールドは個別の folder-item を持たなくなる（実測）。"""
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    datasource.apply_field_config(
        {"Dim商品": {"カテゴリ": "カテゴリ", "サブカテゴリ": "サブカテゴリ"}}
    )

    datasource.create_drill_path(
        name="商品階層", fields=["カテゴリ", "サブカテゴリ"], folder="Dim商品"
    )

    folder_el = datasource.get_folders(name="Dim商品")[0]._resolve_element()
    items = [(item.get("name"), item.get("type")) for item in folder_el]
    assert items == [("商品階層", "drillpath")]


def test_update_renames_and_follows_the_folder_item(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    datasource.create_folder(name="Dim商品")
    path = datasource.create_drill_path(
        name="商品階層", fields=["カテゴリ", "サブカテゴリ"], folder="Dim商品"
    )

    path.update(name="商品ドリル")

    assert path.name == "商品ドリル"
    folder_el = datasource.get_folders(name="Dim商品")[0]._resolve_element()
    assert [item.get("name") for item in folder_el] == ["商品ドリル"]


def test_update_replaces_the_fields(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    path = _datasource(workbook).create_drill_path(
        name="商品階層", fields=["カテゴリ", "サブカテゴリ"]
    )

    path.update(fields=["地域", "カテゴリ", "サブカテゴリ"])

    assert path.field_ids == ["[Region]", "[Category]", "[Sub-Category]"]


def test_delete_removes_the_hierarchy_but_keeps_the_fields(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    datasource.create_folder(name="Dim商品")
    path = datasource.create_drill_path(
        name="商品階層", fields=["カテゴリ", "サブカテゴリ"], folder="Dim商品"
    )

    path.delete()

    assert datasource.get_drill_paths() == []
    assert [f.name for f in datasource.get_fields(name="カテゴリ")] == ["カテゴリ"]
    folder_el = datasource.get_folders(name="Dim商品")[0]._resolve_element()
    assert list(folder_el) == []
    with pytest.raises(DetachedModelError):
        path.name


def test_a_drill_path_needs_two_fields(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="at least two fields"):
        _datasource(workbook).create_drill_path(name="商品階層", fields=["カテゴリ"])


def test_the_same_field_cannot_appear_twice(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    with pytest.raises(ValueError, match="listed more than once"):
        _datasource(workbook).create_drill_path(
            name="商品階層", fields=["カテゴリ", "カテゴリ"]
        )


def test_a_duplicate_name_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    datasource.create_drill_path(name="商品階層", fields=["カテゴリ", "サブカテゴリ"])

    with pytest.raises(ValueError, match="already exists"):
        datasource.create_drill_path(name="商品階層", fields=["地域", "カテゴリ"])


def test_a_workbook_with_a_created_drill_path_saves(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = _datasource(workbook)
    datasource.create_folder(name="Dim商品")
    datasource.create_drill_path(
        name="商品階層", fields=["カテゴリ", "サブカテゴリ"], folder="Dim商品"
    )
    target = tmp_path / "out.twb"

    workbook.save(str(target), validate=True, overwrite=True)

    saved = target.read_text(encoding="utf-8")
    assert "<drill-path name=" in saved
    assert 'type="drillpath"' in saved
