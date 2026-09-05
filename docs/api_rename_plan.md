# 改名タスク: 公開 `update_*()` の廃止と取得側の整合

- 起票日: 2026-09-05
- 決定内容: 公開 `update_*()` を廃止し、`update()` のキーワード引数へ統合する
- 根拠: `docs/model_api_spec.md` §3.3 / §13
- 目標形: `docs/api_reference.md`

このファイルは**この改名が完了するまでの一時的な作業計画**です。完了後に削除します。
（進捗の恒久的な記録は `docs/migration_status.md` が実装から自動生成します）

## 前提: 移行規約（仕様 §11）

**新 API を追加してから旧メソッドを消すこと。同じコミットで削除しない。**
旧メソッドの削除は全 Phase 完了後にまとめて判断する。

---

## Phase 0: 仕様の確定

決定を正典へ反映する。**これを先にやらないと `/spec-conformance` が違反を検出できない。**

- [ ] **T0-1** `docs/model_api_spec.md` §3.3 に追記
  - 属性のグループ（style など）も `update()` のキーワード引数で受ける
  - 引数名はグループ名とする（`style=` / `table_style=` / `title_style=`）
  - 固定キーのグループは `TypedDict` で型を与える
  - キー集合が開いているものは `dict[str, str | int | None]` とする
- [ ] **T0-2** `docs/model_api_spec.md` §4.1 に追記
  - §4.1「すべての `get_*()` は `list` を返す」の対象は**リソース取得**である
  - 引数を取らない属性アクセサはプロパティとして公開する
  - 引数を取る取得（`get_categorical_colors(field)`）は `get_` / `set_` 対を維持する
- [ ] **T0-3** `docs/api_reference.md` の「未決定（提案）」節を確定内容へ書き換える
  - あわせて「6件」→「**6種7メソッド**」に訂正（`get_style` が2クラスにある）

---

## Phase 1: `update_*()` → `update()` 統合（5件）

各項目は「新シグネチャを追加 → テスト追加 → 旧メソッドは残す」まで。

- [ ] **T1-1** `TwbWorksheet.update(table_style=...)`
  - 現行: `twbpatch/connected_worksheet.py:985` `update_table_style()`
  - `TableStyle(TypedDict, total=False)` を定義: `header_background` / `header_bold` / `header_color` / `row_band` / `column_widths`
  - 統合先: 同ファイル `TwbWorksheet.update()`（`:1636`）
- [ ] **T1-2** `TwbWorksheet.update(title_style=...)`
  - 現行: `twbpatch/connected_worksheet.py:1137` `update_title_style()`
  - `TitleStyle(TypedDict, total=False)`: `background_color`
- [ ] **T1-3** `TwbDashboardContainer.update(style=...)`
  - 現行: `twbpatch/connected_dashboard.py:1183` `update_style(**styles)`
  - 型は `dict[str, str | int | None]`（キー集合が開いているため TypedDict にしない）
  - 統合先: 同ファイル `TwbDashboardContainer.update()`
- [ ] **T1-4** `TwbDashboardZone.update(style=...)`
  - 現行: `twbpatch/connected_dashboard.py:1669` `update_style(**styles)`
  - 統合先: 同ファイル `TwbDashboardZone.update()`（`:1740`）
- [ ] **T1-5** `TwbPane.set_customized_label(...)`
  - 現行: `twbpatch/connected_worksheet.py:1810` `update_customized_label()`
  - **`update()` へは統合しない。** `main_metric: TwbWorksheetField` が必須で、自身の値の更新ではなく
    他フィールドを受け取る操作のため、動詞名へ改める（既存の `set_label_style` / `set_mark_color` と同じ系統）

### 注意

`update()` は「値が実際に変わったときだけ `is_dirty` を立てる」契約（仕様 §9）。
style 辞書を渡しても XML が変化しない場合は `is_dirty` を変えないこと。

`_set_zone_styles` は `None` を「属性の削除」として扱う。`UNSET`（未指定）との区別を壊さないこと。

---

## Phase 2: 取得側のプロパティ化（7メソッド / 6種）

- [ ] **T2-1** `TwbDatasource.field_grouping`  ← `connected.py:347` `get_field_grouping()`
- [ ] **T2-2** `TwbWorksheet.table_style`  ← `connected_worksheet.py:931` `get_table_style()`
- [ ] **T2-3** `TwbWorksheet.title_style`  ← `connected_worksheet.py:1081` `get_title_style()`
- [ ] **T2-4** `TwbPane.customized_label`  ← `connected_worksheet.py:1779` `get_customized_label()`
- [ ] **T2-5** `TwbPane.mark_opacity`  ← `connected_worksheet.py:1894` `get_mark_opacity()`
- [ ] **T2-6** `TwbDashboardContainer.style`  ← `connected_dashboard.py:1180` `get_style()`
- [ ] **T2-7** `TwbDashboardZone.style`  ← `connected_dashboard.py:1666` `get_style()`

**対象外**: `TwbPane.get_categorical_colors(field)`（`connected_worksheet.py:2027`）は引数を取るため
プロパティ化できない。`set_categorical_colors()` との `get_` / `set_` 対を維持する。

---

## Phase 3: 呼び出し側の追随

旧メソッドを残すため既存コードは動き続けるが、新 API へ寄せる。

- [ ] **T3-1** テストを新 API で書き直す（5ファイル）
  - `tests/test_connected_api.py`
  - `tests/test_connected_dashboard_api.py`
  - `tests/test_connected_final_api.py`
  - `tests/test_draw_api.py`
  - `tests/test_table_style_api.py`
- [ ] **T3-2** サンプルスクリプトを新 API へ（5ファイル）
  - `complete_dashboard_sample.py` / `dashboard_build_sample.py` / `dashboard_build_sample_2cards.py`
  - `draw_card_sample.py` / `draw_sheet_style_sample.py`
  - ※ 実行する場合は出力先を `outputs/` へ変えたコピーで行う（PreToolUse フックが直接実行を拒否する）
- [ ] **T3-3** `README.md` を更新
  - あわせて既存のドリフト（`TwbColumn` / 検索引数 `by` / `list_*` 前提の記述）も解消する

### 現行の呼び出し件数（2026-09-05 時点）

| メソッド | 件数 | | メソッド | 件数 |
|---|---|---|---|---|
| `update_style` | 14 | | `get_style` | 11 |
| `update_table_style` | 4 | | `get_table_style` | 5 |
| `update_title_style` | 1 | | `get_customized_label` | 5 |
| `update_customized_label` | 1 | | `get_field_grouping` | 6 |
| | | | `get_title_style` | 2 |
| | | | `get_mark_opacity` | 2 |

---

## Phase 4: 検証

- [ ] **T4-1** テスト実行
  ```bash
  mkdir -p tmp && uv run --no-sync pytest -q --basetemp=tmp/pytest
  ```
  基準値は 80 passed / 2 skipped（新 API のテストを足した分だけ増える）
- [ ] **T4-2** `/spec-conformance` を実行し、`docs/migration_status.md` を再生成
  - 「公開の `update_*()` が存在しない」が **FAIL → PASS** になることを確認
  - 「仕様の空白（要判断）」の節が消えることを確認
- [ ] **T4-3** このファイル（`docs/api_rename_plan.md`）を削除

---

## 旧メソッドの削除について

Phase 1〜4 が完了しても、**旧メソッドは残したままにする**（仕様 §11）。
削除は新 API の全 Phase 完了後に別タスクとして判断する。
