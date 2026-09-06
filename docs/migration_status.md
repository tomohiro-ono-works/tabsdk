# 移行状況

> このファイルは `/spec-conformance` が生成する。**手で編集しない。**
> 生成日: 2026-09-07 / 正典: `docs/model_api_spec.md`

## テスト結果

```
uv run --no-sync pytest -q --basetemp=tmp/pytest
188 passed, 0 skipped
```

`CLAUDE.md` の記載（172 passed）より 16 件増えている。CLAUDE.md 側の更新が必要。

## §13 受け入れ条件の判定

判定対象は**新 API（`connected*.py` と新規追加コード）だけ**。`models.py` の dataclass と
`TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()` の併存は §11 により違反としない。

| # | 条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 公開 API に `list_*()` が存在しない | PASS | `grep "^    def list_" twbpatch/connected*.py` → 0 件 |
| 2 | 公開の単数取得 `get_<単数形>()` が存在しない | PASS | `connected*.py` に 0 件。旧 `TwbWorkbook.get_datasource/get_worksheet/get_dashboard/get_column` は §11 |
| 3 | 公開の `update_*()` が存在せず `update()` で更新できる | PASS | `grep "^    def update_" twbpatch/connected*.py` → 0 件 |
| 4 | 親モデルに `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | 同上 |
| 5 | すべての `get_*()` が `list` を返す | PASS | 全 20 メソッドの戻り値注釈が `list[...]`（署名検査） |
| 6 | 公開取得 API に `identifier` と `by` が存在しない | PASS | `connected*.py` の `by=` は旧ヘルパー関数への内部呼び出しのみ（`connected.py:640` ほか） |
| 7 | 検索条件がキーワード専用の `id=` / `name=` | PASS | 全取得メソッドが `(self, *, id=None, name=None)` |
| 8 | `id` と `name` の同時指定で `ValueError` | PASS | 実測。`ValueError: id and name cannot be specified together` |
| 9 | `TwbWorksheet.create_field()` が無く `add_field()` で配置できる | PASS | `hasattr(ws, "create_field") == False`、`add_field()` 実測 |
| 10 | シェルフが `rows`/`columns`/`pages`/`filters` を検証 | PASS | 4 値すべて成功、`shelf="bogus"` → `ValueError: unsupported shelf` |
| 11 | `TwbPane` が `mark_type` 更新とエンコーディング配置をできる | PASS | `mark_type="bar"` 成功、`"bogus"` → `ValueError`。`add_field(encoding="color")` 成功 |
| 12 | 複数 Pane では対象 Pane の明示選択が必要 | PASS | `TwbWorksheet.add_field()` に `encoding=` が無く、暗黙の先頭 Pane API が存在しない |
| 13 | 総計が `update(grand_totals=)` と同名プロパティの対称形 | PASS | `ws.grand_totals` → `{'row': None, 'column': None}`、update 後 `{'row': 'bottom', 'column': 'right'}` |
| 14 | 小計が `set_subtotal_visibility()` で、`update()` に含まれない | PASS | `TwbWorksheet.set_subtotal_visibility(*, field, visible)`。`update()` の署名に小計キーワードなし |
| 15 | `TwbWorksheetField.delete()` が配置だけ解除する | PASS | 削除後も `datasource.get_fields()` は 2 件のまま |
| 16 | フォルダ指定が文字列でなく接続済み `TwbFolder` | **FAIL** | `move_to_folder("KPI")` は `TypeError` で正。しかし `create_calculated_field(folder="KPI")` が文字列を受理する（下記「FAIL 詳細」） |
| 17 | Dashboard の標準配置が `TwbDashboardContainer` のタイル配置 | PASS | `create_container()` → `add_worksheet()`。2 回目の `create_container()` は `ValueError: dashboard already has a root tiled container` |
| 18 | タイル配置 API が `direction`/`order`/`weight` を受け取り `x`/`y` を受け付けない | PASS | `create_container(x=1)` / `add_worksheet(x=1)` → `TypeError` |
| 19 | SDK がタイルの階層・順序・比率から座標を計算 | PASS | zone geometry `(0, 0, 1200, 800)` を自動算出。`tests/test_connected_dashboard_api.py:72` |
| 20 | 既存 Dashboard 編集がレイアウト全体を再構築しない | 要目視 | 対象コンテナ配下限定の実装だが、兄弟コンテナ・浮動 Zone・アクションの保存を通しで見るテストが無い |
| 21 | 未対応属性・対象外 Zone・デバイスレイアウトが暗黙に削除されない | PASS | `tests/test_connected_dashboard_api.py:363-372` が `devicelayouts` のバイト一致を確認 |
| 22 | `TwbDashboardZone.delete()` が配置だけ削除する | PASS | Zone 削除後もワークシート数は 2 のまま |
| 23 | 浮動配置が `add_floating_worksheet()` という別 API | PASS | `TwbDashboard.add_floating_worksheet(worksheet, *, x, y, width, height, show_title)` |
| 24 | タイル/浮動 Zone で無効な更新引数は `ValueError` | PASS | タイルに `x=` → `tiled zones do not accept x, y, width, or height`。浮動に `order=`/`weight=` → `floating zones do not accept order or weight` |
| 25 | 参照中リソースの `delete()` が `ResourceInUseError`、XML と `is_dirty` が変化しない | PASS | 実測。`is_dirty` は `False` のまま、ファイルもバイト一致 |
| 26 | `ResourceInUseError.references` から種類・ID・場所を確認できる | PASS | `resource_type='Field'`、`resource_id='[Sales]'`、refs に XPath 付き（`.../datasource-dependencies/column/@name`） |
| 27 | 連鎖削除が公開 API に存在しない | PASS | `field`/`worksheet`/`container` の `delete()` に `cascade` 引数なし |
| 28 | `TwbColumn` と公開 `column` が `TwbField` / `field` へ移行 | 要目視 | 新 API 側は移行済み。`TwbColumn` はトップレベル `__all__` に残るが §11 の併存にあたる |
| 29 | XML 固有の `column` と `TwbWorksheet.columns` は維持 | PASS | `models.TwbWorksheet` に `columns` フィールドが残存 |
| 30 | 公開 `id`=`@name`、公開 `name`=`@caption`。Worksheet は両方 `@name` | PASS | `[Sales]` / `売上`。作成した Worksheet は `id == name == "S1"` |
| 31 | caption 無しなら `@name` 由来の既定表示名になる | PASS | `[Profit]` → `Profit`（角括弧のみ除去） |
| 32 | 公開モデルと JSON 出力に `caption` が無い | PASS | `export_json()` に `"caption"` 文字列なし。`"columns"` も無く `"fields"` に置換済み |
| 33 | XML 内の参照と計算式保存が表示名でなく `id` を使う | PASS | `SUM([売上])/SUM([粗利])` → 保存値 `SUM([Sales])/SUM([Profit])` |
| 34 | 名前が曖昧な場合に暗黙選択しない | PASS | caption 重複時 `AmbiguousFormulaReferenceError`。`get_fields(name=)` は全件（2 件）返す |
| 35 | 接続型モデルが更新後の XML を再取得なしで参照できる | PASS | `f.update(name="ZZZ")` 後に `f.name == "ZZZ"`、別インスタンスからも `"ZZZ"` |
| 36 | CRUD だけではファイルが変更されない | PASS | create/update/delete 後も入力ファイルはバイト一致 |
| 37 | `save()` の成功時だけファイルへ反映される | PASS | 同上。`save()` 後にのみ差分が出る |
| 38 | `reload()` が未保存変更を破棄し既存モデルを無効化する | PASS | `reload()` 後の `w2.name` が `DetachedModelError` |
| 39 | 削除・無効化されたモデルの操作が `DetachedModelError` | PASS | `wsfield.delete()` 後のプロパティ参照が `DetachedModelError: model is detached; acquire it again with get_*()` |
| 40 | 非公開コンテキストが JSON 出力へ含まれない | PASS | `export_json()` に `"_context"` / `"_id"` なし |
| 41 | 既存機能で旧 API と同等の XML 編集結果を得られる | 要目視 | 新旧 API の出力 XML を突き合わせる対照テストが無い |

集計: **PASS 36 / FAIL 1 / 要目視 4**

## FAIL 詳細

### 16. `folder=` が文字列を受理する

`docs/model_api_spec.md` §6.3 は「`folder` は同じ `TwbDatasource` に接続された `TwbFolder` とする。
文字列は受け付けない」と定める。`TwbField.move_to_folder()` は `TypeError: folder must be TwbFolder`
で正しく拒否するが、`TwbDatasource` の作成系 3 メソッドは `str` を受け付けたままになっている。

| 場所 | 現在の型 |
|---|---|
| `twbpatch/connected.py` `TwbDatasource.create_calculated_field(folder=)` | `str \| TwbFolder \| None` |
| `twbpatch/connected.py` `TwbDatasource.create_calculated_fields(folder=)` | `str \| TwbFolder \| None` |
| `twbpatch/connected.py` `TwbDatasource.create_yoy_calculated_fields(folder=)` | `str \| TwbFolder \| None` |

実測: `d.create_calculated_field(name="C1", formula="1", folder="KPI")` が例外にならず成功する。

**判断が要る点。** 仕様自身が §6.2 の例で `create_yoy_calculated_fields(folder="Measure")` と
文字列を書いており、§6.3 の禁止と矛盾している。実装をどちらへ寄せるかは呼び出し元の判断。

- 実装を仕様 §6.3 へ寄せるなら、上記 3 引数の型を `TwbFolder | None` にし、`str` は `TypeError`。
  併せて §6.2 の例を `folder=folder` に直す。
- 文字列の受理を残すなら、§6.3 の「文字列は受け付けない」を `move_to_folder()` 限定の規則へ書き換え、
  §13 の該当条件も「関連付け操作では」と限定する。

## 仕様逸脱（§13 以外）

### §9 `is_dirty`: XML が変化しない `update()` でも `True` になる

§9 は「同じ値への更新を変更として扱うかは実装で統一し、**原則として XML が変化しなければ
`False` のままとする**」と定める。実際には、非 ASCII 文字を含む要素に対する no-op 更新で
`is_dirty` が `True` になる。

実測（`tests/sample_minimal.twb`、`[Sales]` の caption は `売上`）:

```
f.update(name=f.name)
XML actually changed: False | is_dirty: True
```

**原因。** 各 `update()` は `copy.deepcopy()` した要素を編集し、元要素と
`ET.tostring()` の結果を比較して変更を判定する。ところが、ツリーに接続された要素は
非 ASCII を 16 進文字参照で出力し、`deepcopy` した分離要素はリテラルで出力するため、
中身が同一でも文字列が一致しない。

```
original : <column name="[Sales]" caption="&#x58F2;&#x4E0A;" .../>
deepcopy : <column name="[Sales]" caption="売上" .../>
```

`encoding="unicode"` や `with_tail=False` を付けても解消しない（実測）。

**影響範囲。** 判定関数と、`deepcopy` した要素を元要素と比較する全箇所。日本語のワークブックでは
ほぼすべての `update()` が該当する。XML の内容自体は壊れない（`parent.replace()` が
等価な要素を戻すだけ）が、`is_dirty` が保存要否の指標として使えない。

| ファイル | 行 |
|---|---|
| `twbpatch/connected.py` | 217（`_replace_if_changed`）, 1304 |
| `twbpatch/connected_dashboard.py` | 118, 498, 1118 |
| `twbpatch/connected_parameter.py` | 239 |
| `twbpatch/connected_worksheet.py` | 207, 1882, 2654, 2742 |
| `twbpatch/workbook.py` | 138 |

**修正案。** 比較の両辺を同じ経路へ通す共通関数を 1 つ置き、上記 12 箇所の
`ET.tostring(a) == ET.tostring(b)` をそれへ置き換える。

```python
def _canonical_xml(element: ET._Element) -> str:
    """接続状態に依存しない比較用の文字列。両辺を deepcopy して出力形式を揃える。"""
    return ET.tostring(copy.deepcopy(element), encoding="unicode")
```

検証済み: 同内容なら `True`、caption を変えると `False` を返す。

なお `connected.py:1328` / `:1338` は同一の接続済み要素どうしの比較なので影響しない。

## README のドリフト

`README.md`（560 行）は**旧 API だけを説明しており、新 API の記載が 1 件も無い。**

```
grep -cE "get_datasources\(|get_fields\(|get_worksheets\(|get_dashboards\(|create_folder\(|move_to_folder\(|add_field\(|create_container\(|add_worksheet\(|draw_" README.md
→ 0
```

### README にあるが仕様上の移行先がある記述

README の `## TwbWorkbook API` 配下（62-198 行）は全面的に旧 API。

| README の記載 | 仕様 §11 の移行先 |
|---|---|
| `### 検索方法 by`（87 行）— `by="auto"/"caption"/"name"` の解説 | 新 API に `by` は無い。`id=` / `name=` を明示する（§4.2） |
| `wb.list_datasources()` | `wb.get_datasources()` |
| `wb.get_datasource(v, by=...)` | `wb.get_datasources(name=v)` / `(id=v)` |
| `wb.get_column(ds, col, by=...)` | `datasource.get_fields(name=...)` / `(id=...)` |
| `wb.get_worksheet(v, by=...)` | `wb.get_worksheets(id=v)` |
| `wb.get_dashboard(v, by=...)` | `wb.get_dashboards(name=v)` / `(id=v)` |
| `wb.list_worksheet_fields(ws)` | `worksheet.get_fields()` |
| `wb.list_filters(ws)` | `worksheet.get_filters()` |
| `wb.list_relations(ds)` / `list_relationships(ds)` | `datasource.get_relations()` / `get_relationships()` |
| `wb.list_parameters()` | `wb.get_parameters()` |
| `wb.list_dashboard_fields/zones/actions(db)` | `dashboard.get_fields()` / `get_zones()` / `get_actions()` |
| `wb.create_calculated_field(ds, caption, ...)` | `datasource.create_calculated_field(name=..., ...)` |
| `### TwbColumn`（270 行） | §3.1 により公開用語は `TwbField` |
| `wb.unsupported_features()` | `wb.get_unsupported_features()`（両方存在する） |

README に記載されたシンボルは**すべて実装に存在する**（欠落なし）。ドリフトは
「README が新 API を一切載せていない」方向のみ。

### 実装にあるが README に無い公開シンボル

`twbpatch/__init__.py` の `__all__` 35 件のうち、README が扱っていない接続型モデル:

`TwbField` / `TwbPane` / `TwbDashboardContainer` / `TwbWorksheetFilter`
（`TwbDatasource` ほか同名クラスは、README の説明が旧 dataclass のフィールド一覧のままで、
接続型モデルの `get_*()` / `update()` / `delete()` を載せていない）

README に記載の無い公開メソッド:

- 新 API 全般（`get_*()` / `create_*()` / `update()` / `delete()` / `add_field()` /
  `move_to_folder()` / `add_worksheet()` ほか）
- API 方式（§6.14）: `draw_sheet()` / `draw_bar()` / `draw_yoy()` / `draw_card()` /
  `draw_quadrant()` / `draw_crosstab()` / `draw_colored_yoy_sheet()` /
  `set_filter()` / `set_default_font()` / `apply_field_config()` /
  `TwbDashboard.build_report()`
- 例外: `DetachedModelError` / `ResourceInUseError` / `ResourceReference` /
  `AmbiguousFormulaReferenceError`

`wb.export_html()` と `wb.apply_config()` は README に記載あり（28-61 行）。

## 次にやるべきこと

1. **`folder=` の型を決める（FAIL #16）。** 仕様 §6.3 と §6.2 の例が矛盾している。
   どちらへ寄せるかを決めてから `twbpatch/connected.py` の 3 引数か仕様のどちらかを直す。
2. **`is_dirty` の変更判定を直す（§9 逸脱）。** `_canonical_xml()` を 1 つ置き、
   12 箇所の `ET.tostring()` 比較を置き換える。日本語ワークブックでの no-op 更新を
   `is_dirty == False` に保つ回帰テストを追加する。
3. **README に新 API の節を足す。** 現状は旧 API 専用。§11 の対応表を基に
   「新 API（推奨）」と「旧 API（移行期のあいだ維持）」を並記する。
   `TwbColumn` の節に `TwbField` が正である旨を添える。
4. **CLAUDE.md のテスト期待値を 172 → 188 に更新する。**
5. **要目視 2 件のテストを足す**（#20 既存 Dashboard 編集の局所性、#41 新旧 API の
   XML 出力一致）。
