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

#: 計算フィールドが集計済みかどうかは XML のどこにも記録されていない
#: （データソース側の metadata-record も計算フィールドには存在しない、実測済み）。
#: formula 文字列そのものを見て集計関数の呼び出しがあるかを判定する。
_AGGREGATE_FUNCTION_PATTERN = re.compile(
    r"\b(SUM|AVG|MIN|MAX|COUNTD|COUNT|ATTR|MEDIAN)\s*\(",
    re.IGNORECASE,
)


def _record_chart(workbook: TwbWorkbook, worksheet: TwbWorksheet, kind: str) -> TwbWorksheet:
    """描いたグラフの種類を控える。ダッシュボードへ置くときの余白がこれで決まる。"""
    workbook._context.chart_kinds[worksheet.name] = kind
    return worksheet


def _formula_has_aggregate_function(formula: str) -> bool:
    return _AGGREGATE_FUNCTION_PATTERN.search(formula) is not None


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


def _is_aggregated(workbook: TwbWorkbook, field: TwbField, seen: frozenset[str] = frozenset()) -> bool:
    """計算フィールドが集計済みか。式に集計関数があるか、集計済みの計算フィールドを参照していれば True。"""
    if not field.is_calculated or field.id in seen:
        return False
    if _formula_has_aggregate_function(field.raw_formula or ""):
        return True
    [datasource] = workbook.get_datasources(id=field.datasource_id)
    seen = seen | {field.id}
    return any(
        _is_aggregated(workbook, target, seen)
        for reference in field.referenced_fields
        for target in datasource.get_fields(id=reference)
    )


def _auto_metric_aggregation(workbook: TwbWorkbook, field: TwbField) -> str | None:
    if _is_aggregated(workbook, field):
        return "agg"
    if field.role != "measure" or (field.datatype or "").lower() not in _NUMERIC_DATATYPES:
        return "countd"
    return field.default_aggregation or "sum"


def _metric_aggregation(
    workbook: TwbWorkbook,
    field: TwbField,
    common: str | None,
    specific: str | None,
) -> str | None:
    selected = specific if specific != "auto" else common
    return _auto_metric_aggregation(workbook, field) if selected == "auto" else selected


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
        worksheet.update(title=title)
    for field in resolved_items:
        worksheet.add_field(field=field, shelf=item_shelf)
    return _record_chart(workbook, worksheet, "draw_sheet")


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
    bar_color: str | None = None,
    title: str | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    item, metric = _resolve_fields(workbook, [item, metric], datasource)
    item_shelf, metric_shelf = _shelves(item_shelf)
    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.update(title=title)
    worksheet.add_field(field=item, shelf=item_shelf, discrete=True)
    worksheet.add_field(
        field=metric,
        shelf=metric_shelf,
        aggregation=aggregation,
        discrete=False,
    )
    pane = worksheet.get_panes()[0]
    pane.update(mark_type="bar")
    if bar_color is not None:
        pane.update(mark_color=bar_color)
    worksheet.add_sort(
        field=item,
        by=metric,
        direction="descending" if descending else "ascending",
        aggregation=aggregation,
    )
    return _record_chart(workbook, worksheet, "draw_bar")


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
        workbook,
        main_metric,
        aggregation,
        main_aggregation,
    )
    resolved_sub_aggregation = (
        None
        if sub_metric is None
        else _metric_aggregation(workbook, sub_metric, aggregation, sub_aggregation)
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
    return _record_chart(workbook, worksheet, "draw_card")


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

    x_aggregation = _metric_aggregation(workbook, x_metric, "auto", x_aggregation)
    y_aggregation = _metric_aggregation(workbook, y_metric, "auto", y_aggregation)
    size_aggregation = _metric_aggregation(workbook, size_metric, "auto", size_aggregation)
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
        worksheet.update(title=title)
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
    pane.update(mark_scaling=False)
    pane.update(mark_opacity=opacity)
    pane.update(mark_size=4)
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
    worksheet.add_reference_line(field=x_placement, formula="median")
    worksheet.add_reference_line(field=y_placement, formula="median")
    worksheet.add_reference_line(
        field=x_placement,
        formula="median",
        scope="per-pane",
        label_type="automatic",
        z_order=2,
    )
    return _record_chart(workbook, worksheet, "draw_quadrant")


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
        workbook,
        color_metric,
        "auto",
        color_aggregation,
    )
    label_aggregation = _metric_aggregation(
        workbook,
        label_metric,
        "auto",
        label_aggregation,
    )

    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.update(title=title)
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
    pane.update(label_style={"show": True, "cull": False})
    if all(color is not None for color in palette):
        pane.set_continuous_colors(
            color_placement,
            min_color=min_color,
            mid_color=mid_color,
            max_color=max_color,
        )
    return _record_chart(workbook, worksheet, "draw_crosstab")
