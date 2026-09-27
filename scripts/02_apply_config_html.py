"""02: データソース定義 YAML を twb/twbx へ当てた状態で、設定画面 html を出す CLI。

01 で作った YAML を反映してから画面を作り直すので、リネーム後の名前・フォルダ・
階層・計算フィールドが入った状態でダッシュボードを組める。**twb は書き出さない。**
ダッシュボードまで作るのは 03（`03_apply_dashboard.py`）。

引数の順序は問わず拡張子（.yaml/.yml と .twb/.twbx）で判別し、出力は既定で上書きする。

    uv run --no-sync python "scripts/02_apply_config_html.py" <config.yaml> <workbook.twb|twbx> [--output out.html]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from twbpatch import TwbWorkbook

_YAML_EXTS = {".yaml", ".yml"}
_WORKBOOK_EXTS = {".twb", ".twbx"}


def _classify(paths: list[Path]) -> tuple[Path, Path]:
    config: Path | None = None
    workbook: Path | None = None
    for path in paths:
        # 先に存在を見る。パスが文字化けして届いた場合、拡張子まで崩れて
        # 「拡張子から判別できません」になり、原因が分かりにくいため（2026-09-21）
        if not path.exists():
            raise SystemExit(f"ファイルが見つかりません: {path}")
        suffix = path.suffix.lower()
        if suffix in _YAML_EXTS:
            if config is not None:
                raise SystemExit(f"YAML が複数指定されています: {config}, {path}")
            config = path
        elif suffix in _WORKBOOK_EXTS:
            if workbook is not None:
                raise SystemExit(f"ワークブックが複数指定されています: {workbook}, {path}")
            workbook = path
        else:
            raise SystemExit(
                f"拡張子から判別できません（.yaml/.yml か .twb/.twbx を指定）: {path}"
            )
    if config is None:
        raise SystemExit("データソース定義の .yaml/.yml が指定されていません")
    if workbook is None:
        raise SystemExit("対象の .twb/.twbx が指定されていません")
    return config, workbook


def main() -> None:
    parser = argparse.ArgumentParser(
        description="データソース定義 YAML を当てた状態の設定画面 html を出す"
    )
    parser.add_argument(
        "files", nargs="+", help="config.yaml と workbook.twb/twbx（順不同）"
    )
    parser.add_argument(
        "--output", help="出力先 html（省略時は <ワークブック名>_config.html）"
    )
    args = parser.parse_args()

    config, source = _classify([Path(f) for f in args.files])
    output = (
        Path(args.output)
        if args.output
        else source.with_name(source.stem + "_config.html")
    )

    workbook = TwbWorkbook.open(str(source))
    workbook.apply_config(str(config))
    # デザインルール・ダッシュボード・KPI ツリーは .twb に残らないので、
    # YAML をそのまま画面へ戻す（2026-09-21）
    result = workbook.export_html(str(output), overwrite=True, config=str(config))
    print(result)


if __name__ == "__main__":
    main()
