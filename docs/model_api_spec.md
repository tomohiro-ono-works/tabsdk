# 接続型モデル API 仕様

## 1. 目的

`twbpatch` の公開 API を、`TwbWorkbook` にすべての操作を集約する構造から、各モデルが自身と関連リソースを操作する構造へ変更する。

本仕様では次を実現する。

- 公開 API では Tableau の利用者向け用語である `field` を使用する。
- 各モデルをメモリ上の Workbook XML に接続する。
- 取得 API を `get_*()` と複数形の戻り値へ統一する。
- 親モデルが関連リソースの取得・作成を担当する。
- 個体モデルが自身の更新・削除を担当する。
- ファイルへの書き込みは `TwbWorkbook.save()` に限定する。

## 2. 基本方針

### 2.0 クラス方式と API 方式

公開 API は 2 つの層からなる。**どちらも正であり、片方を非推奨にしない。**

| | クラス方式 | API 方式 |
|---|---|---|
| 何か | XML の構造を**踏襲しつつ体系化した**オブジェクトの階層 | クラス方式を内部で組み合わせ、まとまった処理を少ない引数で呼べるようにしたもの |
| 呼び方 | 親から辿って子を取り、その子を操作する | 1 回の呼び出しで完結する |
| XML への影響 | 1 操作が 1 箇所に対応する | 1 回の呼び出しで複数箇所が変わる |
| 例 | `datasource.get_fields()[0].update(name="売上")` | `workbook.draw_sheet(name="帳票", items=[...])` |

```python
# クラス方式
worksheet = workbook.get_worksheets(name="帳票")[0]
worksheet.add_field(field=field, shelf="rows")
worksheet.get_panes()[0].update(mark_type="bar")

# API 方式（上と同じことを 1 行で）
workbook.draw_bar(name="帳票", item=(...), metric=(...))
```

**クラス方式は XML の写しではない。** 構造を踏襲したうえで体系化する。
`TwbPane` は `worksheet/table/panes/pane` という階層を `worksheet.get_panes()` へ畳み、
`TwbField` は `datasource/column` と `datasource-dependencies` を 1 つのモデルにまとめる。

**API 方式はクラス方式の上に建てる。** API 方式が XML を直接組み立てることはしない。
クラス方式で表現できない操作を API 方式に持たせない。逆に、API 方式で書けるからといって
クラス方式の対応する操作を省かない。

命名規則（§3.3）と取得の契約（§4）は**クラス方式に適用する**。API 方式は動作を表す動詞名を持ち、
`get_*` / `create_*` / `update` / `delete` の枠には収めない。

現在の API 方式（`TwbWorkbook.draw_*()` / `add_filter()` / `set_default_font()` /
`apply_field_config()` / `TwbDashboard.build_report()`）は §6.14 に一覧する。

### 2.1 メモリ上の XML を唯一の正とする

`TwbWorkbook.open()` は対象ファイルを一度だけ読み込み、メモリ上に XML ツリーを保持する。

接続型モデルの取得・作成・更新・削除は、この XML ツリーだけを参照または変更する。各操作のたびに `.twb` / `.twbx` ファイルを再読込したり、ファイルへ直接書き込んだりしない。

```text
TWB/TWBX ファイル
        |
        | open（1回読込）
        v
TwbWorkbook ── メモリ上の XML ツリー
        |
        +── TwbDatasource
        |       +── TwbField
        |       +── TwbFolder
        |       +── TwbRelation / TwbRelationship
        |
        +── TwbWorksheet
        |       +── TwbWorksheetField（シェルフ配置）
        |       +── TwbPane
        |       |       +── TwbWorksheetField（エンコーディング）
        |       +── TwbReferenceLine / TwbWorksheetFilter
        |
        +── TwbDashboard
                +── TwbDashboardContainer
                |       +── TwbDashboardContainer
                |       +── TwbDashboardZone（Worksheet配置）
                +── TwbDashboardAction
                +── TwbFilterControl
```

### 2.2 接続型モデル

接続型モデルは、表示用の値だけでなく、元の XML 要素へ到達するための非公開コンテキストと安定した ID を保持する。

概念上、各モデルは次の情報を持つ。

```python
class ConnectedModel:
    _context: WorkbookContext
    _resource_type: str
    _id: str
```

- `_context` は `TwbWorkbook` が所有する XML ツリーと状態を参照する。
- `_id` は対象 XML 要素の `@name` を保持し、要素の再解決に使用する。
- XML に独立した `@name` がない関連リソースは、非公開の複合ロケーターで再解決する。
- XML 要素オブジェクトそのものは長期キャッシュしない。
- 公開プロパティは、アクセス時点のメモリ上 XML から値を取得する。
- 非公開コンテキストは `repr`、比較、JSON 出力へ含めない。

同じ XML 要素に対して複数のモデルインスタンスが生成されてもよい。すべて同じ XML ツリーを参照するため、一方の更新結果は他方からも取得できる。

`TwbWorksheetField` はフィールド定義ではなく配置を表す関連リソースであり、独立した XML `@name` がない場合がある。その場合は Worksheet ID、Pane ID、配置種別、参照先Field IDを組み合わせた非公開ロケーターを使用する。

### 2.3 接続対象と値オブジェクト

XML 上で独立したリソースとして操作する次のモデルを接続型とする。

- `TwbDatasource`
- `TwbField`（旧 `TwbColumn`）
- `TwbFolder`
- `TwbParameter`
- `TwbWorksheet`
- `TwbPane`
- `TwbWorksheetField`
- `TwbDashboard`
- `TwbDashboardContainer`
- `TwbDashboardZone`

次のモデルは、現時点では読み取り用の投影モデルとして扱う。更新 API を追加する時点で接続型への変更を検討する。

- `TwbRelation`
- `TwbRelationship`
- `TwbReferenceLine`
- `TwbWorksheetFilter`
- `TwbFilterControl`
- `TwbDashboardAction`

次のモデルは値オブジェクトまたは診断結果であり、Workbook へ接続しない。

- `BigQuerySource`
- `ExcelSource`
- `CsvSource`
- `UnknownSource`
- `TwbValidationMessage`
- `TwbUnsupportedFeature`

## 3. 命名規則

### 3.1 公開用語

- 公開 API と公開モデルでは `field` を使用する。
- Tableau XML の `<column>` 要素、`column` 属性、列シェルフなど、XML またはレイアウト自体を表す場合は `column` を維持する。
- `TwbColumn` は `TwbField` へ変更する。
- `TwbDatasource.columns` は廃止し、`TwbDatasource.get_fields()` へ変更する。
- `TwbWorksheet.columns` は列シェルフを表すため、名前を変更しない。

### 3.2 `id` と `name`

公開モデルでは、XML の用語をそのまま公開せず、利用者から見た意味へ変換する。

| 公開プロパティ | 取得元 | 意味 |
|---|---|---|
| `id` | XML の `@name` | Tableau 内部識別子 |
| `name` | 原則としてリソースの caption | 利用者向け表示名 |

caption がない、または空の場合、XML の `@name` を基に既定の表示名を生成して公開 `name` とする。`TwbField` では、外側の角括弧だけを除去する。

Datasource や Field では通常、要素自身の `@caption` を使用する。Worksheetは例外とし、Tableau上のシート名に対応するXMLの `@name` を公開 `id` と公開 `name` の両方に使用する。Worksheet要素に `@caption` が存在してもFieldのような別名として扱わない。Dashboardなど他のリソースは、既存のリソース固有の表示名解決規則を使用した後、XMLの `@name` へフォールバックする。

```text
<column name="[Sales]" caption="売上" />
    id   = "[Sales]"
    name = "売上"

<column name="[Profit]" />
    id   = "[Profit]"
    name = "Profit"
```

- 公開モデルに `caption` プロパティは設けない。表示名は `name`、内部参照は `id` とする。
  ただし、**XML 属性が真偽値であって表示名を指さない場合はこの規則の対象外**とする。
  `TwbFilterControl.show_caption`（XML の `show-caption`。フィルタカードの見出しを
  出すかどうか）が該当する。同じゾーンの `show-title`（`show_title`）とは別の属性なので、
  改名すると衝突する。
- caption がない場合のフォールバックは読取時の変換であり、XML に caption を自動追加しない。
- caption を表示名に使うリソースでは、caption を変更しても `id` は変更しない。
- caption を持たない要素では `id` と `name` が同じ値になる場合がある。
- **グループフィールドは例外とし、`caption` を付けない。** Tableau は表示名をそのまま
  `@name`（角括弧付き）に書き、階層など他の要素からもその名前で参照する（実測、
  `docs/backlog.md` L-5）。SDK が caption を足すと Tableau の書き方から外れるため、
  `create_group()` は `id == "[" + name + "]"` として作る。
- Worksheetでは常に `id == name == XML @name` とする。`worksheet.update(name=...)` は内部IDの変更でもあるため、対応するWindow、Dashboard Zone、Actionなどの参照を同時に更新する。
- 内部実装では、XML の `@name` を `xml_id`、公開表示名を `display_name` と呼び分ける。
- 曖昧なローカル変数名 `name` を XML 参照処理で使用しない。
- `get_*()` の `name=`、名前の重複検証、計算式の `name → id` 変換は、すべて同じ表示名解決規則を使用する。

表示名の変換は、各モデルで個別実装せず、共通処理へ集約する。

```python
xml_id = get_xml_id(element)
display_name = get_display_name(element)
```

関連リソースは次の例外的なID規則を持つ。

- `TwbPane.id` は XML の Pane ID とし、`name` がなければ Pane ID を表示名として使用する。
- `TwbWorksheetField.id` は配置ID、`name` は参照先 `TwbField.name` とする。
- `TwbWorksheetField.field_id` は参照先 `TwbField.id` とし、XML のフィールド参照には必ず `field_id` を使用する。
- `TwbDashboardContainer.id` と `TwbDashboardZone.id` は XML の Zone ID とする。
- Worksheetを配置した `TwbDashboardZone.name` は参照先 `TwbWorksheet.name`、`worksheet_id` は参照先 `TwbWorksheet.id` とする。

### 3.3 メソッド名

| 操作 | 規則 | 例 |
|---|---|---|
| 複数取得 | `get_<複数形>` | `get_datasources()`、`get_fields()` |
| 作成 | `create_<単数形>` | `create_calculated_field()` |
| 自身の更新 | `update()` | `field.update(name="売上", formula="SUM([Sales])")` |
| 自身の削除 | `delete()` | `field.delete()` |
| 関連付け | 動作を表す動詞 | `field.move_to_folder(...)` |
| 関連解除 | `remove_*` | `field.remove_from_folder()` |
| 非公開処理 | 先頭に `_` | `_resolve_element()` |

`list_*()` と、単一モデルを返す公開 `get_<単数形>()` は使用しない。

公開 `update_*()` は使用しない。formula、source、value、values など、モデル自身が所有する更新可能な値はすべて `update()` のキーワード引数として受け取る。値固有の変換と検証は `update()` 内部で処理する。

属性のグループも同様に `update()` のキーワード引数で受け取る。引数名はグループ名とする。

```python
worksheet.update(table_style={"header_bold": True, "column_widths": {"#": 36}})
container.update(style={"background_color": "#e6e6e6", "margin": 0})
```

- 引数名は `style=` / `table_style=` / `title_style=` のようにグループ名そのものとする。
- キー集合が固定のグループは `TypedDict`（`total=False`）で型を与える。
- キー集合が開いているグループは `dict[str, str | int | None]` とする。
- グループ内のキーを個別の引数へ展開しない。`update(header_bold=True)` の形は使用しない。

自身が所有する値の更新ではない操作は `update()` へ統合しない。他モデルを引数に取るもの、
または副作用として別要素を作るものは、動作を表す動詞名で公開する
（`set_customized_label(main_metric=...)` など）。

### 3.4 クラス名・変数名

- クラス名は単数形とする。
- コレクションを表す変数は複数形とする。
- `id` は XML の `@name` に対応する Tableau 内部 ID とする。
- `name` は解決済み caption、または XML の `@name` から生成した既定表示名とする。Worksheetは常にXMLの `@name` を使用する。
- 真偽値は原則として `is_*`、`has_*`、`include_*` を使用する。
- XML 固有の生データであることが重要な場合は、既存の `raw_*` または `attrs` を使用する。

### 3.5 XML 参照

XML 内の要素参照、計算式、フォルダ項目、ワークシート配置、フィルタ、ダッシュボード関連付けは、常に公開モデルの `id` に相当する XML 内部 ID を使用する。

- XML 参照へ公開 `name` を保存しない。
- 接続型モデルは `_id` から対象要素を解決する。
- caption の変更は参照先へ影響しない。Worksheetの `name` 変更はXML内部IDの変更でもあるため例外とし、参照元のIDを同時に更新する。
- caption がない場合も、参照には表示用フォールバックではなく `id` を使用する。
- 利用者が計算式などへ公開 `name` を指定した場合だけ、保存前に `name` から `id` へ変換する。
- 同じ公開 `name` が複数存在して参照先を一意に決められない場合、暗黙に選択せず例外にする。
- 曖昧な参照は `ref_map` または明示的な `id` で解決する。

## 4. 取得 API の契約

### 4.1 戻り値

すべての公開 `get_*()` は、取得件数にかかわらず `list` を返す。

```python
datasources = workbook.get_datasources()
fields = datasource.get_fields()
worksheets = workbook.get_worksheets()
```

- 0件は空リスト `[]` とし、正常系として扱う。
- 1件でも要素そのものには変換しない。
- 複数件でも例外にしない。
- 結果順は原則として XML の出現順とする。

**この規則の対象はリソースの取得である。** リソースとは、独立して
`update()` / `delete()` できる接続型モデルを指す。属性の読み取りは対象外とする。

- 引数を取らない属性の読み取りはプロパティとして公開する
  （`worksheet.table_style`、`zone.style`、`pane.mark_opacity`）。
  `update()` の同名キーワード引数で書き、同名のプロパティで読む対称形にする。
- 引数を取る取得はプロパティにできないため、`get_` / `set_` の対を維持する
  （`pane.get_categorical_colors(field)` / `set_categorical_colors(field, colors)`）。
  この `get_` はリソース取得ではないため `list` を返す義務を負わない。

### 4.2 絞り込み

取得メソッドは、必要に応じて `id` または `name` をキーワード引数として受け取れる。検索対象を切り替える `by` は使用しない。

```python
datasources = workbook.get_datasources(name="売上データ")
fields = datasource.get_fields(name="粗利率")
```

標準シグネチャは次の形とする。

```python
def get_resources(
    self,
    *,
    id: str | None = None,
    name: str | None = None,
) -> list[Resource]:
    ...
```

- `id` と `name` がどちらも未指定の場合は全件取得とする。
- `id` は XML 内部 ID との完全一致で検索する。
- `name` は共通の表示名解決規則で得た公開名と一致する要素を検索する。
- 同じ公開 `name` が複数存在する場合は全件返す。
- 一致しない場合は `[]` を返す。
- `id` と `name` の同時指定は禁止し、`ValueError` とする。
- 検索条件は位置引数で受け取らず、必ず `id=` または `name=` を明示する。

更新・削除は取得済みの個体モデルに対して行うため、公開 `name` の重複による対象の曖昧さを持ち込まない。

## 5. CRUD の責務

### 5.1 親モデルの責務

親モデルは、直接所有する関連リソースの取得と作成を担当する。

```python
datasource.get_fields()
datasource.create_calculated_field(...)

workbook.get_worksheets()
workbook.create_worksheet(...)
```

- 親モデルは複数種類の子リソースを所有するため、取得メソッドには対象を表す複数形を付ける。
- `get_*()` は既存リソースを0件以上返す。
- 作成メソッドには、作成対象を表す単数形を付ける。
- `create_*()` の引数はすべてキーワード専用とする。
- `create()` だけでは作成対象を判別できないため使用しない。
- 作成可能な種類が限定される場合は、`create_calculated_field()` のように種類を明示する。

### 5.2 個体モデルの責務

取得済みの個体モデルは、自身の更新と削除を担当する。

```python
field.update(name="売上金額", hidden=False)
field.update(formula="SUM([売上])")
field.delete()
```

- `update()` と `delete()` は取得済みモデル自身だけを対象とするため、対象名を付けない。
- 親モデルに `update_field()` や `delete_field()` は設けない。
- 関連付けと関連解除は、`move_to_folder()`、`remove_from_folder()` のように動作を明示する。
- 複数件の一括更新・一括削除が必要になった場合は、通常のCRUDとは別のバッチAPIとして設計する。

### 5.3 戻り値

| 操作 | 戻り値 |
|---|---|
| `get_*()` | `list[Model]` |
| `create_*()` | 作成した接続型モデル |
| `update()` | 更新後の同じ接続型モデル（`self`） |
| `delete()` | `None` |
| `remove_*()` | 操作対象の接続型モデル（`self`） |

### 5.4 更新引数

`update()` はキーワード引数だけを受け付ける。未指定と `None` を区別する必要があるため、実装では非公開の `UNSET` センチネルを使用する。

- `UNSET` は変更しないことを表す。
- `None` を許可する属性では、値の削除または既定値への復帰を表せる。
- `None` を許可しない属性へ指定した場合は例外にする。
- formula 固有の `formula_ref`、`strict`、`ref_map` は、formula を指定した場合だけ有効とする。
- formula を指定せずformula固有オプションだけを指定した場合は例外にする。

### 5.4a フィールドを受け取る引数

フィールドを指す引数は**1 つにまとめ、3 通りの型を受ける**。`field=` と `field_name=` のように分けない。

| 渡す値 | 解決 |
|---|---|
| `TwbField` | そのまま使う |
| `("データソース名", "フィールド名")` | データソースを名前で解決してから探す |
| `"フィールド名"` | 呼び出し先の文脈から探す（下記） |

```python
worksheet.add_field(field="カテゴリ", shelf="rows")
worksheet.add_field(field=("売上データ", "カテゴリ"), shelf="rows")
worksheet.add_field(field=field_obj, shelf="rows")
```

**素の文字列の文脈**は、呼び出し先が既に依存しているデータソースとする。

- ワークシートとペインは、そのワークシートの `datasource-dependencies` から探す。
- 依存が無い場合、ワークブックのデータソースが 1 つだけならそれを使う。
- 複数あって 1 つに決まらない場合は暗黙に選ばず `AmbiguousCaptionError` にする（§3.5）。
- API 方式で `datasource` 引数を取るものは、それが文脈になる。

**引数はキーワード専用とする。** 位置引数で受けない（§4.2 と §5.4 に揃える）。

解決処理は 1 箇所へ集約する。各メソッドが個別に実装すると、受け付ける型が
メソッドごとにずれる。

### 5.5 操作の原子性

1回の `create`、`update`、`delete` は、引数と対象を検証してから XML を変更する。処理が例外になった場合、そのメソッドによる変更を途中状態で残さない。

複数メソッドをまとめたトランザクションや自動ロールバックは初期仕様に含めない。未保存の変更をすべて破棄する場合は `reload()` を使用する。

## 6. クラスごとの公開 API

### 6.1 `TwbWorkbook`

`TwbWorkbook` は XML ツリー、ファイル入出力、トップレベルリソースを管理する。

```python
TwbWorkbook.open(path)

workbook.get_datasources(id=None, name=None)
workbook.get_parameters(id=None, name=None, include_hidden=False)
workbook.get_worksheets(id=None, name=None)
workbook.get_dashboards(id=None, name=None)

workbook.validate()
workbook.get_unsupported_features()
workbook.export_json()
workbook.reload()
workbook.save(path, validate=True, overwrite=False)
```

次の作成メソッドを追加する。以下は初期実装用の暫定仕様とし、実ファイルでの互換性確認後に確定する。

```python
workbook.create_worksheet(
    name=name,
    visible=True,
)

workbook.create_parameter(
    name=name,
    value=value,
    datatype="string",
    domain_type="any",
    allowable_values=None,
    min_value=None,
    max_value=None,
    step_size=None,
    hidden=False,
)

workbook.create_dashboard(
    name=name,
    width=1200,
    height=800,
    sizing_mode="fixed",
)
```

新規Dashboardは既定で固定 `1200 × 800` とする。自動サイズを使用する場合は `sizing_mode="automatic"` を明示する。

新規Worksheetの暫定仕様は次のとおりとする。

- `name` を公開 `name` とXML内部 `id`の両方に使用し、冗長な `caption` は作成しない。
- 利用者が内部IDを指定する引数は設けない。SDKがXML内部IDと参照マッピングを管理する。
- 同じ `id` または公開 `name` が存在する場合は `ValueError` とする。
- 空の `view` と、ID `"1"`・mark type `"automatic"` の標準Paneを1つ作成する。
- Datasource dependency は作成時に指定せず、`worksheet.add_field()` / `pane.add_field()` の初回配置時に追加する。
- `visible=False` の場合だけ、対応するWindowへ `hidden="true"` を作成する。

新規Parameterの暫定仕様は次のとおりとする。

- 内部 `id` は表示名から決定的に生成した `[<name>]` とし、ハッシュを使用しない。
- 利用者が内部IDを指定する引数は設けない。SDKがXML内部IDと参照マッピングを管理する。
- XMLの `caption` には利用者向けの `name` を保存する。
- `datatype` は `"string"`、`"integer"`、`"real"`、`"boolean"`、`"date"`、`"datetime"` を初期対応値とする。
- `domain_type` は `"any"`、`"list"`、`"range"` を初期対応値とする。
- `list` では `allowable_values` を必須とし、`list[value]` または挿入順を保持する `dict[value, display_name]` を受け付ける。現在値が候補に含まれない場合は `ValueError` とする。
- `range` では `min_value` と `max_value` を必須とし、`step_size` は任意とする。現在値が範囲外の場合は `ValueError` とする。
- `any` へ候補値または範囲引数を指定した場合は `ValueError` とする。
- Parameters Datasource が存在しない場合は遅延作成する。
- 同じ `id` または公開 `name` が存在する場合は `ValueError` とする。

**Datasource の作成は Tableau 抽出（.hyper）に限る**（2026-09-13）。CSV / Excel / BigQuery などの
一般的な作成（backlog H-2）は不採用のままとし、KPI ツリーのエッジ用に .hyper だけを足す。

```python
workbook.create_hyper_datasource(
    name=name,
    path="edge.hyper",
    fields=[{"name": "edge", "datatype": "string", "role": "dimension"}, ...],
)
```

- **.hyper の中身はライブラリで読めないため、列は呼び出し側が `fields` で宣言する。** ファイルとは突き合わせない
- `fields` の各要素は `name`（.hyper の表の列名）/ `datatype` / `role` の 3 キー。`datatype` は実測した
  `"string"` / `"integer"` だけを受け付け、他の型は Tableau の保存形を見てから足す
- XML は Tableau が「テキストファイルに接続して抽出を作った」ときの保存形に合わせる。抽出の `dbname` に `path` を、
  テキスト側には同じフォルダの `<ファイル名>.txt` を書く。テキストは抽出を開くときに参照されない前提
- 抽出の表は Tableau の既定の `[Extract].[Extract]` とする
- 内部 `id` は `federated.` ＋ 28 文字の英小文字・数字。公開 `name` は `caption` に保存する
- 同じ公開 `name` の Datasource がある、`path` が `.hyper` でない、`fields` が空・重複・未対応の型や役割の場合は
  `ValueError` とし、XML を変更しない

WorksheetとParameterの作成は、既存の `.twb` / `.twbx` を開いたWorkbookへの追加を対象とする。0からWorkbook全体を生成する機能は初期対象外とする。

- 対象Tableauバージョンを利用者が引数で指定するAPIは設けない。
- Workbookの既存バージョン情報、名前空間、近接する既存XML構造を維持・再利用する。
- 安全に互換構造を生成できない場合は推測で追加せず、XMLを変更しないまま `UnsupportedFeatureError` とする。

### 6.2 `TwbDatasource`

```python
datasource.get_fields(id=None, name=None)
datasource.get_folders(id=None, name=None)
datasource.get_relations(id=None, name=None)
datasource.get_relationships(id=None, name=None)

datasource.create_folder(name="KPI")

datasource.create_calculated_field(
    name=name,
    formula=formula,
    datatype=datatype,
    role=role,
    discrete=discrete,
    folder=folder,
    hidden=hidden,
    formula_ref=formula_ref,
    strict=strict,
    ref_map=ref_map,
)

datasource.update(source=UNSET, name=UNSET)
datasource.delete()
```

`source` は接続先を表す値オブジェクトとして公開プロパティから取得する。単一値であるため `get_source()` は設けない。

### 6.3 `TwbField`

```python
field.update(
    name=UNSET,
    role=UNSET,
    discrete=UNSET,
    hidden=UNSET,
    formula=UNSET,
    formula_ref="auto",
    strict=True,
    ref_map=None,
)

field.move_to_folder(folder)
field.remove_from_folder()
field.delete()
```

`folder` は同じ `TwbDatasource` のフォルダ名（文字列）か、そのデータソースに接続された `TwbFolder` とする。文字列で渡した場合、そのフォルダが無ければ `NotFoundError` にする。**暗黙には作らない。**

`create_folder_if_missing=True`（既定 `False`）を渡したときだけ、その名前でフォルダを作って割り当てる（2026-09-07 決定）。旧 `TwbWorkbook` の `folder=` は黙って作っていたが、打ち間違いに気づけないため**作るときは明示する**形にした。`TwbFolder` を渡す場合はすでに実在するのでフラグは効かない。

**`folder=` と `create_folder_if_missing=` を受け取るメソッドはすべて同じ規則に従う。** `create_calculated_field()`、`create_calculated_fields()`、`create_drill_path()`、`create_group()`、`field.move_to_folder()` の 5 つ。解決は `TwbDatasource._resolve_folder()` に集約する（2026-09-07 に `move_to_folder()` も揃えた）。

フォルダ所属は独立した関連操作とし、`field.update(folder=...)` には含めない。

### 6.4 `TwbFolder`

```python
folder.get_fields(id=None, name=None)
folder.delete()
```

フォルダは XML の `@name` が表示名と内部識別子を兼ねる。安全な参照更新を伴う名前変更を実装するまで `folder.update(name=...)` は公開しない。

フォルダが空になった場合に自動削除するかどうかは別仕様とする。初期仕様では自動削除しない。

### 6.5 `TwbParameter`

```python
parameter.update(value=UNSET, allow_hidden=False)
parameter.delete()
```

パラメータの作成は `TwbWorkbook.create_parameter()` が担当する。初期引数と検証規則は `TwbWorkbook` の暫定作成仕様に従う。

### 6.6 `TwbWorksheet`

```python
worksheet.get_fields(id=None, name=None)
worksheet.get_panes(id=None, name=None)
worksheet.get_reference_lines(id=None, name=None)
worksheet.get_filters(id=None, name=None)

worksheet.add_field(
    field,
    shelf=shelf,
    aggregation=aggregation,
    discrete=discrete,
)

worksheet.set_subtotal_visibility(field=field, visible=True)

worksheet.update(name=UNSET, visible=UNSET, grand_totals=UNSET)
worksheet.delete()
```

**総計と小計は置き場所を分ける。** どちらも `TwbWorksheet` が持つが、§3.3 の区分に従う。

| | 公開形 | XML |
|---|---|---|
| 総計 | `update(grand_totals=...)` とプロパティ `grand_totals` | `<table>` の `<rows total onTop>` / `<cols total onLeft>` |
| 小計 | `set_subtotal_visibility(field=, visible=)` | `<table>/<subtotals>/<column>` |

総計はワークシート自身のスカラー設定なので `update()` のグループ引数とし、
キー集合が固定なので `GrandTotals` を `TypedDict` で定義する。
小計は対象を `TwbWorksheetField` で受けるため `update()` へ統合せず、動詞名で公開する。

`grand_totals` のキーは**合計が現れる位置**を表す。値は位置、`None` は総計を付けないこと。

| キー | 値 | 意味 |
|---|---|---|
| `row` | `"top"` / `"bottom"` / `None` | 合計行。Tableau UI の「列の総計」 |
| `column` | `"left"` / `"right"` / `None` | 合計列。Tableau UI の「行の総計」 |

シェルフ名（`rows` / `columns`）をキーにしない。Tableau UI の「行の総計」は XML では
`<cols>` 側にあたり、`add_field(shelf=...)` の語と逆転して取り違えるため。

`set_subtotal_visibility()` の `field` は `rows` または `columns` へ配置済みの
`TwbWorksheetField` に限る。`visible=False` で `<column>` を外し、`<subtotals>` が
空になれば要素ごと削除する（XSD が `<column>` を 1 件以上要求するため）。

合計の集計方法（`column-instance/@visual-totals`）は初期対応に含めない。

`TwbWorksheet.get_fields()` は配置情報を表す `list[TwbWorksheetField]` を返す。`TwbDatasource.get_fields()` が返す `list[TwbField]` とはクラスの文脈と戻り値型で区別する。

`worksheet.add_field()` は、既存の `TwbField` をシェルフへ配置し、接続型の `TwbWorksheetField` を返す。フィールド定義を新規作成する処理ではないため、`worksheet.create_field()` は設けない。

`shelf` は次の値を受け付ける。

- `"rows"`
- `"columns"`
- `"pages"`
- `"filters"`

`aggregation` は小文字で受け取り、初期対応値を `"sum"`、`"avg"`、`"min"`、`"max"`、`"count"`、`"countd"`、`"attr"` とする。`discrete` は `bool | None` とし、`None` はフィールド定義または既存配置の値を使用する。

`field` は同じ `TwbWorkbook` に接続された `TwbField` に限る。必要な datasource dependency を安全に追加できない場合は、XML を変更せず `UnsupportedFeatureError` とする。

### 6.7 `TwbPane`

`TwbPane` は Worksheet 内のPaneとマークカードを表す接続型モデルとする。

```python
pane.get_fields(id=None, name=None)

pane.add_field(
    field,
    encoding=encoding,
    aggregation=aggregation,
    discrete=discrete,
)

pane.update(mark_type=UNSET)
```

`pane.add_field()` は既存の `TwbField` をエンコーディングへ配置し、接続型の `TwbWorksheetField` を返す。

`encoding` は次の値を受け付ける。

- `"color"`
- `"label"`
- `"size"`
- `"detail"`
- `"tooltip"`
- `"shape"`
- `"path"`
- `"angle"`

`pane.add_field()` の `aggregation` と `discrete` は `worksheet.add_field()` と同じ規則を使用する。

公開 `mark_type` は小文字で受け取り、保存時に Tableau XML の表記へ変換する。初期対応値は `"automatic"`、`"bar"`、`"line"`、`"text"`、`"circle"`、`"square"`、`"shape"`、`"area"` とする。

複数Paneを持つWorksheetでは、`worksheet.get_panes()` から対象Paneを明示的に選択する。Paneを省略して暗黙に先頭Paneへ配置するAPIは設けない。

### 6.8 `TwbWorksheetField`

`TwbWorksheetField` は、Datasourceのフィールド定義ではなく、WorksheetまたはPane上の配置を表す接続型モデルとする。

```python
placed_field.update(
    aggregation=UNSET,
    discrete=UNSET,
)

placed_field.delete()
```

- `delete()` は配置だけを解除し、参照先 `TwbField` は削除しない。
- `field_id` は参照先 `TwbField.id` とする。
- `name` は参照先 `TwbField.name` とする。
- `shelf` または `encoding` により配置種別を判別できるようにする。
- Pane上の配置は `pane_id` を保持する。

### 6.9 `TwbDashboard`

```python
dashboard.get_worksheets(id=None, name=None)
dashboard.get_fields(id=None, name=None)
dashboard.get_containers(id=None, name=None)
dashboard.get_zones(id=None, name=None, **layout_options)
dashboard.get_actions(id=None, name=None)
dashboard.get_filter_controls(id=None, name=None)

dashboard.create_container(direction="horizontal")

dashboard.add_floating_worksheet(
    worksheet,
    x=0,
    y=0,
    width=600,
    height=400,
    show_title=True,
)

dashboard.update(name=UNSET, visible=UNSET)
dashboard.delete()
```

`TwbDashboard.get_fields()` は、配下ワークシートの配置情報を表す `list[TwbWorksheetField]` を返す。

タイル配置を標準とする。`dashboard.create_container()` はルートのタイルコンテナを作成する。浮動配置は重ね表示など明示的に必要な場合だけ `add_floating_worksheet()` / `add_floating_text()` / `add_floating_parameter_control()` を使用する。

**浮動のオブジェクトは `<zones>` の直下へ置く**（2026-09-22 に実ダッシュボードで確認）。
レイアウトのコンテナの中には入れず、`x` / `y` / `w` / `h`（台紙を 100000 とした比率）を
持たせる。`zone` に `floating` のような属性は無く、**コンテナの外にあること自体が浮動**を表す。
テキストは `type-v2="text"` に `<formatted-text><run>`。文字揃えは `run/@fontalignment`
（`0`=左 / `1`=中央 / `2`=右）。

Dashboardはタイル配置用のルートコンテナを最大1つ持つ。`dashboard.get_containers()` はルートコンテナを返し、既に存在する状態で `create_container()` を呼び出した場合は `ValueError` とする。ネストしたコンテナは親 `TwbDashboardContainer.get_containers()` から取得する。

### 6.10 `TwbDashboardContainer`

`TwbDashboardContainer` はタイル配置の水平・垂直コンテナを表す接続型モデルとする。

```python
container.get_containers(id=None, name=None)
container.get_zones(id=None, name=None)

container.create_container(
    direction="vertical",
    order=None,
    weight=1,
)

container.add_worksheet(
    worksheet,
    order=None,
    weight=1,
    show_title=True,
)

container.update(
    direction=UNSET,
    order=UNSET,
    weight=UNSET,
)

container.delete()
```

- `direction` は `"horizontal"` または `"vertical"` とする。
- `order=None` は同じ親コンテナの末尾へ追加する。
- `order` を指定する場合は0始まりの整数とし、兄弟要素を含めて順序を正規化する。
- `weight` は正の数とし、同じコンテナ内の兄弟要素との相対比率を表す。
- `worksheet` は同じ `TwbWorkbook` に接続された `TwbWorksheet` とする。
- コンテナ内へ浮動要素は追加しない。

`create_container()` と `add_worksheet()` はタイル配置を作成するため、`x`、`y`、`width`、`height` を受け付けない。

### 6.11 `TwbDashboardZone`

`TwbDashboardZone` は、Dashboard上に配置されたWorksheetまたはその他の表示要素を表す接続型モデルとする。

```python
zone.update(
    order=UNSET,
    weight=UNSET,
    x=UNSET,
    y=UNSET,
    width=UNSET,
    height=UNSET,
    show_title=UNSET,
)

zone.delete()
```

- タイルZoneは `order` と `weight` を更新できる。
- タイルZoneへ `x`、`y`、`width`、`height` を指定した場合は `ValueError` とする。
- 浮動Zoneは `x`、`y`、`width`、`height` をピクセルで更新できる。
- 浮動Zoneへ `order` または `weight` を指定した場合は `ValueError` とする。
- Worksheet Zoneの `delete()` は配置だけを削除し、参照先Worksheetは削除しない。
- `placement_mode` プロパティは `"tiled"` または `"floating"` を返す。
- 既存の `layout` プロパティは `"default"`、`"phone"` などのデバイスレイアウト名を表すため、配置方式には使用しない。

### 6.12 タイル座標の計算

タイル配置でもXMLには現在の描画結果として `x`、`y`、`w`、`h` を保存する。ただし、これらを公開作成APIの入力値にはしない。

SDKは次の情報から座標とサイズを計算する。

- Dashboardのキャンバスサイズ
- コンテナの `direction`
- 子要素の `order`
- 子要素の `weight`
- 親子コンテナの階層

固定サイズDashboardではピクセル値とTableau内部座標を計算する。自動サイズDashboardでは内部の正規化座標を計算し、実際のピクセル配置はTableauが表示時に決定する。

Tableauはファイルを開く際にコンテナ階層・順序・サイズ制約を基に配置を正規化する場合がある。SDKは、Tableauによる正規化後も同じ順序と比率になるXML構造を生成する。

### 6.13 既存Dashboardの編集

既存Dashboardを編集する場合、SDKは現在のコンテナ・Zone階層を接続型モデルとして読み取り、レイアウトツリー全体を再構築しない。

- 変更対象として指定されたコンテナまたはZoneだけを編集する。
- 追加・削除に伴う座標再計算は、原則として変更対象の親コンテナ配下に限定する。
- 対象外の兄弟コンテナ、浮動Zone、アクション、フィルタコントロールを維持する。
- SDKが解釈しない属性と子要素を削除しない。
- デフォルト以外のデバイスレイアウトを暗黙に変更しない。
- 対象コンテナを安全に特定できない場合、推測で再構築せず例外にする。
- Dashboard全体を作り直す操作が将来必要になった場合は、通常の編集APIとは別の明示的なAPIとして設計する。

未実装の操作は、呼び出すと常に失敗するスタブとして追加しない。XML 更新処理と検証を実装する時点で公開する。

### 6.14 API 方式

§2.0 の API 方式にあたる公開メソッド。いずれもクラス方式の上に建てる。

**`TwbWorkbook`**

| メソッド | 何をするか |
|---|---|
| `draw_sheet()` | 項目を指定シェルフへ並べた土台シート |
| `draw_bar()` | 棒グラフ |
| `draw_card()` | KPI カード |
| `draw_quadrant()` | 散布図の四象限 |
| `draw_crosstab()` | ヒートマップ付きクロス集計 |
| `build_kpi_tree()` | 既にあるシートを指標の親子関係のツリーとして左から右へ並べた Dashboard を作る |
| `add_index_relation()` | ウォーターフォールグラフ向けに、連番だけを持つ表をデータソースへ `1=1` でクロスジョインする（①） |
| `build_waterfall_metric()` | ウォーターフォールグラフ向けに、指標を縦持ちに変換した計算フィールドを作る（②③） |
| `build_waterfall_chart()` | ウォーターフォールグラフのワークシートを組む（④） |
| `build_waterfall()` | ①〜④を 1 回でまとめて行う（設定画面向け。連番テーブルはデータソースにつき 1 つを共有） |
| `draw_info()` | アイコン + カスタムツールヒントだけの説明用ワークシートを作る |
| `add_filter()` | フィルターの入口。`scope="worksheet"` / `"datasource"` を引数で選ぶ |
| `set_default_font()` | ワークブック全体の既定フォント |
| `apply_field_config()` | YAML でフィールドの改名とフォルダ分類を一括適用 |
| `apply_config()` | 設定画面が出力した YAML を適用する。受け手が無い節は読み飛ばす |
| `export_json()` | ワークブックの内容を辞書で取り出す |
| `export_html()` | 設定画面の HTML を 1 ファイル出力する（`docs/html_screen_spec.md`） |

#### 棒グラフの二重軸（2026-09-22）

`draw_bar()` の `item` は任意。省くとディメンションを置かず、並べ替えもせず、棒を 1 本描く。

重ねる指標は `sub_metric`（バーインバー）と `line_metric`（二重軸の折れ線）。
**Tableau の二重軸は 2 軸までなので、3 つそろえるときだけ組み方が変わる。**

| 指定 | 軸 1 | 軸 2 | 軸の同期 |
|---|---|---|---|
| `sub_metric` だけ | メイン（棒） | サブ（棒・細く） | する |
| `line_metric` だけ | メイン（棒） | 折れ線 | しない |
| 両方 | メジャーバリュー（メイン＋サブの棒・スタックを外して重ねる） | 折れ線 | しない |

3 つそろえたときは、**棒 2 本が同じ太さになり、色もメジャーネームの配色になる**
（1 つのペインに太さも色も 1 つしか持てないため、`bar_color` / `sub_bar_color` は効かない）。

土台は `TwbWorksheet.set_dual_axis(shelf=, fields=, synchronized=)`。Tableau の書き方は
実ワークブックで確認した。

- シェルフのピルを `+` で連結する。2 本なら `(A + B)`、3 本なら `(A + (B + C))`。
  `/` は入れ子で、**横に並ぶ別の軸**になる（重ならない）
- 軸の書式へ 2 本目以降の
  `<encoding attr="space" class="0" field="<ピル>" field-type="quantitative" fold="true"
  scope="cols|rows" synchronized="true" type="space"/>` を足す。
  `fold` が「重ねる」、`synchronized` が「軸の同期」。同期しないときは属性を書かない
- 描画は軸ごとに分かれる。`<pane x-axis-name="<ピル>">`（行に置いたなら `y-axis-name`）が
  マークの種類・色・太さを持つ。先頭に軸名を持たない土台のペインが 1 つ付くので、
  `get_panes()` は土台・各軸の順に返る

#### メジャーバリューとスタック（2026-09-22）

1 つの軸へメジャーを何本でも並べるのが
`TwbWorksheet.add_measure_values(shelf=, fields=, aggregation=, color=)`。
Tableau は 3 か所に書く（実ワークブックで確認）。

- シェルフのピルは `[<データソース>].[Multiple Values]` の 1 本だけ
- 中身は `[:Measure Names]` へのカテゴリフィルタで、`<groupfilter function="union">` に
  集計済みの参照を `member='"<参照>"'` として並べる
- `[:Measure Names]` を `<slices>` へ足し、色に載せて描き分ける。
  **色を載せるのはメジャーバリューの軸のペインだけ**（二重軸の相手のペインに載せると、
  そちらのマークまで色で分かれる）

積み上げは `TwbPane.update(stacked=)`。`<pane><view><breakdown value>` に書き、
公式スキーマ（[tableau/tableau-document-schemas](https://github.com/tableau/tableau-document-schemas)
の `StackingMode-ST`）では `on` / `off` / `auto` の 3 値。既定の `auto` では棒が積み上がるので、
重ねて描くときは `off`。

**生成した XML は公式スキーマ（twb_2026.2.0.xsd）で検証済み**（2026-09-22）。
なお公開されている XSD は `user:` 名前空間の属性グループ定義を含まないため、
検証にはその参照を外す必要がある。

#### 帳票の揃えと、中に入れる棒・色付け（2026-09-22）

`draw_sheet()` の揃えは**数字が右・文字が左**。Tableau は不連続のピルの揃えを
`<table><style><style-rule element="label">` に `field` 付きで書く
（examples/サンプル.twb と実ダッシュボードの 2 本で確認）。
表ヘッダー（フィールドラベル、`style-rule element="field-labels"` の背景）は
薄い灰色 `#f0f0f0`。

**数値を不連続で置くときのトークンは `:ok`（ordinal）。** `:nk`（nominal）にすると
Tableau が数値を文字として扱う（2026-09-22 修正。`column-instance/@type` も合わせる）。

`bar_metrics` は棒の列、`color_metrics` は色帯の列として横に足す。

| 列 | 軸 | ペイン |
|---|---|---|
| 棒 | メジャーを連続で置き、`display=false` で隠す | マークは Bar |
| 色帯 | `{シート名}_色帯{n}`（`MIN(1)`）を 0〜1 に固定して隠す | GanttBar。長さに `{シート名}_色帯幅{n}`（`MIN(-1)`）、色にメジャー |

**棒・色帯の列の項目名だけ、浮動テキストで補う**（2026-09-22）。**Tableau は行に置いた
項目の名前は出すが、棒・色帯の列の名前だけ出さない**（実ファイルで確認）。行に置いた分まで
置くと見出しが二重になるので、空いている分にだけ重ねる。

`draw_sheet()` は列の並びを `WorkbookContext.sheet_columns` へ覚えるだけ。
**列幅は `build_report()` が「ゾーンの幅 − 余白 ÷ 列数」で決める**（2026-09-22 指定）。
同じ幅を行見出し（`style-rule element="header"` の `width`）と棒・色帯の列
（ペインの `minwidth`/`maxwidth`）へも書くので、文字と実際の列が揃う。
行見出しの幅は**表示名ではなくピルの参照**で書く（同じメジャーが行にも列にも居ると
名前では一意に決まらない）。**幅も位置も概算で、置いたあと Tableau で人が直す前提。**

**どちらの列も、値をラベル（`text` エンコード）で出す。** 列へ置いただけでは数字が
見えない（2026-09-22 修正）。ペインに `mark-labels-show` / `mark-labels-cull` を書き、
ラベルは右に揃える（`style-rule element="cell"` の `text-align`）。

**色は列ごとに指定する。棒は 1 色、色帯は 2 色**（薄い側 → 濃い側の濃淡、2026-09-22 指定）。
2 色は `TwbPane.set_continuous_colors(min_color=, max_color=)` が `<preferences>` へ
`<color-palette custom="true" type="ordered-sequential">` として書き、マークの色の
エンコードがその名前を参照する（3 色を渡すと `ordered-diverging`。`draw_crosstab` と同じ仕組み）。

**軸は重ねない**（`set_dual_axis(overlay=False)` = `fold` を書かない）ので、列は横に並び、
何本でも足せる。色は `<style-rule element="mark"><encoding attr="color" palette="…"
type="interpolated"/>` で段階のない配色にする。

#### メジャーの集計は `"auto"` で自動判定する（2026-09-22 に棒グラフも統一）

`draw_*()` の `aggregation` 系の引数は既定が `"auto"`。フィールドの役割・データ型・式を見て
決めるので、人が選ぶ必要がない（設定画面もこの引数を出さない）。

| フィールド | 置き方 |
|---|---|
| 式の中に集計関数がある計算フィールド（それを参照する計算フィールドも含む） | `agg` → `usr:` → `derivation="User"` |
| 数値のメジャー | 既定の集計、無ければ `sum` |
| それ以外 | `countd` |

**集計済みの式を `sum` で置くと二重に集計される。** `draw_bar()` だけ `aggregation="sum"` に
固定していたため、`SUM([売上]) / SUM([売上(昨年)])` のような計算フィールドが合計として
置かれていた（2026-09-22 修正）。置いたピルだけでなく、**並べ替えの基準
（`computed-sort/@using`）も同じ集計にそろえる。**

`add_measure_values()` は `aggregations=` でメジャーごとに集計を指定できる。
1 つの軸に集計済みの式とふつうのメジャーが混ざるため。

#### `draw_quadrant()` の外れ値フィルター（2026-09-24）

外れ値でグラフの外形が崩れないよう、そのシート専用のパラメータ 2 つで点を絞る。
引数は増やさず、初期値は固定（決定: 中央比率 0.95、売上閾値 0）。

| 名前 | 内容 |
|---|---|
| パラメータ `{シート名}_中央比率`（実数・0.1〜1・刻み 0.05） | X・Y それぞれ、中央値を中心に中央の r 割だけ残す。パーセンタイルの範囲は 0.5 ± r/2 |
| パラメータ `{シート名}_売上閾値`（実数） | 集計後のサイズ指標がこの値以上の点だけ残す |
| 計算フィールド `{シート名}_中央範囲`（真偽・表計算） | `RANK_PERCENTILE(式)` が `(1-r)/2` 以上 `1-(1-r)/2` 以下か（X・Y とも）。点（`item`）に沿って計算する。**`WINDOW_PERCENTILE` は第 2 引数がリテラルしか受けず、パラメータを入れるとエラーになる**（2026-09-25 ユーザー報告）ので使わない |
| 計算フィールド `{シート名}_売上閾値以上`（真偽・集計） | `サイズ指標 >= 閾値` |

真偽値のフィールドはフィルターシェルフへ置き、`true` だけを選ぶ（`member="true"`、引用符なし）。
この `true` の書き方は 2026-09-25 に Tableau で開いて動作を確認した（ユーザー確認）。
売上閾値は集計フィルター（表計算より前）、中央比率は表計算フィルター（集計後）なので、
中央値の算出は閾値を通った点だけで行われる。
`build_report()` は、`draw_quadrant()` のシートの右上へ 2 つのパラメータコントロールを
浮動で横に並べる（左が中央比率、右が売上閾値。`add_floating_parameter_control()`）。
パラメータと計算フィールドは、`{シート名}_四象限` と同じく作り直す。

#### `draw_*()` が作る計算フィールドは作り直す（2026-09-22）

`draw_card(mode="budget")` の `{シート名}_達成` ほか 3 本と、`draw_quadrant()` の
`{シート名}_四象限` は、**そのシートの持ち物**として扱う。同名のフィールドが既にあれば
消してから作り直す。指標を変えて描き直したときに、古い式が残らないようにするため。

`TwbDatasource.create_calculated_field()` 自体は作成専用のままで、同名があれば
`ValueError: caption already exists`（§5 の `create_*()`）。作り直すかどうかは呼ぶ側が決める。
設定 YAML の `calculations` 節は `update()` で上書きする（`config_apply.py`）ので、
同じ名前を定義していても `draw_*()` の式が後から上書きする。

**同名のシートが残っているときは、計算フィールドを触る前に
`ValueError: worksheet already exists` で止める。** 先に作り直そうとすると、そのシートが
参照しているせいで消せず `ResourceInUseError` になり、何が起きたのか分からないため。
どちらにしても `create_worksheet()` で止まるので、同じ文言を先に出す。

**`draw_card(mode="budget", folder=...)` で 4 本を同じフォルダへ入れられる**（2026-09-22、
`build_waterfall_metric()` / `add_index_relation()` の `folder=` と同じ形）。既存の
`create_calculated_field(folder=, create_folder_if_missing=True)` をそのまま使うだけで、
フォルダを作る専用の仕組みは新設していない。KPI ツリー（`build_kpi_tree()`）自体は
計算フィールドを作らないので対象外（作るのは KPI カード側の `draw_card()`）。

#### `build_kpi_tree()` はシートを作らず並べるだけ

既にあるシート（通常は `draw_card()` の KPI カード）を、指標の親子関係のツリーとして左から右へ
並べた Dashboard を作る。**KPI ツリー専用のグラフは作らない**（2026-09-13 決定）。
`build_report()` が既存シートを並べるだけなのと同じ分担にする。

```python
card = workbook.draw_card(datasource, name="売上", main_metric="売上")
workbook.build_kpi_tree(dashboard_name="KPIツリー", root=KpiNode(card, [...]), align="top")
```

入力は値オブジェクト `KpiNode(worksheet, children=[])` で、`twbpatch` から公開する。
`children` が空のノードがツリーの末端になる。**Tableau の階層（`TwbDrillPath`）とは別物**で、
こちらは指標同士の親子関係を表す。

- **`draw_` を付けない。** `draw_*()` はグラフ生成で、設定画面がグラフ種類の一覧を作る対象になる
- **`TwbDashboard` ではなく `TwbWorkbook` に置く。** 大きさはツリーから決まるが、
  `TwbDashboard.update()` は大きさを変えられないため、計算してから Dashboard ごと作る
- ノードの大きさは 横 200 × 縦 150 に固定し（2026-09-14 に 400 × 300 から半分へ）、引数に出さない。ノードごとに変えると、兄弟でカードの
  高さがばらついて揃わなくなる
- Dashboard の大きさは 幅 = 階層の深さ × 200、高さ = 末端ノードの数 × 150 に、台紙の余白（上下左右 8）を足す（固定サイズ）
- **見た目は `build_report()` の KPI カードに揃える**（2026-09-14）。ツリー全体のコンテナを灰色の台紙
  （背景 #f5f5f5・枠線なし・外側の余白 8）にし、カードのゾーンを白（背景 #ffffff・枠線なし・外側の余白 4・内側の余白 0・角の丸み 8）にする。
  カードのタイトルは `build_report()` と同じく、シートにタイトルがあるときだけ出す。枠線は引かず、台紙との余白で区切って見せる
- **台紙の書式は `content_style=` で上書きできる**（2026-09-14）。`build_report(content_style=)` と同じく既定に重ね、
  設定 YAML からはデザインルールの「余白」がここに入る。台紙の外側と内側の余白の合計だけ Dashboard を大きくするため、
  余白は 0 以上の整数に限り、XML を変える前に検証する。エッジ用シートの背景は台紙の背景色に揃える
- `align="center"` は親カードを子の範囲の縦中央に、`"top"` は上端に置く
- **タイル配置で組む。** ノード列とカードを `fixed_size` で固定し、余りを `add_spacer()` で埋める。
  コンテナの最後の子は固定サイズでも残りいっぱいに伸びるため、空白が無いとカードが広がる
- XML を変える前にツリー全体を検証する。同じシートが 2 回出る・別ワークブックのシート・
  `KpiNode` 以外のノードは例外になり、Dashboard は作られない

**エッジ（線）は `edges=True`（または `edge_hyper=` にパス）を渡したときだけ描く**（2026-09-13、`edges=` は 2026-09-15）。
Tableau のダッシュボードには線のオブジェクトが無いため、座標だけを持つ表から親ノードごとに
折れ線のシートを作る。

- **エッジ用データソース「KPIツリーのエッジ」はライブラリが足す。** ワークブックに無ければ
  §6.1 の `create_hyper_datasource()` で列 `edge` / `point`（string・dimension）/ `x` / `y`（integer・measure）を宣言して作り、
  あれば使い回す。既にあるものの抽出のパスが違えば例外にする
- **`edges=True` でパスを渡さなければ、ライブラリ同梱の表（`twbpatch/assets/edge.hyper`）を使う。** 抽出のパスは
  `twbpatch_kpi_tree_edge.hyper`（.twb からの相対）で、**`save()` が .twb の隣（.twbx なら中の .twb と同じフォルダ）へ
  同梱のファイルを置く。** 保存のたびに XML からこの抽出の有無を判定するので、作った .twb を開き直して別の場所へ保存しても付いていく。
  隣に別の内容の同名ファイルがあれば、`overwrite=False` では .twb も書かずに `SaveError` にする。
  設定画面や YAML で .hyper の場所を指定させないため（2026-09-15。絶対パスを埋め込むと .twb を移したときに線が消える）
- `edge_hyper=` にパスを渡したときは、そのファイルを利用者が用意する。ライブラリはコピーしない
- 線 `E-k` は O(0,0) → P-k(1,k) → P2-k(2,k) の 3 点で、k は親の中心から子の中心までの縦位置（ノードの高さの半分、75px 単位）。
  表（同梱の `twbpatch/assets/edge.hyper`、元データは `examples/edge.txt`）の k の上限は 13 で、1 つの親の下の末端は 7 つまで
- **上端揃え（`align="top"`）のときだけ描ける。** 中央揃えでは子が親より上に来て k が負になり、表に無い
- 親ノードとその子の列のあいだに幅 60px のエッジ列を挟む。Dashboard の幅は
  「深さ × 200 +（深さ − 1）× 60 + 台紙の余白 16」になる。線の端とカードのあいだには、カードの外側の余白 4 の灰色の隙間が出る
- エッジ用シートの背景は、ワークシートとペインの両方を台紙と同じ色で塗る。既定の白のままだと台紙の上で帯になり、
  透明（`#00000000`）を書いても Tableau Public では背景が残った（2026-09-14）
- エッジ用シートは `build_kpi_tree()` の中で作る。名前は `エッジ|<親のシート名>`、シートのタブには出さない（`visible=False`）。
  Tableau で手作りしたシートと同じ設定にする: 線マーク・階段補間・詳細に edge と point・edge を値で絞るフィルター・
  y 軸の反転・軸の非表示・線の書式なし
- 軸の範囲は固定する。自動だと余白が入り、線の端がカードとずれる。y は −1〜2 × 末端数 − 1、x は 0〜2
- 次は XML を変える前に例外にする: 中央揃えでの `edges=True` / `edge_hyper=`、`.hyper` でないパス、抽出のパスが違う既存のエッジ用データソース、
  k が上限を超えるツリー、同名のエッジ用シートが既にある、同名の Dashboard が既にある。
  **エッジ用データソースを作るのが最初の変更になるため、Dashboard 名の重複もその前に検証する**
- **既存 Dashboard の作り直しではない**（§6.13）。新しい Dashboard を 1 つ作るだけで、
  同名の Dashboard が既にあれば `create_dashboard()` と同じく `ValueError` になる

#### ウォーターフォール: `add_index_relation()` が①、`build_waterfall_metric()` が②③、
`build_waterfall_chart()` が④（2026-09-22〜23）

ウォーターフォールグラフの実装ロードマップ: ①データソースへ `1=1` のクロスジョインで
リレーションを追加 → ②指標を縦持ちに変換 → ③ガントチャート指標を作成 → ④ウォーターフォール
グラフを作成。①②③④とも実装済み。

**入力と出力（3関数のつながり）**

| 関数 | 入力 | 出力 |
|---|---|---|
| `add_index_relation()`（①） | `datasource`、`join_to`（既存フィールド）、`path`、`column`、`max_index`、`folder`、`overwrite` | `TwbField`（連番。②の `index=` へ渡す） |
| `build_waterfall_metric()`（②③） | `datasource`、`name`、`index`（①の出力）、`metrics`、`connectors`、`landing`、`folder` | `WaterfallMetric`（`value`/`label`/`kind`/`size`: `TwbField`、`count`/`used_index`: `int`。④の `metric=` へ渡す） |
| `build_waterfall_chart()`（④） | `datasource`、`name`、`index`（①と同じ）、`metric`（②③の出力）、色 4 種 | `TwbWorksheet` |
| `build_waterfall()`（①〜④一括） | `datasource`、`name`、`metrics`（メジャーの複数選択）、`connectors`、`landing`、`increase_color`/`decrease_color`/`landing_color`、`title`、`visible`、`folder` | `TwbWorksheet` |

①の `TwbField` と②③の `WaterfallMetric` を、そのまま次の関数の引数として渡すだけで
一通り作れる（README §2.4.2 にコード例がある）。

**`build_waterfall()` は設定画面向けの一括版**（2026-09-23 追加）。`index`・`join_to`・
`path`・`folder`（連番用）を画面から一切出さずに済むよう、①〜④を 1 回の呼び出しに
まとめる。`TwbWorkbook.draw_*()` のような「1 引数 1 グラフ要素」の形にならないのは
`build_waterfall_metric()`/`build_waterfall_chart()` と同じ理由（下記「`draw_*` を
名乗らない」）だが、こちらは画面のグラフ種類の 1 つとして選べるようにするための
薄いラッパーなので、`_CHART_LABELS`（`html_export.py`）には `draw_` 以外の名前でも
明示的に載せられる。`config_apply.py` の `_draw_area()` は `chart` を
`"draw_"` プレフィックスかホワイトリスト（`_EXTRA_CHARTS`）のどちらかで検証するため、
`draw_` 以外の名前をここへ追加するときは両方直す。

- **連番テーブルはデータソースにつき 1 つだけ作り、複数のウォーターフォールで
  使い回す**（2026-09-23、ユーザー承認の「共有テーブル方式」）。列名は固定で
  `"連番"`。**データソースに `"連番"` があるかどうかだけで判断する**（`add_index_relation()`
  を呼ぶかどうかの唯一の基準）。無ければ `path` にワークブックを開いた元ファイルの隣の
  固定名 `twbpatch_waterfall_index.txt`、`overwrite=True` を当てて呼ぶ。

  **`overwrite=True` は `add_index_relation()` に 2026-09-23 追加した引数**（実機で確認した
  バグ修正）。`apply_config()` は毎回 source の `.twb` を開き直し、別名で保存する運用が
  あり得る（`scripts/03_apply_dashboard.py` はまさにこの形）。この場合、source 自体は
  変更されないので、対象データソースには**毎回**「連番」がまだ無い状態になる。一方で
  `.txt` ファイルは前回の実行で既にディスクに書かれて残っているため、`overwrite` 無しでは
  「ファイルの重複」を理由に `ValueError` になっていた。**ファイルの中身は常に同じ
  （1..21）なので、上書きしてよい。** 別名（`_2.txt` など）へ逃げる案も検討したが、
  「連番フィールドの有無だけで判断する」という仕様と矛盾するため採らなかった
  （ユーザーからの指摘）。`add_index_relation()` 本体は、`overwrite=True` で上書きした後に
  XML 側の組み立てが失敗した場合、ファイルを削除するのではなく元の内容へ戻す
  （新規作成時は削除するのと使い分ける）。

  **`join_to` は `metrics` の中から計算フィールドでないものを
  探して使う**（2026-09-23、実機で確認したバグ修正。`join_to` は `<extract>` の
  cols マップに乗る物理フィールドが前提で、計算フィールドは乗らないため
  `metrics[0]` が計算フィールドだと必ず `UnsupportedFeatureError` になっていた。
  `metrics` に物理フィールドが無ければデータソース全体から探す）
- **容量は固定で 21**（2026-09-23、ユーザー承認）。「指標 10 個 + `connectors` +
  `landing`」の最大構成がちょうど収まる数（`2 * 10 - 1 + 2 = 21`）。これを超える
  構成は、計算フィールドを作る前に `ValueError` で止める（原子性）
- **計算フィールド（値・項目名・種別・サイズ）はウォーターフォールごとに個別に作る**
  （`name` で名前空間を分ける、`build_waterfall_metric()` と同じ）
- **`connector_color` は画面に出さない固定値 `#cccccc`**（2026-09-23、ユーザー承認）。
  連結線は「薄い線」という位置づけで、色を変える需要が薄いため。画面には
  `increase_color`/`decrease_color`/`landing_color` の 3 色だけを出す
- `metrics` の画面入力は帳票（`draw_sheet`）の `items` と同じ「複数選択・選んだ順」の
  モーダルを流用し、`_PARAM_ROLES["metrics"] = "measure"` でメジャーだけに絞る

**①は当初「twbpatch のコードでは自動化できない」と判断したが、それは誤りだった。**
twbpatch が組み立てられないのは `<extract>` の中身（.hyper のバイナリ）だけで、
`tableauhyperapi` に依存していないため .hyper を新規に書けず、`create_hyper_datasource()` も
既存の .hyper を**参照するだけ**で新規データは書き込まない。しかし `<connection>` の
物理リレーションと `<object-graph>` の論理オブジェクト・`1=1` の `<relationship>` は
**純粋な XML 操作**であり、`examples/ウォーターフォール.twb` の `edge.txt`（EC Orders への
実際の追加）を実測した形をそのまま書けば足りる。追加する表もタブ区切りの .txt（連番だけ）で、
これも twbpatch が直接書く。**`add_index_relation()` はこの XML 操作だけを行い、`<extract>`
には一切触れない。** 追加した表を実際にクエリへ使うには、Tableau で開いて一度
「データソースの更新」（抽出の更新）をする必要があるが、これは抽出済みのデータソースへ
表やリレーションを足したときに毎回要る通常の手順であって、twbpatch 特有の制約ではない。

**`add_index_relation()` は §2.0 の「API 方式は XML を直接組み立てない」に反する（2026-09-22、
承知の上での例外）。** §2.0 は「API 方式はクラス方式の上に建てる」「クラス方式で表現できない
操作を API 方式に持たせない」としているが、`TwbRelation` / `TwbRelationship` は今のところ
**読み取り専用**（本章冒頭）で、リレーションを書き込むクラス方式のメソッドが存在しない。
`add_index_relation()` は `TwbDatasource._resolve_element()` で生の XML 要素を取り、
`lxml` で直接組み立てている。これは `draw_bar()` 等の API 方式がクラス方式（`create_worksheet()` /
`add_field()` 等）だけを呼ぶのとは違う。`draw_*()` / `build_kpi_tree()` が使う
`create_hyper_datasource()` も同じく XML を直接組み立てるが、こちらは
`create_<単数形>()` の形でクラス方式扱いにできる（新しい `TwbDatasource` を 1 つ作るだけの
操作のため）。`add_index_relation()` は既存の `TwbDatasource` の内部（物理リレーション・
`object-graph`）を直接書き換える操作で、`TwbDatasource.create_relation()` のような
クラス方式のメソッドとして実装するのが本来の形。書き込み可能な `TwbRelation` を設計してから
書き直すかは、③④の設計と合わせて改めて判断する。

`add_index_relation(*, join_to, path, column="連番", max_index=20, folder=None)`:

- `join_to` で指定したフィールドが属するロジカルテーブル（抽出の `<cols>` マップから引く）
  へ、`column`（既定 `連番`、1〜`max_index` の整数）だけを持つ表を `1=1` でクロスジョインする
- 対応する datasource の形は `<connection class="federated">` + `<object-graph>` の
  関連モデル（`named-connections` / 物理 `relation type="collection"` / `object-graph`）。
  この形以外は `UnsupportedFeatureError`
- 新しい物理 `<relation>` の `name` は実際のファイル名（`edge.txt` の実測どおり）、
  `table` は `stem#txt`。`create_hyper_datasource()` の `_text_relation()`（`name` も
  `stem#txt`）とは違う形になる。あちらは抽出だけが実際に読まれる前提で live 側は
  形だけ整えていたが、こちらは live 側の定義がそのまま「データソースの更新」で読まれるため
- `object-graph` のオブジェクト id は `{stem}_{32桁16進数}`（`edge.txt_4AC93E4E...` の実測に合わせる）
- **新しい `<object>` には `context="extract"` の `<properties>` も要る**（2026-09-23、
  実機で確認した不具合）。Orders/People/edge.txt はどれも `context=""`（live）と
  `context="extract"` の 2 つの `<properties>` を持つ。`context="extract"` を省くと、
  Tableau のリレーションシップ画面でその表が Orders と未接続に見え、リレーションが
  効かない。`<relation name="{object_id}" table="[Extract].[{object_id}]" type="table"/>`
  という**名前だけの宣言**でよい（`<extract>` 自体、つまり .hyper のバイナリは変えない
  ので、実際の値は「データソースの更新」まで入らない。ただしリレーションの構造自体は
  更新前から画面に正しく見える）
- 検証を全て終えてから .txt を書き、そのあとで XML を変える（原子性）。XML 側の変更で
  例外が起きたら書いた .txt を消す

`build_waterfall_metric(*, name, index, metrics, aggregation="auto", folder=None)` が②③を担う。
`index` は①で足した連番フィールド、`metrics` は縦持ちにしたい指標（`FieldInput` の
リスト、順不同ではなく**選んだ並び順**に連番 1, 2, 3... を割り当てる）。

- `{name}_値`（measure）: `CASE ATTR([連番]) WHEN 1 THEN <集計式1> ... WHEN N THEN <集計式N> END`
- `{name}_項目名`（dimension）: `CASE [連番] WHEN 1 THEN <表示名1> ... END`。**`ATTR()` を
  付けない**（2026-09-23、実機で確認して修正。ディメンションは行単位でそのまま評価する
  ため不要で、`ATTR()` を付けたままだと Tableau 上で余計だった）。値はメジャーなので
  集計が要り `ATTR()` を付ける。この違いに注意
- `{name}_種別`（dimension）: `{name}_値` の符号で `"増加"`（0 以上）/ `"減少"`（負）を
  **動的に判定する**。増加・減少を専用列で持たせない（2026-09-22、指標ごとに符号が
  変わりうるため固定の対応表にできない）
- `{name}_サイズ`（measure）: `-[{name}_値]`（符号反転）。③のガントバー用
  （2026-09-23、`examples/ウォーターフォール.twb` の手作業の例の符号反転に合わせる）
- 各指標の集計は `draw_bar()` 等と同じ `_metric_aggregation()`（`aggregation="auto"` は
  集計済みの計算フィールドならそのまま、それ以外は既定集計）を使う
- **合計（終了）バーは作らない**（2026-09-23）。当初は最後の連番（`len(metrics) + 1`）へ
  合計を「終了」として持たせる設計だったが、`examples/ウォーターフォール.twb` の手作業の
  ウォーターフォールシートを実測すると、そこには合計バーが無く（`額分類` は
  `IIF([額]>0,"売上","コスト")` という単純な符号判定の 2 値で、専用の「終了」区分も
  無かった）、不要と判断して外した。要るときは呼び出し側で `metrics` へ合計の計算
  フィールドを 1 つ足して渡せばよい

両方とも `folder=` で指定したフォルダへ入れる（無ければ作る。`TwbField.move_to_folder()` /
`create_calculated_field(folder=, create_folder_if_missing=True)` を使う、既存の仕組みのまま）。

**`connectors=True`**（2026-09-23、実機で確認した構成をそのまま採用）。バーとバーの間に
薄い横線の連結を挟みたい場合の指定。奇数番号（1, 3, 5, ...）に指標を割り当て、間の
偶数番号（2, 4, ...）を値 `0` の連結枠にする:

- `{name}_値`: `WHEN <奇数> THEN <集計式>` に加えて `WHEN <偶数> THEN 0` を足す。値 `0` の
  Gantt バーは長さが無いので、`mark_size`（太さ）だけの薄い横線に見える
- `{name}_項目名`: 偶数番号には分岐を作らない（`NULL` のままでラベルを出さない）
- `{name}_種別`: `IF [値] = 0 THEN "連結" ELSEIF [値] > 0 THEN "増加" ELSE "減少" END`
  （`connectors=False` の 2 分岐と違い、`0` を先に判定してから符号で分ける）
- `WaterfallMetric.count` は指標の数のまま、新しい `WaterfallMetric.used_index` が
  実際に使う連番の上限（`connectors=False` なら `count`、`True` なら `2 * count - 1`）

**`landing=True`**（2026-09-23、ユーザーの手作業の例をそのまま採用）。累計を最後に 0 まで
戻す「着地」バーを足したい場合の指定。連番の続き（`connectors=False` なら `count + 1`、
`True` なら `2 * count + 1`。`connectors=True` のときは着地の手前にも連結枠を挟む）に
1 枠足す:

- `{name}_値`: `WHEN <着地の連番> THEN -<式1>-<式2>-...`（選んだ指標すべての合計を
  マイナスで入れる。ユーザーの手作業の実測どおり `-(式1+式2+...)` ではなく
  `-式1-式2-...` の形で書く）
- `{name}_項目名`: `WHEN <着地の連番> THEN "着地"`
- `{name}_種別`: `IF ATTR([連番]) = <着地の連番> THEN "着地"` を最初に判定してから、
  `connectors` の有無で連結・符号の分岐へ続ける
- `build_waterfall_chart()` の `landing_color`（既定 `#4263eb`）がこの `"着地"` の色

②③で一度は「合計バーは作らない」とした（`examples/ウォーターフォール.twb` の手作業の例に
無かったため）が、あちらは合計を**プラス**で足す「終了」だった。`landing` は**マイナス**で
着地させる別物として、要望を受けて追加した。

**③はもう1つ、`TwbWorksheet.add_field(running_total=True)` も担う。** `examples/ウォーターフォール.twb`
の手作業のシートを実測すると、累積は別の計算フィールドではなく、行に置いたピル自体に
Tableau の「累計」クイック表計算が掛かっているだけだった:

```xml
<column-instance column="[Calculation_...]" derivation="User" name="[cum:usr:Calculation_...:qk]" pivot="key" type="quantitative">
  <table-calc aggregation="Sum" ordering-type="Rows" type="CumTotal"/>
</column-instance>
```

`_build_reference()` は `running_total=True` のとき、通常どおり組み立てた参照の
ローカル部分（例: `usr:Calculation_XXX:qk`）へ `cum:` を前置するだけ（`aggregation` は必須、
`table_calculation`/`date_level` とは併用不可）。`_ensure_dependency()` 側は、
derivation・type の判定に使う集計トークンの抽出だけ `cum:` を外してから行い（`type` の
判定は末尾のトークンを見るだけなので影響なし。`running_total` は常に `"quantitative"`
——集計したメジャーなので）、`<table-calc type="CumTotal" aggregation="Sum"
ordering-type="Rows"|"Columns">`（置いた `shelf` に合わせる）を足す。`shelf` は
`rows`/`columns` のみ（`pages`/`filters` では意味がないため例外）。

**`running_total_fields`**（2026-09-23、実機で確認した「特定のディメンション」の形）。
計算対象を「Table (Down/Across)」ではなく明示的なフィールドで指定したいときに渡す
`list[TwbField]`（列に置いていないフィールドも対象にできる。実際、ウォーターフォールの
`metric.label` は列に置かないが計算対象には含める）。渡すと:

- 参照のローカル部分の末尾へ `:2` が付く（例: `cum:usr:Calculation_XXX:qk:2`。
  既存の `table_calculation="field"` と同じ接尾辞）
- `<table-calc type="CumTotal" aggregation="Sum" ordering-type="Field">` の下へ、渡した
  フィールドの数だけ `<order field="...">` を並べる（`ordering-field` 属性 1 つではなく、
  子要素のリスト）
- `<order field=...>` の値は実機で 2 通り確認した: 計算フィールドは素の
  `[datasource].[id]`、物理フィールドは集計なし・不連続の通常のディメンション参照
  （`_order_field_reference()` がこの違いを反映する）

`build_waterfall_chart(*, name, index, metric, increase_color="#2f9e44",
decrease_color="#e03131", connector_color="#cccccc", landing_color="#4263eb", title=None,
visible=True)` が④を担う。`index` と②③の `WaterfallMetric` を受け取りワークシートを組む:

- `index` だけを列へ（`discrete=True`）。**`metric.label` は列に置かない**
  （2026-09-23、実機で確認して変更。当初は `examples/ウォーターフォール.twb` の手作業の
  シートに合わせて列へも置いていたが、`index` だけで列の位置は決まり、ラベルの
  マークだけで表示できる）
- `metric.value` を `aggregation="agg", running_total=True,
  running_total_fields=[index, metric.label]` で行へ。計算対象は「特定のディメンション」で
  `index`・`metric.label` の両方を明示する（列に置いていない `metric.label` も対象にできる）
- マークはガントチャート（`mark_type="gantt"`）、太さは実測値 `1.9890055656433105`
- 色は `metric.kind`（`aggregation="agg", discrete=True`）。`increase_color`/`decrease_color`/
  `connector_color`/`landing_color` を `set_categorical_colors()` で
  `"増加"`/`"減少"`/`"連結"`/`"着地"` に割り当てる（`metric` がその種類を作らなかった
  場合はその色は使われない。実在しないカテゴリを渡しても `set_categorical_colors()` は無害）
- サイズは `metric.size`（`aggregation="agg", discrete=False`）
- ラベルは `metric.label`（集計なし、`discrete=True`）。`label_style={"show": True, "cull": True}`
- **`index` を `1..metric.used_index` に絞るフィルタを作る**（2026-09-23、実機で確認した
  不具合）。①の連番テーブルは `max_index`（既定 20）まで容量を持つが、`metrics` で
  使わなかった分は `CASE` に該当する `WHEN` が無く値が `NULL` になるだけで、フィルタしないと
  空の列として残ってしまう。`WaterfallMetric.used_index` を使い、`add_filter()` +
  `TwbWorksheetFilter.update(values=[...])` で絞る

  **`TwbWorksheetFilter.update()` の `member` 属性は、フィールドの `datatype` が
  `integer`/`real` なら引用符を付けない**（2026-09-23、実機で確認した不具合。
  `connected_parameter.py` の `_serialize_value()` と同じ規約）。以前は文字列型と同じく
  常に `member='"1"'` と書いていたため、整数型の `連番` に対するフィルタが Tableau 側の
  実際の値（引用符なしの `1`）と一致せず、絞り込みが効かなかった。

**`build_waterfall_chart()` は `draw_*` を名乗らない**（`build_kpi_tree()` と同じ理由）。
`metric` が単純な `FieldInput` ではなく `WaterfallMetric`（`build_waterfall_metric()` の戻り値）
を取るため、`dir(TwbWorkbook)` の `draw_*` メソッドは HTML 設定画面の draw-specs に全部
載る契約（`test_export_html_draw_specs_come_from_real_signatures`）を満たせない。

**`index` の見出し（軸の連番の数字ラベル）は隠す**（2026-09-23、ユーザーの指摘で追加）。
`TwbWorksheet._apply_field_header_display(field, show=False)`（`_apply_field_text_align()`と
同じ `<table><style><style-rule element="label"><format attr="display" field="…" value="false">`
のパターン、`examples/ウォーターフォール.twb` で実測）。ラベルのマークで項目名を出すので、
軸の数字を見せる意味が無い。

**セル幅・回転したラベルは未実装**（2026-09-23）。実測した手作業のシートにはあったが、
構造（シェルフ配置・マーク・色・サイズ）と列見出しの非表示を先に組んだ。残りは後で
個別に足す。

#### インフォメーション: `draw_info()`（2026-09-23 追加）

`outputs/waterfall_chart_test10.twb` の手作業の `"info"` ワークシートを実測して作った。
アイコン + カスタムツールヒント（マウスを乗せると出る自由な説明文）だけの小さな
ワークシートを 1 つ作る。

`(workbook, datasource=None, *, name, text, icon="info", heading="説明",
color="#e15759", visible=True, folder=None) -> TwbWorksheet`。`text` だけが必須。

- **行・列にデータを置かず、`STR(1)` を返すだけのダミー計算フィールドを 1 つ、
  `pane.add_field(encoding="tooltip", aggregation="attr")` で置くだけ。** マーク自体は
  `mark_type="shape"` + 固定色 + 固定シェイプで表現し、実データは一切使わない
- **ATTR は式ではなく参照側にだけ付ける**（2026-09-24、実測）。実物の式は `STR(1)` のままで、
  `column-instance` が `derivation="Attribute"`、参照が `[attr:Calculation_...:nk]`。
  式にも `ATTR()` を付けると二重になる。合わせて `<mark class="Shape"/>` の直後に
  `<mark-sizing mark-sizing-setting="marks-scaling-off"/>` も要る
  （既存の `TwbPane._apply_mark_sizing(scaling=False)` をそのまま使う）
- **ダミーの計算フィールドはデータソースにつき 1 つを複数の `draw_info()` で共有する**
  （固定名 `"インフォメーション_key"`。`build_waterfall()` の共有連番と同じ考え方——
  既にあれば `create_calculated_field()` を呼ばずにそのまま使う）
- **アイコンは固定シェイプとして書く。データドリブンではない。** Tableau は
  `<pane><style><style-rule element="mark"><format attr="shape"
  value="<パレット名>/<ファイル名>.png"></format></style-rule></style></pane>` と書く
  （`_ENCODINGS["shape"]` はフィールド値に応じたシェイプ*エンコーディング*用で、
  こちらとは別物）。`icon` の 4 種類は Tableau 側の `形状/webinfo/` フォルダに置いた
  Google Material Symbols のアイコンに固定で対応させる
  （`info`→`info_*.png`、`quest`→`help_*.png`、`setting`→`settings_*.png`、
  `attention`→`error_*.png`）。**画像そのものはワークブックに埋め込まれない。**
  そのシェイプパレットが無い環境で開くと、Tableau は既定のシェイプを代わりに表示する
  だけで、開けなくなるわけではない
- カスタムツールヒントは `<pane>` 直下の `<customized-tooltip><formatted-text>` に、
  見出しを太字の `<run bold="true">`、本文を別の `<run>` として書く。見出しがあるときは
  本文の run の先頭に改行を 1 つ入れる（実測どおり）。新しいプライベートメソッド
  `TwbPane._apply_mark_shape()` / `TwbPane._apply_customized_tooltip()` を
  `connected_worksheet.py` に足した（`_apply_mark_color()` と同じ
  `<style-rule element="mark">` 操作のパターン）
- ダッシュボードに置いたときの内側の余白は `draw_card` と同じ `0`
  （`_CHART_ZONE_PADDING["draw_info"] = 0`）
- 画面の `text` 引数は複数行になりうるため、`_param_kind()` に `name == "text"` の特例で
  `"textarea"` を追加した（`draw.py` に他に `text` という名前の引数が無いことを確認して
  安全に判定できる）。`icon` は `_PARAM_CHOICES` に登録した固定選択肢のプルダウン

**設定画面: グラフのエリア／KPI ツリーのノードに「インフォメーションを追加」
チェックボックス**（2026-09-23 追加、`docs/html_screen_spec.md` に画面側の詳細）。
`draw_info()` は画面の「グラフ種類」プルダウンには出さない（`_HIDDEN_FROM_CHART_LIST`。
ユーザーの要望で選択肢から外した）。代わりに、既存グラフに説明アイコンを浮動で重ねる
チェックボックスとして使う。`_draw_specs()` の出力自体には残す
（`infoControl()` が `DRAW_SPECS["draw_info"]` から `icon` の選択肢と既定値を読むため、
`specs[method_name]["selectable"]` で選択肢からの除外だけを表す）。YAML は
`areas[].info:` / KPI ツリーのノードの `info:`（`text`/`icon`/
`heading`/`color`）。受け手 `config_apply.py` の `_apply_info()` は `build_report()` /
`build_kpi_tree()` の**後**に呼ぶ（対象ゾーンの px 位置はレイアウト計算後にしか
決まらない）。対象シートのゾーンを `dashboard.get_zones()` から
`zone.worksheet_id == sheet` で探し、その右上（ゾーンの `x + width - 30 - 4`, `y + 4`。
30px 四方・余白 4px はユーザー承認の固定値）へ `add_floating_worksheet()`
（浮動配置、既存 API）でアイコンのワークシート（`info|<対象シート名>`）を重ねる。

#### フィルターの入口は `add_filter()` 1 つ

Tableau のフィルターは XML 上 3 か所に分かれて書かれる。クラス方式ではそれぞれの
持ち主が書くが、**使う側の入口は 1 つにして種別を引数で選ぶ**（2026-09-07 決定）。

| 書く場所 | クラス方式 |
|---|---|
| `shared-views` のデータソースフィルター | `TwbDatasource.set_filter()` |
| ワークシートの `<slices>` | `TwbWorksheet.add_filter_slice()` |
| ワークシートの filters シェルフ | `TwbWorksheet.add_filter()` |

`TwbWorkbook.add_filter(field, *, scope, worksheets)` はこの 3 つを組み合わせる。
`scope="datasource"` は 1 番目と 2 番目、`scope="worksheet"` は 3 番目を使う。

**ダッシュボードのフィルターカードは含めない。** カードは
`TwbDashboardContainer.add_filter()` が置く。「どのコンテナのどこに」はコンテナ側の
情報であり、`add_filter()` に持たせると持ち主がずれる。代わりに `add_filter()` は
作ったシェルフ上の配置（`TwbWorksheetField`）を返し、それをそのままカードへ渡す。

`scope="datasource"` の戻り値は空リストになる。データソースフィルターはシェルフ上の
配置を持たず、カードの `<zone>` は「ワークシート＋そのフィルター参照」を指す作りなので、
構造としてカードにできない。

**`TwbDashboard`**

| メソッド | 何をするか |
|---|---|
| `build_report()` | `struct` からコンテナ階層とゾーン配置を一括で組み立てる |

#### ゾーンの書式はグラフの種類で決める（2026-09-21）

`build_report()` / `build_kpi_tree()` がワークシートを置くときのゾーンの書式は、
**そのシートを描いた `draw_*()` の種類で決める**。利用者に余白を指定させない。

| グラフ | 外側の余白 | 内側の余白 |
|---|---|---|
| `draw_card()` | 4 | 0 |
| `draw_bar()` | 4 | 16 |
| `draw_crosstab()` | 4 | 16 |
| `draw_quadrant()` | 4 | 16 |
| `draw_sheet()` | 4 | 8 |
| 上記以外（手で作ったシート） | 4 | 16 |

**表示倍率もグラフの種類で決める**（2026-09-21、棒グラフの向き分けは 2026-09-22）。
帳票（`draw_sheet()`）は「幅を合わせる」、棒グラフ（`draw_bar()`）は向きで分け、
横棒（`item_shelf="rows"`、既定）は「幅を合わせる」、縦棒（`item_shelf="columns"`）は
「高さを合わせる」。ほかは「ビュー全体」。ダッシュボードの window の
`viewpoint/zoom[@type]`（`fit-width` / `fit-height` / `entire-view`）に書く。帳票は列が
右へ伸びるためビュー全体だと横スクロールになり、棒グラフは棒が伸びる向きに合わせて
枠いっぱいに表示させる。

- 角の丸みは全種類 8。**Tableau は角の丸みだけ接頭辞付きの要素名
  `_.fcp.DashboardRoundedCorners.true...format` で書き、`document-format-change-manifest` へ
  `_.fcp.DashboardRoundedCorners.true...DashboardRoundedCorners` の宣言も足す**（2026-09-21 に実ファイルで確認）。
  公開する書式名は `corner_radius` で、この形式への変換は内部で行う
- グラフの種類は `draw_*()` がワークブックの作業用の記録に残す。**`.twb` には残らない**ので、
  開き直した後のシートや手で作ったシートは「上記以外」の扱いになる
- `spacing_scale=` で余白を一律に伸ばせる（`margin` / `padding` のみ、0 は 0 のまま）。
  設定 YAML のデザインルール「余白」が `wide` のとき 1.5 倍になる
- `border_color=` を渡したときだけ枠線を引く（solid・幅 2）。省略時は枠線なし。
  設定 YAML のデザインルール「枠線の色」がここに入る（2026-09-21）。
  Tableau が `.twb` へ書く太さは 0 / 1 / 2 の整数で、幅 1 は細くて見えづらいため
  1 段階太い 2 にした（2026-09-22 に実ワークブックで実測）

#### フィルタカードの名称は太字・文字 10（2026-09-22）

`build_report()` が置いたフィルタは、名称（タイトル）を太字・文字の大きさ 10 にする。
**Tableau はフィルタカードの書式を、置いた先のダッシュボードではなく
フィルタを持つワークシート側へ書く。** `<worksheet><table><style>` の
`<style-rule element='quick-filter-title'>` に `font-weight` / `font-size` を並べる
（実ワークブックで確認。パラメータコントロールの `parameter-ctrl-title` と同じ書き方）。

#### カードのラベルの文字の大きさ（2026-09-22）

`set_customized_label()` が組み立てる run の大きさは固定で、利用者に指定させない。

| 部分 | 大きさ | 太字 | 色 |
|---|---|---|---|
| 指標名（見出し） | 12 | する | `main_color` |
| メイン指標（大きな値） | 16 | する | `value_color` |
| サブ指標（サブ指標モード） | 10 | する | `#555555` 固定 |
| 予実比較の率 | 12 | **しない** | `sub_value_color` |
| 予実比較の文言（達成/未達） | 12 | する | 条件ごとの色 |

**率と文言は run を分ける。** 太さと色が違うため、1 つの run にまとめられない。

#### 段の幅の割り方は段ごとに選ぶ（2026-09-21）

`struct` の段に `distribute_evenly` を置ける。`True` なら Tableau の「均等に配布」
（`layout-strategy-id="distribute-evenly"`）で、**エリアごとの `fixed_size` は効かない**。
`False` なら指定した px がそのまま幅になる。省略（`None`）は、幅指定が無くグラフが
2 つ以上並ぶときだけ均等割りにする。

- **均等割りと固定幅は併用できない。** Tableau が保存した .twb でも、均等割りの
  コンテナの中に固定サイズのゾーンは 1 つも無い（実ファイル 3 本で確認）。
  以前は両方書いていたため、`fixed-size="400"` とゾーンの `w`（均等割りの結果）が
  食い違う .twb を作っていた
- **コンテナの最後の子は、固定サイズなら伸ばさない。** 以前は必ず残りいっぱいまで
  伸ばしていたため、段に 1 つだけ置いた固定幅が効かなかった。全部が固定サイズで
  余りを吸う相手がいないときだけ、今までどおり末尾が吸う
- 幅を全部指定した段には、`build_report()` が末尾に空きゾーンを足して余りを吸わせる
  （段の並びの末尾と同じやり方）
| `create_action()` | アクションを1件作る。`<action>` 本体と、参照するデータソース・列の宣言を同時に書く |

**`TwbDashboardContainer`**

| メソッド | 何をするか |
|---|---|
| `add_worksheet()` / `add_filter()` / `add_text()` / `add_image()` / `add_spacer()` | コンテナへ 1 ゾーンを追加する。座標と重みの再計算を伴う |

**`TwbPane` / `TwbWorksheet` の `set_*`**

`set_customized_label()` / `set_axis_visibility()` / `set_axis_range()` / `set_categorical_colors()` /
`set_continuous_colors()` / `add_sort()` / `set_subtotal_visibility()` /
`add_reference_line()` は、複数の
XML 箇所（`style-rule` と `format` の組など）をまとめて書く。**いずれも他モデルを
引数に取る**ため §3.3 で `update()` へ統合しない側に当たる。

自分のスカラー値だけを変えるものは `update()` のキーワード引数へ統合済み（A-9）。
`worksheet.update(title=, lines_visible=)`、`pane.update(mark_color=, mark_size=, mark_opacity=,
mark_scaling=, label_style=, line_interpolation=)`。

**KPI ツリーのエッジ用に足した書式**（2026-09-13）。XML の形は Tableau で手作りしたシートの実測に合わせる。

| 公開形 | XML | 補足 |
|---|---|---|
| `worksheet.set_axis_range(field=, min_value=, max_value=, reverse=)` | `style-rule[@element='axis']/encoding[@attr='space']` の `min` / `max` / `range-type="fixed"` / `reverse="true"` | 範囲の固定と反転は Tableau が同じ要素に書くので 1 つのメソッドにする。すべて省略すると要素を消し、自動の範囲に戻す |
| `worksheet.update(lines_visible=False)` | `axis` / `dropline` / `refline` / `gridline` / `zeroline` の `stroke-size=0` と `line-visibility=off`、`axis` の `tick-color=#00000000` | Tableau で書式の線をすべて「なし」にしたときの XML。個別には切り替えない。プロパティ `lines_visible` と対になる |
| `pane.update(line_interpolation="step")` | `style-rule[@element='mark']/format[@attr='line-interpolation']` | `"linear"` は Tableau の既定なので要素を書かない。実測したのは `step` だけのため、他の値（ジャンプ）は受け付けない |

## 7. コレクション属性の扱い

取得メソッドと内容が重複する次のコレクション属性は廃止する。

| 旧属性 | 新 API |
|---|---|
| `TwbDatasource.columns` | `TwbDatasource.get_fields()` |
| `TwbDatasource.folders` | `TwbDatasource.get_folders()` |
| `TwbDatasource.relations` | `TwbDatasource.get_relations()` |
| `TwbDatasource.relationships` | `TwbDatasource.get_relationships()` |
| `TwbWorksheet.fields` | `TwbWorksheet.get_fields()` |
| `TwbWorksheet.reference_lines` | `TwbWorksheet.get_reference_lines()` |
| `TwbDashboard.worksheets` | `TwbDashboard.get_worksheets()` |
| `TwbDashboard.zones` | `TwbDashboard.get_zones()` |
| `TwbDashboard.actions` | `TwbDashboard.get_actions()` |

これらを取得時点のリストとしてモデルへ保持しないことで、更新後に古い値が残ることを防ぐ。

`TwbRelation.children` のように1つの読み取り結果内で完結する構造は、投影モデルの一部として維持できる。

## 8. 保存・再読込・削除後の状態

### 8.1 保存

`create`、`update`、`delete` はメモリ上の XML だけを変更する。

```python
workbook.save("output.twb", validate=True, overwrite=True)
```

`save()` が成功した時点で、メモリ上の内容がファイルへ反映される。保存前に例外が発生した場合、元ファイルは変更しない。

### 8.2 再読込

`workbook.reload()` は、未保存の変更を破棄して元ファイルを再読込する。

再読込後は、それ以前に取得した接続型モデルを無効とする。呼び出し側は `get_*()` でモデルを再取得する。

### 8.3 外部変更

別プロセスや Tableau Desktop が元ファイルを変更しても、自動ではメモリ上の XML へ反映しない。明示的な `reload()` または再度 `open()` が必要となる。

### 8.4 参照中リソースの削除

`delete()` は変更前にWorkbook全体の参照関係を検証する。対象が他のリソースから参照されている場合は削除せず、`ResourceInUseError` を送出する。

```python
try:
    field.delete()
except ResourceInUseError as error:
    for reference in error.references:
        print(reference.resource_type, reference.resource_id, reference.location)
```

`ResourceInUseError` は次の情報を持つ。

`ResourceInUseError` は `TwbPatchError` のサブクラスとする。

- `resource_type`: 削除対象の種類
- `resource_id`: 削除対象の内部ID
- `references`: 参照元の種類、ID、場所を持つ構造化リスト

初期仕様では `cascade=True` のような連鎖削除を提供しない。呼び出し側が参照元モデルを取得し、配置や関連を明示的に解除してから対象を削除する。

主な削除ブロック対象は次のとおりとする。

- Fieldを参照する計算式、Worksheet配置、フィルタ、リファレンスライン、フォルダ項目
- Worksheetを参照するDashboard Zone、アクション、フィルタコントロール
- 子要素を持つDashboard Container
- Fieldを保持するFolder

削除が拒否された場合、XML、`is_dirty`、取得済みモデルの状態を変更しない。

### 8.5 削除済みモデル

`delete()` が成功したモデルは無効状態になる。削除済みモデルの公開プロパティ、`get_*()`、`update()`、`delete()` を再度使用した場合は `DetachedModelError` を送出する。

`reload()` によって無効になったモデルも同じ例外を送出する。

## 9. 変更状態と検証

`TwbWorkbook` は未保存の変更有無を管理する。

```python
workbook.is_dirty: bool
```

- `create`、実際に値を変更した `update`、`delete` で `True` になる。
- `open()`、`reload()`、正常終了した `save()` で `False` になる。
- 同じ値への更新を変更として扱うかは実装で統一し、原則として XML が変化しなければ `False` のままとする。

`save(validate=True)` は保存前に現在の XML ツリーを検証し、エラーがあればファイルを書き込まない。

## 10. シリアライズ

接続型モデルの非公開コンテキストは、JSON や辞書へ出力しない。

`dataclasses.asdict()` に依存せず、現在の XML から公開値を組み立てる専用シリアライザーを使用する。

`export_json()` は新しい公開モデルの命名に合わせる。

- XML の `@name` は `id` として出力する。
- XML の `@caption` または既定表示名は `name` として出力する。
- `caption` は出力しない。
- 旧 `columns` は `fields` として出力する。
- 廃止したコレクション属性の内容は、対応する `get_*()` を使って出力する。

## 11. 旧 API からの移行

新仕様は段階的に実装する。移行期間中は旧 API のメソッド名、引数、戻り値を変更せず、新 API を併設する。

- 各Phaseの実装後に既存テストと新APIテストを実行する。
- 新APIの実装途中で、対応する旧APIを削除・改名しない。
- 旧APIの非推奨化と削除は、新APIの全Phase完了後に別途判断する。
- 以下の表は最終的な移行先を示し、初期Phaseで旧APIを削除することを意味しない。

初期Phaseは、既存の編集機能を利用できる `TwbWorkbook → TwbDatasource → TwbField / TwbFolder` の接続型モデル、メモリ更新、保存、再読込を対象とする。Worksheet、Pane、Dashboardコンテナの編集は後続Phaseで実装する。

### 11.3 削除の実施（2026-09-07・完了）

**A-1 / A-2 / A-6 の完了をもって併存期間を終え、`TwbWorkbook` の旧メソッド 25 件を削除した。**
下の対応表は移行の記録として残す。

判断の基準は「新 API に**同じ情報を取る手段があるか**」の一点。あるものだけを消し、
無いものは残した。**残したのは 4 件。**

| 残したメソッド | 新 API に無いもの |
|---|---|
| `list_dashboard_zones()` | デバイスレイアウト（raw 座標・任意サイズでの px 換算・`parent_id` / `depth` は 2026-09-13 に `TwbDashboardZone` へ足した） |
| `list_dashboard_actions()` | 無し。`excluded_source_worksheets` / `excluded_target_worksheets` / `details` は 2026-09-13 に `TwbDashboardAction` へ足した（除外は id で持つ） |
| `list_dashboard_fields()` | `max_filter_value_chars=` |
| `list_worksheet_fields()` | フィールドの `values` / `mark_type` / `category` / `type` |

穴を埋めてから消す（`docs/backlog.md` L-6）。`list_dashboard_actions()` は穴が埋まったが、消すかどうかは未判断。

`models.py` の dataclass は**削除しない**。投影層 14 モジュールの戻り値であり、
接続型モデルの `_snapshot()` がこれを読んでいる。公開するのは新 API の戻り値に
なるものだけとし、`TwbColumn` は旧メソッドと一緒に `__all__` から外した。

| 旧 API | 新 API |
|---|---|
| `wb.list_datasources()` | `wb.get_datasources()` |
| `wb.get_datasource(value, by="caption")` | `wb.get_datasources(name=value)` |
| `wb.get_datasource(value, by="name")` | `wb.get_datasources(id=value)` |
| `wb.list_columns(datasource)` | `datasource.get_fields()` |
| `wb.get_column(datasource, value, by="caption")` | `datasource.get_fields(name=value)` |
| `wb.get_column(datasource, value, by="name")` | `datasource.get_fields(id=value)` |
| `wb.update_source(datasource, source)` | `datasource.update(source=source)` |
| `wb.rename_field(datasource, field, caption)` | `field.update(name=caption)` |
| `wb.reset_field_caption(datasource, field)` | `field.update(name=None)` |
| `wb.update_column(datasource, column, ...)` | `field.update(...)` |
| `wb.update_formula(datasource, column, formula)` | `field.update(formula=formula)` |
| `wb.create_calculated_field(datasource, ...)` | `datasource.create_calculated_field(...)` |
| `wb.move_field_to_folder(datasource, field, folder)` | `field.move_to_folder(folder)` |
| `wb.remove_field_from_folder(datasource, field)` | `field.remove_from_folder()` |
| `wb.list_worksheets()` | `wb.get_worksheets()` |
| `wb.get_worksheet(value, by="caption")` | 直接の移行先なし（Worksheetのcaptionは公開別名として扱わない） |
| `wb.get_worksheet(value, by="name")` | `wb.get_worksheets(id=value)` または `wb.get_worksheets(name=value)` |
| `wb.list_worksheet_fields(worksheet)` | `worksheet.get_fields()` |
| `wb.list_reference_lines(worksheet)` | `worksheet.get_reference_lines()` |
| `wb.list_filters(worksheet)` | `worksheet.get_filters()` |
| `wb.list_dashboards()` | `wb.get_dashboards()` |
| `wb.get_dashboard(value, by="caption")` | `wb.get_dashboards(name=value)` |
| `wb.get_dashboard(value, by="name")` | `wb.get_dashboards(id=value)` |
| `wb.list_dashboard_fields(dashboard)` | `dashboard.get_fields()` |
| `wb.list_dashboard_zones(dashboard)` | `dashboard.get_zones()` |
| `wb.list_dashboard_actions(dashboard)` | `dashboard.get_actions()` |
| `wb.list_dashboard_filter_controls(dashboard)` | `dashboard.get_filter_controls()` |
| `wb.add_dashboard_box(dashboard, worksheet, ...)`（旧要件案） | `container.add_worksheet(worksheet, order=..., weight=...)` |
| `wb.list_relations(datasource)` | `datasource.get_relations()` |
| `wb.list_relationships(datasource)` | `datasource.get_relationships()` |
| `wb.list_parameters()` | `wb.get_parameters()` |

旧 API の `by="auto"` に直接対応する新引数は設けない。移行時に、指定値が表示名なら `name=`、内部 ID なら `id=` を明示する。

### 11.1 公開名前空間

同名のクラスが `models.py`（旧 dataclass）と `connected*.py`（接続型モデル）の両方にある場合、パッケージのトップレベルは**接続型モデルを公開する**。

```python
from twbpatch import TwbWorksheet          # 接続型モデル
from twbpatch.models import TwbWorksheet   # 旧 dataclass
```

- 対象は `TwbDatasource` / `TwbFolder` / `TwbParameter` / `TwbWorksheet` / `TwbWorksheetField` / `TwbDashboard` / `TwbDashboardZone` / `TwbDashboardAction` の 8 クラス。
- `TwbDrillPath` は旧 dataclass に対応が無い新規クラス。`<drill-path>` が `name` しか持たないため、Worksheet と同じく `id == name` とする。
- 旧 dataclass は `twbpatch.models` から引き続き import できる。改名も削除もしない。
- 接続型モデルがまだ無いクラスは、引き続き `models.py` のものをトップレベルへ公開する。
- `TwbWorkbook.list_*()` の戻り値は移行期のあいだ旧 dataclass のままとする。型注釈のために接続型モデルが必要な利用者は `get_*()` を使う。

### 11.2 グラフ生成の公開形

グラフ生成は **`TwbWorkbook.draw_*()` メソッドを正とする**。

```python
workbook.draw_sheet(name="帳票", items=[("売上データ", "カテゴリ")])
workbook.draw_sheet(datasource, name="帳票", items=["カテゴリ"])
```

- 第 1 引数の `datasource` は省略できる。省略した場合、項目は `(データソース名, フィールド名)` のタプルで指定する。
- `twbpatch.draw` のモジュール関数は実装の置き場であって公開 API ではない。トップレベルの `twbpatch` からは公開しない。
- 実装をメソッド側へ移さないのは、`workbook.py` をこれ以上大きくしないため。メソッドは委譲だけを行う。

## 12. 利用例

```python
from twbpatch import TwbWorkbook

workbook = TwbWorkbook.open("template.twb")

datasources = workbook.get_datasources(name="売上データ")
if not datasources:
    raise RuntimeError("データソースが見つかりません")

datasource = datasources[0]

folders = datasource.get_folders(name="KPI")
folder = folders[0] if folders else datasource.create_folder(name="KPI")

fields = datasource.get_fields(name="粗利率")
if fields:
    field = fields[0]
    field.update(formula="SUM([粗利]) / SUM([売上])")
    field.move_to_folder(folder)
else:
    field = datasource.create_calculated_field(
        name="粗利率",
        formula="SUM([粗利]) / SUM([売上])",
        folder=folder,
    )

assert workbook.is_dirty
workbook.save("output.twb", validate=True, overwrite=True)
```

### Worksheetのフィールド配置と棒グラフ

```python
worksheets = workbook.get_worksheets(name="売上推移")
worksheet = worksheets[0]

region = datasource.get_fields(name="地域")[0]
sales = datasource.get_fields(name="売上")[0]

column_placement = worksheet.add_field(
    field=region,
    shelf="columns",
    discrete=True,
)
row_placement = worksheet.add_field(
    field=sales,
    shelf="rows",
    aggregation="sum",
)

panes = worksheet.get_panes()
if len(panes) != 1:
    raise RuntimeError("対象Paneを一意に選択できません")

pane = panes[0]
pane.update(mark_type="bar")
pane.add_field(field=region, encoding="color")
pane.add_field(field=sales, encoding="label", aggregation="sum")
```

行・列・ページ・フィルタは `worksheet.add_field(..., shelf=...)`、色・ラベルなどのマーク表現は `pane.add_field(..., encoding=...)` で設定する。

### Dashboardのタイル配置

```python
dashboard = workbook.get_dashboards(name="経営ダッシュボード")[0]
sales_sheet = workbook.get_worksheets(name="売上推移")[0]
profit_sheet = workbook.get_worksheets(name="利益推移")[0]
kpi_sheet = workbook.get_worksheets(name="主要KPI")[0]

root = dashboard.create_container(direction="horizontal")

left = root.create_container(
    direction="vertical",
    order=0,
    weight=2,
)
right = root.create_container(
    direction="vertical",
    order=1,
    weight=1,
)

left.add_worksheet(sales_sheet, order=0, weight=1)
left.add_worksheet(profit_sheet, order=1, weight=1)
right.add_worksheet(kpi_sheet, order=0, weight=1)
```

この例では左右を `2:1` に分割し、左側を上下 `1:1` に分割する。SDKはDashboardサイズ、コンテナ階層、順序、比率からタイルの座標とサイズを計算する。

### 12.1 Tableau 定義書出力 API

```python
from twbpatch import get_definitions, export_excel

definitions = get_definitions("sample.twbx")  # dict[str, pandas.DataFrame]
export_excel("sample.twbx", "sample_definition.xlsx")
```

- 入力は `.twb` / `.twbx`、出力は新規 `.xlsx`。既存ファイルは上書きしない。Excel 出力は `get_definitions()` を一度だけ呼ぶ。
- Windows 用の `scripts/04定義書作成用.bat` は引数の Workbook を受け取り、省略時には既存のファイル選択ダイアログを使う。出力先は第2引数で指定し、省略時は入力と同じフォルダーの `<ワークブック名>_definition.xlsx` とする。`scripts/04_export_definitions.py` は `export_excel()` を呼ぶ薄い CLI とする。
- 辞書キーと Excel シート名は `ダッシュボード一覧`、`シート一覧`、`シート詳細`、`シート詳細_フィルタ`、`フィールド`、`パラメータ`、`ダッシュボードアクション`。0 件でも規定の列を維持する。列の定義は `docs/requirements.md` の「Tableau 定義書出力 API」に従う。
- API 方式は接続型モデルの読み取り口を組み合わせる。XML やアクションの生の `links` / `params` を定義書 API で解釈しない。
- `TwbField.original_name` は metadata-record の `remote-name` を返す。計算フィールドや記録のない元列名は `None`。
- `TwbDrillPath.folder` は階層を含む `TwbFolder` を返し、フォルダに属さなければ `None` を返す。`フィールド` 定義には `階層` 列を設け、ドリルパスの所属とそのフォルダを記録する。
- DataFrame と Excel は `シート一覧`: ダッシュボード名→シート名、`シート詳細`: ダッシュボード名→シート名→フィールド→キー、`シート詳細_フィルタ`: ダッシュボード名→シート名→フィールド、`フィールド`: データソース名→フォルダ→階層→データ型→フィールド名、`パラメータ`: パラメータ名、`ダッシュボードアクション`: ダッシュボード→アクション種別の昇順で返す。空欄は末尾に置く。
- `TwbPane.mark_color` と `get_continuous_colors(field)` は明示的な固定色と 2 色/3 色パレットを返す。`get_categorical_colors(field)` は明示的なカテゴリ別色を返す。自動配色は推測しない。
- `シート詳細` の同一ダッシュボード・シート・フィールドの `ペイン：色` は1行にまとめ、カテゴリ値または最小・中間・最大と色コードの対応をカンマ区切りで `値` に記録する。
- `シート詳細` のフィールド配置行には `field.table_calculation` と `field.discrete` を独立列で出力する。ペインの `mark_opacity` は `1 - mark_opacity` をパーセント表記に変換し、`ペイン：透過率` のキー・値行に出力する。
- フィルターは `シート詳細_フィルタ` に分け、ダッシュボード・シート・フィルターフィールドにつき1行にする。選択値、種別、適用範囲、選択方式、ダッシュボード上のフィルターカードの `mode`、フィールド配置の表計算・不連続フラグを列に出力する。ワークシートのフィルター一覧にないカードもカードの情報で1行にする。選択値と複数の表示形式はカンマ区切りにし、取得できない設定は空欄にする。
- `パラメータ` は `データ型` を独立列に出力する。選択型は許容値をカンマ区切り、範囲指定型は `最小=...`, `最大=...`, `間隔=...` をカンマ区切りで `パラメータ値` へ出力する。最小値・最大値・間隔の独立列は設けない。
- `TwbDashboardAction.field_mappings` は判定できた `source_field` / `target_field` の表示名の組を返す。`target_parameter_name` は対象パラメータの表示名。異なるフィールドを結ぶフィルターは Tableau 保存例で対応方向を検証するまで空リストとする。取得できないフィールド・パラメータは空欄にする。
- アクションは旧 `<action>` に加え、`<edit-parameter-action>`、`<edit-group-action>`、`<nav-action>` を読み取る。新形式に対する既存 `update()` / `delete()` は非対応とする。
- ダッシュボードのシート所属は既定レイアウトのみを使い、未配置シートも一覧・詳細へ出力する。

## 13. 受け入れ条件

- 公開 API に `list_*()` が存在しない。
- 公開の単数取得メソッド `get_<単数形>()` が存在しない。
- 公開の `update_*()` が存在せず、モデル自身の値を `update()` で更新できる。
- 親モデルに公開の `update_<リソース>()` / `delete_<リソース>()` が存在しない。
- すべての `get_*()` が `list` を返す。
- 公開取得 API に `identifier` と `by` が存在しない。
- 公開取得 API の検索条件がキーワード専用の `id=` / `name=` に統一されている。
- `id` と `name` を同時指定すると `ValueError` になる。
- `TwbWorksheet` に `create_field()` が存在せず、既存 `TwbField` を `add_field()` で配置できる。
- Worksheetのシェルフ配置が `rows`、`columns`、`pages`、`filters` を検証する。
- `TwbPane` が `mark_type` を更新し、対応エンコーディングへフィールドを配置できる。
- 複数Paneでは対象Paneの明示的な選択が必要になる。`TwbWorksheet.add_reference_line()` は `pane=` を受け取り、Paneが複数あるとき省略すると `ValueError` にする。Paneが1つのときは省略できる。
- 総計が `worksheet.update(grand_totals=...)` と同名プロパティの対称形で読み書きできる。
- 小計が `worksheet.set_subtotal_visibility()` で付け外しでき、`update()` に含まれない。
- `TwbWorksheetField.delete()` が配置だけを解除し、Datasourceの `TwbField` を削除しない。
- フォルダ指定が、同じDatasourceのフォルダ名か、そこへ接続された `TwbFolder` を受け取る。`folder=` を取るメソッドすべてで規則が同じ。
- Dashboardの標準配置が `TwbDashboardContainer` によるタイル配置になっている。
- タイル配置APIが `direction`、`order`、`weight` を受け取り、`x` / `y` を受け付けない。
- SDKがタイルの階層・順序・比率からXMLの座標とサイズを計算する。
- 既存Dashboardの編集がレイアウト全体を再構築せず、対象コンテナ配下だけを変更する。
- 未対応属性、対象外Zone、デバイスレイアウトが暗黙に削除・変更されない。
- `TwbDashboardZone.delete()` が配置だけを削除し、Worksheetを削除しない。
- 浮動配置が `add_floating_worksheet()` という明示的な別APIになっている。
- タイルZoneと浮動Zoneで無効な更新引数を指定すると `ValueError` になる。
- 参照中のリソースを `delete()` すると `ResourceInUseError` になり、XMLと `is_dirty` が変化しない。
- `ResourceInUseError.references` から参照元の種類、ID、場所を確認できる。
- 連鎖削除が公開APIに存在せず、参照解除を明示的に行う必要がある。
- `TwbColumn` と公開 API の `column` が `TwbField` / `field` へ移行している。
- XML 固有の `column` と `TwbWorksheet.columns` は維持されている。
- 公開 `id` が XML の `@name`、公開 `name` が原則として XML の `@caption` に対応している。Worksheetでは `id` と `name` の両方がXMLの `@name` に対応する。
- XML に `@caption` がない場合、公開 `name` が `@name` 由来の既定表示名になる。
- 公開モデルと JSON 出力に `caption` が存在しない。
- XML 内の参照と計算式保存が、表示名ではなく `id` を使用している。
- 公開 `name` から参照を解決できない、または複数候補がある場合は暗黙に選択しない。
- 接続型モデルが、更新後のメモリ上 XML を再取得なしで参照できる。
- CRUD 操作だけではファイルが変更されない。
- `save()` の成功時だけファイルへ反映される。
- `reload()` が未保存変更を破棄し、既存の接続型モデルを無効化する。
- 削除または無効化されたモデルの操作が `DetachedModelError` になる。
- 非公開コンテキストが JSON 出力へ含まれない。
- 既存の対応機能について、旧 API と同等の XML 編集結果を得られる。

# ダッシュボードレイアウトテンプレート（承認済み追加契約）

`TwbDashboard.layout -> DashboardLayout` は独立した型付き辞書を返す。
`TwbDashboard.update(layout=...)` は既定レイアウトを一括適用し、ID と window を同期する。
XML の取得・構築はクラス層内で行う。従来 API は維持する。

- `DashboardLayout`: `width` / `height`（正の有限ピクセル寸法）、`size`（sizing-mode と min/max 寸法）、`nodes`、`style`（要素別書式）、`viewpoints`（シート ID 別 zoom 属性）。サイズが未指定なら 1200×800、範囲指定では最大寸法を座標換算に用いる。
- `LayoutNode`: `kind`、`placement`（tiled/floating）、絶対ピクセルの `x` / `y` / `width` / `height`、`attributes`（対応する配置属性）、`style`、順序付き `children`、`text_runs`、相対 `image_path`。タイルの最上位コンテナは最大1個。
- `TextRun`: `text`、対応する文字書式の `style`、`dynamic`。静的な文字適用では動的参照を除去する。通常レイアウトのシート参照は保持する。
- `TemplateSelection`: `key` と省略可能な `dashboard_id`。`TemplateCatalogEntry`: `key` と `dashboards`（`id` / `name` の配列）。

`export_html(..., template_root=None)` / `apply_config(..., template_root=None)` を追加する。
既定ルートはプロジェクトの `template/dashboard_template`。キーは単一フォルダ名、ファイルは `template.twb` または `template.twbx` の一方だけとする。
YAML は `design.dashboard_template` と `design.dashboard_template_dashboard` にキーとダッシュボード XML ID を保存する。
単一ダッシュボードなら ID を省略できる。欠落・曖昧な選択・必須画像の欠落は適用前に入力エラーとする。

テンプレートは既定レイアウトのコンテナ・静的文字・画像のみを取り込む。
シート／フィルター／パラメーターは元の寸法の中央揃え文字「グラフ」／「フィルター」／「パラメーター」に置換する（12pt、#333333、太字なし）。
凡例・アクション・未対応物・データ定義は取り込まず警告も出さない。除外タイルは透明スペーサーで空間を保持する。
テンプレートの書式を保持し、通常の design は下部生成領域に適用する。
生成グラフはプレースホルダーへ対応付けず、テンプレート全体の下に追加する。
最終寸法は最大幅と高さの合計、左揃えで拡大縮小しない。`dashboard.width/height` は下部の寸法、生成エリアが無ければテンプレートだけとする。
KPI ツリーは独立した生成経路を維持する。

画像はテンプレートフォルダ内の相対参照、TWBX では内部 TWB と必要画像だけを選択的に読む。
ハッシュ名と画像バイトをメモリ保持し、`save()` 時に TWB の隣または TWBX の内部 TWB の隣へ保存する。
再保存に画像を利用でき、`reload()` は未保存画像を破棄する。既存の保存・上書き契約と TWBX 保存条件は維持する。
