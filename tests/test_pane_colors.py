"""B-2: `TwbPane.set_categorical_colors()` / `set_continuous_colors()` を直接検証する。

どちらも `draw_bar()` などの経由でしか実行されておらず、異常系が確かめられていなかった。

- 不連続の色分けは `<style-rule element="mark">` の `<encoding type="palette">` に
  ラベルと色の対で書かれ、**データソース側の `<style>` にも同じ内容が写る**
- 連続の色分けは `/workbook/preferences` に `<color-palette>` を作り、
  `<encoding type="interpolated" palette="...">` から名前で参照する
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "colors.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _pane_with_color(tmp_path, field_name="カテゴリ"):
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")
    worksheet.add_field(
        field=datasource.get_fields(name="カテゴリ")[0], shelf="rows"
    )
    pane = worksheet.get_panes()[0]
    colored = pane.add_field(
        field=datasource.get_fields(name=field_name)[0], encoding="color"
    )
    return workbook, worksheet, pane, colored


def _mark_encodings(worksheet):
    return worksheet._resolve_element().xpath(
        ".//style-rule[@element='mark']/encoding[@attr='color']"
    )


# --- 不連続（パレット） -------------------------------------------------------


def test_categorical_colors_are_written_as_label_to_color_pairs(tmp_path) -> None:
    workbook, worksheet, pane, colored = _pane_with_color(tmp_path)

    result = pane.set_categorical_colors(
        colored, {"家具": "#4E79A7", "事務用品": "#F28E2B"}
    )

    assert result is pane
    encoding = _mark_encodings(worksheet)[0]
    assert encoding.get("type") == "palette"
    assert [m.get("to") for m in encoding] == ["#4E79A7", "#F28E2B"]
    # ラベルはダブルクォート込みの文字列で書く
    assert [m[0].text for m in encoding] == ['"家具"', '"事務用品"']
    assert workbook.is_dirty is True


def test_the_colors_come_back_through_the_getter(tmp_path) -> None:
    _, _, pane, colored = _pane_with_color(tmp_path)

    pane.set_categorical_colors(colored, {"家具": "#4E79A7"})

    assert pane.get_categorical_colors(colored) == {"家具": "#4E79A7"}


def test_the_datasource_style_gets_the_same_content(tmp_path) -> None:
    workbook, _, pane, colored = _pane_with_color(tmp_path)

    pane.set_categorical_colors(colored, {"家具": "#4E79A7"})

    datasource_el = workbook.get_datasources()[0]._resolve_element()
    encoding = datasource_el.xpath(
        "./style/style-rule[@element='mark']/encoding[@attr='color']"
    )[0]
    assert [m.get("to") for m in encoding] == ["#4E79A7"]


def test_setting_them_again_replaces_the_previous_entry(tmp_path) -> None:
    _, worksheet, pane, colored = _pane_with_color(tmp_path)

    pane.set_categorical_colors(colored, {"家具": "#4E79A7"})
    pane.set_categorical_colors(colored, {"家具": "#E15759", "家電": "#59A14F"})

    assert len(_mark_encodings(worksheet)) == 1
    assert pane.get_categorical_colors(colored) == {"家具": "#E15759", "家電": "#59A14F"}


def test_a_field_without_the_color_encoding_is_rejected(tmp_path) -> None:
    workbook, worksheet, pane, _ = _pane_with_color(tmp_path)
    labelled = pane.add_field(
        field=workbook.get_datasources()[0].get_fields(name="売上")[0],
        encoding="label",
        aggregation="sum",
    )

    with pytest.raises(ValueError, match="color encoding"):
        pane.set_categorical_colors(labelled, {"家具": "#4E79A7"})


def test_a_field_from_another_pane_is_rejected(tmp_path) -> None:
    workbook, _, _, colored = _pane_with_color(tmp_path)
    other_pane = workbook.create_worksheet(name="別シート").get_panes()[0]

    with pytest.raises(ValueError, match="must belong to the pane"):
        other_pane.set_categorical_colors(colored, {"家具": "#4E79A7"})


def test_an_empty_color_map_is_rejected(tmp_path) -> None:
    _, _, pane, colored = _pane_with_color(tmp_path)

    with pytest.raises(ValueError, match="non-empty dict"):
        pane.set_categorical_colors(colored, {})


def test_a_color_that_is_not_rrggbb_is_rejected(tmp_path) -> None:
    _, _, pane, colored = _pane_with_color(tmp_path)

    with pytest.raises(ValueError, match="#RRGGBB"):
        pane.set_categorical_colors(colored, {"家具": "red"})


def test_an_empty_label_is_rejected(tmp_path) -> None:
    _, _, pane, colored = _pane_with_color(tmp_path)

    with pytest.raises(ValueError, match="non-empty strings"):
        pane.set_categorical_colors(colored, {"": "#4E79A7"})


def test_a_bare_field_is_rejected(tmp_path) -> None:
    workbook, _, pane, _ = _pane_with_color(tmp_path)
    field = workbook.get_datasources()[0].get_fields(name="カテゴリ")[0]

    with pytest.raises(TypeError, match="TwbWorksheetField"):
        pane.set_categorical_colors(field, {"家具": "#4E79A7"})


# --- 連続（補間パレット） -----------------------------------------------------


def test_continuous_colors_create_a_palette_in_preferences(tmp_path) -> None:
    workbook, worksheet, pane, colored = _pane_with_color(tmp_path, field_name="売上")

    result = pane.set_continuous_colors(
        colored, min_color="#4E79A7", mid_color="#FFFFFF", max_color="#E15759"
    )

    assert result is pane
    palettes = workbook.tree.getroot().xpath("./preferences/color-palette")
    assert len(palettes) == 1
    assert palettes[0].get("type") == "ordered-diverging"
    assert [c.text for c in palettes[0]] == ["#4e79a7", "#ffffff", "#e15759"]

    encoding = _mark_encodings(worksheet)[0]
    assert encoding.get("type") == "interpolated"
    assert encoding.get("palette") == palettes[0].get("name")


def test_setting_them_again_reuses_the_same_palette(tmp_path) -> None:
    workbook, worksheet, pane, colored = _pane_with_color(tmp_path, field_name="売上")

    pane.set_continuous_colors(
        colored, min_color="#4E79A7", mid_color="#FFFFFF", max_color="#E15759"
    )
    pane.set_continuous_colors(
        colored, min_color="#000000", mid_color="#888888", max_color="#FFFFFF"
    )

    palettes = workbook.tree.getroot().xpath("./preferences/color-palette")
    assert len(palettes) == 1
    assert [c.text for c in palettes[0]] == ["#000000", "#888888", "#ffffff"]
    assert len(_mark_encodings(worksheet)) == 1


def test_a_continuous_color_that_is_not_rrggbb_is_rejected(tmp_path) -> None:
    _, _, pane, colored = _pane_with_color(tmp_path, field_name="売上")

    with pytest.raises(ValueError, match="#RRGGBB"):
        pane.set_continuous_colors(
            colored, min_color="#4E79A7", mid_color="white", max_color="#E15759"
        )


def test_a_bare_field_is_rejected_for_continuous_colors(tmp_path) -> None:
    workbook, _, pane, _ = _pane_with_color(tmp_path, field_name="売上")
    field = workbook.get_datasources()[0].get_fields(name="売上")[0]

    with pytest.raises(TypeError, match="TwbWorksheetField"):
        pane.set_continuous_colors(
            field, min_color="#4E79A7", mid_color="#FFFFFF", max_color="#E15759"
        )


def test_a_field_from_another_pane_is_rejected_for_continuous_colors(tmp_path) -> None:
    workbook, _, _, colored = _pane_with_color(tmp_path, field_name="売上")
    other_pane = workbook.create_worksheet(name="別シート").get_panes()[0]

    # Pane の id はシート内の連番なので、シートを見ないと他シートの Pane と一致する
    with pytest.raises(ValueError, match="must belong to the pane"):
        other_pane.set_continuous_colors(
            colored, min_color="#4E79A7", mid_color="#FFFFFF", max_color="#E15759"
        )
