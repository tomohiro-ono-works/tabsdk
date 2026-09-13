"""軸の範囲・反転、線の書式、線の補間。

XML の形は、Tableau で手作りした KPI ツリーのエッジ用シート（2026-09-13 実測）に合わせている。
"""

import pytest

from twbpatch import TwbWorkbook


DATASOURCE_ID = "federated.0edge00000000000000000000000"
DATASOURCE_NAME = "エッジ"


def _edge_sheet(tmp_path):
    path = tmp_path / "edge.twb"
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="{DATASOURCE_ID}" caption="{DATASOURCE_NAME}">
      <column name="[edge]" caption="Edge" datatype="string" role="dimension" type="nominal" />
      <column name="[x]" caption="X" datatype="integer" role="measure" type="quantitative" />
      <column name="[y]" caption="Y" datatype="integer" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))
    worksheet = workbook.create_worksheet(name="ツリーエッジ")
    y = worksheet.add_field(
        field=(DATASOURCE_NAME, "Y"), shelf="rows", aggregation="sum", discrete=False
    )
    x = worksheet.add_field(
        field=(DATASOURCE_NAME, "X"), shelf="columns", aggregation="sum", discrete=False
    )
    return workbook, worksheet, x, y


def _table_style_rules(workbook):
    return workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='ツリーエッジ']/table/style/style-rule"
    )


def _axis_children(workbook):
    rules = [rule for rule in _table_style_rules(workbook) if rule.get("element") == "axis"]
    return [] if not rules else [(child.tag, dict(child.attrib)) for child in rules[0]]


def test_set_axis_range_writes_fixed_reversed_space_before_formats(tmp_path) -> None:
    workbook, worksheet, _, y = _edge_sheet(tmp_path)
    worksheet.set_axis_visibility(field=y, visible=False)

    worksheet.set_axis_range(field=y, min_value=-1, max_value=5, reverse=True)

    tag, attrib = _axis_children(workbook)[0]
    assert tag == "encoding"
    assert list(attrib.items()) == [
        ("attr", "space"),
        ("class", "0"),
        ("field", f"[{DATASOURCE_ID}].[sum:y:qk]"),
        ("field-type", "quantitative"),
        ("max", "5"),
        ("min", "-1"),
        ("range-type", "fixed"),
        ("reverse", "true"),
        ("scope", "rows"),
        ("type", "space"),
    ]
    assert _axis_children(workbook)[1][0] == "format"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_set_axis_range_reverse_only_matches_tableau(tmp_path) -> None:
    workbook, worksheet, _, y = _edge_sheet(tmp_path)

    worksheet.set_axis_range(field=y, reverse=True)

    assert _axis_children(workbook) == [(
        "encoding",
        {
            "attr": "space",
            "class": "0",
            "field": f"[{DATASOURCE_ID}].[sum:y:qk]",
            "field-type": "quantitative",
            "reverse": "true",
            "scope": "rows",
            "type": "space",
        },
    )]


def test_set_axis_range_without_options_restores_automatic_range(tmp_path) -> None:
    workbook, worksheet, x, y = _edge_sheet(tmp_path)
    worksheet.set_axis_visibility(field=x, visible=False)
    worksheet.set_axis_range(field=x, min_value=0, max_value=2)

    worksheet.set_axis_range(field=x)

    assert [tag for tag, _ in _axis_children(workbook)] == ["format"]


def test_set_axis_range_rejects_invalid_arguments_without_changes(tmp_path) -> None:
    workbook, worksheet, _, y = _edge_sheet(tmp_path)
    filter_field = worksheet.add_filter(field=(DATASOURCE_NAME, "Edge"))
    before = _axis_children(workbook)

    with pytest.raises(ValueError, match="together"):
        worksheet.set_axis_range(field=y, min_value=0)
    with pytest.raises(ValueError, match="less than"):
        worksheet.set_axis_range(field=y, min_value=2, max_value=2)
    with pytest.raises(TypeError, match="number"):
        worksheet.set_axis_range(field=y, min_value=True, max_value=2)
    with pytest.raises(ValueError, match="rows or columns"):
        worksheet.set_axis_range(field=filter_field, reverse=True)

    assert _axis_children(workbook) == before


def test_update_lines_visible_toggles_all_line_formats(tmp_path) -> None:
    workbook, worksheet, _, _ = _edge_sheet(tmp_path)
    assert worksheet.lines_visible is True

    worksheet.update(lines_visible=False)

    rules = _table_style_rules(workbook)
    assert [rule.get("element") for rule in rules] == [
        "axis", "dropline", "refline", "gridline", "zeroline",
    ]
    for rule in rules:
        values = {item.get("attr"): item.get("value") for item in rule}
        assert values["stroke-size"] == "0"
        assert values["line-visibility"] == "off"
    assert {item.get("attr"): item.get("value") for item in rules[0]}["tick-color"] == "#00000000"
    assert worksheet.lines_visible is False

    worksheet.update(lines_visible=True)

    assert _table_style_rules(workbook) == []
    assert worksheet.lines_visible is True
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_update_lines_visible_rejects_non_bool(tmp_path) -> None:
    _, worksheet, _, _ = _edge_sheet(tmp_path)

    with pytest.raises(TypeError, match="lines_visible"):
        worksheet.update(lines_visible="off")


def test_pane_line_interpolation_step_and_back(tmp_path) -> None:
    workbook, worksheet, _, _ = _edge_sheet(tmp_path)
    pane = worksheet.get_panes()[0]
    assert pane.line_interpolation == "linear"

    pane.update(mark_type="line", line_interpolation="step")

    assert pane.line_interpolation == "step"
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='ツリーエッジ']/table/panes/pane/style"
        "/style-rule[@element='mark']/format[@attr='line-interpolation']/@value"
    ) == ["step"]

    pane.update(line_interpolation="linear")

    assert pane.line_interpolation == "linear"
    with pytest.raises(ValueError, match="linear or step"):
        pane.update(line_interpolation="jump")
    assert not [message for message in workbook.validate() if message.severity == "error"]
