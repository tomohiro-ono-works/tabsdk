# A-8: フィールド指定の書き味を揃える

- 起票日: 2026-09-06
- 決定: クラス方式のメソッドも、フィールドを**名前で指定できる**ようにする
- 根拠: A-7（`folder=`）と同じ不揃い。実測は下記

このファイルは作業が完了するまでの一時的な計画。完了後に削除する。

## 何が問題か

**API 方式は名前で書けるのに、クラス方式はオブジェクトしか受け付けない。**

```python
# API 方式（draw.py の _resolve_fields）— 3 通り受ける
workbook.draw_bar(name="棒", item=("売上データ", "カテゴリ"), metric=("売上データ", "売上"))
workbook.draw_bar(datasource, name="棒", item="カテゴリ", metric="売上")
workbook.draw_bar(name="棒", item=field_obj, metric=metric_obj)

# クラス方式 — オブジェクトのみ
field = datasource.get_fields(name="カテゴリ")[0]
worksheet.add_field(field, shelf="rows")
```

A-7（`folder=`）と同じ構図。**解決処理が 1 箇所に無いことが原因。**

## 決定済み（2026-09-06）

### 引数は 1 つにする

`field=` と `field_name=` のように分けず、**1 つの引数で 3 通りの型を受ける**。

```python
worksheet.add_field(field="カテゴリ", shelf="rows")
worksheet.add_field(field=("売上データ", "カテゴリ"), shelf="rows")
worksheet.add_field(field=field_obj, shelf="rows")
```

分けなかった理由:

- `draw_*` が既に `item=` ひとつで 3 通りを受けている。分けると A-8 の目的（書き味を
  揃える）と逆方向になる
- 引数が倍に増える。`add_sort(field, by=)` は `field` / `field_name` / `by` / `by_name`
  の 4 つになる
- 「両方渡した」「どちらも渡さない」の検証が全メソッドに要る

### 引数はキーワード専用にする

**位置引数を許さない。** 仕様 §4.2（`get_*()`）と §5.4（`update()`）が既にこの方針で、
`add_*` 系だけ第 1 引数が位置引数として残っている。

```python
worksheet.add_field(field=..., shelf="rows")   # これだけを許す
worksheet.add_field(..., shelf="rows")         # 不可
```

**破壊的変更**: `worksheet.add_field(field_obj, shelf="rows")` という既存の書き方が
動かなくなる。未リリースであり、呼び出し元はテストと `examples/` だけなので追随できる。

## 先に決めること

### 決定 1: 曖昧さの解決規則

`folder=` はデータソース内で完結したが、フィールドは**データソースが複数あると
名前だけで決まらない**。`draw_*` は既に規則を持っているので、それに揃える。

| 渡す値 | 意味 |
|---|---|
| `TwbField` | そのまま使う |
| `("データソース名", "フィールド名")` | データソースを名前で解決してから探す |
| `"フィールド名"` | 呼び出し先が単一データソースに属する場合のみ。決まらなければ例外 |

**論点**: `worksheet.add_field("カテゴリ")` の素の文字列をどう扱うか。
`draw_*` は第 2 引数の `datasource` が文脈を与えていたが、`worksheet` にはそれが無い。

- 案 A: ワークブックに**データソースが 1 つだけ**なら文字列を許す。複数なら `AmbiguousCaptionError`
- 案 B: ワークシートが**既に依存しているデータソース**から探す。0 個または複数なら例外
- 案 C: 文字列は許さず、タプルと `TwbField` だけにする

### 決定 2: 解決処理の置き場

`draw.py:17` の `_resolve_fields()` が既に規則を実装している。これを共通化して
クラス方式からも呼ぶ。置き場は `field_ref.py` か新規 `field_input.py`。

**`draw.py` に残したまま `connected_worksheet.py` から import すると循環する**
（`draw.py` → `connected_worksheet.py`）。移動が要る。

## 対象メソッド（実測）

### `TwbField` を受け取る（名前で書けるようにする対象）

| クラス | メソッド | 場所 |
|---|---|---|
| `TwbWorksheet` | `add_field(field, *, shelf=...)` | `connected_worksheet.py:1222` |
| `TwbWorksheet` | `add_filter(field)` | `:1567` |
| `TwbWorksheet` | `add_filter_slice(field)` | `:1612` |
| `TwbWorksheet` | `add_sort(field, *, by=...)` | `:1640`（`by` も `TwbField`） |
| `TwbWorksheet` | `add_field(table_calculation_field=...)` | `:1230` |
| `TwbPane` | `add_field(field, *, encoding=...)` | `:2354` |
| `TwbPane` | `add_field(table_calculation_field=...)` | `:2362` |

非公開の `_set_table_calculation_partition(partition_field)`（`:1291`）と
`_configure_colored_yoy_columns(layout_field)`（`:1371`）も同じ経路を通す。

### `TwbWorksheetField` を受け取る（**対象外**）

シェルフに置かれた後の配置を指す。フィールドそのものではないので名前で解決できない。

| クラス | メソッド | 場所 |
|---|---|---|
| `TwbWorksheet` | `add_reference_line(field)` | `:903` |
| `TwbWorksheet` | `set_axis_visibility(field)` | `:1191` |
| `TwbPane` | `set_customized_label(main_metric=, sub_metric=)` | `:2199` |
| `TwbPane` | `get_categorical_colors(field)` / `set_categorical_colors(field)` | `:2417` / `:2444` |
| `TwbPane` | `set_continuous_colors(field)` | `:2501` |
| `TwbDashboardContainer` | `add_filter(field)` | `connected_dashboard.py:1342` |

> ただし `worksheet.get_fields(name=...)` で取れるので、利用者の手間は小さい。
> 対象外とする判断でよいか、着手前に確認する。

## Phase 分け

- [ ] **P0-1** 決定 1（素の文字列の扱い）を仕様 §2.0 か §5.4 へ追記。
      あわせて「フィールドを受ける引数は 1 つ・キーワード専用」も明記する
- [ ] **P0-2** 決定 2（解決処理の置き場）を決めて移動する。`draw.py` の呼び出しを差し替え、
      テストが通ることを確認（移動だけで挙動を変えない）
- [ ] **P1-1** `TwbWorksheet.add_field()` を共通解決へ差し替え。異常系を含めテスト
- [ ] **P1-2** `TwbPane.add_field()` を同様に
- [ ] **P1-3** `add_filter()` / `add_filter_slice()` / `add_sort()` を同様に
- [ ] **P1-4** `table_calculation_field` と非公開 2 件を同様に
- [ ] **P2-1** `examples/build_dashboard.py` のペイン直接操作を名前指定へ書き換え、
      「クラス方式でも名前で書ける」ことを見せる
- [ ] **P2-2** `docs/api_reference.md` の引数表を更新
- [ ] **P3-1** テスト実行。`/spec-conformance` を再実行

## 完了条件

- クラス方式と API 方式で、フィールドの指定方法が同じ
- 解決処理が 1 箇所にあり、各メソッドが個別に実装していない
- 曖昧なとき（同名フィールドが複数、データソースが決まらない）は暗黙に選ばず例外
- 既存の `TwbField` を渡す書き方は、キーワード指定にすれば動く
- 公開メソッドの引数に位置引数が残っていない
