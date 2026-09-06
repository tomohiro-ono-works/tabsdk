# 移行状況

**このファイルは `/spec-conformance` が生成する。手で編集しない。**
生成日: 2026-09-07 / 正典: `docs/model_api_spec.md`

## テスト結果

```
244 passed, 0 skipped
```

`uv run --no-sync pytest -q --basetemp=tmp/pytest`（3.18s、exit 0）。
`CLAUDE.md` の期待値 172 は古い。244 が現在の実測値。

## §13 受け入れ条件の判定

判定は `connected*.py` と新規追加コードだけを対象にする。`models.py` の dataclass と
`TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()` / `by=` の併存は §11 により違反としない。

| 条件 | 判定 | 根拠 |
|---|---|---|
| 公開 API に `list_*()` が存在しない | PASS | `connected*.py` に `def list_` は 0 件 |
| 公開の単数取得 `get_<単数形>()` が存在しない | PASS | `connected*.py` の `get_*` は全て複数形 |
| 公開の `update_*()` が存在しない | PASS | `connected*.py` に `def update_` は 0 件 |
| 親モデルに `update_<リソース>()` / `delete_<リソース>()` が無い | PASS | 同上、`def delete_` も 0 件 |
| すべての `get_*()` が `list` を返す | PASS | 14 メソッドすべて `-> list[...]`。`TwbPane.get_categorical_colors(field)` は引数を取る属性取得で §4.1 の対象外 |
| 公開取得 API に `identifier` と `by` が存在しない | PASS | `connected*.py` の `by="name"` は全て旧ヘルパー呼び出し側の実引数（`connected.py:640` ほか） |
| 検索条件がキーワード専用の `id=` / `name=` | PASS | `get_children()` を除く全 `get_*` が `*,` 付き |
| `id` と `name` の同時指定が `ValueError` | PASS | `connected.py:60` `_validate_get_args()` を全 14 箇所が呼ぶ |
| `TwbWorksheet` に `create_field()` が無い | PASS | リポジトリ全体に `def create_field` は 0 件 |
| シェルフが `rows`/`columns`/`pages`/`filters` を検証 | PASS | `connected_worksheet.py:1395` |
| `TwbPane` が `mark_type` 更新とエンコーディング配置に対応 | PASS | `connected_worksheet.py:2800`、`_MARK_TYPES`（100 行目） |
| 複数 Pane で `add_reference_line(pane=)` が必須 | PASS | `connected_worksheet.py:951`、`tests/test_reference_line_pane.py` |
| 総計が `update(grand_totals=)` とプロパティの対称形 | PASS | `connected_worksheet.py:1040` / `1843` |
| 小計が `set_subtotal_visibility()`、`update()` に含まれない | PASS | `connected_worksheet.py:1295` |
| `TwbWorksheetField.delete()` が配置だけを解除 | PASS | `tests/test_connected_worksheet_api.py` |
| `folder=` の解決規則が全メソッドで同じ | PASS | `TwbDatasource._resolve_folder()`（`connected.py:544`）へ集約、呼び出しは 600 / 685 / 1319 |
| Dashboard 標準配置がタイルコンテナ | PASS | `connected_dashboard.py:1290` `create_container()` |
| タイル API が `direction`/`order`/`weight` を取り `x`/`y` を取らない | PASS | `connected_dashboard.py:1557` / `1600` のシグネチャ |
| SDK が階層・順序・比率から座標を計算 | PASS | `test_nested_tiled_containers_compute_coordinates_from_order_and_weight` |
| `TwbDashboardZone.delete()` が Worksheet を消さない | PASS | `test_tiled_zone_update_and_delete_preserve_worksheet` |
| 浮動配置が `add_floating_worksheet()` として分離 | PASS | `connected_dashboard.py:1331` |
| タイル／浮動 Zone の無効引数が `ValueError` | PASS | `connected_dashboard.py:2051` / `2053` |
| 参照中リソースの `delete()` が `ResourceInUseError` | PASS | `connected*.py` に 11 箇所、`test_container_delete_blocks_children_with_structured_references` ほか |
| `ResourceInUseError.references` から種類・ID・場所を確認できる | PASS | `tests/test_connected_delete_parameter_api.py:77-104` |
| 連鎖削除が公開 API に無い | PASS | リポジトリ全体に `cascade` は 0 件 |
| `TwbColumn` / 公開 `column` が `TwbField` / `field` へ移行 | **FAIL** | `TwbReferenceLine.axis_column` / `value_column`（`connected_worksheet.py:1990` / `2002`）が残っている |
| XML 固有の `column` と `TwbWorksheet.columns` は維持 | PASS | `_SHELVES` の `columns` は維持 |
| 公開 `id` = `@name`、公開 `name` = `@caption`（Worksheet は両方 `@name`） | PASS | `get_xml_id()` / `get_display_name()` へ集約 |
| caption 欠落時に `@name` 由来の既定表示名 | PASS | `test_field_update_is_live_and_caption_falls_back_to_xml_id` |
| 公開モデルと JSON 出力に `caption` が存在しない | **FAIL** | `TwbReferenceLine.axis_caption` / `value_caption`（`connected_worksheet.py:1994` / `2006`）、`TwbFilterControl.show_caption`（`connected_dashboard.py:2193`） |
| XML 内の参照と計算式保存が `id` を使用 | PASS | `test_add_field_places_id_references_on_all_worksheet_shelves` |
| 解決不能・複数候補の `name` を暗黙に選択しない | PASS | `AmbiguousCaptionError`、`tests/test_field_argument.py` |
| 接続型モデルが更新後の XML を再取得なしで参照できる | PASS | `test_field_update_is_live_and_caption_falls_back_to_xml_id` |
| CRUD だけではファイルが変更されない | PASS | `test_updates_stay_in_memory_until_save` |
| `save()` 成功時だけファイルへ反映 | PASS | `test_connected_edits_round_trip_through_save_and_reopen` |
| `reload()` が未保存変更を破棄し既存モデルを無効化 | PASS | `test_reload_discards_memory_changes_and_detaches_old_models` |
| 削除・無効化後の操作が `DetachedModelError` | PASS | `connected*.py` に 47 箇所 |
| 非公開コンテキストが JSON 出力へ含まれない | **FAIL** | `export_json()` が接続型モデルをそのまま返す（下記） |
| 既存 Dashboard の編集が対象コンテナ配下だけを変更 | 要目視 | `connected_dashboard.py:1618` は `deepcopy` → 部分編集 → 差し替え。全体再構築ではないが、対象外の兄弟を保持することを直接検査するテストが無い |
| 未対応属性・対象外 Zone・デバイスレイアウトが暗黙に変更されない | 要目視 | 読み取り側の `test_list_dashboard_zones_handles_device_and_responsive_layouts` のみ。編集後の保持を検査するテストが無い |
| 旧 API と同等の XML 編集結果を得られる | 要目視 | 新旧の出力 XML を突き合わせるパリティテストが存在しない |

## FAIL の詳細

### 1. `export_json()` が接続型モデルを素通しする（§10 / §13）

`serialization.py:7` の `_normalize_projection()` は `is_dataclass` / `dict` / `list` / `tuple`
だけを変換し、それ以外はそのまま返す。ところが次の 3 箇所は接続型モデル（dataclass ではない）を
渡している。

- `serialization.py:197` `worksheet.get_reference_lines()` → `TwbReferenceLine`
- `serialization.py:198` `worksheet.get_filters()` → `TwbWorksheetFilter`
- `serialization.py:236` `dashboard.get_filter_controls()` → `TwbFilterControl`

実測（参照線を 1 本引いたワークブック）:

```
type: <class 'twbpatch.connected_worksheet.TwbReferenceLine'>
json.dumps FAILED: Object of type TwbReferenceLine is not JSON serializable
```

参照線・ワークシートフィルタ・フィルタコントロールのいずれかを持つワークブックでは、
`export_json()` の戻り値に `_context` を抱えたモデルが混ざり、`json.dumps()` が失敗する。
`tests/sample_minimal.twb` にワークシートが無いため既存テストが素通りしている。

**直し方**: 3 モデルへ公開値だけを返す辞書化を用意し、`serialization.py` の 3 箇所で
それを渡す。あわせて `tests/test_export.py` に参照線・フィルタを持つ `tmp_path`
ワークブックのケースを足す。

### 2. 公開モデルに `caption` が残っている（§3.2 / §13）

- `TwbReferenceLine.axis_caption` → `axis_name` へ改名（`connected_worksheet.py:1994`）
- `TwbReferenceLine.value_caption` → `value_name` へ改名（`connected_worksheet.py:2006`）
- `TwbFilterControl.show_caption`（`connected_dashboard.py:2193`）は XML の `show-caption`
  （ゾーンのタイトル表示）であって表示名ではない。`show_title` への改名か、§3.2 の
  例外として仕様へ明記するかの判断が要る。

### 3. 公開モデルに `column` が残っている（§3.1 / §13）

- `TwbReferenceLine.axis_column` → `axis_field_id` へ改名（`connected_worksheet.py:1990`）
- `TwbReferenceLine.value_column` → `value_field_id` へ改名（`connected_worksheet.py:2002`）

いずれも参照先フィールドの内部 ID を返すため、§3.2 の `id` 規則に合わせる。

## 仕様に記載の無い公開メソッド

`connected*.py` の公開メソッドのうち、`docs/model_api_spec.md` に一度も現れないもの。
読み取り専用プロパティは §4.1 で許容されるため除外し、動作を持つものだけを挙げる。

| メソッド | 場所 | 対応 |
|---|---|---|
| `TwbWorksheet.add_filter_slice(field=)` | `connected_worksheet.py:1772` | §6.14 の API 方式一覧へ追記する。テストは `tests/test_unverified_api.py` にある |

## README のドリフト

`README.md`（566 行）は**旧 API だけを説明している**。新 API の公開シンボルは
`export_json` / `export_html` / `apply_config` / `get_unsupported_features` /
`create_calculated_field`（旧シグネチャ）の 5 つしか現れない。

### README に記載が無い公開シンボル

- 取得: `get_datasources` / `get_worksheets` / `get_dashboards` / `get_parameters` /
  `get_fields` / `get_folders` / `get_panes` / `get_zones` / `get_containers`
- 作成: `create_worksheet` / `create_parameter` / `create_dashboard` / `create_folder` /
  `create_container` / `create_action`
- 編集: `add_field` / `add_worksheet` / `add_floating_worksheet` / `move_to_folder` /
  `remove_from_folder` / `set_subtotal_visibility` / `grand_totals` / `build_report`
- API 方式: `draw_sheet` / `draw_bar` / `draw_yoy` / `draw_card` / `draw_quadrant` /
  `draw_crosstab` / `draw_colored_yoy_sheet` / `set_filter` / `set_default_font` /
  `apply_field_config`
- 状態: `is_dirty` / `reload`
- クラス: `TwbField` / `TwbPane` / `TwbDashboardContainer`
- 例外: `DetachedModelError` / `ResourceInUseError` / `ResourceReference` /
  `AmbiguousFormulaReferenceError`
- その他: `write_dicts_csv`

### 仕様と矛盾する記述

README が使う `list_*()` / `get_<単数形>()` / `by=` / `.caption` / `.columns` / `TwbColumn` は
すべて実装に存在するため、**壊れた例は無い**。ただし §3 の公開用語（`field` / `id` / `name`）と
逆の語彙を教えており、利用者は新 API へ到達できない。

- `README.md:19-23` 冒頭の「基本的な使い方」が `list_datasources()` / `.columns` / `.caption`
- `README.md:99-100` `by="auto"` / `by="caption"` の説明表
- `README.md:109-148` 取得 API 一覧が全て旧 API
- `README.md:215-499` モデル属性表が `caption` / `columns` / `TwbColumn` 基準
- `README.md:546-566` 例外と編集の例が `get_worksheet(..., by="name")` /
  `create_calculated_field(datasource=, caption=)`

README に**存在しないシンボル・引数は無い**（`wb.*` の全参照を実装と突き合わせ済み）。

## 次にやること

1. `serialization.py` の 3 箇所を辞書化する（FAIL 1）。`export_json()` が
   参照線・フィルタを持つワークブックで例外になる、実害のある不具合。
2. `TwbReferenceLine` の 4 プロパティを改名する（FAIL 2・3）。
   `axis_column`→`axis_field_id`、`value_column`→`value_field_id`、
   `axis_caption`→`axis_name`、`value_caption`→`value_name`。
3. `TwbFilterControl.show_caption` の扱いを決める（FAIL 2）。改名か仕様への明記か。
4. `add_filter_slice()` を `docs/model_api_spec.md` §6.14 へ追記する。
5. README を新 API 基準へ書き直す。旧 API は §11 の移行表として残す。
6. 要目視 3 件のテストを足す。Dashboard 編集時の兄弟・デバイスレイアウト保持と、
   旧 API との XML パリティ。
