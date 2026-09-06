"""参照線の対象 Pane を明示させる（仕様 §6.7）。

以前は `panes[0]` へ暗黙に引いていた。Pane が 1 つなら正しく動くが、二重軸などで
Pane が複数あるワークシートでは意図しない側に線が出て、気づく手がかりも無かった。
"""

from __future__ import annotations

import pytest
from lxml import etree as ET

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "panes.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="粗利"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _worksheet(workbook):
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="Sheet1")
    placement = worksheet.add_field(
        field=datasource.get_fields(name="売上")[0], shelf="rows"
    )
    return worksheet, placement


def _add_second_pane(worksheet):
    """二重軸のワークシートを手で再現する。`<pane>` を 1 つ足すだけ。"""
    element = worksheet._resolve_element()
    panes = element.xpath(".//*[local-name()='pane']")
    parent = panes[0].getparent()
    parent.append(ET.fromstring(ET.tostring(panes[0])))
    worksheet._context.mark_dirty()
    return worksheet.get_panes()


def test_one_pane_needs_no_pane_argument(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, placement = _worksheet(workbook)

    line = worksheet.add_reference_line(field=placement, formula="median")

    assert line.id == "refline0"
    assert len(worksheet.get_panes()) == 1


def test_more_than_one_pane_requires_an_explicit_pane(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, placement = _worksheet(workbook)
    assert len(_add_second_pane(worksheet)) == 2

    with pytest.raises(ValueError, match="more than one pane"):
        worksheet.add_reference_line(field=placement, formula="median")


def test_the_line_goes_to_the_pane_that_was_named(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, placement = _worksheet(workbook)
    panes = _add_second_pane(worksheet)

    worksheet.add_reference_line(field=placement, pane=panes[1], formula="median")

    element = worksheet._resolve_element()
    pane_elements = element.xpath(".//*[local-name()='pane']")
    counts = [
        len(pane.xpath("./*[local-name()='reference-line']"))
        for pane in pane_elements
    ]
    # 先頭ではなく指定した 2 つ目へ入る
    assert counts == [0, 1]


def test_a_pane_from_another_worksheet_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, placement = _worksheet(workbook)
    datasource = workbook.get_datasources()[0]
    other = workbook.create_worksheet(name="Sheet2")
    other.add_field(field=datasource.get_fields(name="粗利")[0], shelf="rows")

    with pytest.raises(ValueError, match="pane must belong to the worksheet"):
        worksheet.add_reference_line(
            field=placement, pane=other.get_panes()[0], formula="median"
        )


def test_field_is_keyword_only(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet, placement = _worksheet(workbook)

    with pytest.raises(TypeError, match="positional"):
        worksheet.add_reference_line(placement)  # type: ignore[misc]
