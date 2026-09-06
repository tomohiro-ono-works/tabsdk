"""`is_dirty` が「XML が実際に変わったか」を表すことを確かめる（仕様 §9）。

日本語を含むワークブックでは、ツリーに繋がった要素と `copy.deepcopy()` した要素で
`ET.tostring()` の文字参照の書き方が違い（16 進 と 10 進）、中身が同じでも
「変更あり」と判定されていた。`xml_equal()` の導入で解消した（2026-09-07）。
"""

from __future__ import annotations

import copy

from lxml import etree as ET

from twbpatch import TwbWorkbook
from twbpatch.context import xml_equal


SAMPLE = "tests/sample_minimal.twb"


def test_xml_equal_ignores_the_character_reference_format() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources(name="売上データ")[0]
    attached = datasource._resolve_element().xpath("./column[@name='[Sales]']")[0]
    detached = copy.deepcopy(attached)

    # 素の tostring() では一致しない。これが誤検出の原因だった。
    assert ET.tostring(attached) != ET.tostring(detached)
    assert xml_equal(attached, detached)


def test_no_op_update_keeps_is_dirty_false() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    field = workbook.get_datasources(name="売上データ")[0].get_fields(name="売上")[0]

    field.update(name="売上")

    assert workbook.is_dirty is False


def test_real_update_sets_is_dirty() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    field = workbook.get_datasources(name="売上データ")[0].get_fields(name="売上")[0]

    field.update(name="売上金額")

    assert workbook.is_dirty is True


def test_is_dirty_stays_true_after_a_later_no_op() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources(name="売上データ")[0]
    datasource.get_fields(name="売上")[0].update(name="売上金額")

    datasource.get_fields(name="粗利")[0].update(name="粗利")

    assert workbook.is_dirty is True
