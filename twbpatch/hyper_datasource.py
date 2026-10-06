"""Tableau 抽出（.hyper）だけを持つデータソースの作成。

一般的なデータソースの作成（CSV / Excel / BigQuery など、backlog H-2）は不採用のまま。
KPI ツリーのエッジ用に、.hyper に限って作れるようにした（docs/developer/tasks/I2_kpi_tree.md）。

.hyper の中身はライブラリで読めないため、列は呼び出し側が宣言し、ファイルとは突き合わせない。
XML は Tableau が「テキストファイルに接続して抽出を作った」ときに保存した形（2026-09-13 実測）に合わせる。
テキストファイル側は、抽出を開くときに参照されない前提で、形式だけ整えた値を書く。
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import TypedDict

from lxml import etree as ET

from .connected import TwbDatasource, get_display_name
from .context import WorkbookContext
from .errors import UnsupportedFeatureError


class HyperField(TypedDict):
    """`create_hyper_datasource(fields=...)` の 1 列。`name` は .hyper の表の列名。"""

    name: str
    datatype: str
    role: str


#: 実測した型だけを受け付ける。他の型は Tableau の保存形を見てから足す。
_REMOTE_TYPES = {"string": "129", "integer": "20"}
_ROLES = {"dimension", "measure"}
_ID_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"


def _tableau_id() -> str:
    """Tableau の `federated.xxx` と同じ 28 文字の小文字英数字。"""
    return "".join(secrets.choice(_ID_CHARS) for _ in range(28))


def _validate(context: WorkbookContext, name: str, path: str, fields: list[HyperField]) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must not be empty")
    if any(get_display_name(element) == name.strip() for element in context.tree.getroot().xpath(
        "/workbook/datasources/datasource"
    )):
        raise ValueError(f"datasource already exists: {name.strip()}")
    if not isinstance(path, str) or not path.lower().endswith(".hyper"):
        raise ValueError("path must be a .hyper file")
    stem = path.replace("\\", "/").rsplit("/", 1)[-1][: -len(".hyper")]
    if not stem or "[" in stem or "]" in stem:
        raise ValueError(f"unsupported .hyper file name: {path}")
    if not isinstance(fields, list) or not fields:
        raise ValueError("fields must be a non-empty list")
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) != {"name", "datatype", "role"}:
            raise ValueError("each field needs exactly name, datatype and role")
        column = field["name"]
        if not isinstance(column, str) or not column or "[" in column or "]" in column:
            raise ValueError(f"invalid field name: {column!r}")
        if column in seen:
            raise ValueError(f"duplicate field name: {column}")
        seen.add(column)
        if field["datatype"] not in _REMOTE_TYPES:
            raise ValueError(f"unsupported datatype: {field['datatype']!r} (string or integer)")
        if field["role"] not in _ROLES:
            raise ValueError(f"role must be dimension or measure: {field['role']!r}")
    return stem


def _metadata_record(
    parent: ET._Element,
    field: HyperField,
    ordinal: int,
    *,
    parent_name: str,
    object_id: str,
    family: str | None,
) -> None:
    """列 1 つぶんの metadata-record。テキスト側と抽出側で並びと照合順序が少し違う（実測どおり）。"""
    record = ET.SubElement(parent, "metadata-record", attrib={"class": "column"})
    datatype = field["datatype"]
    ET.SubElement(record, "remote-name").text = field["name"]
    ET.SubElement(record, "remote-type").text = _REMOTE_TYPES[datatype]
    ET.SubElement(record, "local-name").text = f"[{field['name']}]"
    ET.SubElement(record, "parent-name").text = parent_name
    ET.SubElement(record, "remote-alias").text = field["name"]
    ET.SubElement(record, "ordinal").text = str(ordinal)
    if family is not None:
        ET.SubElement(record, "family").text = family
    ET.SubElement(record, "local-type").text = datatype
    ET.SubElement(record, "aggregation").text = "Count" if datatype == "string" else "Sum"
    if datatype == "string" and family is None:
        ET.SubElement(record, "scale").text = "1"
        ET.SubElement(record, "width").text = "1073741823"
    ET.SubElement(record, "contains-null").text = "true"
    if datatype == "string":
        ET.SubElement(
            record,
            "collation",
            attrib={"flag": "0", "name": "LJA_RJP" if family is None else "LJA"},
        )
    ET.SubElement(record, "object-id").text = f"[{object_id}]"


def _text_relation(parent: ET._Element, leaf: str, table: str, fields: list[HyperField]) -> None:
    relation = ET.SubElement(
        parent,
        "relation",
        attrib={"connection": leaf, "name": table, "table": f"[{table}]", "type": "table"},
    )
    columns = ET.SubElement(
        relation,
        "columns",
        attrib={"character-set": "UTF-8", "header": "yes", "locale": "ja_JP", "separator": "\t"},
    )
    for ordinal, field in enumerate(fields):
        ET.SubElement(
            columns,
            "column",
            attrib={"datatype": field["datatype"], "name": field["name"], "ordinal": str(ordinal)},
        )


def _build(root: ET._Element, name: str, path: str, stem: str, fields: list[HyperField]) -> ET._Element:
    datasource_id = f"federated.{_tableau_id()}"
    leaf = f"textscan.{_tableau_id()}"
    table = f"{stem}#txt"
    object_id = stem
    directory = path.replace("\\", "/").rsplit("/", 1)[0] if "/" in path.replace("\\", "/") else "."

    attrs = {"caption": name, "inline": "true", "name": datasource_id}
    if root.get("version"):
        attrs["version"] = str(root.get("version"))
    datasource = ET.Element("datasource", attrib=attrs)

    connection = ET.SubElement(datasource, "connection", attrib={"class": "federated"})
    named = ET.SubElement(ET.SubElement(connection, "named-connections"), "named-connection",
                          attrib={"caption": stem, "name": leaf})
    ET.SubElement(named, "connection",
                  attrib={"class": "textscan", "directory": directory, "filename": f"{stem}.txt"})
    _text_relation(connection, leaf, table, fields)
    records = ET.SubElement(connection, "metadata-records")
    capability = ET.SubElement(records, "metadata-record", attrib={"class": "capability"})
    ET.SubElement(capability, "remote-name")
    ET.SubElement(capability, "remote-type").text = "0"
    ET.SubElement(capability, "parent-name").text = f"[{table}]"
    ET.SubElement(capability, "remote-alias")
    ET.SubElement(capability, "aggregation").text = "Count"
    ET.SubElement(capability, "contains-null").text = "true"
    attributes = ET.SubElement(capability, "attributes")
    for key, value in (
        ("character-set", '"UTF-8"'),
        ("collation", '"ja"'),
        ("currency", '"￥"'),
        ("field-delimiter", '"\\\\t"'),
        ("header-row", '"true"'),
        ("locale", '"ja_JP"'),
        ("single-char", '""'),
    ):
        ET.SubElement(attributes, "attribute", attrib={"datatype": "string", "name": key}).text = value
    for ordinal, field in enumerate(fields):
        _metadata_record(records, field, ordinal, parent_name=f"[{table}]", object_id=object_id, family=None)

    ET.SubElement(datasource, "aliases", attrib={"enabled": "yes"})
    ET.SubElement(datasource, "column", attrib={
        "caption": name,
        "datatype": "table",
        "name": f"[__tableau_internal_object_id__].[{object_id}]",
        "role": "measure",
        "type": "quantitative",
    })
    for field in fields:
        measure = field["role"] == "measure"
        ET.SubElement(datasource, "column", attrib={
            "datatype": field["datatype"],
            "name": f"[{field['name']}]",
            "role": field["role"],
            "type": "quantitative" if measure else ("nominal" if field["datatype"] == "string" else "ordinal"),
        })

    extract = ET.SubElement(datasource, "extract", attrib={
        "count": "-1", "enabled": "true", "object-id": "", "units": "records", "user-specific": "false",
    })
    hyper = ET.SubElement(extract, "connection", attrib={
        "access_mode": "readonly",
        "author-locale": "ja_JP",
        "class": "hyper",
        "dbname": path,
        "default-settings": "hyper",
        "schema": "Extract",
        "sslmode": "",
        "tablename": "Extract",
        "update-time": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"),
        "username": "tableau_internal_user",
    })
    ET.SubElement(hyper, "relation", attrib={"name": "Extract", "table": "[Extract].[Extract]", "type": "table"})
    extract_records = ET.SubElement(hyper, "metadata-records")
    for ordinal, field in enumerate(fields):
        _metadata_record(
            extract_records, field, ordinal, parent_name="[Extract]", object_id=object_id, family=table
        )

    ET.SubElement(datasource, "layout", attrib={
        "dim-ordering": "alphabetic", "measure-ordering": "alphabetic", "show-structure": "true",
    })
    semantic = ET.SubElement(datasource, "semantic-values")
    ET.SubElement(semantic, "semantic-value", attrib={"key": "[Country].[Name]", "value": '"日本"'})
    objects = ET.SubElement(ET.SubElement(datasource, "object-graph"), "objects")
    graph_object = ET.SubElement(objects, "object", attrib={"caption": name, "id": object_id})
    _text_relation(ET.SubElement(graph_object, "properties", attrib={"context": ""}), leaf, table, fields)
    ET.SubElement(
        ET.SubElement(graph_object, "properties", attrib={"context": "extract"}),
        "relation",
        attrib={"name": "Extract", "table": "[Extract].[Extract]", "type": "table"},
    )
    return datasource


def create_hyper_datasource(
    context: WorkbookContext,
    *,
    name: str,
    path: str,
    fields: list[HyperField],
) -> TwbDatasource:
    stem = _validate(context, name, path, fields)
    root = context.tree.getroot()
    if ET.QName(root).namespace is not None:
        raise UnsupportedFeatureError("namespaced workbook XML is not supported")
    datasource = _build(root, name.strip(), path, stem, fields)

    datasources = next((child for child in root if ET.QName(child).localname == "datasources"), None)
    if datasources is None:
        datasources = ET.Element("datasources")
        worksheets = next((child for child in root if ET.QName(child).localname == "worksheets"), None)
        if worksheets is None:
            root.append(datasources)
        else:
            worksheets.addprevious(datasources)
    datasources.append(datasource)
    context.mark_dirty()
    return TwbDatasource(context, datasource.get("name"))
