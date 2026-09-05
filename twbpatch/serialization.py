from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def _normalize_projection(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, list):
        return [_normalize_projection(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_projection(item) for item in value]
    if not isinstance(value, dict):
        return value

    result: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = key
        if key == "caption":
            normalized_key = "name"
        elif key.endswith("_caption"):
            normalized_key = f"{key[:-8]}_name"
        elif key == "columns":
            normalized_key = "fields"
        elif key == "referenced_columns":
            normalized_key = "referenced_fields"
        if normalized_key == "name" and normalized_key in result and result[normalized_key] is not None:
            continue
        result[normalized_key] = _normalize_projection(item)
    return result


def _serialize_placement(field: Any) -> dict[str, Any]:
    return {
        "id": field.id,
        "name": field.name,
        "field_id": field.field_id,
        "datasource_id": field.datasource_id,
        "shelf": field.shelf,
        "encoding": field.encoding,
        "pane_id": field.pane_id,
        "aggregation": field.aggregation,
        "discrete": field.discrete,
    }


def _serialize_container(container: Any) -> dict[str, Any]:
    return {
        "id": container.id,
        "name": container.name,
        "direction": container.direction,
        "order": container.order,
        "weight": container.weight,
        "containers": [_serialize_container(child) for child in container.get_containers()],
        "zones": [_serialize_zone(zone) for zone in container.get_zones()],
    }


def _serialize_zone(zone: Any) -> dict[str, Any]:
    return {
        "id": zone.id,
        "name": zone.name,
        "worksheet_id": zone.worksheet_id,
        "placement_mode": zone.placement_mode,
        "order": zone.order,
        "weight": zone.weight,
        "x": zone.x,
        "y": zone.y,
        "width": zone.width,
        "height": zone.height,
        "show_title": zone.show_title,
    }


def _serialize_relation(relation: Any, datasource_name: str | None) -> dict[str, Any]:
    return {
        "datasource": datasource_name,
        "datasource_id": relation.datasource_id,
        "id": relation.id,
        "type": relation.type,
        "name": relation.name,
        "table": relation.table,
        "connection": relation.connection,
        "join": relation.join,
        "custom_sql": relation.custom_sql,
        "scope": relation.scope,
        "logical_table": relation.logical_table,
        "logical_table_id": relation.logical_table_id,
        "clauses": relation.clauses,
        "children": [
            _serialize_relation(child, datasource_name)
            for child in relation.get_children()
        ],
        "attrs": relation.attrs,
    }


def _serialize_relationship(relationship: Any, datasource_name: str | None) -> dict[str, Any]:
    return {
        "datasource": datasource_name,
        "datasource_id": relationship.datasource_id,
        "id": relationship.id,
        "left_object": relationship.left_object,
        "left_object_id": relationship.left_object_id,
        "right_object": relationship.right_object,
        "right_object_id": relationship.right_object_id,
        "expression": relationship.expression,
        "attrs": relationship.attrs,
    }


def serialize_workbook(workbook: Any) -> dict[str, Any]:
    datasources: list[dict[str, Any]] = []
    for datasource in workbook.get_datasources():
        source = datasource.source
        datasource_record = {
            "id": datasource.id,
            "name": datasource.name,
            "source_type": datasource.source_type,
            "source": _normalize_projection(source),
            "fields": [],
            "folders": [],
            "relations": [
                _serialize_relation(relation, datasource.name)
                for relation in datasource.get_relations()
            ],
            "relationships": [
                _serialize_relationship(relationship, datasource.name)
                for relationship in datasource.get_relationships()
            ],
        }
        for field in datasource.get_fields():
            folder = field.folder
            datasource_record["fields"].append(
                {
                    "id": field.id,
                    "name": field.name,
                    "datatype": field.datatype,
                    "role": field.role,
                    "discrete": field.discrete,
                    "hidden": field.hidden,
                    "formula": field.formula,
                    "raw_formula": field.raw_formula,
                    "referenced_fields": field.referenced_fields,
                    "formats": field.formats,
                    "folder_id": folder.id if folder is not None else None,
                    "is_calculated": field.is_calculated,
                }
            )
        for folder in datasource.get_folders():
            datasource_record["folders"].append(
                {
                    "id": folder.id,
                    "name": folder.name,
                    "field_ids": [field.id for field in folder.get_fields()],
                }
            )
        datasources.append(datasource_record)

    parameters = [
        {
            "id": parameter.id,
            "name": parameter.name,
            "datatype": parameter.datatype,
            "value": parameter.value,
            "value_display": parameter.value_display,
            "domain_type": parameter.domain_type,
            "allowable_values": parameter.allowable_values,
            "aliases": parameter.aliases,
            "default_value_field": parameter.default_value_field,
            "min_value": parameter.min_value,
            "max_value": parameter.max_value,
            "step_size": parameter.step_size,
            "hidden": parameter.hidden,
        }
        for parameter in workbook.get_parameters(include_hidden=True)
    ]

    worksheets: list[dict[str, Any]] = []
    for worksheet in workbook.get_worksheets():
        worksheets.append(
            {
                "id": worksheet.id,
                "name": worksheet.name,
                "visible": worksheet.visible,
                "fields": [_serialize_placement(field) for field in worksheet.get_fields()],
                "panes": [
                    {
                        "id": pane.id,
                        "name": pane.name,
                        "mark_type": pane.mark_type,
                        "fields": [_serialize_placement(field) for field in pane.get_fields()],
                    }
                    for pane in worksheet.get_panes()
                ],
                "reference_lines": _normalize_projection(worksheet.get_reference_lines()),
                "filters": _normalize_projection(worksheet.get_filters()),
            }
        )

    dashboards: list[dict[str, Any]] = []
    for dashboard in workbook.get_dashboards():
        dashboards.append(
            {
                "id": dashboard.id,
                "name": dashboard.name,
                "visible": dashboard.visible,
                "sizing_mode": dashboard.sizing_mode,
                "width": dashboard.width,
                "height": dashboard.height,
                "worksheets": [
                    {"id": worksheet.id, "name": worksheet.name}
                    for worksheet in dashboard.get_worksheets()
                ],
                "fields": [_serialize_placement(field) for field in dashboard.get_fields()],
                "containers": [
                    _serialize_container(container)
                    for container in dashboard.get_containers()
                ],
                "zones": [_serialize_zone(zone) for zone in dashboard.get_zones()],
                "actions": [
                    {
                        "id": action.id,
                        "name": action.name,
                        "type": action.type,
                        "activation": action.activation,
                        "command": action.command,
                        "source_worksheet_ids": action.source_worksheet_ids,
                        "target_worksheet_ids": action.target_worksheet_ids,
                        "links": action.links,
                        "params": action.params,
                    }
                    for action in dashboard.get_actions()
                ],
                "filter_controls": _normalize_projection(dashboard.get_filter_controls()),
            }
        )

    return {
        "datasources": datasources,
        "parameters": parameters,
        "worksheets": worksheets,
        "dashboards": dashboards,
    }
