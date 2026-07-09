from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    return names


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return value


def write_dicts_csv(
    rows: list[dict[str, Any]],
    path: str | Path,
    *,
    fieldnames: list[str] | None = None,
    encoding: str = "utf-8-sig",
) -> None:
    headers = fieldnames or _fieldnames(rows)
    with Path(path).open("w", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in headers})
