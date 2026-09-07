"""E-2 の決定: 無いフォルダは既定でエラー。`create_folder_if_missing=True` で作る。

旧 `TwbWorkbook.create_calculated_field(folder=)` はフォルダを黙って作っていた
（`create_if_missing=True`）。新 API は `NotFoundError` で、旧を消すとその楽さが
無くなる。**既定はエラーのまま、作りたいときだけフラグで明示する**（2026-09-07 決定）。

`folder=` の解決は `TwbDatasource._resolve_folder()` の 1 か所なので、
`folder=` を受け取る 6 メソッドすべてで同じように効く。
"""

from __future__ import annotations

import pytest

from twbpatch import NotFoundError, TwbWorkbook


SOURCE = """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[SubCategory]" caption="サブカテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Year]" caption="年区分"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
</workbook>
"""


def _datasource(tmp_path):
    path = tmp_path / "folder.twb"
    path.write_text(SOURCE, encoding="utf-8")
    workbook = TwbWorkbook.open(str(path))
    return workbook, workbook.get_datasources()[0]


def _folder_names(datasource):
    return [folder.name for folder in datasource.get_folders()]


# --- 既定はエラー -------------------------------------------------------------


def test_create_calculated_field_rejects_a_missing_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    with pytest.raises(NotFoundError, match="folder not found: KPI"):
        datasource.create_calculated_field(
            name="利益率", formula="[Sales] * 0.1", folder="KPI"
        )

    assert _folder_names(datasource) == []


def test_move_to_folder_rejects_a_missing_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    with pytest.raises(NotFoundError, match="folder not found: KPI"):
        datasource.get_fields(name="売上")[0].move_to_folder("KPI")

    assert _folder_names(datasource) == []


def test_create_group_rejects_a_missing_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    with pytest.raises(NotFoundError, match="folder not found"):
        datasource.create_group(
            field="カテゴリ", groups={"家具": ["Furniture"]}, folder="Dim商品"
        )


def test_create_drill_path_rejects_a_missing_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    with pytest.raises(NotFoundError, match="folder not found"):
        datasource.create_drill_path(
            name="商品階層", fields=["カテゴリ", "サブカテゴリ"], folder="Dim商品"
        )


# --- フラグを立てると作る -----------------------------------------------------


def test_create_calculated_field_can_make_the_folder(tmp_path) -> None:
    workbook, datasource = _datasource(tmp_path)

    field = datasource.create_calculated_field(
        name="利益率",
        formula="[Sales] * 0.1",
        folder="KPI",
        create_folder_if_missing=True,
    )

    assert _folder_names(datasource) == ["KPI"]
    assert field.folder is not None and field.folder.name == "KPI"
    assert workbook.is_dirty is True


def test_move_to_folder_can_make_the_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    field = datasource.get_fields(name="売上")[0]
    field.move_to_folder("KPI", create_folder_if_missing=True)

    assert _folder_names(datasource) == ["KPI"]
    assert field.folder is not None and field.folder.name == "KPI"


def test_create_group_can_make_the_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    field = datasource.create_group(
        field="カテゴリ",
        groups={"家具": ["Furniture"]},
        folder="Dim商品",
        create_folder_if_missing=True,
    )

    assert _folder_names(datasource) == ["Dim商品"]
    assert field.folder is not None and field.folder.name == "Dim商品"


def test_create_drill_path_can_make_the_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    datasource.create_drill_path(
        name="商品階層",
        fields=["カテゴリ", "サブカテゴリ"],
        folder="Dim商品",
        create_folder_if_missing=True,
    )

    assert _folder_names(datasource) == ["Dim商品"]
    folder = datasource.get_folders(name="Dim商品")[0]
    assert folder._resolve_element().xpath("./folder-item/@type") == ["drillpath"]


def test_bulk_creation_makes_the_folder_once(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    datasource.create_calculated_fields(
        calculations={"利益": "[Sales] * 0.1", "原価": "[Sales] * 0.9"},
        folder="KPI",
        create_folder_if_missing=True,
    )

    assert _folder_names(datasource) == ["KPI"]
    assert sorted(f.name for f in datasource.get_folders()[0].get_fields()) == [
        "利益",
        "原価",
    ]


def test_yoy_creation_can_make_the_folder(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    datasource.create_yoy_calculated_fields(
        metric="売上", year_category="年区分", folder="KPI", create_folder_if_missing=True
    )

    assert _folder_names(datasource) == ["KPI"]


# --- 既存フォルダとオブジェクト渡し -------------------------------------------


def test_an_existing_folder_is_reused_not_duplicated(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)
    datasource.create_folder(name="KPI")

    datasource.create_calculated_field(
        name="利益率",
        formula="[Sales] * 0.1",
        folder="KPI",
        create_folder_if_missing=True,
    )

    assert _folder_names(datasource) == ["KPI"]


def test_a_folder_object_ignores_the_flag(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)
    folder = datasource.create_folder(name="KPI")

    field = datasource.create_calculated_field(
        name="利益率", formula="[Sales] * 0.1", folder=folder
    )

    # オブジェクトはすでに実在するので、フラグを立てる必要がない
    assert field.folder is not None and field.folder.name == "KPI"
    assert _folder_names(datasource) == ["KPI"]


def test_an_empty_folder_name_is_still_rejected(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    with pytest.raises(ValueError, match="folder must not be empty"):
        datasource.create_calculated_field(
            name="利益率",
            formula="[Sales] * 0.1",
            folder="   ",
            create_folder_if_missing=True,
        )
