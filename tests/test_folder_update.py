"""L-1: フォルダ名を変えられるようにする。

`TwbFolder` は `delete()` と `get_fields()` しか持たず、他の接続型モデルが
すべて備える `update()` が無かった（仕様 §3.3）。

`<folder>` は `name` しか持たず、それが識別子と表示名を兼ねる。
`<folder-item>` はフィールドと階層を指しているだけなので、改名の追随は要らない。
"""

from __future__ import annotations

import pytest

from twbpatch import DetachedModelError, TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def _datasource(workbook):
    return workbook.get_datasources()[0]


def test_update_renames_the_folder() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = _datasource(workbook)
    folder = datasource.create_folder(name="KPI")
    datasource.get_fields(name="売上")[0].move_to_folder(folder)

    assert folder.update(name="指標") is folder

    assert folder.id == "指標"
    assert folder.name == "指標"
    assert [item.name for item in datasource.get_folders()] == ["指標"]
    assert workbook.is_dirty is True


def test_the_fields_stay_in_the_folder() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = _datasource(workbook)
    folder = datasource.create_folder(name="KPI")
    field = datasource.get_fields(name="売上")[0]
    field.move_to_folder(folder)

    folder.update(name="指標")

    assert [item.name for item in folder.get_fields()] == ["売上"]
    assert field.folder is not None and field.folder.name == "指標"


def test_the_old_name_no_longer_resolves() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = _datasource(workbook)
    datasource.create_folder(name="KPI").update(name="指標")

    assert datasource.get_folders(name="KPI") == []
    assert [f.name for f in datasource.get_folders(name="指標")] == ["指標"]


def test_a_duplicate_name_is_rejected() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = _datasource(workbook)
    datasource.create_folder(name="KPI")
    other = datasource.create_folder(name="指標")

    with pytest.raises(ValueError, match="folder name already exists"):
        other.update(name="KPI")

    assert other.name == "指標"


def test_an_empty_name_is_rejected() -> None:
    folder = _datasource(TwbWorkbook.open(SAMPLE)).create_folder(name="KPI")

    with pytest.raises(ValueError, match="name must not be empty"):
        folder.update(name="  ")


def test_the_same_name_is_a_no_op() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    folder = _datasource(workbook).create_folder(name="KPI")

    before = workbook.is_dirty
    folder.update(name="KPI")

    assert folder.name == "KPI"
    assert workbook.is_dirty is before


def test_update_without_arguments_changes_nothing() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    folder = _datasource(workbook).create_folder(name="KPI")

    assert folder.update() is folder
    assert folder.name == "KPI"


def test_a_deleted_folder_cannot_be_renamed() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    folder = _datasource(workbook).create_folder(name="KPI")
    folder.delete()

    with pytest.raises(DetachedModelError):
        folder.update(name="指標")
