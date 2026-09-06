# 移行状況

> このファイルは `/spec-conformance` が生成する。**手で編集しない。**
> 生成日: 2026-09-07 / 正典: `docs/model_api_spec.md`

## テスト結果

```
uv run --no-sync pytest -q --basetemp=tmp/pytest
239 passed in 3.19s
```

- **239 passed, 0 skipped**（exit code 0）。
- `CLAUDE.md` に書かれた期待値「172 passed」は古い。現状は 239。

## §13 受け入れ条件の判定

判定対象は `connected*.py`（新 API）と `TwbWorkbook` の新 API メソッド。
`models.py` の dataclass と `TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()` は
仕様 §11 により併存が認められているため、違反として数えない。

| # | 条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 公開 API に `list_*()` が存在しない | PASS | `grep "    def list_" twbpatch/connected*.py` が 0 件。`workbook.py` の `list_*` は §11 の旧 API |
| 2 | 公開の単数取得 `get_<単数形>()` が存在しない | PASS | `connected*.py` に単数 `get_` 無し。`workbook.py:217/555/639/732` の `get_dashboard` / `get_worksheet` / `get_datasource` / `get_column` は旧 API |
| 3 | 公開の `update_*()` が存在せず `update()` で更新できる | PASS | `grep "    def update_" twbpatch/connected*.py` が 0 件。各接続型モデルが `update()` を持つ |
| 4 | 親モデルに `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | 同上。削除は `TwbField.delete()` など個体側のみ |
| 5 | すべての `get_*()` が `list` を返す | PASS | 接続型の `get_*` 20 件の戻り値注釈がすべて `list[...]`（AST 検査）。唯一の例外 `TwbPane.get_categorical_colors()`（`twbpatch/connected_worksheet.py:2576`）は引数を取る属性取得で、§4.1 が明示的に除外している |
| 6 | 公開取得 API に `identifier` と `by` が無い | PASS | `grep "by: str\|identifier" twbpatch/connected*.py` が 0 件 |
| 7 | 検索条件がキーワード専用の `id=` / `name=` に統一 | PASS | 接続型の `get_*` はすべて `*,` 以降に `id` / `name` のみ（AST 検査） |
| 8 | `id` と `name` の同時指定が `ValueError` | PASS | `twbpatch/connected.py:60` `_validate_get_args()`。`connected.py` 7 箇所 / `connected_worksheet.py` 7 箇所 / `connected_dashboard.py` 10 箇所 / `connected_parameter.py` 2 箇所で呼ばれる |
| 9 | `TwbWorksheet` に `create_field()` が無く `add_field()` で配置 | PASS | `twbpatch/connected_worksheet.py:1355` `add_field()`。`create_field` は存在しない |
| 10 | シェルフが `rows` / `columns` / `pages` / `filters` を検証 | PASS | `twbpatch/connected_worksheet.py:77` `_SHELVES` と `:1372` の `if shelf not in {*_SHELVES, "filters"}: raise ValueError` |
| 11 | `TwbPane` が `mark_type` 更新とエンコーディング配置をできる | PASS | `twbpatch/connected_worksheet.py:2748` `update(mark_type=)`、`:2511` `add_field(encoding=)`、`:2527` の `_ENCODINGS` 検証 |
| 12 | 複数 Pane では対象 Pane の明示選択が必要 | PASS | `TwbPane` の取得口は `TwbWorksheet.get_panes()`（`twbpatch/connected_worksheet.py:917`）だけ。先頭 Pane へ暗黙配置する公開 API は無い |
| 13 | 総計が `update(grand_totals=)` と同名プロパティの対称形 | PASS | プロパティ `twbpatch/connected_worksheet.py:1016`、`update()` 引数 `:1820`、`GrandTotals` TypedDict `:55` |
| 14 | 小計が `set_subtotal_visibility()` で付け外しでき `update()` に含まれない | PASS | `twbpatch/connected_worksheet.py:1272`。`update()` の引数一覧に小計は無い |
| 15 | `TwbWorksheetField.delete()` が配置だけを解除する | PASS | `twbpatch/connected_worksheet.py:2953`。シェルフ参照または encoding 要素のみ削除し、datasource の `<column>` には触れない |
| 16 | フォルダ指定が文字列ではなく接続済み `TwbFolder` | **FAIL** | `twbpatch/connected.py:544` `_resolve_folder(folder: "str \| TwbFolder \| None")` が文字列を受け付ける。`tests/test_folder_argument.py:38` が意図的にその挙動を固定している。`field.move_to_folder()`（`connected.py:1311`）だけは `TypeError` で文字列を拒否する |
| 17 | Dashboard の標準配置が `TwbDashboardContainer` のタイル配置 | PASS | `twbpatch/connected_dashboard.py:1290` `create_container()`、既存時は `:1305` で `ValueError` |
| 18 | タイル配置 API が `direction` / `order` / `weight` を取り `x` / `y` を取らない | PASS | `twbpatch/connected_dashboard.py:1557` `create_container()` と `:1600` `add_worksheet()` に `x` / `y` / `width` / `height` が無い |
| 19 | SDK がタイルの階層・順序・比率から座標とサイズを計算する | PASS | `twbpatch/connected_dashboard.py:445` `_layout_container()` が `direction`・`order`・`weight`・`fixed_size`・`distribute-evenly` から `x/y/w/h` を算出、`:686` で 100000 正規化座標へ変換 |
| 20 | 既存 Dashboard の編集が全体を再構築せず対象コンテナ配下だけを変更する | **要目視** | `copy.deepcopy` + `_replace_if_changed()` の部分置換で書かれているが、「変更を対象親コンテナ配下に限定する」ことを機械的に確認できない |
| 21 | 未対応属性・対象外 Zone・デバイスレイアウトが暗黙に削除・変更されない | **要目視** | 保持を保証する検査コードもテストも無い。実装の形から推測はできるが根拠として不十分 |
| 22 | `TwbDashboardZone.delete()` が配置だけを削除する | PASS | `twbpatch/connected_dashboard.py:2128`。zone 要素だけを削除し `<worksheet>` 定義には触れない |
| 23 | 浮動配置が `add_floating_worksheet()` という別 API | PASS | `twbpatch/connected_dashboard.py:1331` |
| 24 | タイル / 浮動 Zone で無効な更新引数が `ValueError` | PASS | `twbpatch/connected_dashboard.py:2050-2053`。tiled へ `x/y/width/height` → `ValueError`、floating へ `order/weight` → `ValueError` |
| 25 | 参照中リソースの `delete()` が `ResourceInUseError` になり XML と `is_dirty` が変わらない | PASS | `connected.py:820/1353/1442`、`connected_worksheet.py:1893`、`connected_dashboard.py:1428/1896`、`connected_parameter.py:251` がいずれも XML 変更前に送出。`tests/test_connected_final_api.py:53,117` |
| 26 | `ResourceInUseError.references` から種類・ID・場所が分かる | PASS | `twbpatch/errors.py:36` `ResourceReference(resource_type, resource_id, location)`、`:43` `ResourceInUseError` |
| 27 | 連鎖削除が公開 API に存在しない | PASS | `grep -rn "cascade" twbpatch/` が 0 件 |
| 28 | `TwbColumn` と公開 `column` が `TwbField` / `field` へ移行 | PASS | 新 API は `TwbField` / `get_fields()` / `add_field()` のみ。`TwbColumn` は §11.1 により `models.py` の旧 dataclass として残置 |
| 29 | XML 固有の `column` と `TwbWorksheet.columns` は維持 | PASS | `twbpatch/connected_worksheet.py:77` の `_SHELVES` が `"columns" -> "cols"`、`TwbWorksheetField.shelf` が `"columns"` を返す |
| 30 | 公開 `id` が `@name`、公開 `name` が原則 `@caption`。Worksheet は両方 `@name` | PASS | `connected_worksheet.py:883/888` が Worksheet の `id` / `name` に同じ値を返す。`connected.py:1067/1072` が Field で両者を分離 |
| 31 | `@caption` が無い場合の公開 `name` が `@name` 由来の既定表示名 | PASS | `twbpatch/connected.py:52` の `if caption:` を持つ共通の表示名解決を全モデルが通る |
| 32 | 公開モデルと JSON 出力に `caption` が存在しない | **要目視** | `grep "def caption" twbpatch/connected*.py` は 0 件、`twbpatch/serialization.py:20-22` が `caption` → `name`、`*_caption` → `*_name` へ正規化するので JSON には出ない。ただし公開モデル側に `TwbReferenceLine.axis_caption` / `value_caption`（`connected_worksheet.py:1971/1983`）が残り、JSON 出力名（`axis_name` / `value_name`）と食い違う |
| 33 | XML 内の参照と計算式保存が表示名ではなく `id` を使用 | PASS | `TwbWorksheetField.field_id`（`connected_worksheet.py:2818`）、`move_column_to_folder_el(..., by="name")` が XML `@name` で解決（`connected.py:1325`） |
| 34 | 公開 `name` から一意に解決できない場合に暗黙選択しない | PASS | `AmbiguousCaptionError` を `errors.py` / `__init__.py` で公開し、`twbpatch/field_input.py` の解決が一意でないとき送出 |
| 35 | 接続型モデルが更新後のメモリ上 XML を再取得なしで参照できる | PASS | 全公開プロパティが `_resolve_element()` 経由で都度読み、要素をキャッシュしない。`tests/test_connected_api.py` |
| 36 | CRUD 操作だけではファイルが変更されない | PASS | ファイル書き込みは `twbpatch/workbook.py:143` `save()` だけ。`connected*.py` に書き込みは無い |
| 37 | `save()` の成功時だけファイルへ反映される | PASS | 同上。`tests/test_connected_final_api.py:243` `test_connected_edits_round_trip_through_save_and_reopen` |
| 38 | `reload()` が未保存変更を破棄し既存モデルを無効化する | PASS | `twbpatch/workbook.py:91` `reload()`、`tests/test_is_dirty.py` |
| 39 | 削除・無効化されたモデルの操作が `DetachedModelError` | PASS | `connected.py` に 8 箇所、`connected_worksheet.py` / `connected_dashboard.py` / `connected_parameter.py` にも実装。`_detach()` 後の再利用で送出 |
| 40 | 非公開コンテキストが JSON 出力へ含まれない | PASS | `twbpatch/serialization.py` が `_serialize_placement()` などで公開値を明示的に組み立てる。`tests/test_connected_final_api.py:161` |
| 41 | 既存の対応機能について旧 API と同等の XML 編集結果を得られる | **要目視** | 新旧の XML 出力を突き合わせる比較テストが無い。個別の新 API テストはあるが同等性の証拠にはならない |

**集計: PASS 36 / FAIL 1 / 要目視 4**

## 仕様書自身の食い違い

| 箇所 | 内容 |
|---|---|
| §6.6 / §12 | `worksheet.add_field(region, shelf="columns")` と `field` を位置引数で書いているが、§5.4a は「引数はキーワード専用とする。位置引数で受けない」。実装（`connected_worksheet.py:1355`）はキーワード専用で §5.4a に従っているので、§6.6 と §12 のサンプルが古い |
| §6.3 / §13 | §6.3 は `move_to_folder()` の `folder` について「文字列は受け付けない」と書き、§13 はそれを全フォルダ引数へ一般化している。実装は `move_to_folder()` だけ文字列を拒否し、`create_calculated_field()` などは受け付ける（判定 #16） |

## ドキュメントのドリフト

新 API のリファレンスは `docs/api_reference.md` にある。`README.md` は旧 API だけを説明している。

### `docs/api_reference.md`

`twbpatch/__init__.py` の `__all__` 35 シンボルはすべて記載されている。
未記載は**投影モデル 5 クラスのプロパティ**だけ。api_reference.md の §3 は
`TwbDashboardAction` までで終わり、次の 5 クラスに節が無い。

| クラス | 未記載のプロパティ |
|---|---|
| `TwbRelation` | `attrs` / `clauses` / `connection` / `join` / `logical_table` / `logical_table_id` / `get_children()` |
| `TwbRelationship` | `attrs` / `expression` / `left_object` / `left_object_id` / `right_object` / `right_object_id` |
| `TwbReferenceLine` | `attrs` / `axis_caption` / `axis_column` / `axis_role` / `tooltip_type` / `value_caption` / `value_column` / `value_role` |
| `TwbWorksheetFilter` | `attrs` / `apply_scope` / `apply_scope_label` / `enumeration` / `filter_class` / `filter_group` / `functions` / `selection_type` / `value_scope` / `value_scope_label` |
| `TwbFilterControl` | `apply_scope` / `apply_scope_label` / `enumeration` / `filter_class` / `selection_type` / `show_caption` / `value_scope` / `value_scope_label` |

### `README.md`（566 行）

README に書かれていて**実装に存在しないシンボル・引数は 0 件**。
「返却モデルの変数」（L205-525）の属性表は `models.py` の旧 dataclass と完全に一致する。
ドリフトは一方向で、**新 API がまるごと未記載**という形。

`__all__` のうち README に一度も現れないシンボル:
`write_dicts_csv` / `TwbField` / `TwbPane` / `TwbDashboardContainer` /
`AmbiguousFormulaReferenceError` / `DetachedModelError` / `ResourceInUseError` / `ResourceReference`

未記載の公開メソッド（分類別）:

| 分類 | 未記載のもの |
|---|---|
| 取得（新） | `get_datasources()` / `get_dashboards()` / `get_parameters()` / `TwbDatasource.get_fields()` / `get_folders()` / `get_relations()` / `get_relationships()` / `TwbWorksheet.get_panes()` / `get_reference_lines()` / `get_filters()` / `TwbDashboard.get_containers()` / `get_zones()` / `get_actions()` / `get_filter_controls()` / `TwbFolder.get_fields()` / `TwbPane.get_fields()` |
| 作成 | `create_worksheet()` / `create_dashboard()` / `create_parameter()` / `create_folder()` / `create_calculated_fields()` / `create_yoy_calculated_fields()` / `create_container()` / `create_action()` |
| 更新・削除 | 全モデルの `update()` / `delete()` / `move_to_folder()` / `remove_from_folder()` |
| 配置 | `add_field()` / `add_filter()` / `add_sort()` / `add_reference_line()` / `add_worksheet()` / `add_text()` / `add_image()` / `add_spacer()` / `add_floating_worksheet()` |
| API 方式（§6.14） | `draw_sheet()` / `draw_bar()` / `draw_yoy()` / `draw_card()` / `draw_quadrant()` / `draw_crosstab()` / `draw_colored_yoy_sheet()` / `set_filter()` / `set_default_font()` / `apply_field_config()` / `build_report()` |
| 書式・表示 | `set_customized_label()` / `set_axis_visibility()` / `set_categorical_colors()` / `set_continuous_colors()` / `set_subtotal_visibility()` / `grand_totals` / `table_style` / `title_style` |
| 状態 | `is_dirty` / `reload()` / `save(validate=, overwrite=)` |

仕様と矛盾する記述:

| 箇所 | 内容 |
|---|---|
| L93-103「検索方法 `by`」 | `by="auto"` / `"caption"` / `"name"` を主要な検索方法として説明する。§4.2 は `by` を廃し `id=` / `name=` に統一する。旧 API の説明であることが書かれていない |
| L105-133「データソース・カラム・パラメータ取得」 | 表が `list_*()` / `get_<単数形>()` だけで構成され、新 API への対応が無い |
| L20-24 の冒頭サンプル | 最初の例が `wb.list_datasources()` と `datasource.columns`。`columns` は §7 の廃止対象で、新 API は `get_fields()` |
| 本文の `caption` 出力例 | `datasource.caption` / `column.caption` / `parameter.caption` / `dashboard.caption` / `field.caption` が並ぶ。旧 dataclass の属性としては実在するが、§3.2 が公開モデルに `caption` を設けないと定めており、どちらの層の話か区別が付かない |
| L205「返却モデルの変数」 | `from twbpatch import TwbWorksheet` が接続型モデルを指すこと（§11.1）に触れず、同名別クラスの説明が無い |
| L276「`TwbColumn`」 | 新名称 `TwbField` への言及が無い（§3.1） |
| L527「主な例外」 | 6 件しか載せず、`AmbiguousFormulaReferenceError` / `DetachedModelError` / `ResourceInUseError` / `ResourceReference` が抜けている |
| 全体 | `docs/api_reference.md` へのリンクが無い。新 API を探す導線が README に存在しない |

## 次にやるべきこと

1. **フォルダ引数の扱いを決める（判定 #16、唯一の FAIL）。**
   実装は `_resolve_folder()`（`twbpatch/connected.py:544`）で文字列を受ける方向へ統一済みで、
   `tests/test_folder_argument.py` の 5 テストがそれを固定している。取りうる道は 2 つ。
   - (a) `docs/model_api_spec.md` §6.3 と §13 を「`folder=` は `TwbFolder` または
     同一 Datasource 内のフォルダ名文字列を受ける。`move_to_folder()` は `TwbFolder` のみ」
     へ書き換える（実装追認、テスト変更なし）。
   - (b) `_resolve_folder()` の `str` 分岐を落とし、`create_calculated_field()` /
     `create_calculated_fields()` / `apply_field_config()` の呼び出し側を `TwbFolder` へ改める
     （`tests/test_folder_argument.py` が要修正）。

2. **README を新 API へ書き直す。** 最小でも冒頭に `docs/api_reference.md` へのリンクと、
   §11.1 の「同名クラスは接続型モデルを公開する」の 1 段落を足す。
   本格対応では「クラス方式」（`get_*` / `create_*` / `update()` / `delete()`）と
   「API 方式」（`draw_*` / `set_*` / `apply_config()`）の 2 章立てにし、
   現在の `list_*` / `by` の表は「移行期の旧 API」節へ落として §11 の対応表を引く。
   「主な例外」の表へ 4 例外を追加する。

3. **`docs/api_reference.md` へ投影モデル 5 クラスの節を足す。**
   `TwbRelation` / `TwbRelationship` / `TwbReferenceLine` / `TwbWorksheetFilter` /
   `TwbFilterControl`。プロパティ表は README L240-506 の内容がそのまま使える。

4. **判定 #20・#21 を裏付けるテストを足す。**
   浮動 Zone・デバイスレイアウト・SDK が解釈しない属性を持つ Dashboard を `tmp_path` に組み、
   `container.add_worksheet()` の前後で対象外要素の XML が完全一致することを確認する。

5. **判定 #41 の同等性テストを足す。**
   `rename_field()` / `update_formula()` / `move_field_to_folder()` / `create_calculated_field()`
   の 4 つを旧 API と新 API で別々の Workbook へ適用し、`ET.tostring()` の一致を確認する。

6. **判定 #32 の `axis_caption` / `value_caption` を決める。**
   `TwbReferenceLine`（`twbpatch/connected_worksheet.py:1971/1983`）は投影モデルだが
   公開プロパティ名に `caption` を含み、`serialization.py:22` が出力時に
   `axis_name` / `value_name` へ改名するのと食い違う。モデル側を揃えるか、
   §3.2 に「`*_caption` は XML 由来の投影値として例外とする」と書き足すか。

7. **`CLAUDE.md` のテスト期待値を 172 から 239 へ直す。**
