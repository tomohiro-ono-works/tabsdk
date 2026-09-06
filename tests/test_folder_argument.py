"""`folder=` を受け取るメソッドが同じ書き味になっていることを固定する。

以前は `create_calculated_field()` だけが文字列を受け付けず、仕様書とサンプルの
とおりに書くと AttributeError で落ちていた。解決処理が各メソッドへコピーされて
いたのが原因。`TwbDatasource._resolve_folder()` に一本化した。
"""

from __future__ import annotations

import pytest

from twbpatch import NotFoundError, TwbWorkbook


def _datasource(tmp_path):
    path = tmp_path / "folder.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
      <column name="[Order ID]" caption="注文ID" datatype="string" role="dimension" type="nominal" />
      <column name="[YearCategory]" caption="当年昨年区分" datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))
    datasource = workbook.get_datasources()[0]
    datasource.create_folder(name="Measure")
    return workbook, datasource


def test_create_calculated_field_accepts_a_folder_name(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)

    field = datasource.create_calculated_field(
        name="粗利率",
        formula="SUM([利益]) / SUM([売上])",
        folder="Measure",
    )

    assert field.folder is not None
    assert field.folder.name == "Measure"


def test_folder_name_and_object_give_the_same_result(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)
    folder = datasource.get_folders(name="Measure")[0]

    by_name = datasource.create_calculated_field(
        name="A", formula="SUM([売上])", folder="Measure"
    )
    by_object = datasource.create_calculated_field(
        name="B", formula="SUM([売上])", folder=folder
    )

    assert by_name.folder.id == by_object.folder.id


def test_every_folder_argument_accepts_a_name(tmp_path) -> None:
    """3 つのメソッドが同じ書き味であることを固定する。"""
    _, datasource = _datasource(tmp_path)

    single = datasource.create_calculated_field(
        name="単数形", formula="SUM([売上])", folder="Measure"
    )
    plural = datasource.create_calculated_fields(
        {"複数形": "COUNTD([注文ID])"}, folder="Measure"
    )
    yoy = datasource.create_yoy_calculated_fields(
        metric="売上", year_category="当年昨年区分", folder="Measure"
    )

    assert single.folder.name == "Measure"
    assert plural[0].folder.name == "Measure"
    assert all(field.folder.name == "Measure" for field in yoy)


@pytest.mark.parametrize(
    "method",
    ["create_calculated_field", "create_calculated_fields", "create_yoy_calculated_fields"],
)
@pytest.mark.parametrize(
    "folder, error",
    [
        ("存在しないフォルダ", NotFoundError),
        ("   ", ValueError),
        (1, TypeError),
    ],
)
def test_bad_folder_arguments_fail_the_same_way(tmp_path, method, folder, error) -> None:
    _, datasource = _datasource(tmp_path)
    arguments = {
        "create_calculated_field": dict(name="X", formula="SUM([売上])"),
        "create_calculated_fields": dict(calculations={"X": "SUM([売上])"}),
        "create_yoy_calculated_fields": dict(metric="売上", year_category="当年昨年区分"),
    }[method]

    with pytest.raises(error):
        getattr(datasource, method)(folder=folder, **arguments)


def test_folder_from_another_datasource_is_rejected(tmp_path) -> None:
    _, datasource = _datasource(tmp_path)
    other_path = tmp_path / "other"
    other_path.mkdir()
    _, other = _datasource(other_path)
    other_folder = other.get_folders(name="Measure")[0]

    with pytest.raises(ValueError, match="same datasource"):
        datasource.create_calculated_field(
            name="X", formula="SUM([売上])", folder=other_folder
        )
