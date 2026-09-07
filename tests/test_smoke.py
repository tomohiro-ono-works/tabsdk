"""ひととおりの編集が通ることの煙テスト。

E-2（2026-09-07）で `TwbWorkbook` の旧メソッドを削除したため、新 API で書き直した。
"""

from twbpatch import TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def _datasource(workbook):
    return workbook.get_datasources(name="売上データ")[0]


def test_create_calculated_field(tmp_path):
    wb = TwbWorkbook.open(SAMPLE)
    field = _datasource(wb).create_calculated_field(
        name="粗利率",
        formula="SUM([粗利]) / SUM([売上])",
        folder="KPI",
        number_format="%",
        create_folder_if_missing=True,
    )

    assert field.id.startswith("[Calculation_")
    assert field.name == "粗利率"
    assert field.formula == "SUM([粗利]) / SUM([売上])"
    assert field.raw_formula == "SUM([Profit]) / SUM([Sales])"
    assert field.folder is not None and field.folder.name == "KPI"
    assert wb.tree.xpath(
        'string(/workbook/datasources/datasource/column[@caption="粗利率"]/@default-format)'
    ) == "p0%"

    out = tmp_path / "out.twb"
    wb.save(str(out), overwrite=True)
    assert out.exists()


def test_rename_field_and_reset_caption():
    wb = TwbWorkbook.open(SAMPLE)
    field = _datasource(wb).get_fields(name="売上")[0]

    field.update(name="売上金額")
    assert field.name == "売上金額"
    assert field.id == "[Sales]"

    # caption を外すと `@name` 由来の既定表示名へ戻る
    field.update(name=None)
    assert field.name == "Sales"
    assert field.id == "[Sales]"


def test_move_field_to_folder_and_remove():
    wb = TwbWorkbook.open(SAMPLE)
    datasource = _datasource(wb)
    field = datasource.get_fields(name="売上")[0]

    field.move_to_folder("売上系", create_folder_if_missing=True)

    assert field.folder is not None and field.folder.name == "売上系"
    root = wb.tree.getroot()
    assert not root.xpath("/workbook/datasources/datasource/folder")
    assert root.xpath(
        '/workbook/datasources/datasource/folders-common/folder[@name="売上系"]'
        '/folder-item[@name="[Sales]" and @type="field"]'
    )

    field.remove_from_folder()
    assert field.folder is None
