"""設定画面（`export_html()`）が出力した YAML を Workbook へ適用する。

仕様 §2.0 の API 方式にあたる。XML には触れず、接続型モデルのメソッドだけを呼ぶ。
YAML の形は `docs/developer/html_screen_spec.md` の「出力する設定ファイル」を正とする。

旧 API の `apply_field_config()` は最上位がデータソース名、こちらは最上位が
`design` / `datasources` / `dashboard` / `kpi_tree` のセクション。形が違うので別メソッドにし、
どちらの形かを見分ける処理を持たない。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .errors import AmbiguousCaptionError, NotFoundError
from .kpi_tree import KpiNode

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの import
    from .connected import TwbDatasource, TwbFolder
    from .workbook import TwbWorkbook

_LOGGER = logging.getLogger(__name__)

# 最上位に置ける節。ここに無いキーは読み飛ばす。
_SECTIONS = ("design", "datasources", "dashboard", "kpi_tree")

# `draw_` 以外の名前で画面のグラフ種類として使うメソッド（2026-09-23、ウォーターフォール）。
# `getattr(workbook, chart)` は任意のメソッド名を呼べてしまうので、プレフィックスだけで
# 許可しない名前は明示的にここへ加える（ホワイトリスト）。
_EXTRA_CHARTS = frozenset({"build_waterfall"})

#: `design` のうち、ワークブック全体へ直接書けるもの。
_DESIGN_APPLIED = ("font",)

#: `design` のうち、`dashboard` を組むときに使うもの。単独では届かない。
_DESIGN_FOR_DASHBOARD = (
    "dashboard_template",
    "dashboard_template_dashboard",
    "main_color",
    "sub_color_1",
    "sub_color_2",
    "sub_color_3",
    "accent_color",
    "text_color_1",
    "text_color_2",
    "background_color",
    "border_color",
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
    "sub_color_3",
    "accent_color",
    "text_color_1",
    "text_color_2",
    #: 台紙（ダッシュボードの地）の色。ヘッダーの文字色からも参照する（2026-09-21）
    "background_color",
    "border_color",
    "min_color",
    "mid_color",
    "max_color",
)

def _spacing_name(design: dict[str, Any]) -> str:
    return str(design.get("spacing") or _DEFAULT_SPACING)


def _design_border_color(design: dict[str, Any]) -> str | None:
    """枠線の色。空なら枠線を引かない（2026-09-21）。"""
    color = str(design.get("border_color") or "").strip()
    return color or None


def _design_content_style(
    spacing: dict[str, int], design: dict[str, Any]
) -> dict[str, Any]:
    """台紙の書式。余白に、デザインルールの背景色を重ねる（2026-09-21）。

    色を省いたときはライブラリ側の既定（灰色）のままにする。
    """
    style: dict[str, Any] = dict(spacing)
    color = str(design.get("background_color") or "").strip()
    if color:
        style["background_color"] = color
    return style


#: `design.spacing` の既定。画面の既定と揃える（2026-09-21 に wide から変更）。
_DEFAULT_SPACING = "narrow"

#: 余白の指定を `build_report(content_style=)` へ写す。
_SPACING = {
    "wide": {"margin": 8, "padding": 16},
    "narrow": {"margin": 4, "padding": 8},
}
#: 余白「広い」のときは、グラフごとの余白も 1.5 倍にする（0 は 0 のまま）。
_SPACING_SCALE = {"wide": 1.5, "narrow": 1.0}

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
    ワークブック全体に書く先は無い。`dashboard` も `kpi_tree` も無い設定では届かないので読み飛ばす。
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


_FIELD_REF_RE = re.compile(r"\[([^\]]+)\]")


def _missing_formula_refs(datasource: TwbDatasource, formula: str) -> list[str]:
    missing: list[str] = []
    for ref in {match.group(1) for match in _FIELD_REF_RE.finditer(formula)}:
        matches = datasource.get_fields(name=ref) or datasource.get_fields(id=f"[{ref}]")
        if not matches:
            missing.append(ref)
    return missing


def _apply_calculations(datasource: TwbDatasource, calculations: Any) -> None:
    """計算フィールドを、式が参照する計算フィールドから先に作る。

    表示名で参照するには参照先が先に存在している必要がある。YAML の並び順には頼らない
    （`_calculation_order()`）。同名のフィールドが既にあれば上書きする。2 周方式では同じ
    YAML を 2 度通すため、2 度目にエラーで止まると往復が回らない。

    **式が参照するフィールドがまだ無ければ、その計算フィールドごと読み飛ばす**
    （2026-09-23、`_apply_renames` と同じ理由。`build_waterfall()` の連番のように
    `dashboard:` 節が後から動的に作るフィールドを、`datasources:` の計算式が先に
    参照していると `create_calculated_field()` / `update()` の `strict=True` で
    `NotFoundError` になり止まっていた）。読み飛ばした計算フィールドを他の式が
    参照していれば、それも連鎖して読み飛ばす（順番に作りながら存在チェックするため
    自然にそうなる）。
    """
    if not isinstance(calculations, list):
        raise ValueError("calculations must be a list")

    # 作り始める前に全件を検証する。途中の 1 件で止まって一部だけ作られないように。
    for entry in calculations:
        if not isinstance(entry, dict):
            raise ValueError("calculation must be a mapping")
        name = entry.get("name")
        formula = entry.get("formula")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("calculation name must be a non-empty string")
        if not isinstance(formula, str) or not formula.strip():
            raise ValueError(f"calculation formula must be a non-empty string: {name}")
        role = entry.get("role") or _DEFAULT_ROLE
        if role not in {"measure", "dimension"}:
            raise ValueError(f"calculation role must be 'measure' or 'dimension': {name.strip()}")

    skipped: list[str] = []
    for entry in _calculation_order(calculations):
        name = entry["name"].strip()
        formula = entry["formula"]
        datatype = entry.get("datatype") or _DEFAULT_DATATYPE
        role = entry.get("role") or _DEFAULT_ROLE
        # ディメンションは不連続、メジャーは連続。画面では指定しない。
        discrete = role == "dimension"

        missing_refs = _missing_formula_refs(datasource, formula)
        if missing_refs:
            skipped.append(name)
            continue

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

    if skipped:
        _skip(f"datasources[{datasource.name}].calculations", skipped)


def _calculation_order(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """式が `[名前]` で参照する計算フィールドを、参照する側より先に並べる。

    画面の計算フィールドの表は行を途中に挿入できず、参照先を後から足すと末尾に入る
    （2026-09-14、表の上から作っていたため `formula reference not found` で止まった）。
    Tableau も計算フィールドの並び順を気にしないので、YAML の並び順に意味を持たせない。
    参照し合っていないものは YAML の並び順のまま。参照が循環していれば何も作らずに例外にする。
    """
    names = [entry["name"].strip() for entry in entries]
    depends = [
        {
            other
            for other, name in enumerate(names)
            if other != index and f"[{name}]" in entry["formula"]
        }
        for index, entry in enumerate(entries)
    ]
    pending = list(range(len(entries)))
    placed: set[int] = set()
    ordered: list[dict[str, Any]] = []
    while pending:
        ready = next((index for index in pending if depends[index] <= placed), None)
        if ready is None:
            cycle = ", ".join(names[index] for index in pending)
            raise ValueError(f"calculations reference each other in a cycle: {cycle}")
        pending.remove(ready)
        placed.add(ready)
        ordered.append(entries[ready])
    return ordered


def _drop_missing_fields(
    datasource: TwbDatasource, folders: Any
) -> dict[str, dict[str, str]]:
    """`folders`（フォルダ名 → {元カラム名: 表示名}）から、まだ存在しないフィールドを
    除いた形を返す。`apply_field_config()` へ渡す前のフィルタ（2026-09-23）。

    `_apply_renames()` と同じ理由——`build_waterfall()` の連番のように `dashboard:` 節が
    後から動的に作るフィールドを、まだ作られていない `.twb` へ適用すると
    `NotFoundError` で止まっていた。あれば流用（フォルダへ入れる）、なければ
    黙って読み飛ばす。
    """
    if not isinstance(folders, dict):
        raise ValueError("folders must be a mapping")
    filtered: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for folder_name, rename_map in folders.items():
        if not isinstance(rename_map, dict):
            raise ValueError(f"folder fields must be a mapping: {folder_name}")
        kept: dict[str, str] = {}
        for original_name, display_name in rename_map.items():
            if not isinstance(original_name, str) or not original_name.strip():
                raise ValueError("field name must be a non-empty string")
            matches = datasource.get_fields(name=original_name) or datasource.get_fields(
                id=f"[{original_name}]"
            )
            if matches:
                kept[original_name] = display_name
            else:
                missing.append(original_name)
        if kept:
            filtered[folder_name] = kept
    if missing:
        _skip(f"datasources[{datasource.name}].folders", missing)
    return filtered


def _apply_renames(datasource: TwbDatasource, renames: Any) -> None:
    """フォルダへは入れず、表示名だけを変更する。

    `folders` は最上位がフォルダ名の3階層 YAML なのでフォルダなしを表現できない
    （§ apply_field_config）。「リネームはしたいがフォルダには入れたくない」場合の
    入口として別セクションにした。

    **まだ存在しないフィールド名は読み飛ばす**（2026-09-23、ユーザーの指摘で変更。
    以前は `NotFoundError`）。`build_waterfall()` の連番のように `dashboard:` 節が
    後から動的に作るフィールドを、画面が前回開いた `.twb`（既にそのフィールドがある
    状態）から書き出してしまうことがあり、それを「まだ連番を持たない別の .twb」へ
    適用すると必ず止まっていた。あれば名前を変え、なければ黙って無視する
    （後段の `dashboard:` がそのフィールドを作れば、次にこの YAML を当てたときに
    はじめてリネームされる）。
    """
    if not isinstance(renames, dict):
        raise ValueError("renames must be a mapping")

    missing: list[str] = []
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
            missing.append(original_name)
            continue
        if len(matches) > 1:
            raise AmbiguousCaptionError(f"field name is ambiguous: {original_name}")
        matches[0].update(name=display_name.strip())
    if missing:
        _skip(f"datasources[{datasource.name}].renames", missing)


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
            folders = _drop_missing_fields(datasource, folders)
            if folders:
                datasource.apply_field_config(folders, field_grouping=field_grouping)

        renames = section.get("renames")
        if renames:
            _apply_renames(datasource, renames)

        calculations = section.get("calculations")
        if calculations:
            _apply_calculations(datasource, calculations)

        # 階層は最後。改名後の名前や、ここで作った計算フィールドも指せるようにする。
        hierarchies = section.get("hierarchies")
        if hierarchies:
            _apply_hierarchies(datasource, hierarchies)

        unknown = [
            key
            for key in section
            if key not in {"folders", "renames", "calculations", "hierarchies"}
        ]
        if unknown:
            _skip(f"datasources[{datasource.name}]", unknown)


def _apply_hierarchies(datasource: TwbDatasource, hierarchies: Any) -> None:
    """階層（ドリルパス）を作る。同じ名前の階層があれば作り直す（2 回適用しても同じ結果）。

    画面は「階層」列から組み立てるので、値は `{fields: [...], folder: ...}`。
    フィールドの並びがそのままドリルの順になる。
    """
    if not isinstance(hierarchies, dict):
        raise ValueError("hierarchies must be a mapping")

    plans: list[tuple[str, list[str], str | None]] = []
    for name, entry in hierarchies.items():
        label = f"hierarchy {name}"
        if not isinstance(name, str) or not name.strip():
            raise ValueError("hierarchy needs a name")
        if isinstance(entry, list):
            entry = {"fields": entry}
        if not isinstance(entry, dict):
            raise ValueError(f"{label} must be a mapping or a list of fields")
        fields = entry.get("fields")
        if not isinstance(fields, list) or len(fields) < 2:
            raise ValueError(f"{label} needs at least two fields")
        names = []
        for field in fields:
            if not isinstance(field, str) or not field.strip():
                raise ValueError(f"{label} has an empty field name")
            names.append(field.strip())
        folder = entry.get("folder")
        if folder is not None and (not isinstance(folder, str) or not folder.strip()):
            raise ValueError(f"{label} folder must be a name")
        unknown = [key for key in entry if key not in {"fields", "folder"}]
        if unknown:
            _skip(label, unknown)
        plans.append((name.strip(), names, folder.strip() if folder else None))

    for name, fields, folder in plans:
        for existing in datasource.get_drill_paths(name=name):
            existing.delete()
        datasource.create_drill_path(
            name=name, fields=fields, folder=folder, create_folder_if_missing=folder is not None
        )


#: KPI カードのモードごとに使う引数（2026-09-21）。`draw_card()` は両モードの
#: 引数を同時に渡されると例外にする。画面はモードに合う方だけを書き出すが、
#: 全部の引数を並べていた頃の YAML も読めるように、ここで落とす。
_CARD_MODE_PARAMS = {
    "sub_metric": ("sub_metric", "sub_aggregation"),
    "budget": ("budget_metric", "budget_threshold", "achieved_color",
               "missed_color", "budget_aggregation", "budget_value_color"),
}


def _card_mode_params(chart: str, params: dict[str, Any]) -> dict[str, Any]:
    if chart != "draw_card":
        return params
    mode = str(params.get("mode") or "sub_metric")
    drop = {
        name
        for key, names in _CARD_MODE_PARAMS.items()
        if key != mode
        for name in names
    }
    return {key: value for key, value in params.items() if key not in drop}


def _numeric_params(
    method: Any, params: dict[str, Any], sheet: str
) -> dict[str, Any]:
    """数値の引数を文字列から数へ戻す（2026-09-21）。

    画面は数の入力欄も文字列で書き出すため（`opacity: "0.4"`）、そのまま渡すと
    `draw_*()` が型で弾く。どれが数かは `draw_*()` の注釈から読む。
    """
    import inspect

    signature = inspect.signature(method)
    out = dict(params)
    for name, parameter in signature.parameters.items():
        annotation = str(parameter.annotation)
        if "float" not in annotation and "int" not in annotation:
            continue
        value = out.get(name)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            out[name] = int(value) if "int" in annotation and "float" not in annotation \
                else float(value)
        except ValueError:
            raise ValueError(f"{name} must be a number: {value!r} ({sheet})") from None
    return out


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
    if not isinstance(chart, str) or not (chart.startswith("draw_") or chart in _EXTRA_CHARTS):
        raise ValueError(f"unknown chart: {chart!r}")
    method = getattr(workbook, chart, None)
    if method is None or not callable(method):
        raise ValueError(f"unknown chart: {chart}")

    params = area.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError(f"params must be a mapping: {sheet}")
    params = _card_mode_params(chart, params)
    resolved = {
        key: [_resolve_token(item, design) for item in value]
        if isinstance(value, list)
        else _resolve_token(value, design)
        for key, value in params.items()
    }
    method(_area_datasource(workbook, area), name=sheet.strip(),
           **_numeric_params(method, resolved, sheet))
    return sheet.strip()


#: インフォメーションアイコンの浮動ゾームの一辺（px）とゾーンの角からの余白。
#: ユーザー承認の固定値（2026-09-23）。
_INFO_ICON_SIZE = 30
_INFO_ICON_MARGIN = 4


def _apply_info(
    workbook: TwbWorkbook,
    dashboard: Any,
    sheet: str,
    area: dict[str, Any],
    design: dict[str, Any],
) -> None:
    """エリアの `info:` から、対象シートのゾームの右上へ浮動でインフォメーション
    アイコンを重ねる（2026-09-23）。`build_report()` が Tiled 配置を組んだ**後**に
    呼ぶ必要がある——対象ゾーンの実際の px 位置（`TwbDashboardZone.x`/`.y`/`.width`）は
    レイアウト計算が終わるまで決まらないため。
    """
    info = area["info"]
    if not isinstance(info, dict):
        raise ValueError(f"area info must be a mapping: {sheet}")
    text = str(info.get("text") or "").strip()
    if not text:
        raise ValueError(f"info needs text: {sheet}")

    zone = next(
        (z for z in dashboard.get_zones() if z.worksheet_id == sheet), None
    )
    if zone is None or zone.x is None:
        raise ValueError(f"cannot place info icon for sheet: {sheet}")

    params: dict[str, Any] = {"text": text}
    if info.get("icon"):
        params["icon"] = info["icon"]
    if info.get("heading"):
        params["heading"] = info["heading"]
    if info.get("color"):
        params["color"] = _resolve_token(info["color"], design)

    icon_worksheet = workbook.draw_info(
        _area_datasource(workbook, area), name=f"info|{sheet}", **params
    )
    dashboard.add_floating_worksheet(
        icon_worksheet,
        x=zone.x + zone.width - _INFO_ICON_SIZE - _INFO_ICON_MARGIN,
        y=zone.y + _INFO_ICON_MARGIN,
        width=_INFO_ICON_SIZE,
        height=_INFO_ICON_SIZE,
        show_title=False,
    )


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
    template=None,
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
    if template is not None and not any(row.get('areas') for row in rows):
        from .dashboard_layout import stack_dashboard_layouts

        connected = workbook.create_dashboard(name=name)
        connected.update(layout=stack_dashboard_layouts(template.layout, None))
        workbook._add_image_assets(template.images)
        return
    names = _row_names(rows)

    # 1 周目: シートを作り、フィルタを登録する。
    struct: dict[str, dict[str, Any]] = {}
    actions: list[tuple[str, str, dict[str, Any]]] = []
    filter_fields: list[tuple[str, str]] = []
    infos: list[tuple[str, dict[str, Any]]] = []
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
            if area.get("info"):
                infos.append((sheet, area))
        item_spec: dict[str, Any] = {"items": items}
        height = _int_or_none(row.get("height"), "row height")
        if height is not None:
            item_spec["height"] = height
        # 幅の割り方は段ごとに選ぶ（2026-09-21）。均等割りの段では Tableau が
        # エリアごとの幅を見ないので、幅を効かせたい段は false にする。
        if "distribute_evenly" in row:
            distribute = row.get("distribute_evenly")
            if not isinstance(distribute, bool):
                raise ValueError("row distribute_evenly must be true or false")
            item_spec["distribute_evenly"] = distribute
        struct[row_name] = item_spec

    for field in filter_fields:
        workbook.add_filter(field, scope="datasource")

    # 2 周目: ダッシュボードを作って並べる。
    header = dashboard.get("header") or {}
    if not isinstance(header, dict):
        raise ValueError("dashboard header must be a mapping")
    content_style = _SPACING.get(_spacing_name(design))
    if content_style is None:
        raise ValueError(f"design.spacing must be one of {tuple(_SPACING)}")

    connected = workbook.create_dashboard(
        name=name,
        width=_int_or_none(dashboard.get("width"), "dashboard width") or 1200,
        height=_int_or_none(dashboard.get("height"), "dashboard height") or 800,
    )
    build_options: dict[str, Any] = {
        "content_style": _design_content_style(content_style, design),
        "spacing_scale": _SPACING_SCALE[_spacing_name(design)],
        "border_color": _design_border_color(design),
    }
    if str(header.get("title") or "").strip():
        build_options["header_title"] = header["title"].strip()
    header_height = _int_or_none(header.get("height"), "header height")
    if header_height is not None:
        build_options["header_height"] = header_height
    # ヘッダーの色はデザインルールを参照できる（2026-09-21。画面の既定は
    # 背景＝@main_color、文字＝@background_color）
    if header.get("background_color"):
        build_options["header_background_color"] = _resolve_token(
            header["background_color"], design
        )
    if header.get("font_color"):
        build_options["header_font_color"] = _resolve_token(header["font_color"], design)
    if design.get("filter_apply_button"):
        build_options["filter_apply_button"] = True

    connected.build_report(dashboard_name=name, struct=struct, **build_options)
    _apply_actions(connected, actions)
    # インフォメーションアイコンは build_report() が Tiled 配置を組んだ後でないと
    # 対象ゾーンの実際の px 位置が決まらないため、最後に浮動で重ねる（2026-09-23）。
    for sheet, area in infos:
        _apply_info(workbook, connected, sheet, area, design)
    if template is not None:
        from .dashboard_layout import stack_dashboard_layouts

        connected.update(layout=stack_dashboard_layouts(template.layout, connected.layout))
        workbook._add_image_assets(template.images)


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


def _apply_kpi_tree(
    workbook: TwbWorkbook,
    kpi_tree: dict[str, Any],
    design: dict[str, Any],
) -> None:
    """ノードごとに KPI カードを作ってから `build_kpi_tree()` で並べる 2 段。

    ノードの `sheet` / `params` はダッシュボードタブのエリアと同じ形なので、グラフ種類
    （KPI カード固定）とデータソース（タブで 1 つ）を補って `_draw_area()` にそのまま渡す。
    """
    if not isinstance(kpi_tree, dict):
        raise ValueError("kpi_tree must be a mapping")
    name = str(kpi_tree.get("name") or "").strip()
    if not name:
        raise ValueError("kpi_tree needs a name")
    datasource = kpi_tree.get("datasource")
    if not isinstance(datasource, str) or not datasource.strip():
        raise ValueError("kpi_tree needs a datasource")
    root = kpi_tree.get("root")
    _check_kpi_node(root)
    content_style = _SPACING.get(_spacing_name(design))
    if content_style is None:
        raise ValueError(f"design.spacing must be one of {tuple(_SPACING)}")

    align = str(kpi_tree.get("align") or "center").strip().lower()
    infos: list[tuple[str, dict[str, Any]]] = []
    workbook.build_kpi_tree(
        dashboard_name=name,
        root=_draw_kpi_node(workbook, root, datasource, design, infos),
        align=align,
        # エッジは上端揃えのときだけ描ける。上端なら必ず描く。.hyper はライブラリ同梱のものを使い、
        # save() が .twb の隣へ置く（2026-09-15。画面や YAML でパスを指定させない）。
        edges=align == "top",
        content_style=_design_content_style(content_style, design),
        spacing_scale=_SPACING_SCALE[_spacing_name(design)],
        border_color=_design_border_color(design),
    )
    # インフォメーションアイコンは build_kpi_tree() がノードを並べた後でないと
    # 対象ゾーンの実際の px 位置が決まらない（ダッシュボードタブと同じ理由、2026-09-23）。
    if infos:
        dashboard = workbook.get_dashboards(name=name)[0]
        for sheet, area in infos:
            _apply_info(workbook, dashboard, sheet, area, design)


def _check_kpi_node(node: Any) -> None:
    """カードを作り始める前にツリーの形だけ確かめる。途中のノードで止まってシートが残らないように。"""
    if not isinstance(node, dict):
        raise ValueError("kpi_tree node must be a mapping")
    children = node.get("children") or []
    if not isinstance(children, list):
        raise ValueError(f"kpi_tree children must be a list: {node.get('sheet')}")
    for child in children:
        _check_kpi_node(child)


def _draw_kpi_node(
    workbook: TwbWorkbook,
    node: dict[str, Any],
    datasource: str,
    design: dict[str, Any],
    infos: list[tuple[str, dict[str, Any]]],
) -> KpiNode:
    area = {
        "sheet": node.get("sheet"),
        "chart": "draw_card",
        "datasource": datasource,
        "params": node.get("params"),
    }
    sheet = _draw_area(workbook, area, design)
    if node.get("info"):
        area["info"] = node["info"]
        infos.append((sheet, area))
    children = [
        _draw_kpi_node(workbook, child, datasource, design, infos)
        for child in node.get("children") or []
    ]
    return KpiNode(workbook.get_worksheets(name=sheet)[0], children)


def apply_workbook_config(
    workbook: TwbWorkbook,
    config: str | Path | dict[str, Any],
    *,
    field_grouping: str = "folder",
    template_root: str | Path | None = None,
) -> TwbWorkbook:
    data = _load(config)

    unknown = [key for key in data if key not in _SECTIONS]
    if unknown:
        _skip("", unknown)

    dashboard = data.get("dashboard")
    kpi_tree = data.get("kpi_tree")
    design = data.get("design")
    template = None
    if isinstance(design, dict) and design.get('dashboard_template'):
        from .dashboard_template import load_dashboard_template

        # Resolve all required inputs before font/datasource/dashboard changes.
        template = load_dashboard_template(template_root, design['dashboard_template'],
                                           design.get('dashboard_template_dashboard'))
    if design is not None:
        _apply_design(workbook, design, has_dashboard=bool(dashboard) or bool(kpi_tree))

    datasources = data.get("datasources")
    if datasources:
        _apply_datasources(workbook, datasources, field_grouping=field_grouping)

    if dashboard:
        _apply_dashboard(workbook, dashboard, design if isinstance(design, dict) else {}, template)
    if kpi_tree:
        _apply_kpi_tree(workbook, kpi_tree, design if isinstance(design, dict) else {})
    return workbook
