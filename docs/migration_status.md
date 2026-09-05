# 移行ステータス

> **このファイルは `/spec-conformance` が生成する。手で編集しない。**
> 生成日: 2026-09-05 ／ 正典: `docs/model_api_spec.md`

判定の対象は **新 API 側（`connected*.py` と新規追加コード）の逸脱だけ**。
`models.py` の dataclass と `TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()` の併存は
仕様 §11 により違反として扱わない（表では「移行中」と表記する）。

## テスト結果

```
uv run --no-sync pytest -q --basetemp=tmp/pytest
126 passed
```

`--basetemp` は必須。省略すると `tmp_path` fixture が `PermissionError` になる（環境要因）。

## §13 受け入れ条件の判定

| # | 条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 公開 API に `list_*()` が存在しない | PASS（新API）／移行中 | `grep "    def list_" twbpatch/connected*.py` → 0 件。旧 `TwbWorkbook.list_*()` 15 本は §11 で併存 |
| 2 | 公開の単数取得 `get_<単数形>()` が存在しない | PASS（新API）／移行中 | `connected*.py` に該当なし。`workbook.py:200,538,609,702` の `get_dashboard` / `get_worksheet` / `get_datasource` / `get_column` は旧 API |
| 3 | 公開の `update_*()` が存在しない | PASS（新API）／移行中 | `grep "    def update_" twbpatch/connected*.py` → 0 件。`workbook.py:690,717,735` は旧 API |
| 4 | 親モデルに `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | `connected*.py` の AST 走査で該当メソッドなし |
| 5 | すべての `get_*()` が `list` を返す | PASS | id/name 付き取得 18 メソッドすべて戻り値注釈が `list[...]`。`TwbRelation.get_children()` も `list`。`TwbPane.get_categorical_colors()` は §4.1 の適用除外（引数を取る取得） |
| 6 | 公開取得 API に `identifier` / `by` が無い | PASS | `grep "by: str\|identifier" twbpatch/connected*.py` → 0 件。`TwbWorksheet.add_sort(field, *, by: TwbField)` は取得 API ではない |
| 7 | 検索条件がキーワード専用 `id=` / `name=` | PASS | 18 メソッドすべて `*` の後ろに `id` / `name` を宣言 |
| 8 | `id` と `name` の同時指定で `ValueError` | PASS | `connected.py:60 _validate_get_args`。18/18 の取得メソッドが呼び出し済み（AST 走査）。実行確認済み |
| 9 | `TwbWorksheet` に `create_field()` が無く `add_field()` で配置 | PASS | `connected_worksheet.py:1227 add_field`。`create_field` は未定義 |
| 10 | シェルフが `rows` / `columns` / `pages` / `filters` を検証 | PASS | `connected_worksheet.py:46 _SHELVES`、`:1227` で `ValueError`。実行確認済み |
| 11 | `TwbPane` が `mark_type` 更新とエンコーディング配置に対応 | PASS | `connected_worksheet.py:2585`（`_MARK_TYPES` 検証）、`:2358`（`_ENCODINGS` 検証）。実行確認済み |
| 12 | 複数 Pane では対象 Pane の明示選択が必要 | PASS | 配置 API は `TwbPane` のメソッドのみ。暗黙に先頭 Pane を選ぶ公開 API なし |
| 13 | `TwbWorksheetField.delete()` が配置だけ解除 | PASS | 実行確認: 配置削除後も `datasource.get_fields(id="[Sales]")` が 1 件 |
| 14 | フォルダ指定が文字列でなく `TwbFolder` | **FAIL** | `TwbField.move_to_folder()` は `TypeError` で拒否（正）。一方 `connected.py` の `create_calculated_field(folder=)` は実行時型検査が無く `AttributeError: 'str' object has no attribute '_ensure_attached'`。`create_calculated_fields()` / `create_yoy_calculated_fields()` は注釈が `str \| TwbFolder \| None` で文字列を受理する |
| 15 | Dashboard の標準配置がタイルコンテナ | PASS | `TwbDashboard.create_container()` / `TwbDashboardContainer.add_worksheet()`。ルート 2 個目は `ValueError`（実行確認） |
| 16 | タイル配置 API が `direction` / `order` / `weight` を取り `x` / `y` を取らない | PASS | `create_container()` / `add_worksheet()` のシグネチャに座標引数なし |
| 17 | SDK が階層・順序・比率から座標とサイズを計算 | PASS | 実測: 1200×800 の横コンテナに weight 2:1 → zone が `x=0,w=800` と `x=800,w=400` |
| 18 | 既存 Dashboard の編集が対象コンテナ配下だけを変更 | 要目視 | `tests/sample_minimal.twb` に既存 Dashboard が無く実測不能。`TwbDashboard.build_report()`（`connected_dashboard.py:773`）は仕様外の一括構築 API のため非破壊性の確認が必要 |
| 19 | 未対応属性・対象外 Zone・デバイスレイアウトが暗黙に変更されない | 要目視 | 同上。デバイスレイアウトを含む実ワークブックでの確認が必要 |
| 20 | `TwbDashboardZone.delete()` が配置だけ削除 | PASS | 実行確認: zone 削除後も対象 Worksheet が残存 |
| 21 | 浮動配置が `add_floating_worksheet()` として分離 | PASS | `connected_dashboard.py` `TwbDashboard.add_floating_worksheet()` |
| 22 | タイル / 浮動 Zone への無効な更新引数が `ValueError` | PASS | `connected_dashboard.py` `TwbDashboardZone.update()` の `placement_mode` 分岐。実行確認済み |
| 23 | 参照中リソースの `delete()` が `ResourceInUseError`、XML と `is_dirty` が不変 | PASS | 送出 7 箇所（Datasource / Field / Folder / Dashboard / Container / Parameter / Worksheet）。実測で XML 文字列と `is_dirty` の両方が不変 |
| 24 | `ResourceInUseError.references` から種類・ID・場所を確認できる | PASS | `errors.py` `ResourceReference(resource_type, resource_id, location)`。実測で `('Field', '[Calculation_...]', '/workbook/datasources/datasource/column[3]/calculation/@formula')` |
| 25 | 連鎖削除が公開 API に存在しない | PASS | `cascade` 引数を持つ公開メソッドなし |
| 26 | `TwbColumn` と公開 `column` が `TwbField` / `field` へ移行 | PASS（新API）／移行中 | `connected*.py` は `TwbField` / `field` に統一済み。`__init__.py` の `__all__` に残る `TwbColumn` と `workbook.list_columns()` 等は §11 で併存 |
| 27 | XML 固有の `column` と `TwbWorksheet.columns` が維持 | PASS | `_SHELVES` のキー `"columns"` と XML 属性 `column=` を維持。列シェルフは接続型では `get_fields()` の `shelf == "columns"` で表現し、旧 dataclass 側は `models.py:262 columns` を保持 |
| 28 | 公開 `id` = XML `@name`、`name` = `@caption`（Worksheet は両方 `@name`） | PASS | `connected.py:50 get_display_name`、`connected_worksheet.py _worksheet_display_name`。実測で `('RENAMED','RENAMED')` |
| 29 | caption 不在時に `@name` 由来の既定表示名 | PASS | `get_display_name(..., strip_field_brackets=True)` が外側の角括弧だけ除去 |
| 30 | 公開モデルと JSON 出力に `caption` が無い | PASS（新API） | `grep "def caption" twbpatch/connected*.py` → 0 件。`export_json()` 実測で `caption` を含むキーは 0 件 |
| 31 | XML 内参照と計算式保存が `id` を使用 | PASS | `connected.py` の formula 保存が `name → id` 変換を通す。`references.py` / `field_ref.py` が ID 解決を担当 |
| 32 | 公開 `name` が解決不能・複数候補なら暗黙選択しない | PASS | `connected.py:527` で `AmbiguousCaptionError` |
| 33 | 接続型モデルが更新後の XML を再取得なしで参照 | PASS | 全公開プロパティが `_resolve_element()` 経由でアクセス時に XML から読む（`connected*.py`） |
| 34 | CRUD だけではファイルが変更されない | PASS | 実測: `field.update()` 後もファイルのバイト列が不変、`is_dirty=True` |
| 35 | `save()` 成功時だけファイルへ反映 | PASS | `workbook.py:141 save()` のみが書き込み経路 |
| 36 | `reload()` が未保存変更を破棄し既存モデルを無効化 | PASS | 実測: `reload()` 後の `datasource.name` が `DetachedModelError` |
| 37 | 削除・無効化モデルの操作が `DetachedModelError` | PASS | 送出 45 箇所（connected 4 ファイル）。実測: 削除済み Folder の `.name` が `DetachedModelError` |
| 38 | 非公開コンテキストが JSON 出力に含まれない | PASS | `export_json()` 実測で `"_..."` キーは 0 件。`serialization.py` が専用シリアライザ |
| 39 | 既存機能で旧 API と同等の XML 編集結果 | 要目視 | 新旧の出力を突き合わせる回帰テストが存在しない |

### 参照更新の実測（§3.2）

`worksheet.update(name=...)` は XML 内部 ID の変更であり、参照元を同時に更新する必要がある。

| 参照元 | 更新される | 根拠 |
|---|---|---|
| `/workbook/windows/window[@class='worksheet']/@name` | される | `connected_worksheet.py:193` |
| Dashboard Zone `@name` | される | `connected_worksheet.py:199` |
| `/workbook/actions/action` 配下の `@name` / `@worksheet` / `@sheet` | される | `connected_worksheet.py:205` |
| `/workbook/windows/window/viewpoints/viewpoint/@name` | **されない** | 実測: `S1` → `RENAMED` 改名後も `viewpoint[@name='S1']` が残存 |

### §4.1 の読み書き対称性（§13 に明示条項は無いが仕様逸脱）

| 対象 | 状況 | 判定 |
|---|---|---|
| `TwbWorksheet.title` / `set_title()` | 引数を取らない自己所有値だが `update()` に `title=` が無い | **FAIL**（§4.1） |
| `TwbPane.mark_opacity` / `set_mark_opacity()` | 同上。`TwbPane.update()` は `mark_type` のみ | **FAIL**（§4.1） |
| `TwbPane.set_mark_size()` / `set_mark_color()` / `set_mark_sizing()` / `set_label_style()` | 自己所有のスカラー値だが `update()` のキーワードでも同名プロパティでもない | **FAIL**（§3.3 / §4.1） |
| `TwbPane.set_customized_label()` / `set_continuous_colors()` / `TwbWorksheet.set_axis_visibility()` / `TwbDatasource.set_filter()` | 他モデルを引数に取る | PASS（§3.3 が動詞名を許容） |
| `TwbPane.get_categorical_colors()` / `set_categorical_colors()` | 引数を取る取得 | PASS（§4.1 が明示的に許容） |
| `TwbWorksheet.table_style` / `title_style`、`TwbDashboardContainer.style`、`TwbDashboardZone.style` | プロパティで読み `update()` の同名キーワードで書く | PASS |

`TableStyle` / `TitleStyle` は `TypedDict(total=False)`、コンテナ / Zone の `style` は
`dict[str, str \| int \| None]` で、§3.3 の型付け規則に適合している。

### 仕様外の公開メソッド（仕様への追記か API 見直しの判断が必要）

`docs/model_api_spec.md` に記載が無い接続型モデルの公開メソッド 21 本。

- `TwbDatasource.set_filter()` / `apply_field_config()` / `create_calculated_fields()`（`connected.py:367, 493, 639`）
- `TwbRelation.get_children()`（`connected.py:899`）
- `TwbDashboard.build_report()`（`connected_dashboard.py:773`）
- `TwbDashboardContainer.add_filter()` / `add_text()` / `add_image()` / `add_spacer()`（`connected_dashboard.py:1340, 1452, 1475, 1489`）
- `TwbWorksheet.add_reference_line()` / `set_title()` / `set_axis_visibility()` / `add_filter()` / `add_filter_slice()` / `add_sort()`（`connected_worksheet.py:893, 1138, 1181, 1559, 1604, 1633`）
- `TwbPane.set_label_style()` / `set_mark_opacity()` / `set_mark_sizing()` / `set_mark_size()` / `set_mark_color()` / `set_continuous_colors()`（`connected_worksheet.py:2253, 2283, 2300, 2316, 2333, 2491`）

`TwbWorkbook` 側の仕様外公開メソッド: `set_default_font()`、`set_filter()`、`apply_field_config()`、
`draw_colored_yoy_sheet()` / `draw_yoy()` / `draw_bar()` / `draw_card()` / `draw_quadrant()` / `draw_crosstab()`
（§11.2 は `draw_*()` を正としつつ `draw_sheet()` しか列挙していない）。

未実装: `TwbDashboard.get_zones()` は §6.9 の `**layout_options` を受け取らない。

## README ドリフト

`README.md` は **全体が旧 API の説明のままで、新 API の記載が 1 箇所も無い。**

### 1. 実装にあるが README に無い公開シンボル

`__all__` にあって README に現れない: `TwbField`、`TwbPane`、`TwbDashboardContainer`、
`AmbiguousFormulaReferenceError`、`DetachedModelError`、`ResourceInUseError`、`ResourceReference`、
`write_dicts_csv`。

`TwbWorkbook` の公開メンバーで README に無いもの:
`is_dirty`、`reload`、`get_datasources`、`get_worksheets`、`get_dashboards`、`get_parameters`、
`create_worksheet`、`create_parameter`、`create_dashboard`、`apply_field_config`、`set_default_font`、
`set_filter`、`draw_sheet`、`draw_yoy`、`draw_bar`、`draw_card`、`draw_quadrant`、`draw_crosstab`、
`draw_colored_yoy_sheet`、および旧 API の `update_source`、`update_column`、`update_formula`、
`rename_field`、`reset_field_caption`、`move_field_to_folder`、`move_column_to_folder`、
`remove_field_from_folder`。

README が言及するメソッドで実装に存在しないものは無い。

### 2. README にあるが実装と矛盾する記述

| README | 問題 |
|---|---|
| L165-167「取得メソッドは dataclass のスナップショットを返します。返却オブジェクトの変数を書き換えても XML には反映されません」 | `get_*()` は接続型モデルを返し、`update()` はメモリ上 XML を直接変更する（仕様 §2.2）。旧 `list_*()` にしか当てはまらない |
| L169-486「返却モデルの変数」の全テーブル（`TwbDatasource`、`TwbFolder`、`TwbParameter`、`TwbDashboard`、`TwbDashboardZone`、`TwbWorksheet`、`TwbWorksheetField`、`TwbReferenceLine`、`TwbWorksheetFilter`、`TwbRelation`、`TwbRelationship`、`TwbDashboardAction`、`TwbFilterControl`） | これらの名前は `from twbpatch import ...` では **接続型モデル** に解決される（§11.1）。README が並べる `caption`、`columns`、`folders`、`relations`、`worksheets`、`zones`、`actions`、`items`、`children` は接続型モデルには存在しない |
| L53-63「検索方法 `by`」 | `by` は旧 API 専用。新 API の `id=` / `name=` と「同時指定は `ValueError`」（§4.2）が未記載 |
| L14-24 の基本例が `wb.list_datasources()` と `datasource.columns` | `.columns` は §7 で廃止された属性。新 API の入口は `wb.get_datasources()` → `datasource.get_fields()` |
| L88-93 の例が `datasource.caption`、`column.referenced_columns`、`parameter.caption` | 接続型モデルでは `name`、`referenced_fields`、`name` |
| L236-252 `TwbColumn.format` | 接続型 `TwbField` は複数形の `formats` |
| L487-499「主な例外」の表が 6 件のみ | `AmbiguousFormulaReferenceError`、`DetachedModelError`、`ResourceInUseError` が欠落 |
| L514-526「編集と保存の例」が `wb.create_calculated_field(datasource=..., caption=..., formula=...)` | 新 API は `datasource.create_calculated_field(name=..., formula=...)`。`caption=` という引数名は §3.2 が禁じる用語 |
| L146-157 に `unsupported_features()` と `get_unsupported_features()` が併記 | 仕様 §6.1 は `get_unsupported_features()` のみ。旧名の位置づけが読者に伝わらない |

## 次にやるべきこと

1. **`worksheet.update(name=...)` の参照更新漏れを塞ぐ**（§3.2 違反）。
   `twbpatch/connected_worksheet.py:188 _rename_worksheet_references()` は
   `window[@class='worksheet']`、`zone[@name]`、`actions` の 3 系統しか書き換えず、
   `/workbook/windows/window/viewpoints/viewpoint[@name]` が旧 ID のまま残る。
   実測: Worksheet `S1` を `RENAMED` へ改名後も `viewpoint[@name='S1']` が残存。
   同関数へ `viewpoint[@name=$old_id]` の書き換えループを追加する。

2. **フォルダ引数の型を `TwbFolder` に統一する**（§13 / §6.3、上表 #14）。
   - `twbpatch/connected.py` `TwbDatasource.create_calculated_field()`: `folder` の実行時型検査が無く、
     文字列を渡すと `AttributeError` になる。`move_to_folder()` と同じく `TypeError` を送出する。
   - 同 `create_calculated_fields()` と `create_yoy_calculated_fields()`: 注釈 `str | TwbFolder | None` から
     `str` を外す。ただし仕様 §6.2 の例が `folder="Measure"` と文字列を使っているため、
     **仕様側の例を `datasource.get_folders(name=...)[0]` 形へ直すか、この 2 メソッドを例外として
     仕様に明記するかを先に決める。**

3. **`update()` への読み書き対称性の回収**（§3.3 / §4.1）。
   - `TwbWorksheet.set_title()` → `TwbWorksheet.update(title=...)`
   - `TwbPane.set_mark_opacity()` / `set_mark_size()` / `set_mark_color()` / `set_mark_sizing()` /
     `set_label_style()` → `TwbPane.update(mark_opacity=..., mark_size=..., mark_color=..., ...)`、
     または §3.3 の「グループ名を引数名にする」規則に従い `TwbPane.update(mark_style={...})` へ集約。
     既存の `set_*` は §11 の移行規約に従い、新形の公開後に削除可否を判断する。

4. **`README.md` を新 API 基準で書き直す。** 最低限、次の 4 点。
   - 基本例を `wb.get_datasources()` → `datasource.get_fields()` → `field.update()` → `wb.save()` に差し替える。
   - 「返却モデルの変数」を接続型モデルの公開プロパティ表へ置き換え、旧 dataclass は
     `twbpatch.models` 経由である旨（§11.1）を明記する。
   - 「検索方法 `by`」を「絞り込み `id=` / `name=`（同時指定は `ValueError`）」へ置き換え、
     `by` は旧 API 専用と注記する。
   - 例外表へ `AmbiguousFormulaReferenceError` / `DetachedModelError` / `ResourceInUseError` を追加する。

5. **要目視 3 件の解消。**
   - #18 / #19: 既存 Dashboard（デバイスレイアウトと未対応属性を含むもの）を対象に、
     コンテナ 1 つの編集が兄弟 Zone・浮動 Zone・アクション・`device-layout` を保存することを確認する。
     とくに `TwbDashboard.build_report()` の非破壊性。
   - #39: 旧 API と新 API で同じ編集を行い XML 差分が無いことを確認する回帰テストを追加する。

6. **仕様外の公開メソッド 21 本 + `TwbWorkbook` 側 9 本の扱いを決める。**
   `docs/model_api_spec.md` §6 へ追記するか、公開 API から外すかを判断する。
   `docs/model_api_spec.md` が唯一の正典である以上、未記載のまま公開し続ける状態は解消する。
