import pytest

from twbpatch import TwbWorkbook

DATASOURCE_NAME = "DS"


def _info_workbook(tmp_path):
    path = tmp_path / "info.twb"
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="{DATASOURCE_NAME}">
      <column name="[A]" caption="A" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_draw_info_creates_the_dummy_field_and_icon_mark(tmp_path) -> None:
    """アイコン + カスタムツールヒントだけのシートを作る（`info` シートを実測）。"""
    workbook = _info_workbook(tmp_path)

    worksheet = workbook.draw_info(name="info", text="説明文です", icon="setting")

    assert worksheet.get_panes()[0].mark_type == "shape"
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    key_fields = datasource.get_fields(name="インフォメーション_key")
    assert len(key_fields) == 1
    assert key_fields[0].formula == "STR(1)"
    assert key_fields[0].role == "dimension"

    pane = worksheet._resolve_element().xpath("./table/panes/pane")[0]
    style = pane.xpath("./style/style-rule[@element='mark']/format[@attr='shape']")
    assert style[0].get("value") == (
        "webinfo/settings_120dp_1F1F1F_FILL0_wght400_GRAD0_opsz48.png"
    )
    color = pane.xpath("./style/style-rule[@element='mark']/format[@attr='mark-color']")
    assert color[0].get("value") == "#e15759"

    # 行・列に何も置かない Shape マークは、実測した手作業のシートと同じく
    # `mark-sizing-setting="marks-scaling-off"` と、ツールヒントの ATTR 集計が要る
    # （2026-09-24、ユーザーの指摘）。
    sizing = pane.xpath("./mark-sizing")
    assert sizing[0].get("mark-sizing-setting") == "marks-scaling-off"
    tooltip_column = pane.xpath("./encodings/tooltip")[0].get("column")
    assert tooltip_column.startswith("[ds1].[attr:")

    tooltip = pane.xpath("./customized-tooltip/formatted-text/run")
    assert len(tooltip) == 2
    assert tooltip[0].get("bold") == "true"
    assert tooltip[0].text == "説明"
    assert tooltip[1].text == "\n説明文です"

    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_info_rejects_an_unknown_icon(tmp_path) -> None:
    workbook = _info_workbook(tmp_path)

    with pytest.raises(ValueError, match="icon must be one of"):
        workbook.draw_info(name="info", text="説明文です", icon="unknown")


def test_draw_info_requires_non_empty_text(tmp_path) -> None:
    workbook = _info_workbook(tmp_path)

    with pytest.raises(ValueError, match="text must not be empty"):
        workbook.draw_info(name="info", text="")


def test_draw_info_uses_a_custom_heading_and_color(tmp_path) -> None:
    workbook = _info_workbook(tmp_path)

    worksheet = workbook.draw_info(
        name="info", text="本文", icon="info", heading="ヒント", color="#123456"
    )

    pane = worksheet._resolve_element().xpath("./table/panes/pane")[0]
    tooltip = pane.xpath("./customized-tooltip/formatted-text/run")
    assert tooltip[0].text == "ヒント"
    color = pane.xpath("./style/style-rule[@element='mark']/format[@attr='mark-color']")
    assert color[0].get("value") == "#123456"


def test_draw_info_shares_the_dummy_field_across_icons(tmp_path) -> None:
    """データソースにつき 1 つのダミーフィールドを複数のアイコンで使い回す
    （waterfall の共有連番と同じ考え方、2026-09-23）。"""
    workbook = _info_workbook(tmp_path)

    workbook.draw_info(name="info1", text="1つ目", icon="info")
    workbook.draw_info(name="info2", text="2つ目", icon="attention")

    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    assert len(datasource.get_fields(name="インフォメーション_key")) == 1


def test_draw_info_requires_datasource_when_ambiguous(tmp_path) -> None:
    path = tmp_path / "multi.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="DS1">
      <column name="[A]" caption="A" datatype="real" role="measure" type="quantitative" />
    </datasource>
    <datasource name="ds2" caption="DS2">
      <column name="[B]" caption="B" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))

    with pytest.raises(ValueError, match="datasource is required"):
        workbook.draw_info(name="info", text="説明文です")

    datasource = workbook.get_datasources(name="DS1")[0]
    worksheet = workbook.draw_info(datasource, name="info", text="説明文です")
    assert worksheet.get_panes()[0].mark_type == "shape"


def test_draw_info_puts_the_dummy_field_in_the_given_folder(tmp_path) -> None:
    workbook = _info_workbook(tmp_path)

    workbook.draw_info(name="info", text="説明文です", folder="43_インフォメーション")

    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    field = datasource.get_fields(name="インフォメーション_key")[0]
    assert field.folder.name == "43_インフォメーション"
