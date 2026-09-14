"""設定画面（`export_html()`）が出力した YAML を Workbook へ適用する。

仕様 §2.0 の API 方式にあたる。XML には触れず、接続型モデルのメソッドだけを呼ぶ。
YAML の形は `docs/html_screen_spec.md` の「出力する設定ファイル」を正とする。

旧 API の `apply_field_config()` は最上位がデータソース名、こちらは最上位が
`design` / `datasources` / `dashboard` のセクション。形が違うので別メソッドにし、
どちらの形かを見分ける処理を持たない。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .errors import AmbiguousCaptionError, NotFoundError

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの import
    from .connected import TwbDatasource, TwbFolder
    from .workbook import TwbWorkbook

_LOGGER = logging.getLogger(__name__)

# 最上位に置ける節。ここに無いキーは読み飛ばす。
_SECTIONS = ("design", "datasources", "dashboard")

#: `design` のうち、ワークブック全体へ直接書けるもの。
_DESIGN_APPLIED = ("font",)

#: `design` のうち、`dashboard` を組むときに使うもの。単独では届かない。
_DESIGN_FOR_DASHBOARD = (
    "main_color",
    "sub_color_1",
    "sub_color_2",
    "text_color",
    "min_color",
    "mid_color",
    "max_color",
    "spacing",
    "filter_apply_button",
)

_CALCULATION_KEYS = ("name", "formula", "datatype", "role", "folder")

_DEFAULT_DATATYPE = "real"
_DEFAULT_ROLE = "measure"

#: `@main_color` のように design を参照できるキー。
#: min/mid/max_color は draw_crosstab 用のヒートマップ既定3色（2026-09-12 追加）。
#: draw_crosstab は3色そろえるかゼロかしか許さないため、画面はグラフ選択時に
#: 自動でこの3トークンを参照させ、3色を毎回手入力させない。
_DESIGN_TOKENS = (
    "main_color",
    "sub_color_1",
    "sub_color_2",
    "text_color",
    "min_color",
    "mid_color",
    "max_color",
)

#: 余白の指定を `build_report(content_style=)` へ写す。
_SPACING = {
    "wide": {"margin": 8, "padding": 16},
    "narrow": {"margin": 4, "padding": 8},
}

_AREA_KINDS = ("worksheet", "filter")


def _load(config: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, (str, Path)):
        with Path(config).open(encoding="utf-8") as file:
            config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError("config must be a mapping")
    return config


def _skip(section: str, keys: Any) -> None:
    """受け手がまだ無い設定を、名前を出して読み飛ばす。

    画面は常に全節を出力する。エラーにすると出力した YAML がそのまま使えない。
    """
    prefix = f"{section}." if section else ""
    names = ", ".join(f"{prefix}{key}" for key in keys)
    _LOGGER.warning("受け手が未実装のため読み飛ばします: %s", names)


def _apply_design(workbook: TwbWorkbook, design: Any, *, has_dashboard: bool) -> None:
    """`design` のうちワークブック全体へ書けるものを適用する。

    色・余白・フィルタの「適用」ボタンは**ダッシュボードを組むときに使う**もので、
    ワークブック全体に書く先は無い。`dashboard` が無い設定では届かないので読み飛ばす。
    """
    if not isinstance(design, dict):
        raise ValueError("design must be a mapping")

    font = design.get("font")
    if font is not None:
        if not isinstance(font, str) or not font.strip():
            raise ValueError("design.font must be a non-empty string")
        workbook.set_default_font(font.strip())

    consumed = set(_DESIGN_APPLIED)
    if has_dashboard:
        consumed |= set(_DESIGN_FOR_DASHBOARD)
    pending = [key for key in design if key not in consumed]
    if pending:
        _skip("design", pending)


def _resolve_folder(datasource: TwbDatasource, name: str) -> TwbFolder:
    name = name.strip()
    if not name:
        raise ValueError("folder must not be empty")
    existing = datasource.get_folders(name=name)
    return existing[0] if existing else datasource.create_folder(name=name)


def _apply_calculations(datasource: TwbDatasource, calculations: Any) -> None:
    """計算フィールドを定義順に作る。

    定義順に作るのは、後の式が前の計算フィールドを表示名で参照できるようにするため。
    同名のフィールドが既にあれば上書きする。2 周方式では同じ YAML を 2 度通すため、
    2 度目にエラーで止まると往復が回らない。
    """
    if not isinstance(calculations, list):
        raise ValueError("calculations must be a list")

    for entry in calculations:
        if not isinstance(entry, dict):
            raise ValueError("calculation must be a mapping")

        name = entry.get("name")
        formula = entry.get("formula")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("calculation name must be a non-empty string")
        if not isinstance(formula, str) or not formula.strip():
            raise ValueError(f"calculation formula must be a non-empty string: {name}")
        name = name.strip()

        datatype = entry.get("datatype") or _DEFAULT_DATATYPE
        role = entry.get("role") or _DEFAULT_ROLE
        if role not in {"measure", "dimension"}:
            raise ValueError(f"calculation role must be 'measure' or 'dimension': {name}")
        # ディメンションは不連続、メジャーは連続。画面では指定しない。
        discrete = role == "dimension"

        unknown = [key for key in entry if key not in _CALCULATION_KEYS]
        if unknown:
            _skip(f"calculations[{name}]", unknown)

        folder_name = entry.get("folder")
        folder = (
            _resolve_folder(datasource, folder_name)
            if isinstance(folder_name, str) and folder_name.strip()
            else None
        )

        existing = datasource.get_fields(name=name)
        if len(existing) > 1:
            raise AmbiguousCaptionError(f"field name is ambiguous: {name}")
        if existing:
            field = existing[0]
            if not field.is_calculated:
                raise ValueError(
                    f"field is not a calculated field, refusing to overwrite: {name}"
                )
            field.update(
                formula=formula,
                datatype=datatype,
                role=role,
                discrete=discrete,
            )
            if folder is not None:
                field.move_to_folder(folder)
            _LOGGER.info("計算フィールドを上書きしました: %s", name)
            continue

        datasource.create_calculated_field(
            name=name,
            formula=formula,
            datatype=datatype,
            role=role,
            discrete=discrete,
            folder=folder,
        )


def _apply_renames(datasource: TwbDatasource, renames: Any) -> None:
    """フォルダへは入れず、表示名だけを変更する。

    `folders` は最上位がフォルダ名の3階層 YAML なのでフォルダなしを表現できない
    （§ apply_field_config）。「リネームはしたいがフォルダには入れたくない」場合の
    入口として別セクションにした。
    """
    if not isinstance(renames, dict):
        raise ValueError("renames must be a mapping")

    for original_name, display_name in renames.items():
        if not isinstance(original_name, str) or not original_name.strip():
            raise ValueError("field name must be a non-empty string")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"display name must be a non-empty string: {original_name}")
        original_name = original_name.strip()

        matches = datasource.get_fields(name=original_name)
        if not matches:
            matches = datasource.get_fields(id=f"[{original_name}]")
        if not matches:
            raise NotFoundError(f"field not found: {original_name}")
        if len(matches) > 1:
            raise AmbiguousCaptionError(f"field name is ambiguous: {original_name}")
        matches[0].update(name=display_name.strip())


def _apply_datasources(
    workbook: TwbWorkbook,
    datasources: Any,
    *,
    field_grouping: str,
) -> None:
    if not isinstance(datasources, dict):
        raise ValueError("datasources must be a mapping")

    # 先に全部解決してから適用する。存在しない名前で途中まで書き換えないため。
    plans: list[tuple[TwbDatasource, dict[str, Any]]] = []
    for name, section in datasources.items():
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ValueError(f"datasource section must be a mapping: {name}")
        matches = workbook.get_datasources(name=name)
        if not matches:
            raise NotFoundError(f"datasource not found: {name}")
        if len(matches) > 1:
            raise AmbiguousCaptionError(f"datasource name is ambiguous: {name}")
        plans.append((matches[0], section))

    for datasource, section in plans:
        # フォルダを先に作る。計算フィールドの folder: に指定できるようにするため。
        folders = section.get("folders")
        if folders:
            datasource.apply_field_config(folders, field_grouping=field_grouping)

        renames = section.get("renames")
        if renames:
            _apply_renames(datasource, renames)

        calculations = section.get("calculations")
        if calculations:
            _apply_calculations(datasource, calculations)

        unknown = [
            key for key in section if key not in {"folders", "renames", "calculations"}
        ]
        if unknown:
            _skip(f"datasources[{datasource.name}]", unknown)


def _resolve_token(value: Any, design: dict[str, Any]) -> Any:
    """`@main_color` をデザインルールの実際の値へ置き換える。"""
    if not isinstance(value, str) or not value.startswith("@"):
        return value
    key = value[1:]
    if key not in _DESIGN_TOKENS:
        raise ValueError(f"unknown design token: {value}")
    resolved = design.get(key)
    if not resolved:
        raise ValueError(f"design has no {key}, referenced as {value}")
    return resolved


def _int_or_none(value: Any, label: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number: {value!r}") from None


def _area_datasource(workbook: TwbWorkbook, area: dict[str, Any]) -> TwbDatasource:
    name = area.get("datasource")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("area needs a datasource")
    matches = workbook.get_datasources(name=name)
    if len(matches) != 1:
        raise NotFoundError(f"datasource not found or ambiguous: {name}")
    return matches[0]


def _draw_area(workbook: TwbWorkbook, area: dict[str, Any], design: dict[str, Any]) -> str:
    """エリア 1 つ分のワークシートを作る。

    画面の 1 エリア = 1 シート。`build_report()` は既にあるシートを並べるだけなので、
    先に `draw_*()` で作ってから並べる 2 段になる。
    """
    sheet = area.get("sheet")
    if not isinstance(sheet, str) or not sheet.strip():
        raise ValueError("worksheet area needs a sheet name")
    chart = area.get("chart")
    if not isinstance(chart, str) or not chart.startswith("draw_"):
        raise ValueError(f"unknown chart: {chart!r}")
    method = getattr(workbook, chart, None)
    if method is None or not callable(method):
        raise ValueError(f"unknown chart: {chart}")

    params = area.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError(f"params must be a mapping: {sheet}")
    resolved = {
        key: [_resolve_token(item, design) for item in value]
        if isinstance(value, list)
        else _resolve_token(value, design)
        for key, value in params.items()
    }
    method(_area_datasource(workbook, area), name=sheet.strip(), **resolved)
    return sheet.strip()


def _area_field(area: dict[str, Any]) -> tuple[str, str]:
    field = area.get("field")
    if not isinstance(field, str) or not field.strip():
        raise ValueError("filter area needs a field")
    return (area["datasource"], field.strip())


def _row_names(rows: list[dict[str, Any]]) -> list[str]:
    """段の表示名を決める。名前が空でも重複しても、一意なキーにする。"""
    names: list[str] = []
    for index, row in enumerate(rows):
        name = str(row.get("name") or "").strip() or f"段{index + 1}"
        while name in names:
            name = f"{name}_{index + 1}"
        names.append(name)
    return names


def _apply_dashboard(
    workbook: TwbWorkbook,
    dashboard: dict[str, Any],
    design: dict[str, Any],
) -> None:
    if not isinstance(dashboard, dict):
        raise ValueError("dashboard must be a mapping")
    name = str(dashboard.get("name") or "").strip()
    if not name:
        raise ValueError("dashboard needs a name")

    rows = dashboard.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("dashboard rows must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("dashboard row must be a mapping")
        if not isinstance(row.get("areas") or [], list):
            raise ValueError("row areas must be a list")
    names = _row_names(rows)

    # 1 周目: シートを作り、フィルタを登録する。
    struct: dict[str, dict[str, Any]] = {}
    actions: list[tuple[str, str, dict[str, Any]]] = []
    filter_fields: list[tuple[str, str]] = []
    for row_name, row in zip(names, rows):
        items: list[dict[str, Any]] = []
        for area in row.get("areas") or []:
            if not isinstance(area, dict):
                raise ValueError(f"area must be a mapping: {row_name}")
            kind = area.get("kind")
            if kind not in _AREA_KINDS:
                raise ValueError(f"area kind must be one of {_AREA_KINDS}: {row_name}")
            if kind == "filter":
                # set_filter() は既にあるワークシートへスライスを足す。すべての
                # シートを作り終えてから呼ぶ（フィルタの段が先に来ても届くように）。
                field = _area_field(area)
                filter_fields.append(field)
                items.append({"kind": "filter", "field": field})
                continue
            sheet = _draw_area(workbook, area, design)
            width = _int_or_none(area.get("width"), "area width")
            if width is None:
                items.append({"kind": "worksheet", "sheet": sheet})
            else:
                items.append(
                    {"kind": "worksheet", "sheets": [sheet], "fixed_size": width}
                )
            if area.get("action"):
                actions.append((sheet, area["datasource"], area["action"]))
        item_spec: dict[str, Any] = {"items": items}
        height = _int_or_none(row.get("height"), "row height")
        if height is not None:
            item_spec["height"] = height
        struct[row_name] = item_spec

    for field in filter_fields:
        workbook.add_filter(field, scope="datasource")

    # 2 周目: ダッシュボードを作って並べる。
    header = dashboard.get("header") or {}
    if not isinstance(header, dict):
        raise ValueError("dashboard header must be a mapping")
    content_style = _SPACING.get(str(design.get("spacing") or "wide"))
    if content_style is None:
        raise ValueError(f"design.spacing must be one of {tuple(_SPACING)}")

    connected = workbook.create_dashboard(
        name=name,
        width=_int_or_none(dashboard.get("width"), "dashboard width") or 1200,
        height=_int_or_none(dashboard.get("height"), "dashboard height") or 800,
    )
    build_options: dict[str, Any] = {"content_style": dict(content_style)}
    if str(header.get("title") or "").strip():
        build_options["header_title"] = header["title"].strip()
    header_height = _int_or_none(header.get("height"), "header height")
    if header_height is not None:
        build_options["header_height"] = header_height
    if header.get("background_color"):
        build_options["header_background_color"] = header["background_color"]
    if header.get("font_color"):
        build_options["header_font_color"] = header["font_color"]
    if design.get("filter_apply_button"):
        build_options["filter_apply_button"] = True

    connected.build_report(dashboard_name=name, struct=struct, **build_options)
    _apply_actions(connected, actions)


def _apply_actions(
    dashboard: Any,
    actions: list[tuple[str, str, dict[str, Any]]],
) -> None:
    """エリアに付いたアクションを張る。名前は画面が出さないので組み立てる。"""
    used: set[str] = set()
    for sheet, datasource, action in actions:
        if not isinstance(action, dict):
            raise ValueError(f"action must be a mapping: {sheet}")
        kind = action.get("type")
        if kind not in {"filter", "url"}:
            raise ValueError(f"action type must be 'filter' or 'url': {sheet}")
        label = f"{sheet} で絞り込む" if kind == "filter" else f"{sheet} からリンク"
        candidate, index = label, 1
        while candidate in used:
            index += 1
            candidate = f"{label}{index}"
        used.add(candidate)

        if kind == "url":
            dashboard.create_action(
                kind="url", name=candidate, source=sheet, url=action.get("url") or ""
            )
            continue
        target = str(action.get("target") or "").strip()
        field = str(action.get("field") or "").strip()
        if not target:
            raise ValueError(f"filter action needs a target sheet: {sheet}")
        if not field:
            raise ValueError(f"filter action needs a field: {sheet}")
        dashboard.create_action(
            kind="filter",
            name=candidate,
            source=sheet,
            targets=[target],
            field=(datasource, field),
        )


def apply_workbook_config(
    workbook: TwbWorkbook,
    config: str | Path | dict[str, Any],
    *,
    field_grouping: str = "folder",
) -> TwbWorkbook:
    data = _load(config)

    unknown = [key for key in data if key not in _SECTIONS]
    if unknown:
        _skip("", unknown)

    dashboard = data.get("dashboard")
    design = data.get("design")
    if design is not None:
        _apply_design(workbook, design, has_dashboard=bool(dashboard))

    datasources = data.get("datasources")
    if datasources:
        _apply_datasources(workbook, datasources, field_grouping=field_grouping)

    if dashboard:
        _apply_dashboard(workbook, dashboard, design if isinstance(design, dict) else {})
    return workbook
