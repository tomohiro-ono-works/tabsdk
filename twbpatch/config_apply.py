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

# design のうち受け手があるもの。残りは J-5（全体の書式 API）待ち。
_DESIGN_APPLIED = ("font",)

_CALCULATION_KEYS = ("name", "formula", "datatype", "role", "folder")

_DEFAULT_DATATYPE = "real"
_DEFAULT_ROLE = "measure"


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


def _apply_design(workbook: TwbWorkbook, design: Any) -> None:
    if not isinstance(design, dict):
        raise ValueError("design must be a mapping")

    font = design.get("font")
    if font is not None:
        if not isinstance(font, str) or not font.strip():
            raise ValueError("design.font must be a non-empty string")
        workbook.set_default_font(font.strip())

    pending = [key for key in design if key not in _DESIGN_APPLIED]
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

        calculations = section.get("calculations")
        if calculations:
            _apply_calculations(datasource, calculations)

        unknown = [key for key in section if key not in {"folders", "calculations"}]
        if unknown:
            _skip(f"datasources[{datasource.name}]", unknown)


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

    design = data.get("design")
    if design is not None:
        _apply_design(workbook, design)

    datasources = data.get("datasources")
    if datasources:
        _apply_datasources(workbook, datasources, field_grouping=field_grouping)

    if data.get("dashboard"):
        _LOGGER.warning(
            "受け手が未実装のため読み飛ばします: dashboard"
            "（K-1 / H-10 / H-1 の後に実装する）"
        )
    return workbook
