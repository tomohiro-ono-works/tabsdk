"""接続型モデルから Tableau 定義書の DataFrame 群を作る。"""

from __future__ import annotations

import csv
from io import StringIO
from itertools import product

import pandas as pd

from .workbook import TwbWorkbook


_COLUMNS = {
    "ダッシュボード一覧": ["ダッシュボード名"],
    "シート一覧": ["ダッシュボード名", "シート名", "シート概要"],
    "シート詳細": [
        "ダッシュボード名", "シート名", "キー", "フィールド", "値",
        "field.table_calculation", "field.discrete",
    ],
    "シート詳細_フィルタ": [
        "ダッシュボード名", "シート名", "フィールド", "選択値",
        "フィルター種別", "フィルター適用範囲", "フィルター選択方式",
        "フィルター表示形式", "field.table_calculation", "field.discrete",
    ],
    "フィールド": [
        "データソース名", "フォルダ", "階層", "フィールド名", "オリジナル名",
        "フィールド種別", "データ型", "区分", "計算式",
    ],
    "パラメータ": [
        "パラメータ名", "データ型", "デフォルト値", "パラメータ値",
    ],
    "ダッシュボードアクション": [
        "ダッシュボード", "アクション種別", "発火元シート", "発火元フィールド",
        "発火先シート", "発火先フィールド", "発火先パラメータ",
    ],
}

_MARK_NAMES = {
    "automatic": "自動", "bar": "棒", "line": "折れ線", "text": "テキスト",
    "circle": "円", "square": "四角", "shape": "形状", "area": "面",
    "pie": "円グラフ", "gantt": "ガント",
}
_ENCODING_NAMES = {
    "label": "ラベル", "color": "色", "size": "サイズ",
    "detail": "詳細", "tooltip": "ツールヒント", "shape": "形状",
    "path": "パス", "angle": "角度",
}
_ACTION_NAMES = {
    "filter": "フィルターアクション", "highlight": "ハイライトアクション",
    "url": "URLアクション", "parameter": "パラメータアクション",
    "set": "セットアクション", "navigation": "ナビゲーションアクション",
}

_SORT_COLUMNS = {
    "シート一覧": ["ダッシュボード名", "シート名"],
    "シート詳細": ["ダッシュボード名", "シート名", "フィールド", "キー"],
    "シート詳細_フィルタ": ["ダッシュボード名", "シート名", "フィールド"],
    "フィールド": ["データソース名", "フォルダ", "階層", "データ型", "フィールド名"],
    "パラメータ": ["パラメータ名"],
    "ダッシュボードアクション": ["ダッシュボード", "アクション種別"],
}


def _comma_join(values: list[str]) -> str | None:
    if not values:
        return None
    buffer = StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(values)
    return buffer.getvalue().removesuffix("\n")


def _detail_rows(dashboard, worksheet) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    dashboard_name = dashboard.name if dashboard is not None else None
    color_rows: dict[str | None, dict[str, object]] = {}
    color_values: dict[str | None, list[str]] = {}

    def add(
        key: str,
        field: str | None = None,
        value: object = None,
        *,
        placement=None,
    ) -> dict[str, object]:
        row = {
            "ダッシュボード名": dashboard_name,
            "シート名": worksheet.name,
            "キー": key,
            "フィールド": field,
            "値": value,
            "field.table_calculation": placement.table_calculation if placement is not None else None,
            "field.discrete": placement.discrete if placement is not None else None,
        }
        rows.append(row)
        return row

    def add_color(field_name: str | None, values: list[str], *, placement=None) -> None:
        if field_name not in color_rows:
            color_rows[field_name] = add("ペイン：色", field_name, placement=placement)
            color_values[field_name] = []
        elif placement is not None:
            row = color_rows[field_name]
            for column, current in (
                ("field.table_calculation", placement.table_calculation),
                ("field.discrete", placement.discrete),
            ):
                if row[column] != current:
                    row[column] = None
        for value in values:
            if value not in color_values[field_name]:
                color_values[field_name].append(value)

    for pane in worksheet.get_panes():
        add("グラフの種類", value=_MARK_NAMES.get(pane.mark_type, pane.mark_type))
        if pane.mark_color:
            add_color(None, [pane.mark_color])
        if pane.mark_opacity is not None:
            add("ペイン：透過率", value=f"{1 - pane.mark_opacity:.2%}")
        for field in pane.get_fields():
            key = "ペイン：" + _ENCODING_NAMES.get(field.encoding, field.encoding or "")
            value = field.aggregation or field.date_level
            if field.encoding == "color":
                categorical = pane.get_categorical_colors(field)
                continuous = pane.get_continuous_colors(field)
                if categorical:
                    add_color(
                        field.name,
                        [f"{label}={color}" for label, color in categorical.items()],
                        placement=field,
                    )
                    continue
                if continuous:
                    add_color(
                        field.name,
                        [
                            f"{label}={continuous[part]}"
                            for part, label in (
                                ("min_color", "最小"), ("mid_color", "中間"),
                                ("max_color", "最大"),
                            )
                            if part in continuous
                        ],
                        placement=field,
                    )
                    continue
                add_color(field.name, [value] if value is not None else [], placement=field)
                continue
            add(key, field.name, value, placement=field)
    for field_name, row in color_rows.items():
        row["値"] = _comma_join(color_values[field_name])
    worksheet_fields = worksheet.get_fields()
    for field in worksheet_fields:
        if field.shelf in {"rows", "columns"}:
            add(
                "行" if field.shelf == "rows" else "列",
                field.name, field.aggregation or field.date_level, placement=field,
            )
    return rows


def _filter_rows(dashboard, worksheet) -> list[dict[str, object]]:
    dashboard_name = dashboard.name if dashboard is not None else None
    filter_fields = {
        field.attrs.get("column"): field
        for field in worksheet.get_fields()
        if field.shelf == "filters" and field.attrs.get("column")
    }
    controls_by_column: dict[str, list] = {}
    if dashboard is not None:
        for control in dashboard.get_filter_controls():
            if control.worksheet != worksheet.name or control.column is None:
                continue
            controls_by_column.setdefault(control.column, []).append(control)

    def display_modes(column: str) -> str | None:
        modes = list(dict.fromkeys(
            control.mode for control in controls_by_column.get(column, [])
            if control.mode is not None
        ))
        return ",".join(modes) or None

    rows: list[dict[str, object]] = []
    filter_ids: set[str] = set()
    for filter_item in worksheet.get_filters():
        filter_ids.add(filter_item.id)
        placement = filter_fields.get(filter_item.id)
        rows.append({
            "ダッシュボード名": dashboard_name,
            "シート名": worksheet.name,
            "フィールド": filter_item.name,
            "選択値": ",".join(filter_item.values) if filter_item.values else None,
            "フィルター種別": filter_item.filter_class,
            "フィルター適用範囲": filter_item.apply_scope,
            "フィルター選択方式": filter_item.selection_type,
            "フィルター表示形式": display_modes(filter_item.id),
            "field.table_calculation": placement.table_calculation if placement is not None else None,
            "field.discrete": placement.discrete if placement is not None else None,
        })
    for column, controls in controls_by_column.items():
        if column in filter_ids:
            continue
        control = controls[0]
        placement = filter_fields.get(column)
        rows.append({
            "ダッシュボード名": dashboard_name,
            "シート名": worksheet.name,
            "フィールド": control.field or column,
            "選択値": ",".join(control.values) if control.values else None,
            "フィルター種別": control.filter_class,
            "フィルター適用範囲": control.apply_scope,
            "フィルター選択方式": control.selection_type,
            "フィルター表示形式": display_modes(column),
            "field.table_calculation": placement.table_calculation if placement is not None else None,
            "field.discrete": placement.discrete if placement is not None else None,
        })
    return rows


def _parameter_values(parameter) -> str | None:
    if parameter.domain_type == "range":
        return _comma_join([
            f"{label}={value}" for label, value in (
                ("最小", parameter.min_value), ("最大", parameter.max_value),
                ("間隔", parameter.step_size),
            ) if value is not None
        ])
    return _comma_join([
        str(item["value"])
        for item in parameter.allowable_values
        if item["value"] is not None
    ])


def get_definitions(input_path: str) -> dict[str, pd.DataFrame]:
    """`.twb` / `.twbx` を一度開き、7 定義を DataFrame 辞書で返す。"""
    workbook = TwbWorkbook.open(str(input_path))
    rows: dict[str, list[dict[str, object]]] = {name: [] for name in _COLUMNS}
    dashboards = workbook.get_dashboards()
    worksheets = workbook.get_worksheets()
    placements: dict[str, list] = {sheet.id: [] for sheet in worksheets}

    for dashboard in dashboards:
        rows["ダッシュボード一覧"].append({"ダッシュボード名": dashboard.name})
        for worksheet in dashboard.get_worksheets():
            placements[worksheet.id].append(dashboard)

    for worksheet in worksheets:
        for dashboard in placements[worksheet.id] or [None]:
            rows["シート一覧"].append({
                "ダッシュボード名": dashboard.name if dashboard is not None else None,
                "シート名": worksheet.name,
                "シート概要": None,
            })
            rows["シート詳細"].extend(_detail_rows(dashboard, worksheet))
            rows["シート詳細_フィルタ"].extend(_filter_rows(dashboard, worksheet))

    for datasource in workbook.get_datasources():
        hierarchies: dict[str, list[str]] = {}
        hierarchy_folders: dict[str, list[str]] = {}
        for path in datasource.get_drill_paths():
            folder = path.folder
            for field_id in path.field_ids:
                names = hierarchies.setdefault(field_id, [])
                if path.name not in names:
                    names.append(path.name)
                if folder is not None:
                    folders = hierarchy_folders.setdefault(field_id, [])
                    if folder.name not in folders:
                        folders.append(folder.name)
        for field in datasource.get_fields():
            folder = field.folder
            rows["フィールド"].append({
                "データソース名": datasource.name,
                "フォルダ": folder.name if folder else _comma_join(hierarchy_folders.get(field.id, [])),
                "階層": _comma_join(hierarchies.get(field.id, [])),
                "フィールド名": field.name,
                "オリジナル名": field.original_name,
                "フィールド種別": "計算フィールド" if field.is_calculated else "オリジナル",
                "データ型": field.datatype,
                "区分": {"dimension": "ディメンション", "measure": "メジャー"}.get(field.role, field.role),
                "計算式": field.formula if field.is_calculated else None,
            })

    for parameter in workbook.get_parameters(include_hidden=True):
        rows["パラメータ"].append({
            "パラメータ名": parameter.name,
            "データ型": parameter.datatype,
            "デフォルト値": parameter.value,
            "パラメータ値": _parameter_values(parameter),
        })

    for dashboard in dashboards:
        for action in dashboard.get_actions():
            mappings = action.field_mappings or [{"source_field": None, "target_field": None}]
            for source, target, mapping in product(
                action.source_worksheet_ids or [None],
                action.target_worksheet_ids or [None],
                mappings,
            ):
                source_sheet = workbook.get_worksheets(id=source) if source else []
                target_sheet = workbook.get_worksheets(id=target) if target else []
                rows["ダッシュボードアクション"].append({
                    "ダッシュボード": dashboard.name,
                    "アクション種別": _ACTION_NAMES.get(action.type, action.type),
                    "発火元シート": source_sheet[0].name if source_sheet else None,
                    "発火元フィールド": mapping["source_field"],
                    "発火先シート": target_sheet[0].name if target_sheet else None,
                    "発火先フィールド": mapping["target_field"],
                    "発火先パラメータ": action.target_parameter_name,
                })

    definitions: dict[str, pd.DataFrame] = {}
    for name, columns in _COLUMNS.items():
        frame = pd.DataFrame(rows[name], columns=columns)
        if name in _SORT_COLUMNS:
            frame = frame.sort_values(
                by=_SORT_COLUMNS[name], kind="stable", na_position="last",
            )
        definitions[name] = frame.fillna("").reset_index(drop=True)
    return definitions
