# 移行ステータス

> **このファイルは `/spec-conformance` が生成する。手で編集しない。**
> 生成日: 2026-09-05 / 正典: `docs/model_api_spec.md`

## テスト結果

```
uv run --no-sync pytest -q --basetemp=tmp/pytest
89 passed, 2 skipped
```

`CLAUDE.md` に記載の期待値（80 passed, 2 skipped）より 9 件増えている。テストの追加によるもので、失敗は無い。

## §13 受け入れ条件の判定

判定対象は新 API（`connected*.py` と `TwbWorkbook` の新規メソッド）のみ。
`TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()` と `models.py` の dataclass 群は
仕様 §11 により併存が認められているため、違反として扱わない。

| # | 条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 公開 API に `list_*()` が存在しない | PASS | `connected*.py` に `def list_` 0 件 |
| 2 | 公開の単数取得 `get_<単数形>()` が存在しない | PASS | リソース取得はすべて複数形（`connected.py:266,293,309,328,1218` ほか）。無引数の `get_style()` 等は §4.1 の属性読み取りで対象外 |
| 3 | 公開の `update_*()` が存在しない | **FAIL** | 下記「FAIL の詳細」参照（5 件） |
| 4 | 親モデルに `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | `connected*.py` に `def delete_` 0 件、子リソース名を持つ `update_` 0 件 |
| 5 | すべてのリソース `get_*()` が `list` を返す | PASS | 戻り値注釈が全 18 箇所 `list[...]`（`connected.py:271,298,314,333,1223` / `connected_worksheet.py:849,864,878,942,1842` / `connected_dashboard.py:665,686,700,720,737,754,1234,1251`） |
| 6 | 公開取得 API に `identifier` と `by` が無い | PASS | `connected*.py` に `by: str` / `identifier` 0 件 |
| 7 | 検索条件がキーワード専用の `id=` / `name=` | PASS | `inspect.signature` で全リソース `get_*` の `id`/`name` が KEYWORD_ONLY |
| 8 | `id` と `name` の同時指定が `ValueError` | PASS | 実測（`wb.get_datasources/get_worksheets/get_dashboards/get_parameters`、`ds.get_fields/get_folders` すべて `ValueError`）。ガードは `connected.py:54 _validate_get_args()`、呼び出し 26 箇所 |
| 9 | `TwbWorksheet.create_field()` が無く `add_field()` がある | PASS | `hasattr` 実測（`create_field` False / `add_field` True）、`connected_worksheet.py:1242` |
| 10 | シェルフが `rows`/`columns`/`pages`/`filters` を検証 | PASS | `connected_worksheet.py:46 _SHELVES`、`:1255` の `if shelf not in {*_SHELVES, "filters"}` |
| 11 | `TwbPane` が `mark_type` 更新とエンコーディング配置に対応 | PASS | `connected_worksheet.py:2301 update(mark_type=)`、`:2307` 検証、`:58 _ENCODINGS`（8 種）、`:2068 add_field` |
| 12 | 複数 Pane では対象 Pane の明示選択が必要 | PASS | 配置 API は `TwbPane` のインスタンスメソッドのみ。Worksheet 側に暗黙先頭 Pane の API なし |
| 13 | `TwbWorksheetField.delete()` が配置だけを解除 | PASS | `connected_worksheet.py:2483`、`tests/test_connected_worksheet_api.py:209` |
| 14 | フォルダ指定が `TwbFolder` オブジェクト | PASS | `TwbField.move_to_folder(folder: TwbFolder)`（`connected.py:1128`）、`tests/test_connected_api.py:140` |
| 15 | Dashboard の標準配置が `TwbDashboardContainer` のタイル | PASS | `connected_dashboard.py:988 create_container`、`:1263`、`:1306 add_worksheet` |
| 16 | タイル API が `direction`/`order`/`weight` を受け、`x`/`y` を受けない | PASS | `TwbDashboardContainer.create_container(*, direction, order, weight, ...)` / `add_worksheet(*, order, weight, ...)` に座標引数なし |
| 17 | SDK がタイルの階層・順序・比率から座標を計算 | PASS | `tests/test_connected_dashboard_api.py:72` |
| 18 | 既存 Dashboard 編集が対象コンテナ配下だけを変更 | PASS | `tests/test_connected_dashboard_api.py:356` |
| 19 | 未対応属性・対象外 Zone・デバイスレイアウトを暗黙変更しない | 要目視 | `:356` のテストは対象コンテナ限定のみ検証。デバイスレイアウトと未解釈属性の保持を直接検証するテストが無い |
| 20 | `TwbDashboardZone.delete()` が配置だけを削除 | PASS | `connected_dashboard.py:1844`、`tests/test_connected_dashboard_api.py:277` |
| 21 | 浮動配置が `add_floating_worksheet()` という別 API | PASS | `connected_dashboard.py:1029` |
| 22 | タイル/浮動 Zone で無効な更新引数が `ValueError` | PASS | `connected_dashboard.py:1773-1776`（tiled への x/y/w/h、floating への order/weight）、`tests/test_connected_dashboard_api.py:306` |
| 23 | 参照中の `delete()` が `ResourceInUseError`、XML と `is_dirty` 不変 | PASS | `tests/test_connected_delete_parameter_api.py:67`、`tests/test_connected_dashboard_api.py:377` |
| 24 | `ResourceInUseError.references` から種類・ID・場所を取得 | PASS | `errors.py:36 ResourceReference(resource_type, resource_id, location)`、`errors.py:43` |
| 25 | 連鎖削除が公開 API に存在しない | PASS | `twbpatch/*.py` に `cascade` 0 件 |
| 26 | `TwbColumn` と公開 `column` が `TwbField` / `field` へ移行 | PASS | 新 API は `TwbField` のみ。`__all__` の `TwbColumn` は §11 の旧 API |
| 27 | XML 固有の `column` と `TwbWorksheet.columns` は維持 | PASS | `models.TwbWorksheet.__dataclass_fields__` に `columns` あり |
| 28 | 公開 `id`=`@name`、公開 `name`=`@caption`（Worksheet は両方 `@name`） | PASS | `connected.py:36 get_xml_id()` / `:44 get_display_name()` に集約、`tests/test_connected_api.py:105` |
| 29 | `@caption` が無い場合は `@name` 由来の既定表示名 | PASS | `connected.py:44-51`（`strip_field_brackets` で角括弧のみ除去） |
| 30 | 公開モデルと JSON 出力に `caption` が無い | PASS | 接続型 11 クラスに `caption` 属性 0 件、`export_json()` に `"caption"` 0 件（実測） |
| 31 | XML 内参照と計算式保存が `id` を使用 | PASS | `tests/test_connected_api.py:121` |
| 32 | `name` から参照を解決できない/複数候補なら暗黙選択しない | PASS | `AmbiguousFormulaReferenceError` / `AmbiguousCaptionError`（`errors.py:15,11`） |
| 33 | 接続型モデルが更新後の XML を再取得なしで参照できる | PASS | `tests/test_connected_api.py:105` |
| 34 | CRUD だけではファイルが変更されない | PASS | `tests/test_connected_api.py:342` |
| 35 | `save()` の成功時だけファイルへ反映 | PASS | `workbook.py:141-158`、`tests/test_connected_api.py:342` |
| 36 | `reload()` が未保存変更を破棄しモデルを無効化 | PASS | `workbook.py:89`、`tests/test_connected_api.py:359` |
| 37 | 削除・無効化モデルの操作が `DetachedModelError` | PASS | `connected*.py` で計 38 箇所送出、`tests/test_connected_api.py:359` |
| 38 | 非公開コンテキストが JSON 出力に含まれない | PASS | `export_json()` に `_context` 0 件（実測）、`tests/test_connected_final_api.py:161` |
| 39 | 既存の対応機能で旧 API と同等の XML 編集結果 | 要目視 | 同等性を直接比較するテストは `tests/test_style_group_api.py:50` の 1 件のみ。他の編集機能に対応する比較テストが無い |
| 40 | （§5.1）`create_*()` の引数がすべてキーワード専用 | **FAIL** | `TwbDatasource.create_calculated_fields(self, calculations)` が位置引数（`connected.py:634`） |

## FAIL の詳細

### 3. 公開 `update_*()` が新 API 側に 5 件残っている

いずれも docstring で「旧 API。§11 により存続」と宣言しているが、これらは `models.py` の
dataclass でも `TwbWorkbook` の旧メソッドでもなく、**新 API の接続型モデル自身に生えている**。
仕様 §11 が併存を認めているのは `TwbWorkbook` 側の旧 API であり、接続型モデル上の
`update_*()` は §3.3「公開 `update_*()` は使用しない」と §13 の条件に直接抵触する。

| ファイル:行 | メソッド | 対応する新 API |
|---|---|---|
| `twbpatch/connected_dashboard.py:1197` | `TwbDashboardContainer.update_style(**styles)` | `container.update(style={...})` |
| `twbpatch/connected_dashboard.py:1687` | `TwbDashboardZone.update_style(**styles)` | `zone.update(style={...})` |
| `twbpatch/connected_worksheet.py:1016` | `TwbWorksheet.update_table_style(...)` | `worksheet.update(table_style={...})` |
| `twbpatch/connected_worksheet.py:1192` | `TwbWorksheet.update_title_style(...)` | `worksheet.update(title_style={...})` |
| `twbpatch/connected_worksheet.py:1888` | `TwbPane.update_customized_label(...)` | `pane.set_customized_label(...)` |

いずれも本体は既に新 API へ委譲する薄いラッパー。削除しても内部実装
（`_apply_table_style` / `_apply_title_style` / `set_customized_label`）は残る。

同様に、属性読み取りの旧別名も §4.1「引数を取らない属性の読み取りはプロパティとして公開する」
に対する重複であり、対になるプロパティが既に存在する。§13 の条件ではないため FAIL には
含めないが、`update_*()` を削除するなら同時に整理する対象になる。

| 旧別名 | 対になるプロパティ |
|---|---|
| `connected.py:352 get_field_grouping()` | `connected.py:348 field_grouping` |
| `connected_dashboard.py:1193 / 1683 get_style()` | `:1189 / :1679 style` |
| `connected_worksheet.py:961 get_table_style()` | `:957 table_style` |
| `connected_worksheet.py:1135 get_title_style()` | `:1131 title_style` |
| `connected_worksheet.py:1856 get_customized_label()` | `:1852 customized_label` |
| `connected_worksheet.py:1995 get_mark_opacity()` | `:1991 mark_opacity` |

`get_categorical_colors(field)` は引数を取るため §4.1 により `get_` / `set_` の対を維持してよい。

### 40. `create_calculated_fields()` が位置引数を受け取る

`twbpatch/connected.py:634`

```python
def create_calculated_fields(self, calculations, ...)
```

§5.1「`create_*()` の引数はすべてキーワード専用とする」に反する。
`def create_calculated_fields(self, *, calculations: ...)` へ変更する。

なお `TwbWorkbook.create_calculated_field(datasource, caption, formula)` も位置引数だが、
こちらは §11 の旧 API のため対象外。

## 仕様に無い公開 API（正典側の未記載）

実装済みだが `docs/model_api_spec.md` §6 に記載が無い公開メソッド。仕様が正典である以上、
**実装を消すか仕様へ追記するかを決める必要がある。** 現状は正典が実装に追随していない。

| クラス | メソッド |
|---|---|
| `TwbWorkbook` | `set_default_font()`, `set_filter()`, `apply_field_config()`, `draw_sheet()`, `draw_colored_yoy_sheet()`, `draw_yoy()`, `draw_bar()`, `draw_card()`, `draw_quadrant()`, `draw_crosstab()` |
| `TwbDatasource` | `set_filter()`, `apply_field_config()`, `create_calculated_fields()`, `field_grouping` / `get_field_grouping()`, `update(field_grouping=...)` |
| `TwbWorksheet` | `add_reference_line()`, `add_filter()`, `add_filter_slice()`, `add_sort()`, `set_axis_visibility()`, `title` / `set_title()` |
| `TwbPane` | `set_label_style()`, `set_mark_opacity()`, `set_mark_sizing()`, `set_mark_size()`, `set_mark_color()`, `set_categorical_colors()`, `set_continuous_colors()`, `set_customized_label()` |
| `TwbDashboard` | `build_report()` |
| `TwbDashboardContainer` | `add_filter()`, `add_text()`, `add_image()`, `add_spacer()`, `add_dashboard_object()`, `create_container(fixed_size=, hidden=, distribute_evenly=)` |
| `TwbDashboardZone` | `update(fixed_size=, friendly_name=, hidden=, style=)`, `kind`, `friendly_name`, `fixed_size`, `text` |
| `TwbWorksheetField` | `table_calculation`, `date_level`、`add_field(table_calculation=, table_calculation_field=, date_level=)` |

## README のドリフト

`README.md`（526 行）は **旧 API だけを記述しており、新 API を一切載せていない。**
`CLAUDE.md` の「実装を変えたら README も更新する」に対して未追随。

### README にあるが仕様上は使わない記述

| README 箇所 | 内容 | 問題 |
|---|---|---|
| L53-63 `### 検索方法 by` | `by="auto"/"caption"/"name"` の説明 | §13「公開取得 API に `by` が存在しない」。新 API には存在しない引数を主要な検索方法として説明している |
| L65-93 | `wb.list_datasources()`, `wb.get_datasource()`, `wb.get_column()`, `wb.list_columns()`, `wb.list_parameters()` | すべて §11 の旧 API。移行先 `wb.get_datasources()` / `datasource.get_fields()` の記載が無い |
| L94-145 | `wb.list_dashboard_fields()`, `wb.list_dashboard_zones()`, `wb.list_dashboard_actions()`, `wb.get_dashboard()`, `wb.get_worksheet()`, `wb.list_worksheet_fields()`, `wb.list_filters()`, `wb.list_relations()`, `wb.list_relationships()` | 同上 |
| L152, L161 | `unsupported_features()` | 実装には残る（`workbook.py:166`）が新 API 名は `get_unsupported_features()`（`:169`）。両方を並べており、どちらを使うべきか示していない |
| L236 `### TwbColumn` | 旧モデル `TwbColumn` の解説 | §3.1 で `TwbField` へ移行済み。`TwbField` の節が無い |
| L165-486「返却モデルの変数」 | `models.py` の dataclass の属性表 | 接続型モデルの属性・メソッドを説明した節が無い |
| L487-512「主な例外」 | 6 例外のみ | `DetachedModelError`, `ResourceInUseError`, `ResourceReference`, `AmbiguousFormulaReferenceError` が未記載（いずれも `__all__` にある） |
| L500-511 例外の例 | `wb.get_worksheet("SalesTrend", by="name")` | 廃止予定の `by=` を推奨形として提示 |
| L514-525「編集と保存の例」 | `wb.create_calculated_field(datasource=, caption=, formula=)` | 旧 API。`caption=` は §3.2 で公開語彙から外れた語。新 API は `datasource.create_calculated_field(name=, formula=)` |

### 実装にあるが README に無い公開シンボル

`__all__` にあり README に記載が無いもの:

- `TwbField`, `TwbPane`, `TwbDashboardContainer`
- `DetachedModelError`, `ResourceInUseError`, `ResourceReference`, `AmbiguousFormulaReferenceError`
- `write_dicts_csv`, `draw_bar`, `draw_card`, `draw_colored_yoy_sheet`, `draw_crosstab`, `draw_quadrant`, `draw_sheet`, `draw_yoy`

新 API のメソッド群（`get_datasources()`, `get_worksheets()`, `get_dashboards()`, `get_parameters()`,
`create_worksheet()`, `create_dashboard()`, `create_parameter()`, `reload()`, `is_dirty`、
および接続型モデルの `update()` / `delete()` / `add_field()` / `move_to_folder()` など）は
README に一切登場しない。

## 次にやるべきこと

FAIL 項目から導いた作業。上から順に実施する。

1. **新 API 側の `update_*()` 5 件を削除する**（条件 3 / §3.3）
   - `connected_dashboard.py:1197` `TwbDashboardContainer.update_style` を削除
   - `connected_dashboard.py:1687` `TwbDashboardZone.update_style` を削除
   - `connected_worksheet.py:1016` `TwbWorksheet.update_table_style` を削除
   - `connected_worksheet.py:1192` `TwbWorksheet.update_title_style` を削除
   - `connected_worksheet.py:1888` `TwbPane.update_customized_label` を削除
   - `tests/test_style_group_api.py:50 test_worksheet_update_style_group_matches_legacy_method` は
     旧メソッドとの同値比較なので、`update(table_style=...)` 単独の検証へ書き換える
2. **`create_calculated_fields()` をキーワード専用にする**（条件 40 / §5.1）
   - `connected.py:634` を `def create_calculated_fields(self, *, calculations: ...)` へ変更し、
     呼び出し側（`workbook.py`、`tests/`、`draw.py`）を追随させる
3. **属性読み取りの旧別名 6 件を削除する**（§4.1）
   - 上表「旧別名」の `get_field_grouping` / `get_style`×2 / `get_table_style` /
     `get_title_style` / `get_customized_label` / `get_mark_opacity`
   - 対になるプロパティは既に存在するため、呼び出し側をプロパティへ置換するだけで済む
4. **`docs/model_api_spec.md` §6 へ未記載の公開 API を追記する**
   - 上表「仕様に無い公開 API」の 8 クラス分。仕様が正典である以上、実装だけが先行している
     状態を解消する。追記しないものは実装から削除する
5. **`README.md` を新 API 中心に書き直す**
   - `### 検索方法 by`（L53-63）を `id=` / `name=` の説明へ差し替え
   - 「返却モデルの変数」（L165-486）へ接続型モデルの節を追加、`TwbColumn` の節を `TwbField` に更新
   - 「主な例外」へ `DetachedModelError` / `ResourceInUseError` / `ResourceReference` /
     `AmbiguousFormulaReferenceError` を追加
   - 「編集と保存の例」（L514-525）を `datasource.create_calculated_field(name=, formula=)` +
     `workbook.save()` の新 API 例へ差し替え
   - `unsupported_features()` の行（L152, L161）を `get_unsupported_features()` に統一
6. **要目視 2 件の検証を追加する**
   - 条件 19: デバイスレイアウトと SDK が解釈しない属性・子要素が Dashboard 編集後も保持される
     ことを検証するテスト（`tests/test_connected_dashboard_api.py`）
   - 条件 39: 旧 API と新 API の XML 編集結果を比較するテスト。現状 `test_style_group_api.py:50`
     の 1 件のみで、`update_*()` を削除するとこの唯一の比較も消える

### 補足（FAIL ではない観察）

- `TwbWorkbook.open()` / `save()` は `path: str` 注釈どおり文字列専用で、`pathlib.Path` を渡すと
  `parser.py:22` の `path.lower()` で `AttributeError` になる。仕様 §6.1 は `open(path)` としか
  書いておらず、`Path` を受けるかは未定義。受けるなら `parser.py:22` と `workbook.py:146` で
  `str(path)` 変換を入れる
- `_AGGREGATIONS` に `"agg"`、`_MARK_TYPES` に `"pie"` が仕様の初期対応値を超えて存在する
  （`connected_worksheet.py:47,69`）。追加方向のため受け入れ条件には抵触しない
