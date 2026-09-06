# 移行状況（自動生成）

> このファイルは `/spec-conformance` が生成する。**手で編集しない。**
> 状態は毎回 `twbpatch/` の実装から導出し、前回の内容を引き継がない。

- 生成日: 2026-09-06
- 正典: `docs/model_api_spec.md`（§3 命名 / §4 取得契約 / §5 CRUD / §13 受け入れ条件）
- 判定対象: 新 API（`connected.py` / `connected_worksheet.py` / `connected_dashboard.py` /
  `connected_parameter.py` と `TwbWorkbook` の新規メソッド）。
  旧 API（`models.py` の dataclass、`TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()`）の
  併存は仕様 §11 により違反として扱わない。

## テスト結果

```
uv run --no-sync pytest -q --basetemp=tmp/pytest
167 passed, 0 skipped
```

`CLAUDE.md` は期待値を `158 passed` と書いているが、実測は `167 passed`（テストが追加されたため）。
`CLAUDE.md` 側の数値が古い。

## §13 受け入れ条件の判定

| # | 条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 公開 API に `list_*()` が存在しない | PASS | 接続型モデルに `list_*` は 0 件（`twbpatch/connected*.py` を実行時走査）。`TwbWorkbook.list_*()` 15 本は旧 API（§11 で許容） |
| 2 | 公開の単数取得 `get_<単数形>()` が存在しない | PASS | 接続型モデルに 0 件。`workbook.py:216,554,625,718` の `get_dashboard` / `get_worksheet` / `get_datasource` / `get_column` は旧 API |
| 3 | 公開の `update_*()` が存在せず `update()` で更新できる | PASS | 接続型モデルに 0 件。`workbook.py:706,733,751` の `update_source` / `update_column` / `update_formula` は旧 API |
| 4 | 親モデルに公開の `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | 実行時走査で `Twb*` クラスに該当メソッド 0 件 |
| 5 | すべての `get_*()` が `list` を返す | PASS | AST 検査で `id=` / `name=` を取る公開 `get_*` 22 本すべて戻り値注釈が `list[...]` |
| 6 | 公開取得 API に `identifier` と `by` が存在しない | PASS | `grep "by: str\|identifier" twbpatch/connected*.py` が 0 件 |
| 7 | 検索条件がキーワード専用の `id=` / `name=` に統一 | PASS | AST 検査で 22 本すべて `kwonlyargs` に `id` / `name` |
| 8 | `id` と `name` の同時指定で `ValueError` | PASS | `connected.py:60` `_validate_get_args()`。22 本すべてが（`workbook.py` の 4 本は委譲先のモジュール関数経由で）呼び出す。実測で `ValueError` |
| 9 | `TwbWorksheet.create_field()` が無く `add_field()` で配置 | PASS | 実測 `hasattr(TwbWorksheet, "create_field") == False`、`connected_worksheet.py:1354` に `add_field()` |
| 10 | シェルフが `rows` / `columns` / `pages` / `filters` を検証 | PASS | `connected_worksheet.py:1371`。実測で `shelf="rowz"` が `ValueError: unsupported shelf: rowz` |
| 11 | `TwbPane` が `mark_type` を更新しエンコーディングへ配置できる | PASS | `connected_worksheet.py:2747` `update(mark_type=)`、`:2510` `add_field(encoding=)`、`:2526` で `encoding` を検証。実測済み |
| 12 | 複数 Pane では対象 Pane の明示的な選択が必要 | PASS | Pane を省略して暗黙に先頭へ配置する公開 API は無い。配置は `TwbPane.add_field()` のみで、対象は `worksheet.get_panes()`（`:916`）から選ぶ |
| 13 | 総計が `update(grand_totals=)` と同名プロパティの対称形 | PASS | `connected_worksheet.py:1016` プロパティ / `:1811` `update(grand_totals=GrandTotals)`。実測で往復一致 |
| 14 | 小計が `set_subtotal_visibility()` で、`update()` に含まれない | PASS | `connected_worksheet.py:1271`。`update()` のシグネチャに小計の引数なし |
| 15 | `TwbWorksheetField.delete()` が配置だけを解除する | PASS | `connected_worksheet.py:2952`。実測でエンコーディング削除後も `datasource.get_fields()` の件数が不変 |
| 16 | フォルダ指定が文字列ではなく同じ Datasource の `TwbFolder` | **FAIL** | `connected.py:588 / 663 / 715` の `folder: str \| TwbFolder \| None`。`_resolve_folder()`（`connected.py:544`）が文字列名を解決する。`field.move_to_folder()`（`:1300`）だけが仕様どおり `TypeError` で文字列を拒否 |
| 17 | Dashboard の標準配置が `TwbDashboardContainer` のタイル配置 | PASS | `connected_dashboard.py:989` `create_container()`、`:1299` `add_worksheet()`。ルートは 1 つに制限（`:1004` で `ValueError`）。実測済み |
| 18 | タイル配置 API が `direction` / `order` / `weight` を受け `x` / `y` を受け付けない | PASS | 実測シグネチャ: `create_container(direction, order, weight, fixed_size, friendly_name, hidden, distribute_evenly)` / `add_worksheet(worksheet, order, weight, show_title, fixed_size, friendly_name)` |
| 19 | SDK がタイルの階層・順序・比率から座標とサイズを計算する | PASS | 実測で `add_worksheet(order=0, weight=1)` の Zone が `x=0 y=0 w=1200 h=800` を取得。`tests/test_connected_dashboard_api.py:72` |
| 20 | 既存 Dashboard の編集が対象コンテナ配下だけを変更する | PASS | `tests/test_connected_dashboard_api.py:356` |
| 21 | 未対応属性・対象外 Zone・デバイスレイアウトが暗黙に変わらない | PASS | 同テスト `:363-372` が `devicelayouts` の直列化結果の不変を検証 |
| 22 | `TwbDashboardZone.delete()` が配置だけを削除する | PASS | `connected_dashboard.py:1815`。実測で削除後も `get_worksheets()` の件数が不変 |
| 23 | 浮動配置が `add_floating_worksheet()` という別 API | PASS | `connected_dashboard.py:1030` |
| 24 | タイル Zone / 浮動 Zone で無効な更新引数は `ValueError` | PASS | `connected_dashboard.py:1744` でタイルへの `x` / `y` / `width` / `height` を拒否（実測）。浮動への `order` / `weight` は `tests/test_connected_dashboard_api.py:306` |
| 25 | 参照中リソースの `delete()` が `ResourceInUseError`、XML と `is_dirty` が不変 | PASS | `connected.py:820,1342,1431` / `connected_dashboard.py:1127,1591` / `connected_parameter.py:251` / `connected_worksheet.py:1892`。実測で `is_dirty` 不変 |
| 26 | `references` から参照元の種類・ID・場所を確認できる | PASS | `errors.py` の `ResourceReference(resource_type, resource_id, location)`。実測値 `('Field', '[Sales]', '/workbook/datasources/datasource/column[1]')` |
| 27 | 連鎖削除が公開 API に存在しない | PASS | `grep -rn "cascade" twbpatch/` が 0 件 |
| 28 | `TwbColumn` と公開 `column` が `TwbField` / `field` へ移行 | PASS | 接続型モデルは `TwbField` / `get_fields()` / `field=` に統一。`TwbColumn` は `twbpatch.models` の旧 dataclass として存置（§11） |
| 29 | XML 固有の `column` と `TwbWorksheet.columns` は維持 | 要目視 | 旧 dataclass `models.TwbWorksheet` は `columns` フィールドを保持（実測）。一方、トップレベルへ公開されている接続型 `TwbWorksheet` に `columns` プロパティは無く、列シェルフは `get_fields()` の `shelf == "columns"` で表す。仕様のこの条件が旧 dataclass だけを指すのか、接続型にも `columns` を要求するのかが本文から一意に読めない |
| 30 | 公開 `id` が `@name`、`name` が `@caption`（Worksheet は両方 `@name`） | PASS | `connected.py:57` `get_display_name()`、`connected_worksheet.py` の `_worksheet_display_name()`。`tests/test_connected_api.py:105` |
| 31 | `@caption` が無い場合、`name` が `@name` 由来の既定表示名 | PASS | `connected.py:57-64`（`strip_field_brackets` で外側の角括弧のみ除去）。`tests/test_connected_api.py:105` |
| 32 | 公開モデルと JSON 出力に `caption` が存在しない | PASS | 実測で接続型 10 クラスに `caption` 属性なし。`export_json()` の出力に `"caption"` を含まない（`serialization.py:20` で `caption` → `name` へ正規化） |
| 33 | XML 内の参照と計算式保存が表示名ではなく `id` を使用 | PASS | 実測: `create_calculated_field(formula="SUM([利益])/SUM([売上])")` が `SUM([Profit])/SUM([Sales])` として保存される |
| 34 | 公開 `name` から解決できない／複数候補なら暗黙に選択しない | PASS | `domain/formula.py:29` が `AmbiguousFormulaReferenceError`。実測で同一 caption 2 件の Datasource に対し例外 |
| 35 | 接続型モデルが更新後のメモリ上 XML を再取得なしで参照できる | PASS | `tests/test_connected_api.py:105` |
| 36 | CRUD 操作だけではファイルが変更されない | PASS | 実測: `field.update()` 後に `is_dirty == True`、元ファイルのバイト列は不変 |
| 37 | `save()` の成功時だけファイルへ反映される | PASS | `workbook.py:142` `save(path, validate=True, overwrite=False)`。上記 36 の裏返しとして実測 |
| 38 | `reload()` が未保存変更を破棄し既存モデルを無効化する | PASS | `tests/test_connected_api.py:359`。実測で `reload()` 後の旧モデル操作が `DetachedModelError` |
| 39 | 削除・無効化されたモデルの操作が `DetachedModelError` | PASS | 実測。`_ensure_attached()` が `connected*.py` 全体で使われている（`DetachedModelError` の言及は 4 ファイルで計 45 箇所） |
| 40 | 非公開コンテキストが JSON 出力へ含まれない | PASS | 実測で `export_json()` の出力に `_context` を含まない |
| 41 | 既存の対応機能について旧 API と同等の XML 編集結果を得られる | 要目視 | 新旧を同一入力で走らせて XML を突き合わせる回帰テストが無い。`tests/test_smoke.py` は旧 API 単独、`tests/test_connected_*.py` は新 API 単独 |

判定: PASS 38 / FAIL 1 / 要目視 2。

## README のドリフト

`README.md`（最終更新 2026-07-18）は**新 API を 1 つも記載していない**。
`twbpatch/__init__.py` の `__all__` は 36 シンボルを公開するが、README は旧 API だけを説明している。

### README に無い公開シンボル

| 分類 | シンボル |
|---|---|
| 接続型モデル | `TwbField`、`TwbPane`、`TwbDashboardContainer` |
| 例外 | `DetachedModelError`、`ResourceInUseError`、`ResourceReference`、`AmbiguousFormulaReferenceError` |
| ユーティリティ | `write_dicts_csv` |

### README に無い公開メソッド（`grep` で 0 件）

- 取得: `get_datasources` / `get_worksheets` / `get_dashboards` / `get_parameters` / `get_fields` / `get_folders` / `get_panes` / `get_containers` / `get_zones` / `get_actions` / `get_filter_controls` / `get_relations` / `get_relationships` / `get_reference_lines` / `get_filters` / `get_unsupported_features`
- 作成: `create_worksheet` / `create_dashboard` / `create_parameter` / `create_folder` / `create_container` / `create_calculated_fields` / `create_yoy_calculated_fields`
- 更新・配置: `update` / `delete` / `move_to_folder` / `remove_from_folder` / `add_field` / `add_worksheet` / `add_filter` / `add_text` / `add_image` / `add_spacer` / `add_floating_worksheet` / `add_sort` / `add_reference_line` / `set_subtotal_visibility` / `set_axis_visibility` / `set_customized_label` / `set_categorical_colors` / `set_continuous_colors`
- API 方式: `draw_sheet` / `draw_bar` / `draw_yoy` / `draw_card` / `draw_quadrant` / `draw_crosstab` / `draw_colored_yoy_sheet` / `set_filter` / `set_default_font` / `apply_field_config` / `build_report`
- その他: `export_html`

### 仕様と矛盾する記述

| README の箇所 | 内容 | 問題 |
|---|---|---|
| L53-64「検索方法 `by`」 | `by="auto"` / `"caption"` / `"name"` を検索方法として説明 | 仕様 §4.2 は `by` を使わない。新 API は `id=` / `name=` のみ。README は移行先を示していない |
| L165-486「返却モデルの変数」 | `TwbDatasource` / `TwbWorksheet` / `TwbDashboard` など 8 クラスの属性表に `caption` を列挙（README 全体で `caption` に 22 箇所言及） | 仕様 §11.1 により `from twbpatch import TwbDatasource` は接続型モデルを返す。接続型に `caption` プロパティは無い（受け入れ条件 #32）。README の属性表が `twbpatch.models` の旧 dataclass の説明であることが書かれていない |
| L236「`TwbColumn`」 | 列モデルとして `TwbColumn` を説明 | 仕様 §3.1 の移行先 `TwbField` に触れていない |
| L487-499「主な例外」 | 6 例外のみ列挙 | `DetachedModelError` / `ResourceInUseError` / `ResourceReference` / `AmbiguousFormulaReferenceError` が漏れている |
| L514-524「編集と保存の例」 | `wb.create_calculated_field(datasource=..., caption=...)` | 仕様 §11 の移行先は `datasource.create_calculated_field(name=..., formula=...)`。`caption=` は公開 API から消える引数 |
| L28-36「公開変数」 | 公開変数は `tree` のみ | `is_dirty`（仕様 §9）が未記載 |

`docs/api_reference.md`（最終更新 2026-09-06）は新 API を含んでおり、README との二重管理になっている。

## 次にやるべきこと

1. **フォルダ引数の型を仕様と一致させる（受け入れ条件 #16、FAIL）**
   `twbpatch/connected.py` の `create_calculated_field()`（L588）、`create_calculated_fields()`（L663）、
   `create_yoy_calculated_fields()`（L715）の `folder` 引数が `str | TwbFolder | None` になっている。
   取りうる対応は 2 つで、どちらかを決める必要がある。
   - 実装を仕様へ合わせる: 3 メソッドの型を `TwbFolder | None` に狭め、`_resolve_folder()` の
     文字列分岐（L552-559）を削除する。`tests/test_folder_argument.py` の
     `test_create_calculated_field_accepts_a_folder_name` は破棄になる。
   - 仕様を実装へ合わせる: `docs/model_api_spec.md` §6.3 の「文字列は受け付けない」と §13 の該当条件を、
     「`create_*` は名前でも受け付ける／`move_to_folder()` は `TwbFolder` のみ」と書き分ける。
     `tests/test_folder_argument.py` の意図（`folder=` の書き味を揃える）はこの方向を選んだ結果に見えるが、
     仕様側へ反映されていない。

2. **受け入れ条件 #29 の文言を一意にする（要目視）**
   `docs/model_api_spec.md` §13 の「XML 固有の `column` と `TwbWorksheet.columns` は維持されている」が、
   旧 dataclass の話なのか、接続型 `TwbWorksheet` にも `columns` を求めるのかを本文で確定させる。
   接続型には現在 `columns` プロパティが無い。

3. **新旧同等性の回帰テストを追加する（受け入れ条件 #41、要目視）**
   同じ入力ワークブックに対して旧 API と新 API で同じ編集を行い、出力 XML の一致を検証するテストが無い。
   少なくとも `rename_field` / `update_formula` / `create_calculated_field` / `move_field_to_folder` の
   4 つは新旧で突き合わせられる。

4. **README を新 API へ書き直す**
   ドリフトが「一部の記述が古い」水準を超えており、README は旧 API の説明書として丸ごと取り残されている。
   `docs/api_reference.md` が新 API を網羅しているため、README はそちらへ委譲する短い入口にするか、
   §11.1 に従って「トップレベルの `Twb*` は接続型モデル、`twbpatch.models` が旧 dataclass」という
   区別を明記したうえで全面改訂するかを決める。

5. **`CLAUDE.md` のテスト期待値を更新する**
   `158 passed` と書かれているが実測は `167 passed`。
