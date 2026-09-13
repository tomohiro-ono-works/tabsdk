"""Tableau 抽出（.hyper）だけを持つデータソースの作成。

XML の形は、Tableau が「テキストファイルに接続して抽出を作った」ときの保存形（2026-09-13 実測）に合わせている。
"""

import pytest

from twbpatch import TwbWorkbook


EDGE_FIELDS = [
    {"name": "edge", "datatype": "string", "role": "dimension"},
    {"name": "point", "datatype": "string", "role": "dimension"},
    {"name": "x", "datatype": "integer", "role": "measure"},
    {"name": "y", "datatype": "integer", "role": "measure"},
]


def _workbook(tmp_path):
    path = tmp_path / "book.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook version="18.1">
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _datasource_el(workbook, datasource):
    return workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$name]", name=datasource.id
    )[0]


def test_create_hyper_datasource_exposes_declared_fields(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    datasource = workbook.create_hyper_datasource(name="エッジ", path="edge.hyper", fields=EDGE_FIELDS)

    assert datasource.id.startswith("federated.") and len(datasource.id) == len("federated.") + 28
    assert datasource.name == "エッジ"
    assert workbook.get_datasources(name="エッジ")[0].id == datasource.id
    fields = {
        field.id: (field.datatype, field.role)
        for field in datasource.get_fields()
        if field.datatype != "table"
    }
    assert fields == {
        "[edge]": ("string", "dimension"),
        "[point]": ("string", "dimension"),
        "[x]": ("integer", "measure"),
        "[y]": ("integer", "measure"),
    }
    # <datasources> は <worksheets> の前に作る
    assert [child.tag for child in workbook.tree.getroot()] == ["datasources", "worksheets"]
    assert workbook.is_dirty
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_create_hyper_datasource_writes_text_connection_with_extract(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    datasource = workbook.create_hyper_datasource(
        name="エッジ", path="../examples/edge.hyper", fields=EDGE_FIELDS
    )
    element = _datasource_el(workbook, datasource)

    assert element.get("version") == "18.1"
    assert [child.tag for child in element] == [
        "connection", "aliases", "column", "column", "column", "column", "column",
        "extract", "layout", "semantic-values", "object-graph",
    ]
    text = element.xpath("./connection/named-connections/named-connection/connection")[0]
    assert (text.get("class"), text.get("directory"), text.get("filename")) == (
        "textscan", "../examples", "edge.txt",
    )
    relation = element.xpath("./connection/relation")[0]
    assert (relation.get("name"), relation.get("table")) == ("edge#txt", "[edge#txt]")
    assert relation.xpath("./columns/@separator") == ["\t"]

    hyper = element.xpath("./extract/connection")[0]
    assert (hyper.get("class"), hyper.get("dbname"), hyper.get("tablename")) == (
        "hyper", "../examples/edge.hyper", "Extract",
    )
    assert hyper.xpath("./relation/@table") == ["[Extract].[Extract]"]

    extract_edge = hyper.xpath("./metadata-records/metadata-record[remote-name='edge']")[0]
    assert [child.tag for child in extract_edge] == [
        "remote-name", "remote-type", "local-name", "parent-name", "remote-alias", "ordinal",
        "family", "local-type", "aggregation", "contains-null", "collation", "object-id",
    ]
    text_x = element.xpath("./connection/metadata-records/metadata-record[remote-name='x']")[0]
    assert (text_x.findtext("remote-type"), text_x.findtext("local-type"), text_x.findtext("aggregation")) == (
        "20", "integer", "Sum",
    )
    assert element.xpath("./column[@datatype='table']/@name") == [
        "[__tableau_internal_object_id__].[edge]"
    ]
    assert element.xpath("./object-graph/objects/object/properties/@context") == ["", "extract"]


def test_create_hyper_datasource_rejects_invalid_input_without_changes(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.create_hyper_datasource(name="エッジ", path="edge.hyper", fields=EDGE_FIELDS)
    before = len(workbook.get_datasources())

    with pytest.raises(ValueError, match="already exists"):
        workbook.create_hyper_datasource(name="エッジ", path="edge2.hyper", fields=EDGE_FIELDS)
    with pytest.raises(ValueError, match=r"\.hyper"):
        workbook.create_hyper_datasource(name="別", path="edge.csv", fields=EDGE_FIELDS)
    with pytest.raises(ValueError, match="unsupported datatype"):
        workbook.create_hyper_datasource(
            name="別", path="edge.hyper", fields=[{"name": "d", "datatype": "date", "role": "dimension"}]
        )
    with pytest.raises(ValueError, match="role"):
        workbook.create_hyper_datasource(
            name="別", path="edge.hyper", fields=[{"name": "x", "datatype": "integer", "role": "metric"}]
        )
    with pytest.raises(ValueError, match="duplicate"):
        workbook.create_hyper_datasource(name="別", path="edge.hyper", fields=EDGE_FIELDS + EDGE_FIELDS[:1])
    with pytest.raises(ValueError, match="non-empty"):
        workbook.create_hyper_datasource(name="別", path="edge.hyper", fields=[])

    assert len(workbook.get_datasources()) == before


def test_created_hyper_datasource_survives_save_and_reopen(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.create_hyper_datasource(name="エッジ", path="edge.hyper", fields=EDGE_FIELDS)
    output = tmp_path / "saved.twb"

    workbook.save(str(output))

    reopened = TwbWorkbook.open(str(output))
    fields = reopened.get_datasources(name="エッジ")[0].get_fields()
    assert [field.id for field in fields if field.datatype != "table"] == ["[edge]", "[point]", "[x]", "[y]"]
