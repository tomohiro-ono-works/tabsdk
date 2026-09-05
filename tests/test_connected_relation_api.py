"""A-2: リファレンスラインとリレーションの接続型モデル化。

`TwbRelation` / `TwbRelationship` は読み取り専用。join / union / カスタム SQL の
編集は H-8 として見送っているため、`update()` / `delete()` を持たない。

根拠: docs/backlog.md A-2 / H-8（2026-09-05 決定）
"""

from __future__ import annotations

import pytest

from twbpatch import (
    DetachedModelError,
    TwbReferenceLine,
    TwbRelation,
    TwbRelationship,
    TwbWorkbook,
)


def _reference_line_workbook(tmp_path):
    path = tmp_path / "refline.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _relation_workbook(tmp_path):
    path = tmp_path / "relation.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="Source">
      <connection>
        <relation join="inner" type="join" name="Orders+Returns">
          <relation connection="db.1" name="Orders" table="[public].[orders]" type="table" />
          <relation connection="db.1" name="Returns" table="[public].[returns]" type="table" />
          <clause type="join">
            <expression op="=" />
          </clause>
        </relation>
      </connection>
      <object-graph>
        <objects>
          <object id="Orders" caption="Orders" />
          <object id="Returns" caption="Returns" />
        </objects>
        <relationships>
          <relationship id="orders_returns">
            <first-end-point object-id="Orders" />
            <second-end-point object-id="Returns" />
            <expression op="=" />
          </relationship>
        </relationships>
      </object-graph>
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _worksheet_with_reference_line(workbook):
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="Sheet1")
    field = worksheet.add_field(datasource.get_fields(name="売上")[0], shelf="rows")
    line = worksheet.add_reference_line(field, formula="median")
    return worksheet, line


def test_get_reference_lines_returns_connected_models(tmp_path) -> None:
    workbook = _reference_line_workbook(tmp_path)
    worksheet, line = _worksheet_with_reference_line(workbook)

    assert type(line) is TwbReferenceLine
    assert [type(item) for item in worksheet.get_reference_lines()] == [TwbReferenceLine]
    assert line.id == "refline0"
    assert line.name == line.id
    assert line.worksheet_id == "Sheet1"
    assert line.formula == "median"
    assert line.scope == "per-table"
    assert line.axis_caption == "売上"

    assert [item.id for item in worksheet.get_reference_lines(id="refline0")] == ["refline0"]
    assert worksheet.get_reference_lines(name="missing") == []


def test_reference_line_update_changes_only_given_arguments(tmp_path) -> None:
    workbook = _reference_line_workbook(tmp_path)
    worksheet, line = _worksheet_with_reference_line(workbook)

    assert line.update(formula="AVERAGE", label_type="none") is line
    updated = worksheet.get_reference_lines()[0]
    assert updated.formula == "average"      # 小文字へ正規化する
    assert updated.label_type == "none"
    assert updated.scope == "per-table"      # 未指定は変えない


def test_reference_line_update_rejects_unknown_formula(tmp_path) -> None:
    workbook = _reference_line_workbook(tmp_path)
    _, line = _worksheet_with_reference_line(workbook)
    with pytest.raises(ValueError, match="unsupported reference line formula"):
        line.update(formula="stdev")
    with pytest.raises(TypeError, match="formula must be a string"):
        line.update(formula=1)


def test_reference_line_delete_detaches(tmp_path) -> None:
    workbook = _reference_line_workbook(tmp_path)
    worksheet, line = _worksheet_with_reference_line(workbook)

    assert line.delete() is None
    assert worksheet.get_reference_lines() == []
    with pytest.raises(DetachedModelError):
        line.formula


def test_get_relations_returns_connected_models_with_children(tmp_path) -> None:
    workbook = _relation_workbook(tmp_path)
    datasource = workbook.get_datasources()[0]

    relations = datasource.get_relations()
    assert [type(item) for item in relations] == [TwbRelation]
    root = relations[0]
    assert root.type == "join"
    assert root.join == "inner"
    assert root.name == "Orders+Returns"
    assert root.datasource_id == "ds1"
    assert [clause["tag"] for clause in root.clauses] == ["clause"]

    children = root.get_children()
    assert [type(item) for item in children] == [TwbRelation, TwbRelation]
    assert [child.name for child in children] == ["Orders", "Returns"]
    assert [child.table for child in children] == ["[public].[orders]", "[public].[returns]"]
    assert children[0].get_children() == []

    assert [item.name for item in datasource.get_relations(name="Orders+Returns")] == [
        "Orders+Returns"
    ]
    assert datasource.get_relations(name="missing") == []


def test_get_relationships_returns_connected_models(tmp_path) -> None:
    workbook = _relation_workbook(tmp_path)
    datasource = workbook.get_datasources()[0]

    relationships = datasource.get_relationships()
    assert [type(item) for item in relationships] == [TwbRelationship]
    relationship = relationships[0]
    assert relationship.id == "orders_returns"
    assert relationship.left_object_id == "Orders"
    assert relationship.right_object_id == "Returns"
    assert relationship.expression["attrs"] == {"op": "="}

    assert [item.id for item in datasource.get_relationships(id="orders_returns")] == [
        "orders_returns"
    ]


def test_relations_are_read_only(tmp_path) -> None:
    """H-8（join / union の編集）を見送っているため書き込みを持たない。"""
    workbook = _relation_workbook(tmp_path)
    datasource = workbook.get_datasources()[0]

    for model in (datasource.get_relations()[0], datasource.get_relationships()[0]):
        assert not hasattr(model, "update")
        assert not hasattr(model, "delete")


def test_export_json_keeps_its_shape(tmp_path) -> None:
    """接続型モデル化しても export_json() の出力は変わらない。"""
    workbook = _relation_workbook(tmp_path)
    exported = workbook.export_json()["datasources"][0]

    assert exported["relations"][0]["type"] == "join"
    assert [child["name"] for child in exported["relations"][0]["children"]] == [
        "Orders",
        "Returns",
    ]
    assert exported["relationships"][0]["id"] == "orders_returns"


def test_list_methods_still_return_old_dataclasses(tmp_path) -> None:
    from twbpatch import models

    workbook = _relation_workbook(tmp_path)
    assert isinstance(workbook.list_relations("Source")[0], models.TwbRelation)
    assert isinstance(workbook.list_relationships("Source")[0], models.TwbRelationship)

    line_workbook = _reference_line_workbook(tmp_path)
    _worksheet_with_reference_line(line_workbook)
    assert isinstance(line_workbook.list_reference_lines()[0], models.TwbReferenceLine)
