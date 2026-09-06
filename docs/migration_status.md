# 移行状況

> このファイルは `/spec-conformance` が生成する。**手で編集しない。**
> 生成日: 2026-09-07 / 正典: `docs/model_api_spec.md`

判定の対象は**新 API 側（`connected*.py` と新規追加コード）だけ**とする。
`models.py` の dataclass と `TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()` は
仕様 §11 が併存を認めているため、存在すること自体を違反として扱わない。

## テスト結果

```
uv run --no-sync pytest -q --basetemp=tmp/pytest
239 passed, 0 skipped
```

## §13 受け入れ条件の判定

| # | 条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 公開 API に `list_*()` が存在しない | PASS | `connected*.py` に `def list_` 0 件。旧 `TwbWorkbook.list_*()` は §11 により対象外 |
| 2 | 公開の単数取得 `get_<単数形>()` が存在しない | PASS | `connected*.py` の `get_*` 20 件すべて複数形 |
| 3 | 公開の `update_*()` が存在せず `update()` で更新できる | PASS | `connected*.py` に `def update_` 0 件 |
| 4 | 親モデルに `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | 同上 |
| 5 | すべての `get_*()` が `list` を返す | PASS | 戻り値注釈を全件確認。`TwbPane.get_categorical_colors()` のみ `dict` だが §4.1 の「引数を取る取得」で対象外 |
| 6 | 公開取得 API に `identifier` と `by` が無い | PASS | `connected*.py` に該当 0 件 |
| 7 | 検索条件がキーワード専用の `id=` / `name=` | PASS | 対象 18 メソッドすべて `(self, *, id=None, name=None)` |
| 8 | `id` と `name` の同時指定が `ValueError` | PASS | `twbpatch/connected.py:60` `_validate_get_args()`、対象 18 メソッドすべてが呼ぶ |
| 9 | `TwbWorksheet` に `create_field()` が無く `add_field()` で配置 | PASS | `twbpatch/connected_worksheet.py:1355` |
| 10 | シェルフが `rows` / `columns` / `pages` / `filters` を検証 | PASS | `twbpatch/connected_worksheet.py:77` `_SHELVES`、同 `:1372` |
| 11 | `TwbPane` が `mark_type` を更新し対応エンコーディングへ配置できる | PASS | `twbpatch/connected_worksheet.py:2748` `update()`、同 `:2511` `add_field()`、同 `:97` に `angle` を含む 8 種 |
| 12 | 複数Paneでは対象Paneの明示的な選択が必要になる | **FAIL** | `twbpatch/connected_worksheet.py:992` — `TwbWorksheet.add_reference_line()` が `panes[0]` へ暗黙に書き込む |
| 13 | 総計が `update(grand_totals=)` と同名プロパティの対称形 | PASS | `twbpatch/connected_worksheet.py:1017` プロパティ / 同 `:1812` `update()`、`tests/test_connected_worksheet_api.py:329,357` |
| 14 | 小計が `set_subtotal_visibility()` で付け外しでき `update()` に含まれない | PASS | `twbpatch/connected_worksheet.py:1272`、`tests/test_connected_worksheet_api.py:375,403` |
| 15 | `TwbWorksheetField.delete()` が配置だけを解除する | PASS | `twbpatch/connected_worksheet.py:2953` |
| 16 | `folder=` の規則が全メソッドで同じ | PASS | `twbpatch/connected.py:544` `_resolve_folder()` を同 `:600` / `:685` / `:1319` が共用。`create_yoy_calculated_fields()` は `create_calculated_fields()` へ委譲 |
| 17 | Dashboardの標準配置が `TwbDashboardContainer` によるタイル配置 | PASS | `twbpatch/connected_dashboard.py:1290` / `:1557` / `:1600` |
| 18 | タイル配置APIが `direction` / `order` / `weight` を取り `x` / `y` を受け付けない | PASS | `twbpatch/connected_dashboard.py:1557,1600` のシグネチャに座標引数なし |
| 19 | SDKがタイルの階層・順序・比率からXMLの座標とサイズを計算する | PASS | `tests/test_connected_dashboard_api.py:72` |
| 20 | 既存Dashboardの編集が対象コンテナ配下だけを変更する | 要目視 | 実装は `copy.deepcopy` + `_replace_if_changed` の差分適用だが、兄弟コンテナが不変であることを網羅検証するテストが無い |
| 21 | 未対応属性・対象外Zone・デバイスレイアウトが暗黙に削除・変更されない | 要目視 | デバイスレイアウトの非改変を直接確認するテストが無い |
| 22 | `TwbDashboardZone.delete()` が配置だけを削除しWorksheetを削除しない | PASS | `tests/test_connected_dashboard_api.py:299` |
| 23 | 浮動配置が `add_floating_worksheet()` という明示的な別API | PASS | `twbpatch/connected_dashboard.py:1331` |
| 24 | タイルZoneと浮動Zoneで無効な更新引数が `ValueError` | PASS | `twbpatch/connected_dashboard.py:2049-2052`、`tests/test_connected_dashboard_api.py:328,368` |
| 25 | 参照中リソースの `delete()` が `ResourceInUseError` になり XML と `is_dirty` が変化しない | PASS | `twbpatch/connected.py:820,1360,1449` / `connected_dashboard.py:1428,1896` / `connected_parameter.py:251` / `connected_worksheet.py:1893`、`tests/test_connected_delete_parameter_api.py` |
| 26 | `ResourceInUseError.references` から参照元の種類・ID・場所を確認できる | PASS | `twbpatch/errors.py:43`、`tests/test_connected_delete_parameter_api.py:73` |
| 27 | 連鎖削除が公開APIに存在しない | PASS | `twbpatch/` に `cascade` 0 件 |
| 28 | `TwbColumn` と公開 API の `column` が `TwbField` / `field` へ移行している | PASS | 新 API は `TwbField` のみ。トップレベルの `TwbColumn` は旧 dataclass（§11） |
| 29 | XML 固有の `column` と `TwbWorksheet.columns` が維持されている | PASS | `twbpatch/models.py:262` `columns: list[str]`（列シェルフ） |
| 30 | 公開 `id` が `@name`、公開 `name` が原則 `@caption`。Worksheetは両方 `@name` | PASS | `twbpatch/connected.py:40-57` `get_xml_id()` / `get_display_name()` |
| 31 | `@caption` が無い場合、公開 `name` が `@name` 由来の既定表示名になる | PASS | `twbpatch/connected.py:50-57`、`tests/test_connected_api.py:105` |
| 32 | 公開モデルと JSON 出力に `caption` が存在しない | PASS | `connected*.py` に `def caption` 0 件。`export_json()` 実測で `"caption"` キーなし、`"columns"` は `"fields"` へ正規化（`twbpatch/serialization.py:20-26`） |
| 33 | XML 内の参照と計算式保存が表示名ではなく `id` を使用している | PASS | `twbpatch/field_ref.py` / `twbpatch/calculation.py` で `name` から `id` へ変換 |
| 34 | 参照が解決できない・複数候補の場合に暗黙選択しない | PASS | `twbpatch/field_input.py:74,87,104` `AmbiguousCaptionError` |
| 35 | 接続型モデルが更新後のメモリ上 XML を再取得なしで参照できる | PASS | `tests/test_connected_api.py:105` |
| 36 | CRUD 操作だけではファイルが変更されない | PASS | `tests/test_connected_api.py:349` |
| 37 | `save()` の成功時だけファイルへ反映される | PASS | 同上、`tests/test_connected_final_api.py:243` |
| 38 | `reload()` が未保存変更を破棄し既存の接続型モデルを無効化する | PASS | `tests/test_connected_api.py:366` |
| 39 | 削除・無効化されたモデルの操作が `DetachedModelError` になる | PASS | `twbpatch/connected.py:221` ほか、`tests/test_connected_api.py:376` |
| 40 | 非公開コンテキストが JSON 出力へ含まれない | PASS | `export_json()` 実測で `_context` / `_id` なし |
| 41 | 既存の対応機能について旧 API と同等の XML 編集結果を得られる | 要目視 | 新旧の出力 XML を突き合わせる比較テストが無い |

## §13 以外で見つかった仕様本文との差分

| 箇所 | 仕様 | 実装 |
|---|---|---|
| `twbpatch/connected.py:659` `TwbDatasource.create_calculated_fields(calculations, ...)` | §5.1「`create_*()` の引数はすべてキーワード専用とする」 | 第 1 引数 `calculations` が位置引数 |
| `twbpatch/connected.py:367` `TwbDatasource.set_filter(field)` | §5.4a「引数はキーワード専用とする」 | `field` が位置引数 |
| `twbpatch/connected_worksheet.py:951` `TwbWorksheet.add_reference_line(field, ...)` | §5.4a、および §6.6 の公開 API 一覧に記載が無い | `field` が位置引数。メソッド自体が仕様未記載 |
| `twbpatch/connected_worksheet.py:1313` `set_axis_visibility(field, *, visible)` | §5.4a | `field` が位置引数。`set_subtotal_visibility(*, field=)` と不揃い |
| `twbpatch/connected_dashboard.py:1641` `TwbDashboardContainer.add_filter(field, ...)` | §5.4a | `field` が位置引数 |
| `twbpatch/connected_worksheet.py:1778` `add_sort(*, field, by, ...)` | §13「公開取得 API に `by` が存在しない」 | 取得 API ではないため違反ではないが、廃止した検索用 `by=` と字面が衝突する |
| `twbpatch/connected_worksheet.py:1955` `TwbReferenceLine.axis_caption` / `value_caption` | §3.2「公開モデルに `caption` プロパティは設けない」 | 投影モデルに `*_caption` が残っている |
| `twbpatch/config_apply.py:102` `_resolve_folder()` | §6.3「文字列で渡したフォルダが無ければ `NotFoundError`。暗黙に作らない」 | 無ければ `create_folder()` する別実装。API 方式の分類処理なので意図的な可能性がある |

## README ドリフト

`README.md`（566 行）は**旧 API だけを説明しており、接続型モデル（新 API）の記載が無い**。

### 実装にあるが README に無い公開シンボル

`TwbField` / `TwbPane` / `TwbDashboardContainer` / `DetachedModelError` /
`ResourceInUseError` / `ResourceReference` / `AmbiguousFormulaReferenceError` / `write_dicts_csv`

### 実装にあるが README に無い公開メソッド

- 取得: `get_datasources()` / `get_parameters()` / `get_worksheets()` / `get_dashboards()` /
  `get_fields()` / `get_folders()` / `get_panes()` / `get_zones()` / `get_containers()` ほか
- 作成: `create_worksheet()` / `create_parameter()` / `create_dashboard()` /
  `create_folder()` / `create_calculated_field()`（モデル側） / `create_container()` / `create_action()`
- 更新・削除: 各モデルの `update()` / `delete()` / `move_to_folder()` / `remove_from_folder()`
- 配置: `add_field()` / `add_worksheet()` / `add_filter()` / `add_text()` /
  `add_image()` / `add_spacer()` / `add_floating_worksheet()` / `add_sort()`
- API 方式: `draw_sheet()` / `draw_bar()` / `draw_yoy()` / `draw_card()` / `draw_quadrant()` /
  `draw_crosstab()` / `draw_colored_yoy_sheet()` / `set_filter()` / `set_default_font()` /
  `apply_field_config()` / `build_report()`
- 状態: `is_dirty` / `reload()` / `get_unsupported_features()`

### 仕様と矛盾する記述

| 箇所 | 内容 |
|---|---|
| README:93-103「検索方法 `by`」節 | 仕様 §13 が新 API から排した `by="auto"` / `"caption"` / `"name"` を、現行の検索方法として説明している |
| README:19-23, 118-131, 164-180 のコード例 | `datasource.caption` / `datasource.columns` / `worksheet.caption` / `field.caption` を使う。旧 dataclass では正しいが、`from twbpatch import TwbDatasource` は接続型モデルを返す（§11.1）ため、同名の別クラスと取り違える |
| README:205-525「返却モデルの変数」 | `TwbDatasource` / `TwbWorksheet` / `TwbDashboard` など 8 クラスについて旧 dataclass のフィールドだけを表にしている。トップレベルで公開されるのは接続型モデル（§11.1）で、`caption` も `columns` も持たない |
| README:276「`TwbColumn`」節 | 仕様 §3.1 の移行先 `TwbField` に触れていない |
| README 全体 | 新 API を網羅した `docs/api_reference.md` への導線が無い |

### 参考: `docs/api_reference.md` の古い記述

`README.md` の対象外だが、`docs/api_reference.md:26,32` が `set_mark_color()` /
`set_mark_size()` を公開 API として挙げている。実装には存在せず、§6.14 のとおり
`pane.update(mark_color=..., mark_size=...)` へ統合済み。

## 次にやるべきこと

1. **`TwbWorksheet.add_reference_line()` の Pane 指定**（§13 #12 の FAIL）
   `twbpatch/connected_worksheet.py:951` を `TwbPane.add_reference_line()` へ移すか、
   `worksheet.add_reference_line(*, field, pane)` として Pane を明示的に受け取る。
   複数 Pane のワークシートで `panes[0]`（同 `:992`）へ暗黙に書く現状は §6.7 に反する。
   あわせて §6.6 の公開 API 一覧へこのメソッドを追記する。

2. **README の全面改訂**
   「検索方法 `by`」節を「取得 API の `id=` / `name=`」へ差し替え、
   「返却モデルの変数」を接続型モデルの公開プロパティへ書き直す。
   旧 API を残す場合は「旧 API（`twbpatch.models` / `wb.list_*()`）」として節を分け、
   §11.1 のとおりトップレベルは接続型モデルであることを明示する。
   `docs/api_reference.md` への導線も張る。

3. **キーワード専用の不揃いを揃える**（§5.1 / §5.4a）
   `create_calculated_fields(calculations, ...)` を `create_calculated_fields(*, calculations, ...)` にする。
   `set_filter(field)` / `add_reference_line(field)` / `set_axis_visibility(field)` /
   `add_filter(field)` の第 1 引数をキーワード専用にする。
   `set_subtotal_visibility(*, field=)` が既にキーワード専用なので、そこへ揃える。

4. **要目視 3 件のテスト追加**（§13 #20 / #21 / #41）
   既存 Dashboard の編集で対象外の兄弟コンテナ・浮動 Zone・デバイスレイアウトが
   不変であることを確認するテストと、旧 API と新 API の出力 XML を突き合わせる
   比較テストを書く。

5. **`docs/api_reference.md` の `set_mark_color()` / `set_mark_size()` を削除**
   `pane.update()` のキーワード引数へ書き替える。
