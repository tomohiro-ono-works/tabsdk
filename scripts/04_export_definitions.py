"""Tableau Workbook から定義書 Excel を作成する CLI。

    uv run --no-sync python scripts/04_export_definitions.py workbook.twbx [output.xlsx]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from twbpatch import export_excel


def main() -> None:
    parser = argparse.ArgumentParser(description="Tableau Workbook の定義書 Excel を作成する")
    parser.add_argument("workbook", help="入力する .twb / .twbx")
    parser.add_argument(
        "output", nargs="?", help="出力先 .xlsx（省略時は <ワークブック名>_definition.xlsx）"
    )
    args = parser.parse_args()

    source = Path(args.workbook)
    output = Path(args.output) if args.output else source.with_name(source.stem + "_definition.xlsx")
    try:
        export_excel(str(source), str(output))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"定義書の出力に失敗しました: {exc}\n")
    print(output.resolve())


if __name__ == "__main__":
    main()
