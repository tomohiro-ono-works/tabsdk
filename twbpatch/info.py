"""インフォメーションアイコン（説明・ヒントのアイコン付きワークシート）。

`outputs/waterfall_chart_test10.twb` の手作業の "info" シートを実測して作った
（2026-09-23）。行・列にデータを置かず、`STR(1)` のダミー計算フィールドを 1 つだけ
ツールヒントの位置へ置き、マークを固定のシェイプ（アイコン画像）・固定色にして、
カスタムツールヒント（マウスを乗せたときに出る自由なテキスト）で説明を表示する。

アイコン画像そのものはワークブックに埋め込まれない。Tableau 側の
`形状/webinfo/` フォルダ（シェイプパレット）を参照するだけなので、
そのパレットと画像がユーザーの Tableau 環境に無いと、Tableau は既定のシェイプを
代わりに表示する（アイコンが選べないだけで、開けなくなるわけではない）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .connected import TwbDatasource, TwbFolder
from .connected_worksheet import TwbWorksheet
from .draw import _record_chart

if TYPE_CHECKING:
    from .workbook import TwbWorkbook

#: `形状/webinfo/` に置いた Google Material Symbols のアイコン（2026-09-23、実測）。
_ICON_PALETTE = "webinfo"
_ICON_FILES = {
    "info": "info_120dp_1F1F1F_FILL0_wght400_GRAD0_opsz48.png",
    "quest": "help_120dp_1F1F1F_FILL0_wght400_GRAD0_opsz48.png",
    "setting": "settings_120dp_1F1F1F_FILL0_wght400_GRAD0_opsz48.png",
    "attention": "error_120dp_1F1F1F_FILL0_wght400_GRAD0_opsz48.png",
}

#: マークのサイズ。実測した手作業の "info" シートの値をそのまま使う。
_INFO_ICON_SIZE = 1.5712155103683472

#: ダミーの計算フィールド名。値は使わずツールヒントの置き場所として要るだけなので、
#: データソースにつき 1 つを複数のアイコンで共有する（waterfall の共有連番と同じ考え方）。
_INFO_KEY_FIELD = "インフォメーション_key"


def draw_info(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    text: str,
    icon: str = "info",
    heading: str = "説明",
    color: str = "#e15759",
    visible: bool = True,
    folder: str | TwbFolder | None = None,
) -> TwbWorksheet:
    """アイコン + カスタムツールヒントだけの小さなワークシートを作る。

    `icon` は `"info"` / `"quest"` / `"setting"` / `"attention"` のいずれか。
    マウスを乗せると `heading`（太字の見出し）と `text`（本文）がツールヒントに出る。
    データを使わないため `datasource` はワークブックに 1 つしか無ければ省略できる
    （複数あれば明示が必要）。
    """
    if icon not in _ICON_FILES:
        raise ValueError(f"icon must be one of {sorted(_ICON_FILES)}")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must not be empty")
    if not isinstance(heading, str):
        raise TypeError("heading must be a string")
    if not isinstance(color, str) or not color.strip():
        raise ValueError("color must be a color code")

    if datasource is None:
        candidates = workbook.get_datasources()
        if len(candidates) != 1:
            raise ValueError(
                "datasource is required when the workbook has zero or multiple datasources"
            )
        [datasource] = candidates
    elif not isinstance(datasource, TwbDatasource):
        raise TypeError("datasource must be TwbDatasource or None")

    existing = datasource.get_fields(name=_INFO_KEY_FIELD)
    if existing:
        key_field = existing[0]
    else:
        key_field = datasource.create_calculated_field(
            name=_INFO_KEY_FIELD,
            formula="STR(1)",
            datatype="string",
            role="dimension",
            folder=folder,
            create_folder_if_missing=True,
        )

    worksheet = workbook.create_worksheet(name=name, visible=visible)
    pane = worksheet.get_panes()[0]
    pane.add_field(field=key_field, encoding="tooltip", aggregation="attr", discrete=True)
    pane.update(mark_type="shape", mark_color=color, mark_size=_INFO_ICON_SIZE)
    pane._apply_mark_sizing(scaling=False)
    pane._apply_mark_shape(f"{_ICON_PALETTE}/{_ICON_FILES[icon]}")
    pane._apply_customized_tooltip(heading=heading, text=text)

    return _record_chart(workbook, worksheet, "draw_info")
