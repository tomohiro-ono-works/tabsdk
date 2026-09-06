"""`field=` などフィールドを受け取る引数の解決を一本化する。

A-8。以前は `draw.py` の `_resolve_fields()` だけが「名前・タプル・オブジェクト」の
3 通りを受ける規則を持っていて、クラス方式のメソッドは `TwbField` しか受け付けなかった。
解決処理を各メソッドへ書くと、A-7（`folder=`）と同じ不揃いが起きる。

| 渡す値 | 解決 |
|---|---|
| `TwbField` | そのまま使う |
| `("データソース名", "フィールド名")` | データソースを名前で解決してから探す |
| `"フィールド名"` | 呼び出し先の文脈（候補データソース）から探す |

素の文字列は暗黙にデータソースを選ばない。候補が 0 個または 1 つに決まらない場合は例外。
"""

from __future__ import annotations

from lxml import etree as ET

from .connected import TwbDatasource, TwbField, get_datasources
from .context import WorkbookContext
from .errors import AmbiguousCaptionError, NotFoundError

FieldInput = str | tuple[str, str] | TwbField


def worksheet_datasources(
    context: WorkbookContext,
    worksheet_el: ET._Element,
) -> list[TwbDatasource]:
    """ワークシートが既に依存しているデータソース。素の文字列の文脈になる。"""
    ids: list[str] = []
    for element in worksheet_el.xpath(
        ".//*[local-name()='datasource-dependencies']/@datasource"
        " | .//*[local-name()='datasources']/*[local-name()='datasource']/@name"
    ):
        datasource_id = str(element)
        if datasource_id not in ids:
            ids.append(datasource_id)

    result: list[TwbDatasource] = []
    for datasource_id in ids:
        matches = get_datasources(context, id=datasource_id)
        if matches:
            result.append(matches[0])
    return result


def resolve_field_input(
    context: WorkbookContext,
    value: FieldInput,
    *,
    datasources: list[TwbDatasource] | None = None,
    argument: str = "field",
) -> TwbField:
    """1 件を解決する。`datasources` は素の文字列を解決するときの候補。"""
    if isinstance(value, TwbField):
        if value._context is not context:
            raise ValueError(f"{argument} must belong to the same workbook")
        value._ensure_attached()
        return value

    candidates = list(datasources or [])
    if isinstance(value, tuple):
        if len(value) != 2 or not all(isinstance(part, str) for part in value):
            raise TypeError(
                f"{argument} tuple must be (datasource name, field name)"
            )
        datasource_name, field_name = value
        matches = get_datasources(context, name=datasource_name)
        if not matches:
            raise NotFoundError(f"datasource not found: {datasource_name}")
        if len(matches) > 1:
            raise AmbiguousCaptionError(
                f"datasource name is ambiguous: {datasource_name}"
            )
        candidates = [matches[0]]
    elif isinstance(value, str):
        field_name = value.strip()
        if not field_name:
            raise ValueError(f"{argument} must not be empty")
        if not candidates:
            # まだ何も置かれていないワークシートなど、文脈が無い場合。
            # ワークブックのデータソースが 1 つなら曖昧さが無いので許す。
            candidates = get_datasources(context)
            if len(candidates) > 1:
                raise AmbiguousCaptionError(
                    f"cannot resolve {argument} by name here: {field_name}."
                    " specify it as (datasource name, field name)"
                )
            if not candidates:
                raise NotFoundError(f"field not found: {field_name}")
    else:
        raise TypeError(
            f"{argument} must be a name, (datasource name, field name), or TwbField"
        )

    found: list[TwbField] = []
    for datasource in candidates:
        found.extend(datasource.get_fields(name=field_name))
    if not found:
        raise NotFoundError(f"field not found: {field_name}")
    if len(found) > 1:
        raise AmbiguousCaptionError(f"field name is ambiguous: {field_name}")
    return found[0]


def resolve_field_inputs(
    context: WorkbookContext,
    values: list[FieldInput],
    *,
    datasources: list[TwbDatasource] | None = None,
    argument: str = "field",
) -> list[TwbField]:
    return [
        resolve_field_input(context, value, datasources=datasources, argument=argument)
        for value in values
    ]
