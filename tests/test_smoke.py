from twbpatch import TwbWorkbook


def test_create_calculated_field(tmp_path):
    wb = TwbWorkbook.open("tests/sample_minimal.twb")
    col = wb.create_calculated_field(
        datasource="売上データ",
        caption="粗利率",
        formula="SUM([粗利]) / SUM([売上])",
        folder="KPI",
    )
    assert col.name.startswith("[Calculation_")
    assert col.caption == "粗利率"
    assert col.formula == "SUM([粗利]) / SUM([売上])"
    assert col.raw_formula == "SUM([Profit]) / SUM([Sales])"
    assert col.folder == "KPI"
    out = tmp_path / "out.twb"
    wb.save(str(out), overwrite=True)
    assert out.exists()


def test_rename_field_and_reset_caption():
    wb = TwbWorkbook.open("tests/sample_minimal.twb")

    renamed = wb.rename_field("売上データ", "売上", "売上金額")
    assert renamed.caption == "売上金額"
    assert renamed.id == "[Sales]"

    reset = wb.reset_field_caption("売上データ", "売上金額")
    assert reset.caption == "Sales"
    assert reset.id == "[Sales]"


def test_move_field_to_folder_and_remove():
    wb = TwbWorkbook.open("tests/sample_minimal.twb")

    moved = wb.move_field_to_folder("売上データ", "売上", "売上系")
    assert moved.folder == "売上系"
    root = wb.tree.getroot()
    assert not root.xpath("/workbook/datasources/datasource/folder")
    assert root.xpath(
        '/workbook/datasources/datasource/folders-common/folder[@name="売上系"]/folder-item[@name="[Sales]" and @type="field"]'
    )

    removed = wb.remove_field_from_folder("売上データ", "売上")
    assert removed.folder is None
