from __future__ import annotations

from lxml import etree as ET

from .models import TwbRelation, TwbRelationship


def _local_name(node: ET._Element) -> str:
    return ET.QName(node).localname


def _attrs(node: ET._Element) -> dict[str, str]:
    return {str(key).split("}")[-1]: str(value) for key, value in node.attrib.items()}


def _element_record(node: ET._Element) -> dict[str, object]:
    record: dict[str, object] = {
        "tag": _local_name(node),
        "attrs": _attrs(node),
    }
    text = (node.text or "").strip()
    if text:
        record["text"] = text
    children = [_element_record(child) for child in node]
    if children:
        record["children"] = children
    return record


def _ancestor(node: ET._Element, name: str) -> ET._Element | None:
    return next((item for item in node.iterancestors() if _local_name(item) == name), None)


def _relation_roots(datasource_el: ET._Element) -> tuple[list[ET._Element], str]:
    roots = [
        relation
        for relation in datasource_el.xpath(".//*[local-name()='relation']")
        if _ancestor(relation, "relation") is None
    ]
    physical = [relation for relation in roots if _ancestor(relation, "object-graph") is None]
    if physical:
        return physical, "connection"
    return roots, "object-graph"


def _materialize_relation(
    relation_el: ET._Element,
    datasource: str,
    datasource_id: str | None,
    *,
    scope: str,
    logical_table: str | None = None,
    logical_table_id: str | None = None,
) -> TwbRelation:
    object_el = _ancestor(relation_el, "object")
    if object_el is not None:
        logical_table_id = object_el.get("id")
        logical_table = object_el.get("caption") or logical_table_id

    relation_type = relation_el.get("type")
    custom_sql = None
    if relation_type == "text":
        custom_sql = "".join(relation_el.itertext()).strip() or None
    children = [
        _materialize_relation(
            child,
            datasource,
            datasource_id,
            scope=scope,
            logical_table=logical_table,
            logical_table_id=logical_table_id,
        )
        for child in relation_el
        if _local_name(child) == "relation"
    ]
    clauses = [
        _element_record(child)
        for child in relation_el
        if _local_name(child) != "relation"
    ]

    return TwbRelation(
        datasource=datasource,
        datasource_id=datasource_id,
        id=relation_el.get("id") or relation_el.get("name") or logical_table_id,
        type=relation_type,
        name=relation_el.get("name"),
        table=relation_el.get("table"),
        connection=relation_el.get("connection"),
        join=relation_el.get("join"),
        custom_sql=custom_sql,
        scope=scope,
        logical_table=logical_table,
        logical_table_id=logical_table_id,
        clauses=clauses,
        children=children,
        attrs=_attrs(relation_el),
    )


def list_relations_from_datasource(datasource_el: ET._Element) -> list[TwbRelation]:
    datasource_id = datasource_el.get("name")
    datasource = datasource_el.get("caption") or datasource_id or ""
    roots, scope = _relation_roots(datasource_el)
    return [
        _materialize_relation(root, datasource, datasource_id, scope=scope)
        for root in roots
    ]


def _endpoint_id(endpoint: ET._Element | None) -> str | None:
    if endpoint is None:
        return None
    return endpoint.get("object-id") or endpoint.get("object") or endpoint.get("id")


def list_relationships_from_datasource(datasource_el: ET._Element) -> list[TwbRelationship]:
    datasource_id = datasource_el.get("name")
    datasource = datasource_el.get("caption") or datasource_id or ""
    object_labels = {
        str(obj.get("id")): obj.get("caption") or obj.get("id")
        for obj in datasource_el.xpath(".//*[local-name()='object-graph']//*[local-name()='object'][@id]")
    }
    result: list[TwbRelationship] = []

    for relationship in datasource_el.xpath(
        ".//*[local-name()='object-graph']//*[local-name()='relationships']/*[local-name()='relationship']"
    ):
        left_nodes = relationship.xpath("./*[local-name()='first-end-point']")
        right_nodes = relationship.xpath("./*[local-name()='second-end-point']")
        endpoints = relationship.xpath("./*[contains(local-name(), 'end-point')]")
        left = left_nodes[0] if left_nodes else (endpoints[0] if endpoints else None)
        right = right_nodes[0] if right_nodes else (endpoints[1] if len(endpoints) > 1 else None)
        left_id = _endpoint_id(left)
        right_id = _endpoint_id(right)
        expressions = relationship.xpath("./*[local-name()='expression']")

        result.append(
            TwbRelationship(
                datasource=datasource,
                datasource_id=datasource_id,
                id=relationship.get("id") or relationship.get("name"),
                left_object=object_labels.get(left_id, left_id),
                left_object_id=left_id,
                right_object=object_labels.get(right_id, right_id),
                right_object_id=right_id,
                expression=_element_record(expressions[0]) if expressions else None,
                attrs=_attrs(relationship),
            )
        )

    return result
