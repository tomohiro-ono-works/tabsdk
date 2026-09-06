# twbpatch 公開 API リファレンス（新名称）

- 作成日: 2026-09-05
- 根拠: `docs/model_api_spec.md`（正典）+ 実装からの AST 抽出
- 対象: 接続型モデル（新 API）。旧 API は §9 に一覧のみ掲載

## 0. 凡例

| 記号 | 意味 |
|---|---|
| `UNSET` | 非公開センチネル。「指定なし＝変更しない」を `None`（値の削除）と区別する |

リソースを取得する `get_*()` はキーワード専用の `id=` / `name=` で絞り込み、常に `list` を返す。
`id` と `name` の同時指定は `ValueError`。一致なしは空リスト。
引数を取らない属性の読み取りはプロパティで公開する（§4.1）。

---

## 1. 命名規則

| 操作 | 規則 | 例 |
|---|---|---|
| 複数取得 | `get_<複数形>()` | `get_fields()` |
| 作成 | `create_<単数形>()` | `create_calculated_field()` |
| 自身の更新 | `update(**kwargs)` | `field.update(name="売上")` |
| 自身の削除 | `delete()` | `field.delete()` |
| 関連付け / 解除 | 動詞 | `move_to_folder()` / `remove_from_folder()` |
| 配置の追加 | `add_<対象>()` | `add_field()` / `add_worksheet()` |
| 属性の設定 | `set_<対象>()` | `set_mark_color()` |

`id` は XML の `@name`（Tableau 内部 ID）、`name` は caption 由来の表示名。
Worksheet のみ `id == name == XML @name`。

---

## 2. `TwbWorkbook`（エントリポイント）

ワークブックを開き、各リソースへの入口を提供する。CRUD はメモリ上の XML だけを変更し、
ファイルへ反映されるのは `save()` 成功時のみ。

### 2.1 変数

| 変数 | 型 | 説明 |
|---|---|---|
| `is_dirty` | `bool` | 未保存の変更があるか。`open()` / `reload()` / `save()` 成功で `False` |

### 2.2 入出力・検証

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `open` *(classmethod)* | `path: str` | `TwbWorkbook` | `.twb` / `.twbx` を開く。`.twbx` は内部の `.twb` を読む |
| `save` | `path: str, *, validate: bool = True, overwrite: bool = False` | `None` | 保存。`validate=True` なら検証に失敗した時点で書き込まない。`overwrite=False` で既存ファイルへの上書きを拒否 |
| `reload` | — | `TwbWorkbook` | 未保存の変更を破棄して再読込。既存の接続型モデルは無効化され、以降の操作は `DetachedModelError` |
| `validate` | — | `list[TwbValidationMessage]` | 現在の XML ツリーを検証し、問題を列挙する |
| `get_unsupported_features` | — | `list[TwbUnsupportedFeature]` | SDK が未対応の Tableau 機能を列挙する |
| `export_json` | — | `dict` | 公開値のみを組み立てて辞書化する。非公開コンテキストと `caption` は含めない |
| `export_html` | `path: str \| Path, *, title: str = "twbpatch 設定", overwrite: bool = False` | `Path` | 設定画面の HTML を 1 ファイル出力する。外部参照なしで単体で開ける。仕様は `docs/html_screen_spec.md` |
| `apply_config` | `config: str \| Path \| dict, *, field_grouping: str = "folder"` | `TwbWorkbook` | 設定画面が出力した YAML を適用する。`design.font` と `datasources` を適用し、受け手が無い節は警告ログを出して読み飛ばす |

### 2.3 リソース取得・作成

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_datasources` | `*, id=None, name=None` | `list[TwbDatasource]` | データソース一覧。`Parameters` は除外される |
| `get_worksheets` | `*, id=None, name=None` | `list[TwbWorksheet]` | ワークシート一覧 |
| `get_dashboards` | `*, id=None, name=None` | `list[TwbDashboard]` | ダッシュボード一覧 |
| `get_parameters` | `*, id=None, name=None, include_hidden: bool = False` | `list[TwbParameter]` | パラメータ一覧。内部用の hidden は既定で除外 |
| `create_worksheet` | `*, name: str, visible: bool = True` | `TwbWorksheet` | 空のワークシートを作成 |
| `create_dashboard` | `*, name: str, width: int = 1200, height: int = 800, sizing_mode: str = "fixed"` | `TwbDashboard` | ダッシュボードを作成 |
| `create_parameter` | `*, name: str, value: object, datatype: str = "string", domain_type: str = "any", allowable_values=None, min_value=None, max_value=None, step_size=None, hidden: bool = False` | `TwbParameter` | パラメータを作成。`domain_type` は `any` / `list` / `range` |

### 2.4 ワークシート生成（`draw_*`）

定型グラフを1メソッドで組み立てる高水準 API。戻り値はいずれも生成された `TwbWorksheet`。
**これが正の公開形**（仕様 §11.2）。`twbpatch.draw` のモジュール関数は実装の置き場で、
トップレベルの `twbpatch` からは公開しない。

第1引数の `datasource` は省略できる。省略時は項目を `(データソース名, フィールド名)` の
タプルで指定する。`TwbField` を直接渡すこともできる。

```python
workbook.draw_sheet(name="帳票", items=[("売上データ", "カテゴリ")])
workbook.draw_sheet(datasource, name="帳票", items=["カテゴリ"])
```

| メソッド | 主な引数（先頭に省略可能な `datasource`） | 説明 |
|---|---|---|
| `draw_sheet` | `*, name, items=None, item_shelf="rows", title=None, visible=True` | 汎用シート。`items` を指定シェルフへ配置するだけの土台 |
| `draw_bar` | `*, name, item, metric, item_shelf="rows", aggregation="sum", descending=True` | 棒グラフ。`item` 別に `metric` を集計して並べる |
| `draw_yoy` | `*, name, item, metric, item_shelf="columns", aggregation="sum", date_level="month", color=None, show_axes=True` | 前年比の時系列。`date_level` で粒度を指定 |
| `draw_card` | `*, name, main_metric, sub_metric=None, main_color="#602fff", value_color="#333333", title_background_color=None, vertical_alignment="center", main_aggregation="auto", sub_aggregation="auto"` | KPI カード。主指標と補助指標を大きく表示 |
| `draw_quadrant` | `*, name, item, x_metric, y_metric, size_metric, colors=(4色), x/y/size_aggregation="auto", opacity=0.6, title=None` | 散布図の四象限。中央値で区切り4色に塗り分ける |
| `draw_crosstab` | `*, name, x_item, y_item, color_metric, label_metric, color/label_aggregation="auto", min_color=None, mid_color=None, max_color=None, title=None` | ヒートマップ付きクロス集計 |
| `draw_colored_yoy_sheet` | `*, name, items, metrics, negative_color="#ff007f", positive_color="#602fff", ratio_color="#555555", mark_type="bar", bar_color=None, axis_min=0, axis_max=1, show_axes=False, bar_opacity=1.0, index_partition_by=None` | 前年差を色分けした帳票。指標ごとに固定軸の棒を並べる |

### 2.5 その他

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `set_default_font` | `font: str` | `TwbWorkbook` | ワークブック既定フォントを設定 |
| `apply_field_config` | `yaml_path: str \| Path, *, field_grouping: str = "folder"` | `TwbWorkbook` | YAML の定義に沿ってフィールド名・フォルダを一括適用 |

---

## 3. 接続型モデル

いずれも `ConnectedModel` を継承し、メモリ上の XML を唯一の正として都度参照する。
更新後に再取得は不要。削除済み・`reload()` 後の操作は `DetachedModelError`。

### 3.1 `TwbDatasource`

データソース1件。フィールドとフォルダを所有する。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` | `str` | Tableau 内部 ID |
| `name` | `str` | 表示名 |
| `source_type` | `str` | 接続種別（`bigquery` / `excel` / `csv` など） |
| `source` | `Source` | 接続先の値オブジェクト（§6） |
| `field_grouping` | `str \| None` | フィールドの grouping 方式 |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbField]` | 所有フィールド一覧 |
| `get_folders` | `*, id=None, name=None` | `list[TwbFolder]` | フォルダ一覧 |
| `get_relations` | `*, id=None, name=None` | `list[TwbRelation]` | 物理テーブルの結合構造 |
| `get_relationships` | `*, id=None, name=None` | `list[TwbRelationship]` | 論理リレーションシップ |
| `create_folder` | `*, name: str` | `TwbFolder` | フォルダを作成 |
| `create_calculated_field` | `*, name, formula, datatype="real", role="measure", discrete=False, folder=None, hidden=False, number_format=None, table_calculation=None, formula_ref="auto", strict=True, ref_map=None` | `TwbField` | 計算フィールドを1件作成。`formula` 内の表示名は保存前に `id` へ変換される |
| `create_calculated_fields` | `calculations: dict, *, folder=None, role="measure", discrete=False, strict=True` | `list[TwbField]` | 計算フィールドを一括作成 |
| `create_yoy_calculated_fields` | `*, metric, year_category, folder=None` | `list[TwbField]` | 前年比に必要な計算フィールド群をまとめて作成 |
| `set_filter` | `field: TwbField` | `TwbDatasource` | データソースレベルのフィルタを設定 |
| `apply_field_config` | `config: str \| Path \| dict, *, field_grouping="folder"` | `TwbDatasource` | 設定に沿って表示名・フォルダを一括適用 |
| `update` | `*, source=UNSET, name=UNSET, field_grouping=UNSET` | `TwbDatasource` | 自身を更新 |
| `delete` | — | `None` | 削除。参照中なら `ResourceInUseError` |

### 3.2 `TwbField`

データソース上のフィールド1件（通常列・計算フィールド共通）。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` | `str` | 内部 ID（例 `[Sales]`） |
| `name` | `str` | 表示名。caption がなければ `id` 由来の既定名 |
| `datasource_id` | `str` | 所属データソースの ID |
| `datatype` | `str \| None` | `string` / `integer` / `real` / `date` など |
| `role` | `str \| None` | `dimension` / `measure` |
| `discrete` | `bool \| None` | 不連続（青）か連続（緑）か |
| `default_aggregation` | `str \| None` | 既定の集計方法 |
| `hidden` | `bool` | 非表示か |
| `formula` | `str \| None` | 計算式（表示名に置換済み） |
| `raw_formula` | `str \| None` | 計算式（XML 上の内部 ID のまま） |
| `referenced_fields` | `list[str]` | 計算式が参照しているフィールド |
| `formats` | `list[dict[str, str]]` | 書式設定 |
| `folder` | `TwbFolder \| None` | 所属フォルダ |
| `is_calculated` | `bool` | 計算フィールドか |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `update` | `*, name=UNSET, datatype=UNSET, role=UNSET, discrete=UNSET, hidden=UNSET, formula=UNSET, formula_ref="auto", strict=True, ref_map=None` | `TwbField` | 自身を更新。`formula` 未指定で formula 系オプションだけ渡すと例外。`datatype` は計算フィールドのみ（それ以外は `UnsupportedFeatureError`） |
| `move_to_folder` | `folder: TwbFolder` | `TwbField` | フォルダへ移動。同一データソースのフォルダのみ |
| `remove_from_folder` | — | `TwbField` | フォルダから外す |
| `delete` | — | `None` | 削除。計算式・配置・フィルタ等から参照されていれば `ResourceInUseError` |

### 3.3 `TwbFolder`

**変数**: `id: str` / `name: str` / `datasource_id: str`

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbField]` | 収容しているフィールド |
| `delete` | — | `None` | 削除。フィールドを保持していれば `ResourceInUseError` |

### 3.4 `TwbParameter`

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str` | 内部 ID / 表示名 |
| `datatype` | `str \| None` | データ型 |
| `value` | `str \| None` | 現在値 |
| `value_display` | `str \| None` | 表示用の現在値 |
| `domain_type` | `str \| None` | `any` / `list` / `range` |
| `allowable_values` | `list[dict]` | 許可値の一覧 |
| `aliases` | `list[dict]` | 値の別名 |
| `default_value_field` | `str \| None` | 既定値の取得元フィールド |
| `min_value` / `max_value` / `step_size` | `str \| None` | range 型の範囲と刻み |
| `hidden` | `bool` | 内部用の非表示パラメータか |

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `update` | `*, value=UNSET, allow_hidden: bool = False` | `TwbParameter` | 現在値を更新。hidden なパラメータは `allow_hidden=True` が必要 |
| `delete` | — | `None` | 削除。参照中なら `ResourceInUseError` |

### 3.5 `TwbWorksheet`

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str` | 常に XML の `@name` と一致。`update(name=...)` は内部 ID の変更でもある |
| `visible` | `bool` | 表示 / 非表示 |
| `title` | `str \| None` | タイトル文字列 |
| `table_style` | `dict[str, Any]` | 表スタイル |
| `title_style` | `dict[str, Any]` | タイトルスタイル |
| `grand_totals` | `dict[str, str \| None]` | 総計の位置。`{"row": "top"\|"bottom"\|None, "column": "left"\|"right"\|None}` |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbWorksheetField]` | 配置済みフィールド（軸・ペイン・フィルタ） |
| `get_panes` | `*, id=None, name=None` | `list[TwbPane]` | ペイン一覧。複数ある場合は対象を明示的に選ぶ |
| `get_reference_lines` | `*, id=None, name=None` | `list[TwbReferenceLine]` | リファレンスライン |
| `get_filters` | `*, id=None, name=None` | `list[TwbWorksheetFilter]` | フィルタ設定 |
| `add_field` | `field: TwbField, *, shelf: str, aggregation=None, discrete=None, table_calculation=UNSET, table_calculation_field=None, date_level=None` | `TwbWorksheetField` | 既存フィールドをシェルフへ配置。`shelf` は `rows` / `columns` / `pages` / `filters` |
| `add_filter` | `field: TwbField` | `TwbWorksheetField` | フィルタとして配置 |
| `add_filter_slice` | `field: TwbField` | `TwbWorksheet` | スライス用フィルタを追加 |
| `add_sort` | `field: TwbField, *, by: TwbField, direction="descending", aggregation="sum"` | `TwbWorksheet` | 指定フィールドで並べ替え |
| `set_subtotal_visibility` | `*, field: TwbWorksheetField, visible=True` | `TwbWorksheet` | 行・列に配置したフィールドへ小計を付ける / 外す |
| `add_reference_line` | `field: TwbWorksheetField, *, formula="median", scope="per-table", label_type="value", probability=95, z_order=1` | `TwbReferenceLine` | リファレンスラインを追加 |
| `set_axis_visibility` | `field: TwbWorksheetField, *, visible: bool` | `TwbWorksheet` | 軸の表示 / 非表示 |
| `update` | `*, name=UNSET, visible=UNSET, title=UNSET, table_style=UNSET, title_style=UNSET, grand_totals=UNSET` | `TwbWorksheet` | 自身を更新。**旧 `update_table_style()` / `update_title_style()` を統合** |
| `delete` | — | `None` | 削除。ダッシュボードから参照されていれば `ResourceInUseError` |

`table_style` に渡す辞書（`TypedDict`、すべて任意）:

| キー | 型 | 説明 |
|---|---|---|
| `header_background` | `str \| None` | ヘッダー背景色 |
| `header_bold` | `bool \| None` | ヘッダーを太字にするか |
| `header_color` | `str \| None` | ヘッダー文字色 |
| `row_band` | `bool \| None` | 行の縞模様 |
| `column_widths` | `dict[str, int]` | 列ごとの幅 |

`title_style` に渡す辞書:

| キー | 型 | 説明 |
|---|---|---|
| `background_color` | `str` | タイトル背景色 |

### 3.6 `TwbPane`

ワークシート内のペイン。マークの種類とエンコーディングを担当する。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` | `str` | Pane ID |
| `name` | `str` | 表示名。無ければ Pane ID |
| `mark_type` | `str` | `bar` / `line` / `circle` / `square` / `text` など |
| `mark_opacity` | `float \| None` | 不透明度 |
| `customized_label` | `dict \| None` | カスタムラベル構成 |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbWorksheetField]` | このペインに配置されたフィールド |
| `add_field` | `field: TwbField, *, encoding: str, aggregation=None, discrete=None, table_calculation=None, table_calculation_field=None` | `TwbWorksheetField` | エンコーディングへ配置。`encoding` は `color` / `label` / `tooltip` / `size` / `shape` / `detail` / `path` / `angle` |
| `set_customized_label` | `*, main_metric: TwbWorksheetField, sub_metric: TwbWorksheetField \| None, main_color: str, value_color="#333333", vertical_alignment="center"` | `TwbPane` | カード用のラベル構成を組み立てる。**旧 `update_customized_label()`。自身の値の更新ではなく他フィールドを受け取る操作のため動詞名へ** |
| `set_label_style` | `*, show: bool = True, cull: bool = False` | `TwbPane` | ラベルの表示と重なり除去 |
| `set_mark_opacity` | `opacity: float` | `TwbPane` | 不透明度を設定 |
| `set_mark_size` | `size: float` | `TwbPane` | マークサイズを設定 |
| `set_mark_sizing` | `*, scaling: bool` | `TwbPane` | サイズの自動スケーリング |
| `set_mark_color` | `color: str` | `TwbPane` | 単色を設定 |
| `get_categorical_colors` | `field: TwbWorksheetField` | `dict[str, str]` | カテゴリ別の色割り当てを取得 |
| `set_categorical_colors` | `field: TwbWorksheetField, colors: dict[str, str]` | `TwbPane` | カテゴリ別の色を設定 |
| `set_continuous_colors` | `field: TwbWorksheetField, *, min_color, mid_color, max_color` | `TwbPane` | 連続値の3色グラデーションを設定 |
| `update` | `*, mark_type=UNSET` | `TwbPane` | マーク種別を変更 |

### 3.7 `TwbWorksheetField`

ワークシート上への「配置」。フィールド本体ではない。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` | `str` | 配置 ID |
| `field_id` | `str` | 参照先 `TwbField.id`。XML 参照には必ずこちらを使う |
| `name` | `str` | 参照先 `TwbField.name` |
| `datasource_id` | `str` | 参照先データソース |
| `shelf` | `str \| None` | `rows` / `columns` / `pages` / `filters` |
| `encoding` | `str \| None` | ペイン配下の場合のエンコーディング |
| `pane_id` | `str \| None` | 所属ペイン |
| `aggregation` | `str \| None` | `SUM` / `COUNT` / `AVG` など |
| `discrete` | `bool \| None` | 不連続か |
| `table_calculation` | `str \| None` | 表計算 |
| `date_level` | `str \| None` | 日付の粒度 |

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `update` | `*, aggregation=UNSET, discrete=UNSET` | `TwbWorksheetField` | 配置の設定を更新 |
| `delete` | — | `None` | **配置だけ**を解除。データソースの `TwbField` は削除しない |

### 3.8 `TwbDashboard`

**変数**: `id` / `name` / `sizing_mode: str` / `width: int \| None` / `height: int \| None` / `visible: bool`

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_worksheets` | `*, id=None, name=None` | `list[TwbWorksheet]` | 配置されているワークシート |
| `get_fields` | `*, id=None, name=None` | `list[TwbWorksheetField]` | 使用されているフィールド |
| `get_containers` | `*, id=None, name=None` | `list[TwbDashboardContainer]` | 直下のコンテナ |
| `get_zones` | `*, id=None, name=None` | `list[TwbDashboardZone]` | ゾーン一覧 |
| `get_actions` | `*, id=None, name=None` | `list[TwbDashboardAction]` | ダッシュボードアクション |
| `get_filter_controls` | `*, id=None, name=None` | `list[TwbFilterControl]` | 表示中のフィルタコントロール |
| `create_container` | `*, direction="horizontal", friendly_name=None, distribute_evenly=False` | `TwbDashboardContainer` | 最上位コンテナを作成 |
| `add_floating_worksheet` | `worksheet: TwbWorksheet, *, x=0, y=0, width=600, height=400, show_title=True` | `TwbDashboardZone` | 浮動配置。タイル配置とは明示的に別 API |
| `build_report` | `*, dashboard_name, struct, container_sizes=None, content_style=None, header_height=43, header_background_color="#c0c0c0", header_font_color="#333333"` | `TwbDashboard` | 構造定義から帳票レイアウトを一括構築 |
| `update` | `*, name=UNSET, visible=UNSET` | `TwbDashboard` | 自身を更新 |
| `delete` | — | `None` | 削除 |

### 3.9 `TwbDashboardContainer`

タイル配置の入れ物。`x` / `y` を受け取らず、`direction` / `order` / `weight` から SDK が座標を計算する。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str` | Zone ID / 表示名 |
| `friendly_name` | `str \| None` | 利用者が付けた名前 |
| `direction` | `str` | `horizontal` / `vertical` |
| `distribute_evenly` | `bool` | 子を均等配分するか |
| `order` | `int \| None` | 親の中での並び順 |
| `weight` | `float \| None` | 親の中での比率 |
| `fixed_size` | `int \| None` | 固定サイズ（px） |
| `hidden` | `bool` | 非表示か |
| `style` | `dict[str, str]` | ゾーンスタイル |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_containers` | `*, id=None, name=None` | `list[TwbDashboardContainer]` | 子コンテナ |
| `get_zones` | `*, id=None, name=None` | `list[TwbDashboardZone]` | 子ゾーン |
| `create_container` | `*, direction="vertical", order=None, weight=1, fixed_size=None, friendly_name=None, hidden=False, distribute_evenly=False` | `TwbDashboardContainer` | 子コンテナを作成 |
| `add_worksheet` | `worksheet: TwbWorksheet, *, order=None, weight=1, show_title=True, fixed_size=None, friendly_name=None` | `TwbDashboardZone` | ワークシートをタイル配置 |
| `add_filter` | `field: TwbWorksheetField, *, mode="checkdropdown", order=None, weight=1` | `TwbDashboardZone` | フィルタコントロールを配置 |
| `add_text` | `text: str, *, order=None, weight=1, fixed_size=None, friendly_name=None, font_size=12, font_color="#333333", bold=False, style=None` | `TwbDashboardZone` | テキストを配置 |
| `add_image` | `*, order=None, weight=1, fixed_size=None, friendly_name=None, style=None` | `TwbDashboardZone` | 画像枠を配置 |
| `add_spacer` | `*, order=None, weight=1, fixed_size=None, friendly_name=None, style=None` | `TwbDashboardZone` | 余白を配置 |
| `update` | `*, direction=UNSET, order=UNSET, weight=UNSET, fixed_size=UNSET, friendly_name=UNSET, hidden=UNSET, distribute_evenly=UNSET, style=UNSET` | `TwbDashboardContainer` | 自身を更新。**旧 `update_style()` を `style=` へ統合** |
| `delete` | — | `None` | 削除。子要素を持つ場合は `ResourceInUseError` |

`style` は `dict[str, str \| int \| None]`。キーは Tableau のゾーンスタイル属性名を
アンダースコア区切りで指定し、内部でハイフンへ変換される（例 `border_color` → `border-color`）。
**キー集合は固定されていない。** 値に `None` を渡すとその属性を削除する。

### 3.10 `TwbDashboardZone`

ワークシート・テキスト・画像など、実体を持つ配置単位。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str` | Zone ID / 参照先の表示名 |
| `kind` | `str` | ゾーン種別 |
| `worksheet_id` | `str \| None` | ワークシート配置の場合の参照先 |
| `placement_mode` | `str` | タイル配置か浮動配置か |
| `text` | `str \| None` | テキストゾーンの内容 |
| `friendly_name` | `str \| None` | 利用者が付けた名前 |
| `order` / `weight` | `int \| None` / `float \| None` | タイル配置時の並び順と比率 |
| `x` / `y` / `width` / `height` | `int \| None` | 浮動配置時の座標とサイズ |
| `show_title` | `bool \| None` | タイトル表示 |
| `fixed_size` | `int \| None` | 固定サイズ |
| `hidden` | `bool` | 非表示か |
| `style` | `dict[str, str]` | ゾーンスタイル |

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `update` | `*, order=UNSET, weight=UNSET, x=UNSET, y=UNSET, width=UNSET, height=UNSET, show_title=UNSET, fixed_size=UNSET, friendly_name=UNSET, hidden=UNSET, style=UNSET` | `TwbDashboardZone` | 自身を更新。**旧 `update_style()` を統合**。タイル配置に `x`/`y`、浮動配置に `order`/`weight` を渡すと `ValueError` |
| `delete` | — | `None` | **配置だけ**を削除。ワークシート本体は削除しない |

### 3.11 `TwbDashboardAction`

読み取り専用。

**変数**: `id` / `name` / `type: str \| None` / `activation: str \| None` / `command: str \| None` /
`source_worksheet_ids: list[str]` / `target_worksheet_ids: list[str]` / `links: list[dict]` / `params: dict[str, str]`

---

## 4. モジュール関数

| 関数 | 引数 | 説明 |
|---|---|---|
| `write_dicts_csv` | `rows: list[dict], path: str \| Path, *, fieldnames=None, encoding="utf-8-sig"` | 辞書のリストを CSV へ書き出す。既定は Excel 互換の BOM 付き UTF-8 |

---

## 5. 値オブジェクト（接続先）

`TwbDatasource.source` が返す。`update(source=...)` に渡して接続先を差し替える。

| クラス | 変数 |
|---|---|
| `BigQuerySource` | `project` / `dataset` / `table` / `server` / `custom_sql` |
| `ExcelSource` | `file_path` / `sheet` / `custom_sql` |
| `CsvSource` | `file_path` / `custom_sql` |
| `UnknownSource` | `raw_type` / `custom_sql` |

すべて `str \| None`、既定 `None`。

---

## 6. 例外

すべて `TwbPatchError` を基底とする。

| 例外 | 送出される場面 |
|---|---|
| `TwbPatchError` | 基底 |
| `NotFoundError` | 指定したリソースが存在しない |
| `AmbiguousCaptionError` | 表示名が重複し対象を一意に決められない |
| `AmbiguousFormulaReferenceError` | 計算式内の参照を一意に解決できない |
| `ValidationError` | `save(validate=True)` の検証に失敗 |
| `UnsupportedFeatureError` | SDK が未対応の構造を操作しようとした |
| `SaveError` | ファイル書き込みに失敗 |
| `DetachedModelError` | 削除済み、または `reload()` で無効化されたモデルを操作した |
| `ResourceInUseError` | 参照中のリソースを削除しようとした |

`ResourceInUseError` の変数:

| 変数 | 型 | 説明 |
|---|---|---|
| `resource_type` | `str` | 削除対象の種類 |
| `resource_id` | `str` | 削除対象の内部 ID |
| `references` | `list[ResourceReference]` | 参照元の一覧 |

`ResourceReference`（frozen dataclass）: `resource_type: str` / `resource_id: str` / `location: str`

---

## 7. 診断モデル

| クラス | 用途 |
|---|---|
| `TwbValidationMessage` | `validate()` が返す検証結果 |
| `TwbUnsupportedFeature` | `get_unsupported_features()` が返す未対応機能 |

---

## 8. 改名の記録（A-6・完了）

| 旧名 | 新名 | 理由 |
|---|---|---|
| `TwbDashboardContainer.update_style(**styles)` | `update(style={...})` | §3.3 公開 `update_*()` の禁止。元から型なしのため損失なし |
| `TwbDashboardZone.update_style(**styles)` | `update(style={...})` | 同上 |
| `TwbWorksheet.update_table_style(...)` | `update(table_style={...})` | 同上。`TypedDict` で型を維持 |
| `TwbWorksheet.update_title_style(...)` | `update(title_style={...})` | 同上 |
| `TwbPane.update_customized_label(...)` | `set_customized_label(...)` | 自身の値の更新ではなく、他フィールドを受け取る操作のため |

旧名はいずれも接続型モデルに後から入った未リリースのメソッドで、移行期に守るべき §11 の旧 API（`TwbWorkbook.list_*()` と `models.py` の dataclass 群）ではない。新形式へ委譲する薄いラッパーになった時点で削除した。**旧名はもう存在しない。**

### 取得側のプロパティ化（完了）

`update_*()` と対になる取得側は **6種7メソッド**（`get_style()` が
`TwbDashboardContainer` と `TwbDashboardZone` の2クラスにある）。
いずれも `list` を返さない単数取得で、§4.1 との整合が取れていなかった。

**決定**: 仕様 §4.1 の「`get_*()` は `list` を返す」はリソース取得の規則であり、
属性の読み取りは対象外とする。引数を取らないこの7メソッドはプロパティへ移した。
`update(style=...)` で書き、`.style` で読む対称形になる。**旧名はもう存在しない。**

| 旧名 | 新名 |
|---|---|
| `TwbDatasource.get_field_grouping()` | `field_grouping` |
| `TwbWorksheet.get_table_style()` | `table_style` |
| `TwbWorksheet.get_title_style()` | `title_style` |
| `TwbPane.get_customized_label()` | `customized_label` |
| `TwbPane.get_mark_opacity()` | `mark_opacity` |
| `TwbDashboardContainer.get_style()` | `style` |
| `TwbDashboardZone.get_style()` | `style` |

`get_categorical_colors(field)` / `set_categorical_colors(field, colors)` は引数を取るため
プロパティにできない。現状の `get_` / `set_` 対を維持する。

---

## 9. 旧 API（移行期のみ存続）

仕様 §11 により削除・改名しない。新規コードでは使用しない。

**`TwbWorkbook` の旧メソッド**

```
list_dashboards, list_dashboard_fields, list_dashboard_zones, list_dashboard_actions,
list_dashboard_filter_controls, list_worksheets, list_worksheet_fields, list_reference_lines,
list_filters, list_datasources, list_relations, list_relationships, list_parameters, list_columns,
get_dashboard, get_worksheet, get_datasource, get_column,
update_source, update_column, update_formula,
rename_field, reset_field_caption, create_calculated_field(位置引数版),
move_field_to_folder, remove_field_from_folder, move_column_to_folder,
unsupported_features, set_filter
```

いずれも検索方法として `by="auto"` を取る。新 API では `id=` / `name=` に統一されている。

**`models.py` の投影 dataclass**

```
TwbColumn, TwbFolder, TwbParameter, TwbRelation, TwbRelationship, TwbDatasource,
TwbReferenceLine, TwbWorksheetFilter, TwbFilterControl, TwbDashboardZone,
TwbDashboardAction, TwbWorksheet, TwbDashboard, TwbWorksheetField
```

接続型モデルと同名のものがあるため、参照時は import 元に注意する。
`TwbColumn` は `TwbField`、`caption` は `name` へ移行する。
