"""A-1: トップレベルの `twbpatch` は接続型モデルを公開する。

根拠: docs/model_api_spec.md §11、docs/backlog.md A-1（2026-09-05 決定）
"""

from __future__ import annotations

import twbpatch
from twbpatch import models

# models.py と connected*.py の両方に同名クラスがあるもの
DUPLICATED = [
    "TwbDatasource",
    "TwbFolder",
    "TwbParameter",
    "TwbWorksheet",
    "TwbWorksheetField",
    "TwbDashboard",
    "TwbDashboardZone",
    "TwbDashboardAction",
    # A-2 で接続型モデル化した分
    "TwbWorksheetFilter",
    "TwbFilterControl",
    "TwbReferenceLine",
    "TwbRelation",
    "TwbRelationship",
]

# 接続型モデルを持たない値オブジェクト
MODELS_ONLY = [
    "TwbValidationMessage",
    "TwbUnsupportedFeature",
]

# E-2（2026-09-07）で公開をやめたもの。`models.py` には残るが `twbpatch` からは出さない
UNEXPORTED = ["TwbColumn"]


def test_duplicated_names_resolve_to_connected_models() -> None:
    for name in DUPLICATED:
        exported = getattr(twbpatch, name)
        assert exported.__module__.startswith("twbpatch.connected"), (
            f"{name} は {exported.__module__} を指している"
        )
        assert exported is not getattr(models, name)


def test_old_dataclasses_remain_importable_from_models() -> None:
    """旧 dataclass は twbpatch.models から引き続き取れる（仕様 §11）。"""
    for name in DUPLICATED:
        assert hasattr(models, name)


def test_models_only_classes_come_from_models() -> None:
    for name in MODELS_ONLY:
        assert getattr(twbpatch, name) is getattr(models, name)


def test_the_old_list_methods_are_gone(tmp_path) -> None:
    """E-2（2026-09-07）で旧 API を削除した。"""
    workbook = twbpatch.TwbWorkbook.open("tests/sample_minimal.twb")

    assert not hasattr(workbook, "list_datasources")
    assert isinstance(workbook.get_datasources()[0], twbpatch.TwbDatasource)


def test_all_entries_are_defined() -> None:
    assert [name for name in twbpatch.__all__ if not hasattr(twbpatch, name)] == []


DRAW_METHODS = [
    "draw_sheet",
    "draw_bar",
    "draw_card",
    "draw_quadrant",
    "draw_crosstab",
]


def test_draw_is_published_as_workbook_methods() -> None:
    """A-4: グラフ生成は TwbWorkbook のメソッドが正（仕様 §6.1）。"""
    for name in DRAW_METHODS:
        assert callable(getattr(twbpatch.TwbWorkbook, name))
        assert not hasattr(twbpatch, name), f"{name} がトップレベルに残っている"
        assert name not in twbpatch.__all__


def test_draw_module_remains_the_implementation() -> None:
    """モジュール関数は実装の置き場。公開 API ではないが消してはいない。"""
    from twbpatch import draw

    for name in DRAW_METHODS:
        assert callable(getattr(draw, name))


def test_unexported_models_are_not_public() -> None:
    """旧 API の戻り値だったクラスは公開しない（E-2、2026-09-07）。"""
    for name in UNEXPORTED:
        assert name not in twbpatch.__all__
        assert not hasattr(twbpatch, name)
        # 投影層が返す型なので models.py には残る
        assert hasattr(models, name)
