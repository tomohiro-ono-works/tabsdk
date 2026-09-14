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

datasource.create_yoy_calculated_fields(
    metric="利益",
    year_category="当年昨年区分",
    folder="Measure",
)

datasource.update(source=UNSET, name=UNSET)
datasource.delete()
```

`source` は接続先を表す値オブジェクトとして公開プロパティから取得する。単一値であるため `get_source()` は設けない。

`create_yoy_calculated_fields()` は、指標の当年値、昨年値、昨年差、正負別表示、色、昨年比の7計算フィールドを順番に作成して `list[TwbField]` を返す。昨年比には `%` 書式を設定する。参照先や生成名に問題がある場合は、呼び出し内で作成したフィールドをすべてロールバックする。

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

**`folder=` と `create_folder_if_missing=` を受け取るメソッドはすべて同じ規則に従う。** `create_calculated_field()`、`create_calculated_fields()`、`create_yoy_calculated_fields()`、`create_drill_path()`、`create_group()`、`field.move_to_folder()` の 6 つ。解決は `TwbDatasource._resolve_folder()` に集約する（2026-09-07 に `move_to_folder()` も揃えた）。

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

タイル配置を標準とする。`dashboard.create_container()` はルートのタイルコンテナを作成する。浮動配置は重ね表示など明示的に必要な場合だけ `add_floating_worksheet()` を使用する。

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
| `draw_yoy()` | 前年比の時系列 |
| `draw_card()` | KPI カード |
| `draw_quadrant()` | 散布図の四象限 |
| `draw_crosstab()` | ヒートマップ付きクロス集計 |
| `draw_colored_yoy_sheet()` | 前年差を色分けした帳票 |
| `build_kpi_tree()` | 既にあるシートを指標の親子関係のツリーとして左から右へ並べた Dashboard を作る |
| `add_filter()` | フィルターの入口。`scope="worksheet"` / `"datasource"` を引数で選ぶ |
| `set_default_font()` | ワークブック全体の既定フォント |
| `apply_field_config()` | YAML でフィールドの改名とフォルダ分類を一括適用 |
| `apply_config()` | 設定画面が出力した YAML を適用する。受け手が無い節は読み飛ばす |
| `export_json()` | ワークブックの内容を辞書で取り出す |
| `export_html()` | 設定画面の HTML を 1 ファイル出力する（`docs/html_screen_spec.md`） |

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
  （背景 #f5f5f5・枠線なし・外側の余白 8）にし、カードのゾーンを白（背景 #ffffff・枠線なし・外側の余白 4・内側の余白 16）にする。
  カードのタイトルは `build_report()` と同じく、シートにタイトルがあるときだけ出す。枠線は引かず、台紙との余白で区切って見せる
- **台紙の書式は `content_style=` で上書きできる**（2026-09-14）。`build_report(content_style=)` と同じく既定に重ね、
  設定 YAML からはデザインルールの「余白」がここに入る。台紙の外側と内側の余白の合計だけ Dashboard を大きくするため、
  余白は 0 以上の整数に限り、XML を変える前に検証する。エッジ用シートの背景は台紙の背景色に揃える
- `align="center"` は親カードを子の範囲の縦中央に、`"top"` は上端に置く
- **タイル配置で組む。** ノード列とカードを `fixed_size` で固定し、余りを `add_spacer()` で埋める。
  コンテナの最後の子は固定サイズでも残りいっぱいに伸びるため、空白が無いとカードが広がる
- XML を変える前にツリー全体を検証する。同じシートが 2 回出る・別ワークブックのシート・
  `KpiNode` 以外のノードは例外になり、Dashboard は作られない

**エッジ（線）は `edge_hyper=` にエッジの座標の .hyper のパスを渡したときだけ描く**（2026-09-13）。
Tableau のダッシュボードには線のオブジェクトが無いため、座標だけを持つ表から親ノードごとに
折れ線のシートを作る。

- **エッジ用データソース「KPIツリーのエッジ」はライブラリが足す。** ワークブックに無ければ
  §6.1 の `create_hyper_datasource()` で列 `edge` / `point`（string・dimension）/ `x` / `y`（integer・measure）を宣言して作り、
  あれば使い回す。既にあるものの抽出のパスが `edge_hyper` と違えば例外にする。.hyper ファイル自体はコピーしない
- 線 `E-k` は O(0,0) → P-k(1,k) → P2-k(2,k) の 3 点で、k は親の中心から子の中心までの縦位置（ノードの高さの半分、75px 単位）。
  表（`examples/edge.hyper`）の k の上限は 13 で、1 つの親の下の末端は 7 つまで
- **上端揃え（`align="top"`）のときだけ描ける。** 中央揃えでは子が親より上に来て k が負になり、表に無い
- 親ノードとその子の列のあいだに幅 60px のエッジ列を挟む。Dashboard の幅は
  「深さ × 200 +（深さ − 1）× 60 + 台紙の余白 16」になる。線の端とカードのあいだには、カードの外側の余白 4 の灰色の隙間が出る
- エッジ用シートの背景は、ワークシートとペインの両方を台紙と同じ色で塗る。既定の白のままだと台紙の上で帯になり、
  透明（`#00000000`）を書いても Tableau Public では背景が残った（2026-09-14）
- エッジ用シートは `build_kpi_tree()` の中で作る。名前は `エッジ|<親のシート名>`、シートのタブには出さない（`visible=False`）。
  Tableau で手作りしたシートと同じ設定にする: 線マーク・階段補間・詳細に edge と point・edge を値で絞るフィルター・
  y 軸の反転・軸の非表示・線の書式なし
- 軸の範囲は固定する。自動だと余白が入り、線の端がカードとずれる。y は −1〜2 × 末端数 − 1、x は 0〜2
- 次は XML を変える前に例外にする: 中央揃えでの `edge_hyper=`、`.hyper` でないパス、抽出のパスが違う既存のエッジ用データソース、
  k が上限を超えるツリー、同名のエッジ用シートが既にある、同名の Dashboard が既にある。
  **エッジ用データソースを作るのが最初の変更になるため、Dashboard 名の重複もその前に検証する**
- **既存 Dashboard の作り直しではない**（§6.13）。新しい Dashboard を 1 つ作るだけで、
  同名の Dashboard が既にあれば `create_dashboard()` と同じく `ValueError` になる

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
| `list_dashboard_zones()` | デバイスレイアウト、raw 座標、任意サイズでの px 換算、`parent_id` / `depth` |
| `list_dashboard_actions()` | `excluded_source_worksheets` / `excluded_target_worksheets` / `details` |
| `list_dashboard_fields()` | `max_filter_value_chars=` |
| `list_worksheet_fields()` | フィールドの `values` / `mark_type` / `category` / `type` |

穴を埋めてから消す（`docs/backlog.md` L-6）。

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
