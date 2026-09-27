from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .connected import TwbDatasource, TwbField, TwbFolder
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


def _is_table_calculation(field: TwbField) -> bool:
    """表計算のフィールドか。集計を付けられないので置き方を変える（2026-09-21）。"""
    from .connected_worksheet import _table_calculation_kind

    return _table_calculation_kind(field) is not None


def _text_align(field: TwbField) -> str:
    """帳票の文字の揃え。数字は右、それ以外は左（2026-09-22 指定）。"""
    return "right" if (field.datatype or "").lower() in _NUMERIC_DATATYPES else "left"


#: 帳票の色帯のマークの太さ。**帯なのでセルいっぱいに太くする**（2026-09-22 指定）。
#: 値は examples/サンプル.twb の色帯から採った実測値（棒は既定のままにする）。
_SHEET_COLOR_BAND_SIZE = 5.5472970008850098

#: 帳票の棒の既定の色。
_SHEET_BAR_COLOR = "#4a7dff"
#: 帳票の色帯の既定の 2 色（薄い側 → 濃い側）。
_SHEET_COLOR_RANGE = ("#e8eef7", "#2f3b52")

#: 表ヘッダー（フィールドラベル）の背景。薄い灰色（2026-09-22 指定）。
_SHEET_HEADER_BACKGROUND = "#f0f0f0"


def _constant_field(
    workbook: TwbWorkbook,
    datasource: TwbDatasource,
    name: str,
    formula: str,
) -> TwbField:
    """帳票の色帯が使う定数の計算フィールド。同名があれば作り直す。"""
    for existing in datasource.get_fields(name=name):
        existing.delete()
    return datasource.create_calculated_field(
        name=name, formula=formula, datatype="integer", role="measure", hidden=True
    )


def draw_sheet(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    items: list[FieldInput] | None = None,
    bar_metrics: list[FieldInput] | None = None,
    color_metrics: list[FieldInput] | None = None,
    bar_colors: list[str] | None = None,
    color_starts: list[str] | None = None,
    color_ends: list[str] | None = None,
    item_shelf: str = "rows",
    title: str | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    """帳票。`items` を指定シェルフへ並べる。

    `bar_metrics` は棒の列、`color_metrics` は色帯の列として**横に足す**
    （2026-09-22 追加。examples/サンプル.twb の作りに合わせた）。
    棒はメジャーを連続で置いて軸を隠すだけ。色帯は `MIN(1)` の軸（0〜1 に固定して
    隠す）へ、長さ `MIN(-1)` のガントバーを置き、色にメジャーを載せる
    （セル幅いっぱいの帯になる）。軸は重ねず横に並べるので、何列でも足せる。

    色は列ごとに指定する。**棒は 1 色（`bar_colors`）、色帯は 2 色**
    （`color_starts` が薄い側、`color_ends` が濃い側。この 2 色の濃淡で塗る）。
    どれもメジャーと同じ並びで渡す。足りない分は既定の色になる。
    """
    resolved_items = _resolve_fields(workbook, items or [], datasource)
    resolved_bars = _resolve_fields(workbook, bar_metrics or [], datasource)
    resolved_colors = _resolve_fields(workbook, color_metrics or [], datasource)
    if (resolved_bars or resolved_colors) and item_shelf != "rows":
        raise ValueError("bar_metrics and color_metrics need item_shelf='rows'")
    if resolved_bars or resolved_colors:
        _check_sheet_name(workbook, name)
    item_shelf, metric_shelf = _shelves(item_shelf)
    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.update(title=title)
    item_pills: list[str] = []
    for field in resolved_items:
        if field.role == "measure" and not _is_table_calculation(field):
            # メジャーは集計してからディメンション（不連続）として置く（2026-09-21）。
            # 帳票は値を並べる表なので、連続の軸ではなく文字として出したい。
            # 表計算（index() など）は集計を付けられないので、今までどおり置く。
            placement = worksheet.add_field(
                field=field,
                shelf=item_shelf,
                aggregation=_metric_aggregation(workbook, field, "auto", "auto"),
                discrete=True,
            )
        else:
            placement = worksheet.add_field(field=field, shelf=item_shelf)
        # 数字は右、文字は左に揃える（2026-09-22 指定）
        worksheet._apply_field_text_align(placement, _text_align(field))
        item_pills.append(placement._resolve_placement().reference)

    if resolved_bars or resolved_colors:
        # 項目名を補うのは棒・色帯の列だけ。行に置いた項目の名前は Tableau が出す。
        # 列幅は `build_report()` がゾーンの幅から決めるので、ここでは名前だけ覚える
        workbook._context.sheet_columns[name] = (
            item_pills,
            [field.name for field in resolved_bars + resolved_colors],
        )
        _add_sheet_columns(
            workbook, worksheet, name, metric_shelf, resolved_bars, resolved_colors,
            _colors_for(bar_colors, len(resolved_bars), (_SHEET_BAR_COLOR,)),
            [
                (start, end)
                for start, end in zip(
                    _colors_for(color_starts, len(resolved_colors),
                                (_SHEET_COLOR_RANGE[0],)),
                    _colors_for(color_ends, len(resolved_colors),
                                (_SHEET_COLOR_RANGE[1],)),
                )
            ],
        )
    # 既定の行の縞模様を消し（2026-09-21）、表ヘッダーを薄い灰色にする（2026-09-22）
    worksheet.update(table_style={
        "row_band": False,
        "header_background": _SHEET_HEADER_BACKGROUND,
    })
    return _record_chart(workbook, worksheet, "draw_sheet")


def _colors_for(given: list[str] | None, count: int, default: tuple[str, ...]) -> list[str]:
    """列ごとの色。指定が足りない分は既定の色で埋める（2026-09-22）。"""
    given = list(given or [])
    if any(not isinstance(color, str) or not color.strip() for color in given):
        raise ValueError("colors must be色コードの文字列")
    return [
        given[index].strip() if index < len(given) else default[0]
        for index in range(count)
    ]


def _add_sheet_columns(
    workbook: TwbWorkbook,
    worksheet: TwbWorksheet,
    name: str,
    shelf: str,
    bars: list[TwbField],
    colors: list[TwbField],
    bar_colors: list[str],
    color_ranges: list[tuple[str, str]],
) -> None:
    """帳票へ棒と色帯の列を足す（2026-09-22）。

    列は軸ごとにペインが分かれる。軸は重ねない（`overlay=False`）ので横に並ぶ。
    """
    # (軸のピル, 値のメジャー, 帯の長さのフィールド)。棒の列は長さが None
    columns: list[tuple[Any, TwbField, TwbField | None]] = []
    for field in bars:
        columns.append((
            worksheet.add_field(
                field=field,
                shelf=shelf,
                aggregation=_metric_aggregation(workbook, field, "auto", "auto"),
                discrete=False,
            ),
            field,
            None,
        ))
    for index, field in enumerate(colors, start=1):
        # 色帯は「常に 1」の軸に「長さ -1」のガントバーを置いてセル幅を埋める。
        # 列ごとに別のピルが要るので、色帯の数だけ定数フィールドを作る。
        [datasource] = workbook.get_datasources(id=field.datasource_id)
        band = _constant_field(workbook, datasource, f"{name}_色帯{index}", "MIN(1)")
        width = _constant_field(workbook, datasource, f"{name}_色帯幅{index}", "MIN(-1)")
        columns.append((
            worksheet.add_field(field=band, shelf=shelf, aggregation="agg", discrete=False),
            field,
            width,
        ))

    placements = [placement for placement, _, _ in columns]
    if len(placements) > 1:
        worksheet.set_dual_axis(shelf=shelf, fields=placements, overlay=False)
    panes = worksheet.get_panes()
    # 軸が 2 本以上あると、先頭に軸名を持たない土台のペインが付く
    axis_panes = panes[1:] if len(placements) > 1 else panes
    bar_index = color_index = 0
    for (placement, metric, width), pane in zip(columns, axis_panes):
        aggregation = _metric_aggregation(workbook, metric, "auto", "auto")
        if width is None:
            pane.update(mark_type="bar", mark_color=bar_colors[bar_index])
            bar_index += 1
            worksheet._apply_axis_format(placement, display=False)
        else:
            worksheet._apply_axis_format(placement, display=False, minimum=0, maximum=1)
            # 色帯はセルいっぱいに太くする。棒は既定の太さのまま（2026-09-22 指定）
            pane.update(mark_type="gantt", mark_size=_SHEET_COLOR_BAND_SIZE)
            color_placement = pane.add_field(
                field=metric, encoding="color", aggregation=aggregation, discrete=False
            )
            pane.add_field(
                field=width, encoding="size", aggregation="agg", discrete=False
            )
            # 薄い側 → 濃い側の 2 色で塗る（2026-09-22 指定）
            start, end = color_ranges[color_index]
            color_index += 1
            pane.set_continuous_colors(color_placement, min_color=start, max_color=end)
        # 値をラベルで出す。列へ置いただけでは数字が見えない（2026-09-22）
        pane.add_field(
            field=metric, encoding="label", aggregation=aggregation, discrete=False
        )
        pane.update(label_style={"show": True, "cull": True, "align": "right"})


#: バーインバーの内側（サブメジャー）の棒の太さ。既定の太さを 1 として細くする。
#: Tableau も実ファイルで外側 1.34 / 内側 0.71 のように差を付けていた（2026-09-22）。
_SUB_BAR_SIZE = 0.5


def draw_bar(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    # 画面の並びを変えないよう、項目を既定値付きのままメジャーより前に置く
    # （キーワード専用の引数なので、既定値の有無と並び順は無関係）
    item: FieldInput | None = None,
    metric: FieldInput,
    sub_metric: FieldInput | None = None,
    line_metric: FieldInput | None = None,
    item_shelf: str = "rows",
    aggregation: str | None = "auto",
    descending: bool = True,
    bar_color: str | None = None,
    sub_bar_color: str | None = None,
    line_color: str | None = None,
    title: str | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    """棒グラフ。

    `item` を省くとディメンションを置かず、棒を 1 本だけ描く（2026-09-22）。
    `sub_metric` はバーインバー、`line_metric` は二重軸の折れ線。
    Tableau の二重軸は 2 軸までなので、**3 つそろえるときだけ組み方が変わる**。

    - `sub_metric` だけ: 二重軸。軸を同期し、内側（サブ）の棒を細くする
    - `line_metric` だけ: 二重軸。2 本目を折れ線にし、単位が違うので同期しない
    - 両方: 棒の軸をメジャーバリューにまとめ（メジャーネームで色分け、
      スタックを外して重ねる）、折れ線を 2 本目の軸にする。
      **このときは棒 2 本が同じ太さになる**（1 つのペインに 1 つの太さしか
      持てないため）

    `aggregation` の既定は他のグラフと同じ `"auto"`（2026-09-22 に `"sum"` から変更）。
    **式の中に集計関数があるメジャーは、合計ではなく集計（`agg`）として置く。**
    以前は棒グラフだけ合計に固定していたため、`SUM([売上]) / SUM([売上(昨年)])`
    のような計算フィールドが二重に集計されていた。
    """
    # 空文字は「指定なし」とみなす。設定画面は使わない引数を空のまま渡すため。
    if isinstance(item, str) and not item.strip():
        item = None
    if isinstance(sub_metric, str) and not sub_metric.strip():
        sub_metric = None
    if isinstance(line_metric, str) and not line_metric.strip():
        line_metric = None

    resolved = _resolve_fields(
        workbook,
        [
            metric,
            *([] if item is None else [item]),
            *([] if sub_metric is None else [sub_metric]),
            *([] if line_metric is None else [line_metric]),
        ],
        datasource,
    )
    metric = resolved[0]
    rest = list(resolved[1:])
    item = None if item is None else rest.pop(0)
    sub_metric = rest.pop(0) if sub_metric is not None else None
    line_metric = rest.pop(0) if line_metric is not None else None

    # 集計はメジャーごとに決める。式の中に集計関数があるものは合計ではなく
    # 集計（agg）として置く（2026-09-22。他のグラフと同じ扱いへ揃えた）。
    metric_aggregations = {
        field.id: _metric_aggregation(workbook, field, aggregation, "auto")
        for field in (metric, sub_metric, line_metric)
        if field is not None
    }

    item_shelf, metric_shelf = _shelves(item_shelf)
    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.update(title=title)
    if item is not None:
        worksheet.add_field(field=item, shelf=item_shelf, discrete=True)

    if sub_metric is not None and line_metric is not None:
        # 棒は 1 本の軸（メジャーバリュー）へまとめ、空いた 2 本目を折れ線に回す。
        # 色は二重軸を組んでから、メジャーバリューの軸のペインにだけ載せる
        # （折れ線の軸に載せると折れ線まで分かれてしまう）。
        bar_placement = worksheet.add_measure_values(
            shelf=metric_shelf,
            fields=[metric, sub_metric],
            aggregations=[
                metric_aggregations[metric.id], metric_aggregations[sub_metric.id]
            ],
            color=False,
        )
    else:
        bar_placement = worksheet.add_field(
            field=metric,
            shelf=metric_shelf,
            aggregation=metric_aggregations[metric.id],
            discrete=False,
        )
    overlay = sub_metric if line_metric is None else line_metric
    if overlay is None:
        pane = worksheet.get_panes()[0]
        pane.update(mark_type="bar")
        if bar_color is not None:
            pane.update(mark_color=bar_color)
    else:
        overlay_placement = worksheet.add_field(
            field=overlay,
            shelf=metric_shelf,
            aggregation=metric_aggregations[overlay.id],
            discrete=False,
        )
        # バーインバーは同じ物差しで比べるので軸を同期する。折れ線は単位が
        # 違うので同期しない（2026-09-22）。
        worksheet.set_dual_axis(
            shelf=metric_shelf,
            fields=[bar_placement, overlay_placement],
            synchronized=line_metric is None,
        )
        ground, main_pane, overlay_pane = worksheet.get_panes()[:3]
        ground.update(mark_type="bar")
        main_pane.update(mark_type="bar")
        if sub_metric is not None and line_metric is not None:
            # メジャーバリューの棒は既定で積み上がる。重ねるので外す
            ground.update(stacked=False)
            main_pane.update(stacked=False)
            main_pane._add_column_encoding(
                encoding="color",
                column=f"[{metric.datasource_id}].[:Measure Names]",
            )
        elif bar_color is not None:
            main_pane.update(mark_color=bar_color)
        if line_metric is None:
            overlay_pane.update(mark_type="bar", mark_size=_SUB_BAR_SIZE)
            if sub_bar_color is not None:
                overlay_pane.update(mark_color=sub_bar_color)
        else:
            overlay_pane.update(mark_type="line")
            if line_color is not None:
                overlay_pane.update(mark_color=line_color)
    if item is not None:
        # 並べ替えの基準も、置いたピルと同じ集計にする（2026-09-22）
        worksheet.add_sort(
            field=item,
            by=metric,
            direction="descending" if descending else "ascending",
            aggregation=metric_aggregations[metric.id],
        )
    # 縦棒（item が列）は「高さを合わせる」、横棒（item が行）は「幅を合わせる」を
    # ダッシュボード側の表示倍率にする（2026-09-22）。種類名を向きで分けて記録する。
    bar_kind = "draw_bar_v" if item_shelf == "columns" else "draw_bar_h"
    return _record_chart(workbook, worksheet, bar_kind)


#: `draw_card(mode=)` の選択肢（2026-09-21 追加）。
CARD_MODES = ("sub_metric", "budget")


def _number(value: object, label: str) -> float:
    """数値を受ける。設定画面は数の入力欄も文字列で渡すため、文字列も許す。"""
    if isinstance(value, bool) or value is None:
        raise TypeError(f"{label} must be a number")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        raise TypeError(f"{label} must be a number: {value!r}") from None


def _check_sheet_name(workbook: TwbWorkbook, name: str) -> None:
    """計算フィールドを作り直す前に、シート名の重複を先に見る（2026-09-22）。

    `{シート名}_…` の計算フィールドはそのシートの持ち物なので作り直すが、
    同名のシートが残っていると**そのシートが参照している**ため消せず、
    `ResourceInUseError`（何が起きたのか分からないエラー）になる。
    どちらにしても `create_worksheet()` で止まるので、先に同じ文言で止める。
    """
    if workbook.get_worksheets(name=name):
        raise ValueError(f"worksheet already exists: {name}")


def _budget_fields(
    workbook: TwbWorkbook,
    name: str,
    budget_metric: TwbField,
    threshold: float,
    aggregation: str | None,
    folder: str | TwbFolder | None,
) -> list[list[TwbField]]:
    """予実比較の「達成」「未達」を条件ごとの計算フィールドにする（2026-09-21）。

    ラベルの文字色は run ごとに 1 色しか書けないため、色を分けたい条件の数だけ
    フィールドを作る。条件に合わない側は NULL になり、その値は表示されない。
    条件ごとに 2 つ作る。率（パーセント表示）と、「達成」「未達」の文言。
    `folder` を渡すと 4 つとも同じフォルダへ入れる（無ければ作る）。
    """
    expression = _metric_formula(budget_metric, aggregation)
    datasource = workbook.get_datasources(id=budget_metric.datasource_id)[0]
    made: list[list[TwbField]] = []
    for suffix, comparison in (("達成", ">="), ("未達", "<")):
        condition = f"IF {expression} {comparison} {threshold} THEN"
        group = []
        for field_name, formula, datatype, number_format in (
            (f"{name}_{suffix}", f"{condition} {expression} END", "real", "%"),
            (f"{name}_{suffix}判定", f'{condition} "{suffix}" END', "string", None),
        ):
            existing = datasource.get_fields(name=field_name)
            if existing:
                existing[0].delete()
            group.append(
                datasource.create_calculated_field(
                    name=field_name,
                    formula=formula,
                    datatype=datatype,
                    role="measure",
                    hidden=None,
                    number_format=number_format,
                    folder=folder,
                    create_folder_if_missing=True,
                )
            )
        made.append(group)
    return made


def draw_card(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    main_metric: FieldInput,
    mode: str = "sub_metric",
    sub_metric: FieldInput | None = None,
    budget_metric: FieldInput | None = None,
    budget_threshold: float = 1.0,
    achieved_color: str = "#2f9e44",
    missed_color: str = "#e03131",
    main_color: str = "#602fff",
    value_color: str = "#333333",
    budget_value_color: str = "#666666",
    title_background_color: str | None = None,
    vertical_alignment: str = "center",
    aggregation: str | None = "auto",
    main_aggregation: str | None = "auto",
    sub_aggregation: str | None = "auto",
    budget_aggregation: str | None = "auto",
    visible: bool = True,
    folder: str | TwbFolder | None = None,
) -> TwbWorksheet:
    if mode not in CARD_MODES:
        raise ValueError(f"mode must be one of {CARD_MODES}")
    # 空文字は「指定なし」とみなす。設定画面は使わない引数を空のまま渡すため。
    if isinstance(sub_metric, str) and not sub_metric.strip():
        sub_metric = None
    if isinstance(budget_metric, str) and not budget_metric.strip():
        budget_metric = None
    if mode == "budget":
        if budget_metric is None:
            raise ValueError("budget mode needs budget_metric")
        if sub_metric is not None:
            raise ValueError("budget mode does not take sub_metric")
        budget_threshold = _number(budget_threshold, "budget_threshold")
        for color in (achieved_color, missed_color):
            if not isinstance(color, str) or not color.strip():
                raise ValueError("achieved_color and missed_color must be color codes")
    elif budget_metric is not None:
        raise ValueError("budget_metric needs mode='budget'")

    resolved = _resolve_fields(
        workbook,
        [
            main_metric,
            *([] if sub_metric is None else [sub_metric]),
            *([] if budget_metric is None else [budget_metric]),
        ],
        datasource,
    )
    main_metric = resolved[0]
    budget_metric = resolved[1] if mode == "budget" else None
    sub_metric = resolved[1] if mode != "budget" and len(resolved) == 2 else None
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
    # 予実比較は達成・未達の 2 フィールドを先に作る。XML を変える前に作るので、
    # ここで失敗してもワークシートは残らない。
    budget_pair = None
    if mode == "budget":
        _check_sheet_name(workbook, name)
        budget_pair = _budget_fields(
            workbook,
            name,
            budget_metric,
            budget_threshold,
            _metric_aggregation(workbook, budget_metric, aggregation, budget_aggregation),
            folder,
        )

    worksheet = workbook.create_worksheet(name=name, visible=visible)
    pane = worksheet.get_panes()[0]
    pane.update(mark_type="automatic")
    sub_placement = None
    sub_pairs = None
    if sub_metric is not None:
        sub_placement = pane.add_field(
            field=sub_metric,
            encoding="label",
            aggregation=resolved_sub_aggregation,
            discrete=False,
        )
    elif budget_pair is not None:
        # 作った式そのものの集計を見て置く（2026-09-21 修正）。集計済みの式は
        # 集計なし（none:）ではなく agg（usr:）で置く。none: にしていたため
        # Tableau で「集計と非集計を混在できない」エラーになっていた。
        sub_pairs = [
            (
                [
                    pane.add_field(
                        field=field,
                        encoding="label",
                        aggregation=_auto_metric_aggregation(workbook, field),
                        # 文言は文字列なので不連続（:nk）で置く（2026-09-21 修正）。
                        # 連続（:qk）にしていたため Tableau がシートをエラーにしていた。
                        discrete=(field.datatype or "").lower() == "string",
                    )
                    for field in group
                ],
                color,
            )
            for group, color in zip(budget_pair, (achieved_color, missed_color))
        ]
    main_placement = pane.add_field(
        field=main_metric,
        encoding="label",
        aggregation=resolved_main_aggregation,
        discrete=False,
    )
    pane.set_customized_label(
        main_metric=main_placement,
        sub_metric=sub_placement,
        sub_metrics=sub_pairs,
        main_color=main_color,
        value_color=value_color,
        # 達成/未達の「率」の文字色。文言の方は達成・未達それぞれの色（2026-09-22）
        sub_value_color=budget_value_color,
        vertical_alignment=vertical_alignment,
    )
    worksheet.update(
        title_style={"background_color": title_background_color or main_color}
    )
    return _record_chart(workbook, worksheet, "draw_card")


#: 四象限のフィルターパラメータの初期値。
_QUADRANT_CENTER_RATIO = 0.95
_QUADRANT_SIZE_THRESHOLD = 0.0


def _center_range_formula(x_expression: str, y_expression: str, ratio: str) -> str:
    """X・Y が両方とも「中央値を中心にした中央の `ratio` 割」に入るかどうか。

    順位のパーセンタイルの範囲は 0.5 ± ratio/2（ratio=0.9 なら 5%〜95%）。
    `WINDOW_PERCENTILE` の第 2 引数は浮動小数点の**リテラルしか受けない**
    （パラメータを入れると Tableau がエラーにする、2026-09-25 ユーザー報告）ので、
    パラメータと比較できる `RANK_PERCENTILE` を使う。
    """

    def within(expression: str) -> str:
        rank = f"RANK_PERCENTILE({expression})"
        return (
            f"({rank} >= (1 - {ratio}) / 2 "
            f"AND {rank} <= 1 - (1 - {ratio}) / 2)"
        )

    return f"{within(x_expression)}\nAND {within(y_expression)}"


def _quadrant_filter_field(
    workbook: TwbWorkbook,
    datasource: TwbDatasource,
    parameter_name: str,
    field_name: str,
    formula: str,
    *,
    parameter_value: float,
    parameter_range: tuple[float, float, float] | None,
    table_calculation: str | None = None,
) -> TwbField:
    """四象限のフィルター用に、パラメータと、それを使う真偽値の計算フィールドを作る。

    どちらも `{シート名}_…` でそのシートの持ち物なので、同名があれば作り直す
    （計算フィールドを先に消す。パラメータはそれに参照されているうちは消せない）。
    """
    for existing in datasource.get_fields(name=field_name):
        existing.delete()
    for existing_parameter in workbook.get_parameters(name=parameter_name):
        existing_parameter.delete()
    if parameter_range is None:
        workbook.create_parameter(
            name=parameter_name, value=float(parameter_value), datatype="real"
        )
    else:
        minimum, maximum, step = parameter_range
        workbook.create_parameter(
            name=parameter_name,
            value=float(parameter_value),
            datatype="real",
            domain_type="range",
            min_value=minimum,
            max_value=maximum,
            step_size=step,
        )
    return datasource.create_calculated_field(
        name=field_name,
        formula=formula,
        datatype="boolean",
        role="measure",
        discrete=True,
        hidden=None,
        table_calculation=table_calculation,
        ref_map={"Parameters": "Parameters", parameter_name: parameter_name},
    )


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
    """散布図の四象限。

    外れ値でグラフの外形が崩れないよう、このシート専用の Tableau パラメータ 2 つで
    点を絞る（Tableau 上で後から変えられる）。
    `{シート名}_中央比率`（初期値 0.95）: X・Y それぞれ中央値を中心に中央の 95% だけ残す。
    `{シート名}_売上閾値`（初期値 0）: 集計後のサイズ指標がこの値以上の点だけ残す。
    """
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
    size_expression = _metric_formula(size_metric, size_aggregation)
    quadrant_formula = (
        f'IF {x_expression} >= WINDOW_MEDIAN({x_expression}) '
        f'AND {y_expression} >= WINDOW_MEDIAN({y_expression}) THEN "1"\n'
        f'ELSEIF {x_expression} < WINDOW_MEDIAN({x_expression}) '
        f'AND {y_expression} >= WINDOW_MEDIAN({y_expression}) THEN "2"\n'
        f'ELSEIF {x_expression} < WINDOW_MEDIAN({x_expression}) '
        f'AND {y_expression} < WINDOW_MEDIAN({y_expression}) THEN "3"\n'
        'ELSE "4" END'
    )

    _check_sheet_name(workbook, name)
    target_datasource = workbook.get_datasources(id=x_metric.datasource_id)[0]
    # `{シート名}_四象限` はそのシートの持ち物なので、同名があれば作り直す
    # （2026-09-21 のカードと同じ扱いへ揃えた、2026-09-22）。指標を変えて
    # 描き直したときに、古い式が残らないようにするため。
    field_name = f"{name}_四象限"
    for existing in target_datasource.get_fields(name=field_name):
        existing.delete()
    quadrant = target_datasource.create_calculated_field(
        name=field_name,
        formula=quadrant_formula,
        datatype="string",
        role="measure",
        discrete=True,
        hidden=None,
        table_calculation="Rows",
    )
    threshold_filter = _quadrant_filter_field(
        workbook,
        target_datasource,
        f"{name}_売上閾値",
        f"{name}_売上閾値以上",
        f"{size_expression} >= [Parameters].[{name}_売上閾値]",
        parameter_value=_QUADRANT_SIZE_THRESHOLD,
        parameter_range=None,
    )
    center_filter = _quadrant_filter_field(
        workbook,
        target_datasource,
        f"{name}_中央比率",
        f"{name}_中央範囲",
        _center_range_formula(x_expression, y_expression, f"[Parameters].[{name}_中央比率]"),
        parameter_value=_QUADRANT_CENTER_RATIO,
        parameter_range=(0.1, 1.0, 0.05),
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
    # 真偽値のフィールドを True だけ残す条件にする（`member="true"`、引用符なし。
    # 2026-09-25 に Tableau で動作を確認）。
    for filter_field, options in (
        (threshold_filter, {"aggregation": "agg"}),
        (
            center_filter,
            {"table_calculation": "field", "table_calculation_field": item},
        ),
    ):
        worksheet.add_filter(field=filter_field, **options)
        [true_only] = worksheet.get_filters(name=filter_field.name)
        true_only.update(values=["true"])
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
