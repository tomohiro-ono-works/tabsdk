from __future__ import annotations

from lxml import etree as ET
from .models import BigQuerySource, ExcelSource, CsvSource, UnknownSource


def extract_custom_sql(datasource_el: ET._Element) -> str | None:
    rels = datasource_el.xpath('.//*[local-name()="relation" and @type="text"]')
    if not rels:
        return None
    return (rels[0].text or "").strip() or None


def detect_source(datasource_el: ET._Element):
    custom_sql = extract_custom_sql(datasource_el)
    connections = datasource_el.xpath('.//*[local-name()="connection"]')
    conn = connections[0] if connections else None
    conn_class = conn.get("class") if conn is not None else None
    filename = conn.get("filename") if conn is not None else None

    if conn_class == "bigquery":
        return "bigquery", BigQuerySource(
            project=conn.get("project") if conn is not None else None,
            dataset=conn.get("dataset") if conn is not None else None,
            table=conn.get("table") if conn is not None else None,
            server=conn.get("server") if conn is not None else None,
            custom_sql=custom_sql,
        )
    if filename and filename.lower().endswith((".xlsx", ".xls")):
        return "excel", ExcelSource(file_path=filename, custom_sql=custom_sql)
    if filename and filename.lower().endswith((".csv", ".tsv", ".txt")):
        return "csv", CsvSource(file_path=filename, custom_sql=custom_sql)
    return "unknown", UnknownSource(raw_type=conn_class, custom_sql=custom_sql)
