from __future__ import annotations

from lxml import etree as ET
from .errors import AmbiguousCaptionError, NotFoundError, UnsupportedFeatureError
from .models import TwbDatasource, BigQuerySource, ExcelSource, CsvSource, UnknownSource
from .sources import detect_source
from .column import list_columns_from_datasource
from .folder import list_folders_from_datasource


def is_parameter_datasource(datasource_el: ET._Element) -> bool:
    return datasource_el.get("name") == "Parameters"


def datasource_elements(tree: ET._ElementTree, *, include_parameters: bool = True) -> list[ET._Element]:
    elements = list(tree.getroot().xpath('/workbook/datasources/datasource'))
    if include_parameters:
        return elements
    return [ds for ds in elements if not is_parameter_datasource(ds)]


def list_datasources_from_tree(tree: ET._ElementTree) -> list[TwbDatasource]:
    result: list[TwbDatasource] = []
    for ds in datasource_elements(tree, include_parameters=False):
        source_type, source = detect_source(ds)
        name = ds.get("name")
        result.append(TwbDatasource(
            name=name,
            caption=ds.get("caption") or name,
            source_type=source_type,
            source=source,
            columns=list_columns_from_datasource(ds),
            folders=list_folders_from_datasource(ds),
            id=name,
        ))
    return result


def resolve_datasource_el(
    tree: ET._ElementTree,
    datasource: str,
    *,
    by: str = "auto",
    include_parameters: bool = True,
) -> ET._Element:
    candidates = datasource_elements(tree, include_parameters=include_parameters)
    if by not in {"auto", "caption", "name"}:
        raise ValueError("by must be 'auto', 'caption', or 'name'.")

    def hits(attr: str) -> list[ET._Element]:
        return [ds for ds in candidates if ds.get(attr) == datasource]

    matched = hits("caption") if by in {"auto", "caption"} else []
    if not matched and by in {"auto", "name"}:
        matched = hits("name")
    if not matched:
        raise NotFoundError(f"datasource not found: {datasource}")
    if len(matched) > 1:
        raise AmbiguousCaptionError(f"datasource is ambiguous: {datasource}")
    return matched[0]


def _first_connection(datasource_el: ET._Element) -> ET._Element:
    connections = datasource_el.xpath('.//*[local-name()="connection"]')
    if not connections:
        raise NotFoundError("connection element not found in datasource")
    return connections[0]


def _first_physical_relation(datasource_el: ET._Element) -> ET._Element | None:
    relations = datasource_el.xpath('.//*[local-name()="relation" and not(@type="text")]')
    return relations[0] if relations else None


def _reject_custom_sql_update(source: BigQuerySource | ExcelSource | CsvSource | UnknownSource) -> None:
    if getattr(source, "custom_sql", None):
        raise UnsupportedFeatureError("Custom SQL rewrite is not supported in v0.")


def _set_if_not_none(el: ET._Element, attr: str, value: str | None) -> None:
    if value is not None:
        el.set(attr, value)


def update_source_el(
    datasource_el: ET._Element,
    source: BigQuerySource | ExcelSource | CsvSource | UnknownSource,
) -> None:
    """
    既存 datasource の接続先属性を更新する。

    方針:
    - datasource 自体は新規作成しない。
    - connection 要素が無い場合はエラー。
    - 引数が None の属性は変更しない。
    - Custom SQL の書き換えは v0 対象外。
    """
    _reject_custom_sql_update(source)
    conn = _first_connection(datasource_el)

    if isinstance(source, BigQuerySource):
        conn.set("class", "bigquery")
        _set_if_not_none(conn, "project", source.project)
        _set_if_not_none(conn, "dataset", source.dataset)
        _set_if_not_none(conn, "table", source.table)
        _set_if_not_none(conn, "server", source.server)
        return

    if isinstance(source, ExcelSource):
        conn.set("class", "excel-direct")
        _set_if_not_none(conn, "filename", source.file_path)
        if source.sheet is not None:
            relation = _first_physical_relation(datasource_el)
            if relation is not None:
                relation.set("table", source.sheet)
        return

    if isinstance(source, CsvSource):
        conn.set("class", "textscan")
        _set_if_not_none(conn, "filename", source.file_path)
        return

    if isinstance(source, UnknownSource):
        if source.raw_type is not None:
            conn.set("class", source.raw_type)
        return

    raise TypeError(f"unsupported source type: {type(source)!r}")
