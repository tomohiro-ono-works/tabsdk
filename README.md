# twbpatch

既存の Tableau `.twb` / `.twbx` を読み込み、データソース、カラム、計算フィールド、フォルダ、ダッシュボード、ワークシート、フィルタなどのメタデータを取得・編集して保存するための Python ライブラリです。

## 動作要件

- Python 3.10 以上
- `lxml` 5.0.0 以上

## 基本的な使い方

クラスベースの API では、`TwbWorkbook.open()` でワークブックを開き、`TwbWorkbook` のメソッドから各種情報を取得します。

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")

for datasource in wb.list_datasources():
    print(datasource.caption, datasource.source_type)

    for column in datasource.columns:
        print(column.caption, column.datatype, column.formula)
```

`.twb` と `.twbx` のどちらも同じ API で開けます。

### 設定画面を HTML で出す

フィールドの一覧を調べて Python へ書き写す代わりに、画面で設定して YAML を落とせます。

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")
wb.export_html("config.html", title="売上分析 設定", overwrite=True)
```

出力した HTML は外部参照を持たず、そのままブラウザで開けます（オフライン可）。
画面はデータソース（表示名・フォルダ・計算フィールド）、全体の書式、ダッシュボードの構成の
3 タブで、「設定 YAML をダウンロード」で 1 ファイルに落ちます。

### 設定画面が出した YAML を適用する

```python
wb = TwbWorkbook.open("template.twb")
wb.apply_config("twbpatch_config.yaml")
wb.save("output.twb", overwrite=True)
```

適用されるのは次のとおりです。

| 節 | 何をするか |
|---|---|
| `design.font` | ワークブック全体の既定フォント |
| `datasources.*.folders` | 表示名の変更とフォルダ分類 |
| `datasources.*.calculations` | 計算フィールドの作成。同名があれば式・データ型・役割・フォルダを上書き |
| `dashboard` | シートを作って並べ、アクションを張る |

`design` の色・余白・フィルターの「適用」ボタンは、**ダッシュボードを組むときに使います**。
グラフの色に `@main_color` と書くと、デザインルールの色コードに置き換わります。
`dashboard` が無い設定では届かないので、名前を警告ログへ出して読み飛ばします。
詳細は [docs/html_screen_spec.md](docs/html_screen_spec.md)。

計算フィールドを画面で定義した場合は、**一度 `.twb` へ焼き直してから画面を出し直します。**
そうすると 2 周目にはグラフの項目候補として選べるようになります。
手順は [docs/roundtrip.md](docs/roundtrip.md) にまとめています。

## `TwbWorkbook` API

### 公開変数

| 変数 | 型 | 説明 |
|---|---|---|
| `tree` | `lxml.etree._ElementTree` | 読み込んだ Tableau Workbook の XML ツリー。通常のメタデータ取得では、後述の取得メソッドの使用を推奨します。 |

`_parsed` および `_` から始まるメソッドは内部実装であり、公開 API ではありません。

### ワークブックを開く

#### `TwbWorkbook.open(path)`

```python
@classmethod
TwbWorkbook.open(path: str) -> TwbWorkbook
```

| 引数 | 説明 |
|---|---|
| `path` | 読み込む `.twb` または `.twbx` ファイルのパス。 |

対応外の拡張子を指定した場合は `ValueError`、`.twbx` 内に `.twb` が存在しない場合は `NotFoundError` が発生します。

### 検索方法 `by`

単一要素を取得するメソッドでは、`by` に以下を指定できます。

| 値 | 動作 |
|---|---|
| `"auto"` | `caption` を先に検索し、見つからない場合に内部名 `name` を検索します。既定値です。 |
| `"caption"` | Tableau 上の表示名だけを検索します。 |
| `"name"` | Tableau XML 内部の名前だけを検索します。 |

対象がない場合は `NotFoundError`、同じ表示名の候補が複数ある場合は `AmbiguousCaptionError` が発生します。不正な `by` の値には `ValueError` が発生します。

### データソース・カラム・パラメータ取得

| メソッド | 戻り値 | 説明 |
|---|---|---|
| `list_datasources()` | `list[TwbDatasource]` | パラメータ用データソースを除く、全データソースを取得します。各要素にカラム、フォルダ、リレーションも含まれます。 |
| `get_datasource(datasource, *, by="auto")` | `TwbDatasource` | 表示名または内部名からデータソースを1件取得します。 |
| `list_relations(datasource=None, *, by="auto")` | `list[TwbRelation]` | テーブル、Custom SQL、join、union などの物理リレーションを再帰構造で取得します。`datasource=None` では全データソースが対象です。 |
| `list_relationships(datasource=None, *, by="auto")` | `list[TwbRelationship]` | Tableau の論理テーブル間に定義されたリレーションシップを取得します。`datasource=None` では全データソースが対象です。 |
| `list_columns(datasource)` | `list[TwbColumn]` | 指定データソースの全カラムを取得します。データソースは `auto` で検索されます。 |
| `get_column(datasource, column, *, by="auto")` | `TwbColumn` | 指定データソースからカラムを1件取得します。`by` はカラムの検索方法です。 |
| `list_parameters(*, include_hidden=False)` | `list[TwbParameter]` | パラメータを取得します。`include_hidden=True` で非表示パラメータも含めます。 |

```python
datasource = wb.get_datasource("売上データ")
print(datasource.name, datasource.caption, datasource.source)

for relation in wb.list_relations("売上データ"):
    print(relation.type, relation.join, relation.table, relation.custom_sql)

for relationship in wb.list_relationships("売上データ"):
    print(relationship.left_object, relationship.right_object)

column = wb.get_column("売上データ", "粗利率")
print(column.name, column.formula, column.referenced_columns)

for parameter in wb.list_parameters(include_hidden=True):
    print(parameter.caption, parameter.value_display)
```

### ダッシュボード・ワークシート取得

| メソッド | 戻り値 | 説明 |
|---|---|---|
| `list_dashboards()` | `list[TwbDashboard]` | 全ダッシュボードを取得します。各要素に配置されたワークシートも含まれます。 |
| `get_dashboard(dashboard, *, by="auto")` | `TwbDashboard` | ダッシュボードを1件取得します。 |
| `list_dashboard_fields(dashboard=None, *, by="auto", max_filter_value_chars=40)` | `list[TwbWorksheetField]` | ダッシュボード内の軸、ペイン、フィルタ、その他のフィールドを取得します。`dashboard=None` では全ダッシュボードが対象です。 |
| `list_dashboard_zones(dashboard=None, *, by="auto", width_px=None, height_px=None, include_device_layouts=False)` | `list[TwbDashboardZone]` | 配置要素、階層、座標、サイズを取得します。`dashboard=None` では全ダッシュボードが対象です。 |
| `list_dashboard_actions(dashboard=None, *, by="auto")` | `list[TwbDashboardAction]` | フィルタ、ハイライト、URL、画面遷移などのアクションを取得します。 |
| `list_worksheets()` | `list[TwbWorksheet]` | 全ワークシートを取得します。 |
| `get_worksheet(worksheet, *, by="auto")` | `TwbWorksheet` | ワークシートを1件取得します。 |
| `list_worksheet_fields(worksheet=None, *, by="auto", max_filter_value_chars=40)` | `list[TwbWorksheetField]` | 行・列・ページ・フィルタ・マーク・ソートに配置されたフィールドを取得します。`worksheet=None` では全ワークシートが対象です。 |
| `list_reference_lines(worksheet=None, *, by="auto")` | `list[TwbReferenceLine]` | リファレンスラインを取得します。`worksheet=None` では全ワークシートが対象です。 |
| `list_filters(worksheet=None, *, by="auto")` | `list[TwbWorksheetFilter]` | ワークシートフィルタを取得します。`worksheet=None` では全ワークシートが対象です。 |
| `list_dashboard_filter_controls(dashboard=None, *, by="auto")` | `list[TwbFilterControl]` | ダッシュボードに配置されたフィルタコントロールを取得します。`dashboard=None` では全ダッシュボードが対象です。 |

`max_filter_value_chars` は `TwbWorksheetField.values` の最大文字数です。`0` 以下を指定すると省略しません。

zone の `x_raw`、`y_raw`、`width_raw`、`height_raw` は、ダッシュボード全体を `100000 × 100000` とするXML上の正規化値です。固定サイズではピクセル値を自動計算します。

```text
x_px      = round(x_raw      * dashboard_width_px  / 100000)
y_px      = round(y_raw      * dashboard_height_px / 100000)
width_px  = round(width_raw  * dashboard_width_px  / 100000)
height_px = round(height_raw * dashboard_height_px / 100000)
```

Automatic／Rangeでは描画サイズを確定できないため、`width_px` と `height_px` を引数で指定しない場合、変換後の座標は `None` です。`include_device_layouts=True` で端末別zoneも取得できます。

```python
dashboard = wb.get_dashboard("経営ダッシュボード")
print(dashboard.caption, dashboard.visible)

for worksheet in dashboard.worksheets:
    print(worksheet.caption, worksheet.visible)

for field in wb.list_worksheet_fields("売上推移"):
    print(field.category, field.type, field.caption, field.mark_type)

for field in wb.list_dashboard_fields("経営ダッシュボード"):
    print(field.worksheet, field.category, field.type, field.caption)

for zone in wb.list_dashboard_zones("経営ダッシュボード"):
    print(zone.type, zone.x_raw, zone.x_px, zone.width_raw, zone.width_px)

for action in wb.list_dashboard_actions("経営ダッシュボード"):
    print(action.type, action.source_worksheets, action.target_worksheets)

for filter_ in wb.list_filters("売上推移"):
    print(filter_.field, filter_.selection_type, filter_.values)
```

### 診断・汎用取得

| メソッド | 戻り値 | 説明 |
|---|---|---|
| `export_json()` | `dict` | データソース、パラメーター、ワークシート、ダッシュボードを新APIの `id` / `name` 形式で辞書へ変換します。 |
| `validate()` | `list[TwbValidationMessage]` | ワークブックを検証し、警告・エラーを取得します。問題がない場合は空リストです。 |
| `unsupported_features()` | `list[TwbUnsupportedFeature]` | ライブラリが完全には対応していない機能を取得します。 |
| `get_unsupported_features()` | `list[TwbUnsupportedFeature]` | 新APIの命名規則で、未対応機能をリストとして取得します。 |

```python
metadata = wb.export_json()

for message in wb.validate():
    print(message.severity, message.code, message.message)

for feature in wb.unsupported_features():
    print(feature.severity, feature.feature, feature.message)
```

## 返却モデルの変数

取得メソッドは dataclass のスナップショットを返します。返却オブジェクトの変数を書き換えても、ワークブックの XML には反映されません。編集には `TwbWorkbook` の更新メソッドを使用してください。

### `TwbDatasource`

| 変数 | 型 | 説明 |
|---|---|---|
| `name` | `str \| None` | Tableau XML 内のデータソース名。 |
| `id` | `str \| None` | データソースID。現在は `name` と同じ値です。 |
| `caption` | `str \| None` | 表示名。未設定の場合は `name` です。 |
| `source_type` | `str` | 接続種別。`bigquery`、`excel`、`csv`、`unknown` のいずれかです。 |
| `source` | `BigQuerySource \| ExcelSource \| CsvSource \| UnknownSource` | 接続先の詳細。 |
| `columns` | `list[TwbColumn]` | データソースに定義されたカラム。 |
| `folders` | `list[TwbFolder]` | データソースに定義されたフォルダ。 |
| `relations` | `list[TwbRelation]` | データソースの物理リレーション構造。 |
| `relationships` | `list[TwbRelationship]` | 論理テーブル間のリレーションシップ。 |

### 接続先モデル

| クラス | 変数 | 型 | 説明 |
|---|---|---|---|
| `BigQuerySource` | `project` | `str \| None` | GCP プロジェクト。 |
|  | `dataset` | `str \| None` | BigQuery データセット。 |
|  | `table` | `str \| None` | テーブル名。 |
|  | `server` | `str \| None` | サーバー属性。 |
|  | `custom_sql` | `str \| None` | Custom SQL。 |
| `ExcelSource` | `file_path` | `str \| None` | Excel ファイルのパス。 |
|  | `sheet` | `str \| None` | シート名。現行の取得処理では未設定の場合があります。 |
|  | `custom_sql` | `str \| None` | Custom SQL。 |
| `CsvSource` | `file_path` | `str \| None` | CSV、TSV、テキストファイルのパス。 |
|  | `custom_sql` | `str \| None` | Custom SQL。 |
| `UnknownSource` | `raw_type` | `str \| None` | Tableau XML の接続クラス名。 |
|  | `custom_sql` | `str \| None` | Custom SQL。 |

### `TwbRelation`

`children` に子リレーションを持つ再帰モデルです。join の場合は、ルートの `children` に結合対象のテーブルや Custom SQL が入ります。

| 変数 | 型 | 説明 |
|---|---|---|
| `datasource` | `str` | データソースの表示名。 |
| `datasource_id` | `str \| None` | データソースの内部名。 |
| `id` | `str \| None` | リレーションのIDまたは名前。 |
| `type` | `str \| None` | `table`、`text`、`join`、`union`、`collection` などの種別。 |
| `name` | `str \| None` | リレーション名。 |
| `table` | `str \| None` | 物理テーブル名。 |
| `connection` | `str \| None` | 接続ID。 |
| `join` | `str \| None` | `inner`、`left` などの結合種別。 |
| `custom_sql` | `str \| None` | `type="text"` の Custom SQL。 |
| `scope` | `str \| None` | 取得元。通常は `connection`、物理構造がない場合は `object-graph`。 |
| `logical_table` | `str \| None` | object-graph から取得した場合の論理テーブル表示名。 |
| `logical_table_id` | `str \| None` | 論理テーブルID。 |
| `clauses` | `list[dict[str, object]]` | join 条件など、relation 以外の子XMLを再帰辞書化したもの。 |
| `children` | `list[TwbRelation]` | 入れ子の子リレーション。 |
| `attrs` | `dict[str, str]` | relation 要素の元 XML 属性。 |

### `TwbRelationship`

| 変数 | 型 | 説明 |
|---|---|---|
| `datasource` | `str` | データソースの表示名。 |
| `datasource_id` | `str \| None` | データソースの内部名。 |
| `id` | `str \| None` | リレーションシップID。 |
| `left_object` | `str \| None` | 左側の論理テーブル表示名。 |
| `left_object_id` | `str \| None` | 左側の論理テーブルID。 |
| `right_object` | `str \| None` | 右側の論理テーブル表示名。 |
| `right_object_id` | `str \| None` | 右側の論理テーブルID。 |
| `expression` | `dict[str, object] \| None` | 結合条件の expression 要素を再帰辞書化したもの。 |
| `attrs` | `dict[str, str]` | relationship 要素の元 XML 属性。 |

### `TwbColumn`

| 変数 | 型 | 説明 |
|---|---|---|
| `name` | `str` | Tableau XML 内のカラム名。 |
| `id` | `str \| None` | カラムID。現在は `name` と同じ値です。 |
| `caption` | `str \| None` | 表示名。 |
| `datatype` | `str \| None` | データ型。例: `string`、`integer`、`real`、`date`。 |
| `role` | `str \| None` | フィールドの役割。主に `dimension` または `measure`。 |
| `discrete` | `bool \| None` | `True` は離散、`False` は連続、判定不能は `None`。 |
| `hidden` | `bool` | 非表示フィールドかどうか。 |
| `formula` | `str \| None` | 表示名に解決された計算式。 |
| `raw_formula` | `str \| None` | Tableau XML に保存されている元の計算式。 |
| `referenced_columns` | `list[str]` | 計算式から参照されるカラムの表示名。 |
| `format` | `list[dict[str, str]]` | カラムに関連する書式属性。要素やワークシート名を含む場合があります。 |
| `folder` | `str \| None` | 所属フォルダ名。 |
| `is_calculated` | `bool` | 計算フィールドかどうかを返す読み取り専用プロパティ。 |

### `TwbFolder`

| 変数 | 型 | 説明 |
|---|---|---|
| `name` | `str` | フォルダ名。 |
| `id` | `str \| None` | フォルダID。現在は `name` と同じ値です。 |
| `role` | `str \| None` | フォルダの役割。現行の取得処理では `None` です。 |
| `items` | `list[str]` | フォルダに含まれるカラムの内部名。 |

### `TwbParameter`

| 変数 | 型 | 説明 |
|---|---|---|
| `name` | `str` | Tableau XML 内のパラメータ名。 |
| `id` | `str \| None` | パラメータID。現在は `name` と同じ値です。 |
| `caption` | `str \| None` | 表示名。 |
| `datatype` | `str \| None` | データ型。 |
| `value` | `str \| None` | 現在値。 |
| `value_display` | `str \| None` | エイリアスを反映した現在値の表示文字列。 |
| `domain_type` | `str \| None` | 値域種別。 |
| `allowable_values` | `list[dict[str, str \| None]]` | 許可値。各辞書は `value` と `alias` を持ちます。 |
| `aliases` | `list[dict[str, str \| None]]` | 値のエイリアス。各辞書は `value` と `alias` を持ちます。 |
| `default_value_field` | `str \| None` | 既定値を供給するフィールド。 |
| `hidden` | `bool` | 非表示パラメータかどうか。 |

### `TwbDashboard`

| 変数 | 型 | 説明 |
|---|---|---|
| `name` | `str` | Tableau XML 内のダッシュボード名。 |
| `id` | `str \| None` | ダッシュボードID。現在は `name` と同じ値です。 |
| `caption` | `str \| None` | 表示名。 |
| `worksheets` | `list[TwbWorksheet]` | ダッシュボードに配置されたワークシート。 |
| `zones` | `list[TwbDashboardZone]` | ダッシュボードの配置要素。既定レイアウトが対象です。 |
| `actions` | `list[TwbDashboardAction]` | ダッシュボードを起点とするアクション。 |
| `visible` | `bool` | Tableau の表示状態。 |

### `TwbDashboardZone`

| 変数 | 型 | 説明 |
|---|---|---|
| `dashboard` | `str` | ダッシュボードの表示名。 |
| `dashboard_id` | `str \| None` | ダッシュボードの内部名。 |
| `id` | `str \| None` | zone ID。 |
| `parent_id` | `str \| None` | 親zone ID。最上位では `None`。 |
| `depth` | `int` | zone階層の深さ。最上位は `0`。 |
| `name` | `str \| None` | zone名またはカスタムタイトル。 |
| `type` | `str \| None` | `worksheet`、`text`、`filter`、`layout-flow` などの種別。 |
| `worksheet` | `str \| None` | 配置ワークシートの表示名。 |
| `worksheet_id` | `str \| None` | 配置ワークシートの内部名。 |
| `mode` | `str \| None` | フィルタやパラメータコントロールの表示形式。 |
| `param` | `str \| None` | フィールド、パラメータ、画像などの参照値。 |
| `url` | `str \| None` | WebページzoneなどのURL。 |
| `text` | `str \| None` | テキストzoneの文字列。 |
| `layout` | `str` | `default` または端末別レイアウト名。 |
| `sizing_mode` | `str \| None` | `fixed`、`range`、`automatic` などのサイズ方式。 |
| `dashboard_width_px` | `int \| None` | 座標変換に使用したダッシュボード幅。 |
| `dashboard_height_px` | `int \| None` | 座標変換に使用したダッシュボード高さ。 |
| `x_raw` | `int \| None` | XML上のX座標。 |
| `x_px` | `int \| None` | ピクセル換算したX座標。 |
| `y_raw` | `int \| None` | XML上のY座標。 |
| `y_px` | `int \| None` | ピクセル換算したY座標。 |
| `width_raw` | `int \| None` | XML上の幅。 |
| `width_px` | `int \| None` | ピクセル換算した幅。 |
| `height_raw` | `int \| None` | XML上の高さ。 |
| `height_px` | `int \| None` | ピクセル換算した高さ。 |
| `fixed_size` | `int \| None` | Tableau XMLの固定サイズ属性。 |
| `is_fixed` | `bool \| None` | 固定要素かどうか。 |
| `is_scaled` | `bool \| None` | スケーリング対象かどうか。 |
| `show_title` | `bool \| None` | タイトル表示設定。 |
| `show_caption` | `bool \| None` | キャプション表示設定。 |
| `show_apply` | `bool \| None` | 適用ボタン表示設定。 |
| `attrs` | `dict[str, str]` | zone要素の元XML属性。 |

### `TwbDashboardAction`

| 変数 | 型 | 説明 |
|---|---|---|
| `dashboard` | `str \| None` | 起点ダッシュボードの表示名。 |
| `dashboard_id` | `str \| None` | 起点ダッシュボードの内部名。 |
| `id` | `str \| None` | アクションIDまたは内部名。 |
| `caption` | `str \| None` | アクションの表示名。 |
| `type` | `str \| None` | `filter`、`highlight`、`url`、`navigation` などに正規化した種別。 |
| `activation` | `str \| None` | `on-select`、`on-hover` などの実行契機。 |
| `command` | `str \| None` | Tableau XML上のコマンド名。 |
| `source_type` | `str \| None` | 起点の種類。 |
| `source_dashboard` | `str \| None` | 起点ダッシュボードの表示名。 |
| `source_dashboard_id` | `str \| None` | 起点ダッシュボードの内部名。 |
| `source_worksheets` | `list[str]` | 起点ワークシートの表示名。 |
| `source_worksheet_ids` | `list[str]` | 起点ワークシートの内部名。 |
| `excluded_source_worksheets` | `list[str]` | 起点から除外されたワークシート。 |
| `target_type` | `str \| None` | 遷移先の種類。 |
| `target_dashboard` | `str \| None` | 遷移先ダッシュボードの表示名。 |
| `target_dashboard_id` | `str \| None` | 遷移先ダッシュボードの内部名。 |
| `target_worksheets` | `list[str]` | 遷移先ワークシートの表示名。 |
| `target_worksheet_ids` | `list[str]` | 遷移先ワークシートの内部名。 |
| `excluded_target_worksheets` | `list[str]` | 遷移先から除外されたワークシート。 |
| `links` | `list[dict[str, str]]` | フィールド対応などのlink属性。 |
| `params` | `dict[str, str]` | URL等のparam値。 |
| `attrs` | `dict[str, str]` | action要素の元XML属性。 |
| `details` | `dict[str, object]` | action配下のXMLを再帰辞書化したもの。 |

### `TwbWorksheet`

| 変数 | 型 | 説明 |
|---|---|---|
| `name` | `str` | Tableau XML 内のワークシート名。 |
| `id` | `str \| None` | ワークシートID。現在は `name` と同じ値です。 |
| `caption` | `str \| None` | 表示名。 |
| `rows` | `list[str]` | 行シェルフに配置されたフィールド参照。 |
| `columns` | `list[str]` | 列シェルフに配置されたフィールド参照。 |
| `filters` | `list[dict[str, str]]` | ワークシート内のフィルタ要素が持つ生の XML 属性。詳細な解析結果には `list_filters()` を使用します。 |
| `datasource_names` | `list[str]` | ワークシートが参照するデータソースの内部名。 |
| `used_columns` | `list[str]` | ワークシートが参照するカラムの内部名。 |
| `reference_lines` | `list[TwbReferenceLine]` | ワークシートに設定されたリファレンスライン。 |
| `fields` | `list[TwbWorksheetField]` | 行・列・ページ・フィルタ・マーク・ソートに配置されたフィールド。 |
| `visible` | `bool` | Tableau の表示状態。 |

### `TwbWorksheetField`

| 変数 | 型 | 説明 |
|---|---|---|
| `worksheet` | `str` | ワークシートの表示名。 |
| `type` | `str` | 配置種別。例: `x軸`、`y軸`、`色`、`ラベル`、`フィルタ`。 |
| `role` | `str \| None` | フィールドの役割。 |
| `caption` | `str \| None` | フィールドの表示名。 |
| `id` | `str \| None` | Tableau XML 内のフィールド参照。 |
| `values` | `str \| None` | フィルタ値を連結した表示文字列。 |
| `category` | `str \| None` | `軸`、`ペイン`、`フィルタ`、`ページ`、`ソート`、`その他` のいずれか。 |
| `aggregation` | `str \| None` | `SUM`、`AVG`、`COUNT` などの集計方法。 |
| `worksheet_id` | `str \| None` | ワークシートの内部名。 |
| `datasource` | `str \| None` | データソースの表示名。 |
| `datasource_id` | `str \| None` | データソースの内部名。 |
| `field_id` | `str \| None` | 解決されたフィールドの内部名。 |
| `pane_id` | `str \| None` | フィールドが配置されたペインID。 |
| `mark_type` | `str \| None` | `Bar`、`Line`、`Text` などのマーク種別。 |
| `attrs` | `dict[str, str]` | 配置元要素の XML 属性。 |

### `TwbReferenceLine`

| 変数 | 型 | 説明 |
|---|---|---|
| `worksheet` | `str` | ワークシートの表示名。 |
| `worksheet_id` | `str \| None` | ワークシートの内部名。 |
| `id` | `str \| None` | リファレンスラインID。 |
| `axis_column` | `str \| None` | 対象軸の元フィールド参照。 |
| `axis_caption` | `str \| None` | 対象軸フィールドの表示名。 |
| `axis_role` | `str \| None` | 対象軸フィールドの役割。 |
| `value_column` | `str \| None` | 値に使用する元フィールド参照。 |
| `value_caption` | `str \| None` | 値フィールドの表示名。 |
| `value_role` | `str \| None` | 値フィールドの役割。 |
| `formula` | `str \| None` | リファレンスラインの計算式。 |
| `scope` | `str \| None` | リファレンスラインの適用範囲。 |
| `label_type` | `str \| None` | ラベル種別。 |
| `tooltip_type` | `str \| None` | ツールチップ種別。 |
| `attrs` | `dict[str, str]` | 元の XML 属性。 |

### `TwbWorksheetFilter`

| 変数 | 型 | 説明 |
|---|---|---|
| `worksheet` | `str` | ワークシートの表示名。 |
| `worksheet_id` | `str \| None` | ワークシートの内部名。 |
| `column` | `str \| None` | フィルタ対象の元フィールド参照。 |
| `field` | `str \| None` | フィルタ対象フィールドの表示名。 |
| `role` | `str \| None` | フィールドの役割。 |
| `filter_class` | `str \| None` | Tableau XML のフィルタクラス。 |
| `filter_group` | `str \| None` | フィルタグループ。 |
| `domain` | `str \| None` | Tableau XML の domain 属性。 |
| `enumeration` | `str \| None` | Tableau XML の列挙方法。 |
| `value_scope` | `str \| None` | 値候補の範囲。 |
| `value_scope_label` | `str \| None` | 値候補範囲の日本語表示。 |
| `apply_scope` | `str \| None` | フィルタの適用範囲。 |
| `apply_scope_label` | `str \| None` | 適用範囲の日本語表示。 |
| `selection_type` | `str \| None` | 単一、複数、範囲などの選択種別。 |
| `values` | `list[str]` | 選択値、最小値、最大値など。 |
| `functions` | `list[str]` | groupfilter の function 属性。 |
| `attrs` | `dict[str, str]` | filter 要素の元 XML 属性。 |
| `groupfilter_attrs` | `list[dict[str, str]]` | 子孫 groupfilter 要素の元 XML 属性。 |

### `TwbFilterControl`

| 変数 | 型 | 説明 |
|---|---|---|
| `dashboard` | `str` | ダッシュボードの表示名。 |
| `dashboard_id` | `str \| None` | ダッシュボードの内部名。 |
| `id` | `str \| None` | コントロールを表すゾーンのID。 |
| `name` | `str \| None` | コントロール名。 |
| `worksheet` | `str \| None` | 関連ワークシートの表示名。 |
| `worksheet_id` | `str \| None` | 関連ワークシートの内部名。 |
| `column` | `str \| None` | 対象の元フィールド参照。 |
| `field` | `str \| None` | 対象フィールドの表示名。 |
| `role` | `str \| None` | 対象フィールドの役割。 |
| `mode` | `str \| None` | 表示形式。例: `dropdown`、`checkdropdown`。 |
| `filter_class` | `str \| None` | 関連するワークシートフィルタのクラス。 |
| `domain` | `str \| None` | Tableau XML の domain 属性。 |
| `enumeration` | `str \| None` | Tableau XML の列挙方法。 |
| `value_scope` | `str \| None` | 値候補の範囲。 |
| `value_scope_label` | `str \| None` | 値候補範囲の日本語表示。 |
| `apply_scope` | `str \| None` | フィルタの適用範囲。 |
| `apply_scope_label` | `str \| None` | 適用範囲の日本語表示。 |
| `selection_type` | `str \| None` | 単一、複数、範囲などの選択種別。 |
| `values` | `list[str]` | 選択値、最小値、最大値など。 |
| `show_apply` | `bool \| None` | 適用ボタンの表示設定。 |
| `show_title` | `bool \| None` | タイトルの表示設定。 |
| `show_caption` | `bool \| None` | キャプションの表示設定。 |
| `x` | `str \| None` | 横方向の配置位置。 |
| `y` | `str \| None` | 縦方向の配置位置。 |
| `width` | `str \| None` | 幅。 |
| `height` | `str \| None` | 高さ。 |
| `attrs` | `dict[str, str]` | コントロールを表すゾーンの元 XML 属性。 |

### 診断モデル

#### `TwbValidationMessage`

| 変数 | 型 | 説明 |
|---|---|---|
| `severity` | `str` | 重要度。主に `error` または `warning`。 |
| `code` | `str` | 検証コード。 |
| `message` | `str` | 検証メッセージ。 |
| `datasource` | `str \| None` | 関連するデータソース。 |
| `column` | `str \| None` | 関連するカラム。 |

#### `TwbUnsupportedFeature`

| 変数 | 型 | 説明 |
|---|---|---|
| `feature` | `str` | 未対応機能の識別名。 |
| `severity` | `str` | 重要度。 |
| `message` | `str` | 説明。 |
| `datasource` | `str \| None` | 関連するデータソース。 |

## 主な例外

すべて `twbpatch` から import できます。

| 例外 | 発生条件 |
|---|---|
| `TwbPatchError` | ライブラリ固有例外の基底クラス。 |
| `NotFoundError` | 指定したデータソース、カラム、ダッシュボード、ワークシートなどが見つからない場合。 |
| `AmbiguousCaptionError` | 同じ表示名を持つ候補が複数あり、1件に特定できない場合。 |
| `ValidationError` | 保存前の検証でエラーが検出された場合。 |
| `UnsupportedFeatureError` | 未対応の編集処理を要求した場合。 |
| `SaveError` | 指定された形式で保存できない場合。 |

```python
from twbpatch import AmbiguousCaptionError, NotFoundError, TwbWorkbook

wb = TwbWorkbook.open("template.twb")

try:
    worksheet = wb.get_worksheet("売上推移")
except NotFoundError:
    print("ワークシートが見つかりません")
except AmbiguousCaptionError:
    # 内部名が分かる場合は name を明示して再検索できます。
    worksheet = wb.get_worksheet("SalesTrend", by="name")
```

## 編集と保存の例

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")
wb.create_calculated_field(
    datasource="売上データ",
    caption="粗利率",
    formula="SUM([粗利]) / SUM([売上])",
)
wb.save("output.twb", overwrite=True)
```
