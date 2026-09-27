"""01データソース作成用: twb / twbx から設定画面 html を出す CLI。

export_html() 1 回を呼ぶだけの薄いラッパー。仕様は docs/html_screen_spec.md。
バッチファイルへのドラッグ&ドロップで使う想定なので、出力は既定で上書きする。

    uv run python "scripts/01_export_html.py" <workbook.twb|twbx> [output.html]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from twbpatch import TwbWorkbook


def main() -> None:
    parser = argparse.ArgumentParser(description="twb/twbx から設定画面 html を出す")
    parser.add_argument("workbook", help="入力の .twb / .twbx")
    parser.add_argument(
        "output", nargs="?", help="出力先 html（省略時は <ワークブック名>_config.html）"
    )
    args = parser.parse_args()

    source = Path(args.workbook)
    output = (
        Path(args.output)
        if args.output
        else source.with_name(source.stem + "_config.html")
    )

    workbook = TwbWorkbook.open(str(source))
    result = workbook.export_html(str(output), overwrite=True)
    print(result)


if __name__ == "__main__":
    main()
