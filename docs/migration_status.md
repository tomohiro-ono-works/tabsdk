# 移行状況

**このファイルは `/spec-conformance` が生成する。手で編集しない。**
生成日: 2026-09-13 / 正典: `docs/model_api_spec.md`

## テスト結果

```
397 passed, 0 skipped
```

`uv run --no-sync pytest -q --basetemp=tmp/pytest`（6.39s、exit 0）。

> 注: 同じコマンドを 1 回目に実行したときは
> `tests/test_export_html.py::test_export_html_table_columns_are_resizable` が
> `assert 5 == 6` で落ちた。実行中に別セッションが `tests/test_export_html.py` を
> 編集していたための競合で、再実行では解消している（作業ツリーに未コミットの
> 変更が 18 ファイルある状態での計測）。

## §13 受け入れ条件の判定

判定は `connected*.py` と新規追加コードだけを対象にする。`models.py` の dataclass と
`TwbWorkbook.list_*()` 4 件（`by=` 引数を含む）の併存は §11.3 により違反としない。

| 条件 | 判定 | 根拠 |
|---|---|---|
| 公開 API に `list_*()` が存在しない | PASS | `grep "    def list_" twbpatch/connected*.py` が 0 件。`workbook.py` に残る 4 件は §11.3 が明示的に残した旧 API |
| 公開の単数取得 `get_<単数形>()` が存在しない | PASS | 公開 `get_*` の戻り値注釈を全件確認。単数を返すのは `create_*` のみ |
| 公開の `update_*()` が存在しない | PASS | `grep "    def update_" twbpatch/connected*.py` が 0 件 |
| 親モデルに `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | 同上。削除は個体モデルの `delete()` のみ |
| すべての `get_*()` が `list` を返す | PASS | 23 個の公開 `get_*` の戻り値注釈がすべて `list[...]`。例外は `TwbPane.get_categorical_colors()` → `dict[str, str]` だが、引数を取る属性取得なので §4.1 で対象外 |
| 公開取得 API に `identifier` と `by` が無い | PASS | `connected*.py` に `by:` 引数なし。`by="name"` の出現は投影層関数への内部呼び出し。`workbook.py:194/208/233/588` の `by: str = "auto"` は旧 `list_*()` 4 件（§11.3） |
| 検索条件がキーワード専用の `id=` / `name=` | PASS | 全 `get_*` が `*, id=None, name=None`。`twbpatch/connected.py:76` の `_validate_get_args` を 27 か所で呼ぶ |
| `id` と `name` の同時指定で `ValueError` | PASS | `twbpatch/connected.py:76-78` |
| `TwbWorksheet.create_field()` が無く `add_field()` で配置 | PASS | `grep "def create_field"` が 0 件。`connected_worksheet.py:1378` |
| シェルフが rows / columns / pages / filters を検証 | PASS | `connected_worksheet.py:1395`（`_SHELVES` + `"filters"`、不正値は `ValueError`） |
| `TwbPane` が `mark_type` 更新とエンコーディング配置 | PASS | `connected_worksheet.py:2787`（`update`）、`2538`（`add_field`）、`tests/test_connected_worksheet_api.py:179` |
| 複数 Pane で `add_reference_line(pane=)` が必要 | PASS | `connected_worksheet.py:951-975`、`tests/test_reference_line_pane.py` |
| 総計が `update(grand_totals=)` とプロパティの対称形 | PASS | `connected_worksheet.py:1040`（プロパティ）/ `1843`（`update` 引数）、`tests/test_connected_worksheet_api.py:330` |
| 小計が `set_subtotal_visibility()` で `update()` に含まれない | PASS | `connected_worksheet.py:1295`。`update()` の引数に小計なし |
| `TwbWorksheetField.delete()` が配置だけを外す | PASS | `connected_worksheet.py:3013`、`tests/test_connected_worksheet_api.py:210` |
| `folder=` の規則が全メソッドで同じ | PASS | `create_folder_if_missing: bool = False` が 6 か所。解決は `TwbDatasource._resolve_folder()`（`connected.py:735`）へ集約、`move_to_folder` も `connected.py:1538` で同じ入口を使う。`tests/test_folder_argument.py` / `test_folder_if_missing.py` |
| Dashboard の標準配置がタイル（`TwbDashboardContainer`） | PASS | `connected_dashboard.py:1337`（`TwbDashboard.create_container`）、`1603`/`1646`（入れ子と配置） |
| タイル API が `direction` / `order` / `weight` を取り `x` / `y` を取らない | PASS | `connected_dashboard.py:1603-1612`、`1646-1655` に座標引数なし |
| SDK がタイルの階層・順序・比率から座標を計算 | PASS | `tests/test_connected_dashboard_api.py:72` |
| 既存 Dashboard の編集が対象コンテナ配下だけ | PASS | `tests/test_dashboard_edit_locality.py:88,98` |
| 未対応属性・対象外 Zone・デバイスレイアウトを暗黙に変えない | PASS | `tests/test_dashboard_edit_locality.py:108,121,132,149` |
| `TwbDashboardZone.delete()` が配置だけを削除 | PASS | `connected_dashboard.py:2285`、`tests/test_connected_dashboard_api.py:299` |
| 浮動配置が `add_floating_worksheet()` という別 API | PASS | `connected_dashboard.py:1378` |
| タイル / 浮動で無効な更新引数は `ValueError` | PASS | `connected_dashboard.py:2208-2211` |
| 参照中リソースの `delete()` が `ResourceInUseError`、XML と `is_dirty` が不変 | PASS | 7 か所で送出（`connected.py:1033,1581,1806` ほか）。`tests/test_connected_delete_parameter_api.py:67`、`test_connected_final_api.py:53,117` |
| `ResourceInUseError.references` から参照元を確認できる | PASS | `twbpatch/errors.py:43`、`tests/test_connected_dashboard_api.py:399` |
| 連鎖削除が公開 API に無い | PASS | `grep -rn "cascade" twbpatch/` が 0 件 |
| `TwbColumn` / `column` が `TwbField` / `field` へ移行 | PASS | `twbpatch/__init__.py` の `__all__` に `TwbColumn` なし。`TwbColumn` の参照は `models.py` / `column.py` / `calculation.py` の投影層内部のみ |
| XML 固有の `column` と `TwbWorksheet.columns` は維持 | PASS | `models.py:115` に `columns`。新 API 側の公開 `column` は `TwbFilterControl.column`（`connected_dashboard.py:2322`）だけで、XML の `@param` 内部参照を返す用途 |
| 公開 `id` = `@name`、公開 `name` = caption（Worksheet は両方 `@name`） | PASS | `tests/test_connected_api.py:148`、`test_connected_worksheet_api.py:229` |
| caption が無いとき `name` が `@name` 由来の既定名 | PASS | `tests/test_connected_api.py:148` |
| 公開モデルと JSON に `caption` が無い | PASS | `grep "    def caption" twbpatch/connected*.py` が 0 件。`serialization.py:40` で `caption` → `name` へ正規化。`tests/test_export_json_projection.py:46` |
| XML の参照と計算式が `id` を使う | PASS | `tests/test_connected_api.py:164` |
| 参照が一意に決まらないとき暗黙に選ばない | PASS | `AmbiguousCaptionError` / `AmbiguousFormulaReferenceError`。`tests/test_add_filter.py:160`、`test_field_argument.py:134` |
| 接続型モデルが更新後の XML を再取得なしで参照 | PASS | `tests/test_connected_api.py:148` |
| CRUD だけではファイルが変わらない | PASS | `tests/test_connected_api.py:392`、`test_apply_config.py:237` |
| `save()` 成功時だけファイルへ反映 | PASS | `tests/test_connected_final_api.py:252` |
| `reload()` が未保存変更を破棄しモデルを無効化 | PASS | `tests/test_connected_api.py:409` |
| 削除・無効化後の操作が `DetachedModelError` | PASS | `twbpatch/context.py` ほか 4 モジュール。`tests/test_connected_filter_api.py:114` |
| 非公開コンテキストが JSON へ出ない | PASS | `tests/test_connected_final_api.py:161` |
| 既存機能で旧 API と同等の XML 編集結果を得られる | 要目視 | 旧 API 25 件は削除済み（§11.3）で、同一入力を旧新で流して XML を突き合わせる比較テストが無い。`tests/test_smoke.py` が新 API 側の結果だけを固定している |

**FAIL は 0 件。`要目視` は 1 件。**

## README のドリフト

`twbpatch/__init__.py` の `__all__`（37 シンボル）はすべて `README.md` に記載がある。
実装にあって README に無い公開メンバは次のとおり。いずれも
`tests/test_zone_action_reads.py`（未コミット）で追加された読み取り系プロパティで、
README §3.10 / §3.11 / §3.7 の変数表が追いついていない。

| クラス | README に無い公開メンバ |
|---|---|
| `TwbDashboardZone`（README §3.10） | `x_raw` / `y_raw` / `width_raw` / `height_raw` / `to_px` / `dashboard_width_px` / `dashboard_height_px` / `sizing_mode` / `parent_id` / `depth` / `dashboard_id` / `attrs` / `type` / `mode` / `param` / `url` / `show_caption` / `is_fixed` / `is_scaled` |
| `TwbDashboardAction`（README §3.11） | `excluded_source_worksheet_ids` / `excluded_target_worksheet_ids` / `details` / `source_type` / `target_type` / `source_dashboard_id` / `target_dashboard_id` / `dashboard_id` / `command` / `activation` / `links` / `params` / `attrs` |
| `TwbWorksheetField`（README §3.7） | `worksheet_id` / `role` / `attrs` |

README にあって実装に無いシンボル・引数、および仕様と矛盾する記述（旧名称・廃止引数）は
検出されなかった。README §8 / §9 に出る `update_style()` / `set_mark_color()` などは
改名・削除の記録として書かれているもので、現行 API としては記載されていない。

## 次にやるべきこと

FAIL が無いため、仕様違反の修正は無い。次の 3 点が残っている。

1. **README §3.10 / §3.11 / §3.7 の変数表を更新する。**
   上表の公開メンバを追記する。`CLAUDE.md` の「実装を変えたら README も更新する」に該当する。

2. **`TwbWorkbook.list_dashboard_actions()` の削除を検討する（旧 API の残り 4 件）。**
   §11.3 はこれを残す理由を「`excluded_source_worksheets` /
   `excluded_target_worksheets` / `details` が新 API に無いから」としていたが、
   `TwbDashboardAction` に `excluded_source_worksheet_ids` /
   `excluded_target_worksheet_ids` / `details`（`connected_dashboard.py:761,766,795`）が
   実装され、穴が埋まっている。`docs/backlog.md` L-6 の「穴を埋めてから消す」が満たされた。
   `list_dashboard_zones()` は `x_raw` / `parent_id` / `depth` / `to_px` の穴は埋まったが、
   `include_device_layouts=` に相当する新 API がまだ無いので残す
   （`tests/test_dashboard_edit_locality.py:149` が `get_zones()` は
   デバイスレイアウトを返さないことを固定している）。
   `list_dashboard_fields()` の `max_filter_value_chars=` と
   `list_worksheet_fields()` の `values` / `mark_type` / `category` / `type` は未実装のまま。

3. **要目視 1 件: 旧 API との XML 同等性。**
   旧 API 25 件は削除済みで比較対象が無い。仕様 §13 最終行の条件を
   「削除前のコミットで生成した XML を固定データとして突き合わせる」形へ
   読み替えるか、条件自体を §11.3 完了に合わせて書き換えるかの判断が要る。
