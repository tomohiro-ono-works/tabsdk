"""投影モデルが `export_json()` を壊さないこと（仕様 §10）。

`TwbReferenceLine` / `TwbWorksheetFilter` / `TwbFilterControl` は dataclass ではないので
`asdict()` で変換できず、そのまま戻り値に残っていた。JSON へ落とすと
`not JSON serializable` になり、非公開コンテキストが混ざる恐れもあった。

`tests/sample_minimal.twb` にはワークシートが無いため、既存のテストを素通りしていた。
"""

from __future__ import annotations

import json

from twbpatch import TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def _workbook_with_projections():
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="Sheet1")
    placement = worksheet.add_field(
        field=datasource.get_fields(name="売上")[0], shelf="rows"
    )
    worksheet.add_reference_line(field=placement, formula="median")
    worksheet.add_filter(field=datasource.get_fields(name="粗利")[0])

    dashboard = workbook.create_dashboard(name="ダッシュボード")
    container = dashboard.create_container(direction="vertical")
    container.add_worksheet(worksheet, show_title=False)
    container.add_filter(field=worksheet.get_fields(name="粗利")[0])
    return workbook


def test_export_json_is_serializable_with_reference_lines_and_filters() -> None:
    workbook = _workbook_with_projections()

    text = json.dumps(workbook.export_json(), ensure_ascii=False)

    assert "TwbReferenceLine" not in text
    assert "_context" not in text


def test_export_json_keeps_no_caption_key() -> None:
    workbook = _workbook_with_projections()

    data = workbook.export_json()
    line = data["worksheets"][0]["reference_lines"][0]

    # axis_caption / value_caption は axis_name / value_name へ正規化される
    assert "axis_name" in line and "value_name" in line
    assert not [key for key in line if "caption" in key]


def test_export_json_carries_the_projection_values() -> None:
    workbook = _workbook_with_projections()

    data = workbook.export_json()
    line = data["worksheets"][0]["reference_lines"][0]
    assert line["formula"] == "median"
    assert line["axis_name"] == "売上"

    filters = data["worksheets"][0]["filters"]
    assert [item["name"] for item in filters] == ["粗利"]

    controls = data["dashboards"][0]["filter_controls"]
    assert [item["field"] for item in controls] == ["粗利"]


def test_export_html_survives_a_workbook_with_projections(tmp_path) -> None:
    """`export_html()` は `export_json()` の上に建っている。"""
    workbook = _workbook_with_projections()

    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "TwbReferenceLine" not in html
    assert "_context" not in html
