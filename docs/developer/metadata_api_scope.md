# 表示状態・参照線・フィルタ取得 API 改修範囲

## 目的

Tableau Workbook (`.twb` / `.twbx`) から、ダッシュボード/ワークシートの表示状態、ワークシートのリファレンスライン、フィルタ設定とダッシュボード上のフィルタコントロール情報を取得できるようにする。

## 改修範囲

### モデル

- `TwbDashboard`
  - `visible`
- `TwbWorksheet`
  - `visible`
  - `reference_lines`
- `TwbReferenceLine`
  - ワークシート名、ID、軸/値フィールド、表示名、role、集計式、scope、label/tooltip、元属性を保持する。
- `TwbWorksheetFilter`
  - ワークシート上のフィルタ対象フィールド、値候補範囲、適用範囲、列挙方式、単一/複数/範囲などの選択種別、値、groupfilter 属性を保持する。
- `TwbFilterControl`
  - ダッシュボード上に表示されるフィルタコントロールの対象フィールド、mode、値候補範囲、適用範囲、選択方式、値、配置属性を保持する。
- `TwbWorksheetField`
  - `category` で `軸` / `ペイン` / `フィルタ` / `その他` を保持する。
  - `aggregation` で `SUM` / `COUNT` / `AVG` などの集計関数を保持する。

### 取得ロジック

- 表示/非表示
  - `/workbook/windows/window[@class='dashboard' or @class='worksheet']` の `hidden` 属性から取得する。
  - `visible=True` を表示、`visible=False` を非表示として公開する。
- リファレンスライン
  - ワークシート配下の `reference-line` を取得する。
  - `axis-column` / `value-column` は既存フィールド解決ロジックと同じ考え方で caption / role に変換する。
- ワークシートフィルタ
  - ワークシート配下の `filter` と子孫 `groupfilter` を取得する。
  - `user:ui-domain` を `value_scope` として保持し、`relevant` / `database` / `hierarchy` などを `value_scope_label` に変換する。
  - `filter-group` や配置元から `apply_scope` を判定し、`このワークシート` / `選択したワークシート` / `このデータソースを使用するすべて` / `関連するデータソースを使用するすべて` の表示名を `apply_scope_label` に保持する。
  - `user:ui-enumeration`、`member`、`value`、`min`、`max`、`function` から選択状態を取得する。
- ダッシュボードフィルタコントロール
  - ダッシュボード配下の `zone[@type-v2='filter']` を取得する。
  - `mode` で `dropdown` / `checkdropdown` などの表示形式を保持する。
  - `param` から対象フィールドを解決する。
  - 対応するワークシートフィルタから値候補範囲、適用範囲、選択状態、値を補完する。

### 公開 API

- 既存 API 拡張
  - `wb.list_dashboards()`
  - `wb.get_dashboard(...)`
  - `wb.list_worksheets()`
  - `wb.get_worksheet(...)`
- 追加 API
  - `wb.list_reference_lines(worksheet=None, by='auto')`
  - `wb.list_filters(worksheet=None, by='auto')`
  - `wb.list_dashboard_filter_controls(dashboard=None, by='auto')`

## 対象ファイル

- `twbpatch/models.py`
- `twbpatch/window.py`
- `twbpatch/field_ref.py`
- `twbpatch/worksheet.py`
- `twbpatch/dashboard.py`
- `twbpatch/filter.py`
- `twbpatch/workbook.py`
- `twbpatch/__init__.py`
- `tests/test_dashboard_worksheet.py`

## 対象外

- フィルタ値やリファレンスラインの更新 API。
- Tableau Desktop での表示検証。
- すべての Tableau バージョン差分に対する網羅対応。
- フィルタの全 UI mode の厳密な意味付け。

## 検証範囲

- `compileall` による構文チェック。
- pytest 未導入環境のため、テスト関数を手動ランナーで全 9 件実行。
- 同梱 `.twbx` で以下を確認。
  - `reference_lines=11`
  - `filters=40`
  - `dashboard_filter_controls=4`
  - `関連値のみ` と判定できるフィルタ件数
