from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field


@dataclass
class BigQuerySource:
    project: str | None = None
    dataset: str | None = None
    table: str | None = None
    server: str | None = None
    custom_sql: str | None = None


@dataclass
class ExcelSource:
    file_path: str | None = None
    sheet: str | None = None
    custom_sql: str | None = None


@dataclass
class CsvSource:
    file_path: str | None = None
    custom_sql: str | None = None


@dataclass
class UnknownSource:
    raw_type: str | None = None
    custom_sql: str | None = None


@dataclass
class TwbColumn:
    name: str
    id: str | None = None
    caption: str | None = None
    datatype: str | None = None
    role: str | None = None
    discrete: bool | None = None
    hidden: bool = False
    formula: str | None = None
    raw_formula: str | None = None
    referenced_columns: list[str] = dataclass_field(default_factory=list)
    format: list[dict[str, str]] = dataclass_field(default_factory=list)
    folder: str | None = None

    @property
    def is_calculated(self) -> bool:
        return self.raw_formula is not None or self.formula is not None


@dataclass
class TwbFolder:
    name: str
    id: str | None = None
    role: str | None = None
    items: list[str] = dataclass_field(default_factory=list)


@dataclass
class TwbParameter:
    name: str
    id: str | None = None
    caption: str | None = None
    datatype: str | None = None
    value: str | None = None
    value_display: str | None = None
    domain_type: str | None = None
    allowable_values: list[dict[str, str | None]] = dataclass_field(default_factory=list)
    aliases: list[dict[str, str | None]] = dataclass_field(default_factory=list)
    default_value_field: str | None = None
    hidden: bool = False


@dataclass
class TwbRelation:
    datasource: str
    datasource_id: str | None = None
    id: str | None = None
    type: str | None = None
    name: str | None = None
    table: str | None = None
    connection: str | None = None
    join: str | None = None
    custom_sql: str | None = None
    scope: str | None = None
    logical_table: str | None = None
    logical_table_id: str | None = None
    clauses: list[dict[str, object]] = dataclass_field(default_factory=list)
    children: list[TwbRelation] = dataclass_field(default_factory=list)
    attrs: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass
class TwbRelationship:
    datasource: str
    datasource_id: str | None = None
    id: str | None = None
    left_object: str | None = None
    left_object_id: str | None = None
    right_object: str | None = None
    right_object_id: str | None = None
    expression: dict[str, object] | None = None
    attrs: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass
class TwbDatasource:
    name: str | None
    caption: str | None
    source_type: str
    source: BigQuerySource | ExcelSource | CsvSource | UnknownSource
    columns: list[TwbColumn]
    folders: list[TwbFolder]
    id: str | None = None
    relations: list[TwbRelation] = dataclass_field(default_factory=list)
    relationships: list[TwbRelationship] = dataclass_field(default_factory=list)


@dataclass
class TwbReferenceLine:
    worksheet: str
    worksheet_id: str | None = None
    id: str | None = None
    axis_column: str | None = None
    axis_caption: str | None = None
    axis_role: str | None = None
    value_column: str | None = None
    value_caption: str | None = None
    value_role: str | None = None
    formula: str | None = None
    scope: str | None = None
    label_type: str | None = None
    tooltip_type: str | None = None
    attrs: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass
class TwbWorksheetFilter:
    worksheet: str
    worksheet_id: str | None = None
    column: str | None = None
    field: str | None = None
    role: str | None = None
    filter_class: str | None = None
    filter_group: str | None = None
    domain: str | None = None
    enumeration: str | None = None
    value_scope: str | None = None
    value_scope_label: str | None = None
    apply_scope: str | None = None
    apply_scope_label: str | None = None
    selection_type: str | None = None
    values: list[str] = dataclass_field(default_factory=list)
    functions: list[str] = dataclass_field(default_factory=list)
    attrs: dict[str, str] = dataclass_field(default_factory=dict)
    groupfilter_attrs: list[dict[str, str]] = dataclass_field(default_factory=list)


@dataclass
class TwbFilterControl:
    dashboard: str
    dashboard_id: str | None = None
    id: str | None = None
    name: str | None = None
    worksheet: str | None = None
    worksheet_id: str | None = None
    column: str | None = None
    field: str | None = None
    role: str | None = None
    mode: str | None = None
    filter_class: str | None = None
    domain: str | None = None
    enumeration: str | None = None
    value_scope: str | None = None
    value_scope_label: str | None = None
    apply_scope: str | None = None
    apply_scope_label: str | None = None
    selection_type: str | None = None
    values: list[str] = dataclass_field(default_factory=list)
    show_apply: bool | None = None
    show_title: bool | None = None
    show_caption: bool | None = None
    x: str | None = None
    y: str | None = None
    width: str | None = None
    height: str | None = None
    attrs: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass
class TwbDashboardZone:
    dashboard: str
    dashboard_id: str | None = None
    id: str | None = None
    parent_id: str | None = None
    depth: int = 0
    name: str | None = None
    type: str | None = None
    worksheet: str | None = None
    worksheet_id: str | None = None
    mode: str | None = None
    param: str | None = None
    url: str | None = None
    text: str | None = None
    layout: str = "default"
    sizing_mode: str | None = None
    dashboard_width_px: int | None = None
    dashboard_height_px: int | None = None
    x_raw: int | None = None
    x_px: int | None = None
    y_raw: int | None = None
    y_px: int | None = None
    width_raw: int | None = None
    width_px: int | None = None
    height_raw: int | None = None
    height_px: int | None = None
    fixed_size: int | None = None
    is_fixed: bool | None = None
    is_scaled: bool | None = None
    show_title: bool | None = None
    show_caption: bool | None = None
    show_apply: bool | None = None
    attrs: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass
class TwbDashboardAction:
    dashboard: str | None = None
    dashboard_id: str | None = None
    id: str | None = None
    caption: str | None = None
    type: str | None = None
    activation: str | None = None
    command: str | None = None
    source_type: str | None = None
    source_dashboard: str | None = None
    source_dashboard_id: str | None = None
    source_worksheets: list[str] = dataclass_field(default_factory=list)
    source_worksheet_ids: list[str] = dataclass_field(default_factory=list)
    excluded_source_worksheets: list[str] = dataclass_field(default_factory=list)
    target_type: str | None = None
    target_dashboard: str | None = None
    target_dashboard_id: str | None = None
    target_worksheets: list[str] = dataclass_field(default_factory=list)
    target_worksheet_ids: list[str] = dataclass_field(default_factory=list)
    excluded_target_worksheets: list[str] = dataclass_field(default_factory=list)
    links: list[dict[str, str]] = dataclass_field(default_factory=list)
    params: dict[str, str] = dataclass_field(default_factory=dict)
    attrs: dict[str, str] = dataclass_field(default_factory=dict)
    details: dict[str, object] = dataclass_field(default_factory=dict)


@dataclass
class TwbWorksheet:
    name: str
    id: str | None = None
    caption: str | None = None
    rows: list[str] = dataclass_field(default_factory=list)
    columns: list[str] = dataclass_field(default_factory=list)
    filters: list[dict[str, str]] = dataclass_field(default_factory=list)
    datasource_names: list[str] = dataclass_field(default_factory=list)
    used_columns: list[str] = dataclass_field(default_factory=list)
    reference_lines: list[TwbReferenceLine] = dataclass_field(default_factory=list)
    fields: list[TwbWorksheetField] = dataclass_field(default_factory=list)
    visible: bool = True


@dataclass
class TwbDashboard:
    name: str
    id: str | None = None
    caption: str | None = None
    worksheets: list[TwbWorksheet] = dataclass_field(default_factory=list)
    zones: list[TwbDashboardZone] = dataclass_field(default_factory=list)
    actions: list[TwbDashboardAction] = dataclass_field(default_factory=list)
    visible: bool = True


@dataclass
class TwbWorksheetField:
    worksheet: str
    type: str
    role: str | None
    caption: str | None
    id: str | None = None
    values: str | None = None
    category: str | None = None
    aggregation: str | None = None
    worksheet_id: str | None = None
    datasource: str | None = None
    datasource_id: str | None = None
    field_id: str | None = None
    pane_id: str | None = None
    mark_type: str | None = None
    attrs: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass
class TwbValidationMessage:
    severity: str
    code: str
    message: str
    datasource: str | None = None
    column: str | None = None


@dataclass
class TwbUnsupportedFeature:
    feature: str
    severity: str
    message: str
    datasource: str | None = None
