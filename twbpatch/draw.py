from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .connected import TwbDatasource, TwbField
from .connected_worksheet import TwbWorksheet
from .errors import AmbiguousCaptionError, NotFoundError
from .field_input import FieldInput, resolve_field_inputs

if TYPE_CHECKING:
    from .workbook import TwbWorkbook

_NUMERIC_DATATYPES = {"integer", "real", "decimal", "number"}


def _resolve_fields(
    workbook: TwbWorkbook,
    values: list[FieldInput],
    datasource: TwbDatasource | None = None,
) -> list[TwbField]:
    """A-8 で `field_input` へ一本化した。ここは薄いラッパー。"""
    if datasource is not None and not isinstance(datasource, TwbDatasource):
        raise TypeError("datasource must be TwbDatasource or None")
    if datasource is not None and datasource._context is not workbook._context:
        raise ValueError("datasource must belong to the workbook")
    return resolve_field_inputs(
        workbook._context,
        values,
        datasources=None if datasource is None else [datasource],
    )


def _shelves(item_shelf: str) -> tuple[str, str]:
    item_shelf = item_shelf.lower()
    if item_shelf not in {"rows", "columns"}:
        raise ValueError("item_shelf must be rows or columns")
    return item_shelf, "columns" if item_shelf == "rows" else "rows"


def _auto_metric_aggregation(field: TwbField) -> str | None:
    if field.is_calculated:
        return "agg"
    if field.role != "measure" or (field.datatype or "").lower() not in _NUMERIC_DATATYPES:
        return "countd"
    return field.default_aggregation or "sum"


def _metric_aggregation(
    field: TwbField,
    common: str | None,
    specific: str | None,
) -> str | None:
    selected = specific if specific != "auto" else common
    return _auto_metric_aggregation(field) if selected == "auto" else selected


def _metric_formula(field: TwbField, aggregation: str | None) -> str:
    reference = f"[{field.name}]"
    if aggregation is None or (field.is_calculated and aggregation == "agg"):
        return reference
    function = {
        "sum": "SUM",
        "avg": "AVG",
        "min": "MIN",
        "max": "MAX",
        "count": "COUNT",
        "countd": "COUNTD",
        "attr": "ATTR",
    }.get(aggregation.lower())
    if function is None:
        raise ValueError(f"unsupported metric aggregation: {aggregation}")
    return f"{function}({reference})"


def draw_sheet(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    items: list[FieldInput] | None = None,
    item_shelf: str = "rows",
    title: str | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    resolved_items = _resolve_fields(workbook, items or [], datasource)
    item_shelf, _ = _shelves(item_shelf)
    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.set_title(title)
    for field in resolved_items:
        worksheet.add_field(field=field, shelf=item_shelf)
    return worksheet


def draw_colored_yoy_sheet(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    items: list[FieldInput],
    metrics: list[FieldInput],
    negative_color: str = "#ff007f",
    positive_color: str = "#602fff",
    ratio_color: str = "#555555",
    mark_type: str = "bar",
    bar_color: str | None = None,
    axis_min: float = 0,
    axis_max: float = 1,
    show_axes: bool = False,
    bar_opacity: float = 1.0,
    index_partition_by: FieldInput | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    if not metrics:
        raise ValueError("metrics must not be empty")
    colors = {
        "negative_color": negative_color,
        "positive_color": positive_color,
        "ratio_color": ratio_color,
    }
    for color_name, color in colors.items():
        if not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
            raise ValueError(f"{color_name} must use #RRGGBB")

    resolved_items = _resolve_fields(workbook, items, datasource)
    resolved_metrics = _resolve_fields(workbook, metrics, datasource)
    partition_field = (
        None
        if index_partition_by is None
        else _resolve_fields(workbook, [index_partition_by], datasource)[0]
    )
    if partition_field is not None and not any(
        item.datasource_id == partition_field.datasource_id
        and item.id == partition_field.id
        for item in resolved_items
    ):
        raise ValueError("index_partition_by must also be included in items")
    datasource_ids = {metric.datasource_id for metric in resolved_metrics}
    if len(datasource_ids) != 1:
        raise ValueError("metrics must belong to the same datasource")
    metric_datasource = workbook.get_datasources(id=resolved_metrics[0].datasource_id)[0]

    metric_fields: list[tuple[TwbField, TwbField, TwbField]] = []
    for metric in resolved_metrics:
        names = (
            f"{metric.name}|昨年差<0",
            f"{metric.name}|昨年差>=0",
            f"{metric.name}比|昨年比",
        )
        fields: list[TwbField] = []
        for field_name in names:
            matches = metric_datasource.get_fields(name=field_name)
            if not matches:
                raise NotFoundError(f"field not found: {field_name}")
            if len(matches) > 1:
                raise AmbiguousCaptionError(f"field name is ambiguous: {field_name}")
            fields.append(matches[0])
        metric_fields.append((fields[0], fields[1], fields[2]))

    layout_matches = metric_datasource.get_fields(name="帳票配置用_MIN1")
    if len(layout_matches) > 1:
        raise AmbiguousCaptionError("field name is ambiguous: 帳票配置用_MIN1")
    if layout_matches:
        layout_field = layout_matches[0]
        formula = re.sub(r"\s+", "", layout_field.raw_formula or "").upper()
        if formula != "MIN(1)":
            raise ValueError("帳票配置用_MIN1 must use formula MIN(1)")
    else:
        layout_field = metric_datasource.create_calculated_field(
            name="帳票配置用_MIN1",
            formula="MIN(1)",
            datatype="integer",
            role="measure",
            discrete=False,
        )

    worksheet = workbook.create_worksheet(name=name, visible=visible)
    index_placement = None
    for item in resolved_items:
        placement = worksheet.add_field(
            field=item,
            shelf="rows",
            discrete=True,
            table_calculation="table_down" if item.name == "#" else None,
        )
        if item.name == "#":
            index_placement = placement
    if partition_field is not None:
        if index_placement is None:
            raise ValueError("index_partition_by requires a # item")
        worksheet._set_table_calculation_partition(index_placement, partition_field)
    worksheet._configure_colored_yoy_columns(
        layout_field,
        metric_fields,
        negative_color=negative_color,
        positive_color=positive_color,
        ratio_color=ratio_color,
        mark_type=mark_type,
        bar_color=bar_color,
        axis_min=axis_min,
        axis_max=axis_max,
        show_axes=show_axes,
        bar_opacity=bar_opacity,
    )
    worksheet.update(
        table_style={
            "header_background": "#f5f5f5",
            "header_bold": True,
            "header_color": "#555555",
            "row_band": False,
            "column_widths": (
                {"#": 36} if any(item.name == "#" for item in resolved_items) else {}
            ),
        }
    )
    return worksheet


def draw_yoy(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    item: FieldInput,
    metric: FieldInput,
    item_shelf: str = "columns",
    aggregation: str = "sum",
    date_level: str = "month",
    color: str | None = None,
    show_axes: bool = True,
    visible: bool = True,
) -> TwbWorksheet:
    item, metric = _resolve_fields(workbook, [item, metric], datasource)
    item_shelf, metric_shelf = _shelves(item_shelf)
    worksheet = workbook.create_worksheet(name=name, visible=visible)
    item_placement = worksheet.add_field(
        field=item,
        shelf=item_shelf,
        discrete=False,
        date_level=date_level,
    )
    metric_placement = worksheet.add_field(
        field=metric,
        shelf=metric_shelf,
        aggregation=aggregation,
        discrete=False,
    )
    pane = worksheet.get_panes()[0]
    pane.update(mark_type="line")
    if color is not None:
        pane.set_mark_color(color)
    if not show_axes:
        worksheet.set_axis_visibility(item_placement, visible=False)
        worksheet.set_axis_visibility(metric_placement, visible=False)
    return worksheet


def draw_bar(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    item: FieldInput,
    metric: FieldInput,
    item_shelf: str = "rows",
    aggregation: str = "sum",
    descending: bool = True,
    visible: bool = True,
) -> TwbWorksheet:
    item, metric = _resolve_fields(workbook, [item, metric], datasource)
    item_shelf, metric_shelf = _shelves(item_shelf)
    worksheet = workbook.create_worksheet(name=name, visible=visible)
    worksheet.add_field(field=item, shelf=item_shelf, discrete=True)
    worksheet.add_field(
        field=metric,
        shelf=metric_shelf,
        aggregation=aggregation,
        discrete=False,
    )
    worksheet.get_panes()[0].update(mark_type="bar")
    worksheet.add_sort(
        field=item,
        by=metric,
        direction="descending" if descending else "ascending",
        aggregation=aggregation,
    )
    return worksheet


def draw_card(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    main_metric: FieldInput,
    sub_metric: FieldInput | None = None,
    main_color: str = "#602fff",
    value_color: str = "#333333",
    title_background_color: str | None = None,
    vertical_alignment: str = "center",
    aggregation: str | None = "auto",
    main_aggregation: str | None = "auto",
    sub_aggregation: str | None = "auto",
    visible: bool = True,
) -> TwbWorksheet:
    resolved = _resolve_fields(
        workbook,
        [main_metric, *([] if sub_metric is None else [sub_metric])],
        datasource,
    )
    main_metric = resolved[0]
    sub_metric = resolved[1] if len(resolved) == 2 else None
    resolved_main_aggregation = _metric_aggregation(
        main_metric,
        aggregation,
        main_aggregation,
    )
    resolved_sub_aggregation = (
        None
        if sub_metric is None
        else _metric_aggregation(sub_metric, aggregation, sub_aggregation)
    )
    worksheet = workbook.create_worksheet(name=name, visible=visible)
    pane = worksheet.get_panes()[0]
    pane.update(mark_type="automatic")
    sub_placement = None
    if sub_metric is not None:
        sub_placement = pane.add_field(
            field=sub_metric,
            encoding="label",
            aggregation=resolved_sub_aggregation,
            discrete=False,
        )
    main_placement = pane.add_field(
        field=main_metric,
        encoding="label",
        aggregation=resolved_main_aggregation,
        discrete=False,
    )
    pane.set_customized_label(
        main_metric=main_placement,
        sub_metric=sub_placement,
        main_color=main_color,
        value_color=value_color,
        vertical_alignment=vertical_alignment,
    )
    worksheet.update(
        title_style={"background_color": title_background_color or main_color}
    )
    return worksheet


def draw_quadrant(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    item: FieldInput,
    x_metric: FieldInput,
    y_metric: FieldInput,
    size_metric: FieldInput,
    colors: tuple[str, str, str, str] | list[str] = (
        "#4400FF",
        "#FF007F",
        "#00C888",
        "#CCD500",
    ),
    x_aggregation: str | None = "auto",
    y_aggregation: str | None = "auto",
    size_aggregation: str | None = "auto",
    opacity: float = 0.6,
    title: str | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    item, x_metric, y_metric, size_metric = _resolve_fields(
        workbook,
        [item, x_metric, y_metric, size_metric],
        datasource,
    )
    datasource_ids = {
        field.datasource_id for field in (item, x_metric, y_metric, size_metric)
    }
    if len(datasource_ids) != 1:
        raise ValueError("draw_quadrant fields must belong to the same datasource")
    if len(colors) != 4:
        raise ValueError("colors must contain exactly four colors")

    x_aggregation = _metric_aggregation(x_metric, "auto", x_aggregation)
    y_aggregation = _metric_aggregation(y_metric, "auto", y_aggregation)
    size_aggregation = _metric_aggregation(size_metric, "auto", size_aggregation)
    x_expression = _metric_formula(x_metric, x_aggregation)
    y_expression = _metric_formula(y_metric, y_aggregation)
    quadrant_formula = (
        f'IF {x_expression} >= WINDOW_MEDIAN({x_expression}) '
        f'AND {y_expression} >= WINDOW_MEDIAN({y_expression}) THEN "1"\n'
        f'ELSEIF {x_expression} < WINDOW_MEDIAN({x_expression}) '
        f'AND {y_expression} >= WINDOW_MEDIAN({y_expression}) THEN "2"\n'
        f'ELSEIF {x_expression} < WINDOW_MEDIAN({x_expression}) '
        f'AND {y_expression} < WINDOW_MEDIAN({y_expression}) THEN "3"\n'
        'ELSE "4" END'
    )

    target_datasource = workbook.get_datasources(id=x_metric.datasource_id)[0]
    quadrant = target_datasource.create_calculated_field(
        name=f"{name}_四象限",
        formula=quadrant_formula,
        datatype="string",
        role="measure",
        discrete=True,
        hidden=None,
        table_calculation="Rows",
    )

    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.set_title(title)
    x_placement = worksheet.add_field(
        field=x_metric,
        shelf="columns",
        aggregation=x_aggregation,
        discrete=False,
    )
    y_placement = worksheet.add_field(
        field=y_metric,
        shelf="rows",
        aggregation=y_aggregation,
        discrete=False,
    )
    pane = worksheet.get_panes()[0]
    pane.update(mark_type="circle")
    pane.set_mark_sizing(scaling=False)
    pane.set_mark_opacity(opacity)
    pane.set_mark_size(4)
    pane.add_field(field=item, encoding="detail", discrete=True)
    pane.add_field(
        field=size_metric,
        encoding="size",
        aggregation=size_aggregation,
        discrete=False,
    )
    color_placement = pane.add_field(
        field=quadrant,
        encoding="color",
        discrete=True,
        table_calculation="field",
        table_calculation_field=item,
    )
    pane.set_categorical_colors(
        color_placement,
        {str(index): color for index, color in enumerate(colors, start=1)},
    )
    worksheet.add_reference_line(x_placement, formula="median")
    worksheet.add_reference_line(y_placement, formula="median")
    worksheet.add_reference_line(
        x_placement,
        formula="median",
        scope="per-pane",
        label_type="automatic",
        z_order=2,
    )
    return worksheet


def draw_crosstab(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    x_item: FieldInput,
    y_item: FieldInput,
    color_metric: FieldInput,
    label_metric: FieldInput,
    color_aggregation: str | None = "auto",
    label_aggregation: str | None = "auto",
    min_color: str | None = None,
    mid_color: str | None = None,
    max_color: str | None = None,
    title: str | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    palette = (min_color, mid_color, max_color)
    if any(color is not None for color in palette) and not all(
        color is not None for color in palette
    ):
        raise ValueError("min_color, mid_color, and max_color must be specified together")
    x_item, y_item, color_metric, label_metric = _resolve_fields(
        workbook,
        [x_item, y_item, color_metric, label_metric],
        datasource,
    )
    color_aggregation = _metric_aggregation(
        color_metric,
        "auto",
        color_aggregation,
    )
    label_aggregation = _metric_aggregation(
        label_metric,
        "auto",
        label_aggregation,
    )

    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.set_title(title)
    worksheet.add_field(field=x_item, shelf="columns", discrete=True)
    worksheet.add_field(field=y_item, shelf="rows", discrete=True)
    pane = worksheet.get_panes()[0]
    pane.update(mark_type="square")
    color_placement = pane.add_field(
        field=color_metric,
        encoding="color",
        aggregation=color_aggregation,
        discrete=False,
    )
    pane.add_field(
        field=label_metric,
        encoding="label",
        aggregation=label_aggregation,
        discrete=False,
    )
    pane.set_label_style(show=True, cull=False)
    if all(color is not None for color in palette):
        pane.set_continuous_colors(
            color_placement,
            min_color=min_color,
            mid_color=mid_color,
            max_color=max_color,
        )
    return worksheet
