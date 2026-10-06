# タスク: Tableau 定義書出力 API

- 起票日: 2026-09-27
- 対象: `docs/developer/backlog.md` の M-1
- 要件: `docs/developer/requirements.md` の「Tableau 定義書出力 API」
- 公開 API の正典: 実装時に `docs/developer/model_api_spec.md` へ追加する

## 目的

Tableau Workbook (`.twb` / `.twbx`) から仕様確認に使う定義情報を抽出し、Python から DataFrame として利用できるようにする。あわせて同じ定義を、新規 Excel ファイルへ出力できるようにする。

## 公開 API

```python
from twbpatch import export_excel, get_definitions

definitions = get_definitions("sample.twbx")
# dict[str, pandas.DataFrame]

export_excel("sample.twbx", "sample_definition.xlsx")
```

- `get_definitions(input_path)` は `.twb` / `.twbx` を解析し、7種類の定義 DataFrame を辞書で返す。
- `export_excel(input_path, output_path)` は `get_definitions()` と共通の定義データを使い、Tableau Workbook を二度解析せずに `.xlsx` を作成する。
- 入力は `.twb` / `.twbx`、出力は `.xlsx` に限定し、その他の拡張子はエラーにする。
- 新規ファイル出力とし、既存の出力先は上書きせずエラーにする。
- `pandas` と `openpyxl` を依存関係に追加する。
- Windows からは `scripts/04定義書作成用.bat` で Workbook を選択して実行できるようにする。既存のファイル選択 UI を再利用し、出力先省略時は `<ワークブック名>_definition.xlsx` とする。

## 定義一覧

辞書キーと Excel シート名は次の7つで統一する。

1. `ダッシュボード一覧`
2. `シート一覧`
3. `シート詳細`
4. `シート詳細_フィルタ`
5. `フィールド`
6. `パラメータ`
7. `ダッシュボードアクション`

列と抽出内容の詳細は `docs/developer/requirements.md` を参照する。

## 動作上の決定

- `.twb` と `.twbx` は同一の公開 API で扱い、形式ごとの読み込み後は共通の解析処理を使う。
- 1定義につき Excel 1シートを作る。
- ダッシュボードに配置されないワークシートも一覧・詳細に含め、ダッシュボード名を空欄にする。
- 同一シートが複数のダッシュボードに置かれる場合、ダッシュボードごとに行を分ける。
- シート概要、元データの列名、計算式など、Workbook に値が記録されていない場合は空欄にする。
- ダッシュボード上のシート配置は既定レイアウトのみを対象とし、デバイス別レイアウトは調べない。
- ペインの色は、Workbook に明示された固定マーク色、カテゴリ別色、連続色パレットを取得対象にする。自動配色で色コードが記録されない場合は空欄にする。
- パラメータの `データ型` 列には Tableau のデータ型、`デフォルト値` 列には Workbook の現在値を記録する。許容値・範囲値はカンマ区切りの文字列として `パラメータ値` 列に記録する。
- シート詳細にはフィールド配置の `field.table_calculation` と `field.discrete` を独立列で出力する。ペインの透過率はキー・値行とする。フィルター値・種別・適用範囲・選択方式・表示形式は `シート詳細_フィルタ` の1フィールド1行にまとめる。
- 範囲パラメータは `最小=...`, `最大=...`, `間隔=...` を `パラメータ値` に統合し、独立列は設けない。
- `フィールド` に `階層` 列を追加し、階層に含まれるフィールドのフォルダは階層のフォルダから取得する。各定義の行は要件書で定めた列順の昇順に並べ、空欄は末尾に置く。
- Excel にはヘッダー、オートフィルター、先頭行固定、列幅調整を適用する。
- アクション項目のうち取得不能または該当しない値は空欄とする。

## class 方式の充足性調査（2026-09-27）

| 出力 | 既存 class で取得できる情報 | 不足する情報 |
|---|---|---|
| ダッシュボード一覧 | `TwbWorkbook.get_dashboards()` と `TwbDashboard.name` | なし |
| シート一覧 | `get_worksheets()` と `TwbDashboard.get_worksheets()` で既定レイアウトの所属を取得 | シート概要は class に無いが、要件どおり値が無ければ空欄にできる。デバイス別配置は対象外 |
| シート詳細 | `TwbWorksheet.get_fields()`、`get_panes()`、`get_filters()`、`TwbPane.mark_type`、`TwbWorksheetField.shelf` / `encoding` / `aggregation` / `date_level`、`TwbWorksheetFilter.values` など | 固定マーク色と連続色パレットの読み取り。カテゴリ別の明示色は `TwbPane.get_categorical_colors()` で取得可能 |
| フィールド | `TwbDatasource.get_fields()`、`TwbField.name` / `id` / `datatype` / `role` / `folder` / `is_calculated` / `formula` | `name` は表示名、`id` は Tableau 内部の列識別子であり、元データの列名 `remote-name` とは限らない。`remote-name` の公開プロパティ |
| パラメータ | `TwbWorkbook.get_parameters(include_hidden=True)`、`TwbParameter.datatype` / `value` / `allowable_values` / `min_value` / `max_value` / `step_size` | なし。「デフォルト値」列には保存済み現在値 `value` を使う |
| ダッシュボードアクション | `TwbDashboard.get_actions()`、`TwbDashboardAction.name` / `type` / `activation` / `command`、発火元・先のダッシュボード ID、発火元・先のシート ID と除外シート ID、`source_type` / `target_type`。`links` / `params` / `attrs` / `details` は生の構造として取得可能 | 発火元・発火先フィールドの対応と発火先パラメータを意味付けした公開プロパティ。`links` / `params` には手掛かりがあるが、アクション種別ごとに構造が異なる |

既存の `TwbDashboard.create_action()` が作成できるのはフィルターアクションと URL アクション。読み取り側は旧形式の `<action>` の `command` に対してハイライト等の文字列判定を持つが、`tsc:brush` などの実際のコマンドとの対応は未確認。さらに、Tableau のスキーマにある `<edit-parameter-action>`・`<edit-group-action>`・`<nav-action>` は現在の列挙対象外。既存テストのアクション XML は主にテスト内で組み立てたもの。

### API 実装前に必要な class 修正

1. **元フィールド名**: `twbpatch/connected.py` の `TwbField` に `original_name: str | None` を追加する。既存の `_FieldDefinition.metadata` を使い、対応する `<metadata-record><remote-name>` を返す。計算フィールドや元名のないフィールドは `None`。`id` を元名と推測しない。
2. **マーク色**: `twbpatch/connected_worksheet.py` の `TwbPane` に `mark_color: str | None` と `get_continuous_colors(field) -> dict[str, str]` を追加する。前者は pane の `<style><style-rule element="mark"><format attr="mark-color">`、後者は色エンコーディングが参照する Workbook のパレットから最小・中間・最大色を読む。既存の `get_categorical_colors()` は再利用する。Tableau の自動配色が XML に明示されない場合は空欄にする。
3. **アクションの列挙とフィールド対応**: `twbpatch/dashboard_action.py` の列挙対象を旧形式 `<action>` に加え、対象となる `<edit-parameter-action>`・`<edit-group-action>` 等へ広げる。種別ごとの `<link>` / `<command>` / `<params>` を class 側で解釈し、`twbpatch/connected_dashboard.py` の `TwbDashboardAction` に `field_mappings: list[dict[str, str | None]]`（各辞書のキーは `source_field` / `target_field`）と `target_parameter_name: str | None` を公開する。`list_actions_from_tree()`、`_snapshot()`、`_resolve_element()` の対象タグも整合させ、既存の更新・削除操作が新形式を誤編集しないよう扱いを決める。読み取り用スナップショット `twbpatch/models.py` も対応させる。フィルターの `links[].expression` 等は class 内でのみ解釈し、定義書 API 側で生 XML 相当の構造を再解析しない。判定できない値は `None` とする。

`TwbPane.mark_type` が `automatic` のシートは、Tableau の描画結果から具体的なグラフ種類を推測せず「自動」と記録する。シート概要は対応する明示値がなければ空欄にする。

調査の根拠は `connected.py:141, 1231`、`connected_worksheet.py:1071, 1188, 3019, 3530, 3620`、`connected_dashboard.py:1099, 1295`、`dashboard_action.py:131`、`connected_parameter.py:150, 169`。`examples/sample_ec.twb` を読み取り専用で開いたところ、データソース 1、フィールド 30、ワークシート 1 を既存 class で取得できた。アクションの読み取りは `tests/test_dashboard_zone_action.py` と `tests/test_dashboard_action_create.py` に既存の例があるが、パラメータ・セットアクション等の Tableau 保存例は未確認。

### 追加調査（2026-09-29、実装なし）

- **元列名と ID**: `TwbField.id` は `<column name>` または `<metadata-record><local-name>` に対応する Tableau 内部の識別子。`TwbField.name` は表示名。`remote-name` は接続先の元列名であり、ID と一致するとは限らない。実例として `examples/sample_ec.twb:497-499` は `remote-name=Region`、`local-name=[Region (People)]`。元列名は metadata-record の `local-name` でフィールド定義と対応付けて取得する。
- **色変更 API の経路**: 公開の `TwbWorkbook.draw_sheet()` / `draw_bar()` / `draw_quadrant()` / `draw_crosstab()` 等は `twbpatch/draw.py` の実装へ委譲し、そこで `TwbPane.update(mark_color=...)`、`set_categorical_colors()`、`set_continuous_colors()` を呼ぶ。`TwbWorkbook.apply_config()` も `_draw_area()` から `workbook.draw_*()` を呼ぶ。インフォアイコンやウォーターフォールでも class メソッドを使う。色変更は class を経由している。既存の読み取り口はカテゴリ別色のみで、固定色・連続色の getter は引き続き不足。
- **フィルターのフィールド対応**: `TwbDashboardAction.links` は `<link expression>`、`params` は `<param name/value>` をそのまま公開する。SDK が作るフィルターでは `action_writer._filter_expression()` が `tsl:<ダッシュボード>?<フィールド>~s0=<<フィールド>~na>` を書き、元・先に同じフィールドを使う。元と先が異なる「選択したフィールド」の一般形は未検証。Tableau の画面は「すべてのフィールド」と元・先を対応付ける「選択したフィールド」の両方を提供する。後者は実保存 `.twb` の `<link expression>` を取得して両辺の向き、複数組、URL エンコードを確認する。`special-fields=all` 等は個別のフィールド対応として推測しない。
- **その他のアクション**: [Tableau Workbook スキーマ](https://github.com/tableau/tableau-document-schemas/blob/main/schemas/2026_1/twb_2026.1.0.xsd) は、旧形式 `<action>` のほか `<edit-parameter-action>`、`<edit-group-action>`、`<nav-action>` を `<actions>` 配下に定義する。現行 `list_actions_from_tree()` は `<action>` のみを取得するため、パラメータ・セット等が一覧から欠落する。[Tableau 公式サンプル](https://github.com/tableau/document-api-python/blob/master/samples/preserve-namespaces/filtering.twb) のセットアクションには `<edit-group-action>` と `<param name='target-group'>` がある。パラメータアクションのフィールド名・パラメータ名の実際の `<param>` 名、ハイライトのフィールド対応は Tableau 保存例で確認する必要がある。

参照: [Tableau のフィルターアクション説明](https://help.tableau.com/current/pro/desktop/en-us/actions_filter.htm)、[パラメータアクション説明](https://help.tableau.com/current/pro/desktop/en-gb/actions_parameters.htm)。本調査ではソース改修・テスト実行を行っていない。

## 修正方針（2026-09-29、実装前の設計）

### 共通の境界

- `get_definitions()` は `TwbWorkbook.open()` 後、接続型 class の公開読み取り API だけを組み合わせる。定義書 API の中では Workbook XML、`links`、`params`、`details` を直接解析しない。
- class の getter はメモリ上の Workbook を読み取り専用で参照し、getter 呼び出しで XML を補完・変更しない。取得できない値は `None` または空のコレクションとし、DataFrame 化する際に空欄へ変換する。
- 既存の色変更メソッド、フィルター・URL アクションの作成・更新・削除、既定レイアウトのシート取得の動作を維持する。デバイス別配置の対応は行わない。

### 1. 元列名: `TwbField.original_name`

1. `TwbField._resolve_definition()` が持つ `_FieldDefinition.metadata` を参照し、`local-name == field.id` で対応付いた `<metadata-record class='column'>` の `remote-name` を返す。
2. `TwbField.name` は表示名、`TwbField.id` は Tableau 内部 ID のままとし、`remote-name` の代用にしない。計算フィールド、`remote-name` が空のフィールド、メタデータがないフィールドは `None` を返す。
3. 定義書の `フィールド.オリジナル名` はこの getter から埋める。`Region` と `[Region (People)]` のように元列名と ID が異なる Workbook で対応関係を確認する。

対象: `twbpatch/connected.py`。既存の `metadata_column_records()` と `_metadata_text()` を利用する。

### 2. ペイン色: 既存 setter に対応する getter

1. `TwbPane.mark_color: str | None` を追加し、ペインの `<style><style-rule element='mark'><format attr='mark-color' value='...'>` から明示色を読む。既存の `_style_value()` を使い、書かれていなければ `None` を返す。
2. `TwbPane.get_continuous_colors(field: TwbWorksheetField) -> dict[str, str]` を追加する。対象ペインの色エンコーディングが参照する `palette` を読み、Workbook の `<preferences><color-palette name='...'><color>...` に記録された 2 色なら `min_color` / `max_color`、3 色なら `min_color` / `mid_color` / `max_color` を返す。対応する明示色がなければ `{}` を返す。Tableau 組み込みパレットの色コードは推測しない。
3. カテゴリ別の明示色は既存の `TwbPane.get_categorical_colors(field)` を使う。色フィールドが対象ペインに属することを確認する。設定がワークシート側にあり、同じ参照を複数ペインで使うなどペイン別の色を区別できない場合は、値を推測せず制約を記録する。
4. `シート詳細` の `ペイン：色` は固定色ならフィールド空欄で `#RRGGBB`、カテゴリ色なら対象フィールドごとに `カテゴリ値=#RRGGBB`、連続色なら対象フィールドごとに `最小=#RRGGBB` / `中間=#RRGGBB` / `最大=#RRGGBB` をカンマ区切りで1行にする。明示色がない場合は色コードを出さない。

対象: `twbpatch/connected_worksheet.py`。`TwbPane.update(mark_color=...)`、`set_categorical_colors()`、`set_continuous_colors()` の書き込み経路は変更しない。

### 3. アクション: 種別の列挙とフィールド対応

1. `dashboard_action.list_actions_from_tree()` は `<actions>` の直下から、旧形式 `<action>` と `<edit-parameter-action>`、`<edit-group-action>`、`<nav-action>` を列挙する。タグ・コマンドから `filter` / `highlight` / `url` / `parameter` / `set` / `navigation` を判定し、既知タグのコマンドが未認識でも行自体を落とさない。ダッシュボード・シートの所属は既定レイアウトで解決する。
2. 既存の `TwbDashboardAction` に `field_mappings: list[dict[str, str | None]]`（`source_field`、`target_field`）と `target_parameter_name: str | None` を読み取り専用で公開する。複数の対応がある場合は対応ごとに1要素を返す。フィールド参照はデータソースと内部 ID で解決し、表示名を返す。曖昧・未確認なら対応を作らず、定義書では空欄にする。
3. 旧形式のフィルターは `links[].expression` と `command` の `param` を class 内で解釈する。SDK が作る同一フィールドの形式は既知。元・先が異なる選択フィールド、複数組、エンコード、全フィールド指定は Tableau が保存した Workbook で形式と向きを確かめてから規則化する。全フィールド指定から個別の対応を推測しない。
4. パラメータアクションは `<edit-parameter-action>` の `<params>` にある元フィールドと対象パラメータを、実保存例で属性名を確認してから読み取る。セットアクションは `<edit-group-action>` の対象セット参照を解析するが、セット名を `発火先フィールド` や `発火先パラメータ` へ誤転記しない。ハイライト・URL・ナビゲーションも、明示されたフィールド対応だけを返す。
5. `twbpatch/models.py` のスナップショット、`TwbDashboardAction._snapshot()` / `_resolve_element()`、`action_writer.resolve_action_element()` の対象タグを揃える。新形式に対する既存の `update()` / `delete()` は、このタスクで書き込み仕様を定義しないため明示的に非対応として扱い、旧形式の動作を維持する。
6. `ダッシュボードアクション` にはアクションを最低1行出し、対応フィールドが複数あれば1対応につき1行にする。対象シートが複数ならシートごとに行を分ける。フィールド・パラメータが該当しない、または確認できない列は空欄にする。

対象: `twbpatch/dashboard_action.py`、`twbpatch/connected_dashboard.py`、`twbpatch/action_writer.py`、`twbpatch/models.py`。現行の `TwbDashboard.create_action()` はフィルター・URL 作成のままにする。

### 実装前に揃える保存例と確認項目

| 保存例 | 確認すること |
|---|---|
| 元列名と内部 ID が異なる `.twb` | `original_name` が `remote-name`、`id` が `local-name` を返す |
| 固定色、カテゴリ色、2色・3色の連続色、色未指定 | getter が setter の保存値を読み戻し、未指定を推測しない |
| フィルター: 同一フィールド、異なる元・先フィールド、複数対応、全フィールド | `<link expression>` の対応の向きと件数、`param` の分岐を確定する |
| ハイライト、URL、パラメータ、セット、ナビゲーション | 保存タグと種別、フィールド・対象パラメータ等の有無、取得不能列の空欄を確認する |

同一フィールドのフィルターは SDK の生成規則を確認済み。セットアクションは Tableau 公式リポジトリの保存例を確認済み。他の形式は Tableau が実際に保存した Workbook を確認してから解析規則を追加する。保存例がない形式でも、スキーマ上のタグから列挙できるアクションは落とさず、未確認のフィールド対応を空欄にする。

## 実装対象

- 公開 API の設計と `twbpatch` からの公開。
- `.twb` / `.twbx` からのダッシュボード、シート構成、配置フィールド、フィルター、データソースフィールド、パラメータ、ダッシュボードアクションの抽出。
- DataFrame 辞書の作成と Excel 書き込み。
- `pandas` および `openpyxl` の依存関係追加。
- 公開 API の説明を `docs/developer/model_api_spec.md` に追加し、README の利用例を更新する。

## フェーズと対象ファイル

### Phase 1: class 読み取り API の補完

- `twbpatch/workbook.py:149, 192, 279, 750, 804` — Workbook の既存出力、Dashboard / Worksheet / Datasource / Parameter 取得口。
- `twbpatch/connected.py:311` — Datasource の Field 取得。
- `twbpatch/connected.py:141, 1231` — 元フィールド名の取得。
- `twbpatch/connected_dashboard.py:1099, 1295` — Dashboard の Worksheet / Action 取得と class の補完。
- `twbpatch/connected_worksheet.py:1071, 1188, 3019, 3530, 3620` — Worksheet の配置 Field / Filter と Pane 色設定の取得。
- `twbpatch/dashboard_action.py:131`、`twbpatch/action_writer.py:201`、`twbpatch/models.py:230` — アクション種別の列挙、内容の意味付け、要素解決と読み取り用スナップショット。
- 上記3点の class 読み取り API を追加し、既存の色変更・アクション変更との整合を確認する。アクションのフィールド対応は、種別ごとの Tableau 保存 XML を根拠にする。デバイス別配置の class 修正は行わない。
- 取得できる値と未取得値の扱いをこの文書および `docs/developer/requirements.md` に照らして確定する。

### Phase 2: DataFrame 辞書 API

- 新規 `twbpatch/definitions.py` — Workbook を開き、6定義の DataFrame を構築。
- `twbpatch/__init__.py:16, 71` — `get_definitions` / `export_excel` を公開名前空間へ追加。
- 新規 `tests/test_definitions.py` — `.twb` / `.twbx`、列順、空データ、重複配置、複数値を検証。

### Phase 3: Excel 出力 API

- 新規 `twbpatch/excel_export.py` — DataFrame 辞書を受け取り `.xlsx` を作成。
- `pyproject.toml:7` — `pandas` と `openpyxl` を依存に追加。
- 新規 `tests/test_excel_export.py` — 7シート、ヘッダー、フィルター、先頭行固定、列幅、既存出力先の拒否を検証。

### Phase 4: 公開仕様と利用例

- `docs/developer/model_api_spec.md` — 公開 API の正典へ定義書出力 API を追加。
- `README.md` — DataFrame 取得と Excel 出力の使用例を追加。
- このタスク文書の受け入れ条件と実装を照合する。

## API 移行規約

新しいトップレベル API を追加し、既存の取得 API や `TwbWorkbook.export_json()` を削除・改名しない。モデル方式の追加と旧 API の整理は分離する。

## 受け入れ条件

- 同じ入力 Workbook から `get_definitions()` が規定の6キーを持つ辞書を返す。
- 各 DataFrame が要件書で定めた列名・順序を持つ。
- `.twb` と `.twbx` の両方を処理できる。
- `TwbField.original_name` は `remote-name` を返し、`id` と違う場合にも元列名を保持する。
- ペインの固定色、カテゴリ別色、2色・3色の連続色を明示値から読め、記録のない色を推測しない。
- 旧形式に加え、パラメータ・セット等の別タグのアクションを列挙できる。確認済みの対応フィールド・対象パラメータは class から取得し、未確認の値を作らない。
- 既存の色変更、フィルター・URL アクションの作成・更新・削除は従来どおり動作する。
- シート詳細はフィールド単位で行を分け、同一キーの複数値を一つのセルへ結合しない。
- 複数ダッシュボードに配置されたシートをダッシュボードごとに出力し、未配置シートも失わない。
- 許容値、フィルター選択値などの複数値を、仕様で定めた行単位またはカンマ区切りの形で出力する。
- `export_excel()` は7つのシートを持つ新規 `.xlsx` を作り、オートフィルター・先頭行固定・ヘッダー・列幅調整を適用する。
- Excel 出力時に Tableau Workbook の解析を二重に行わない。
- 入力不正、未対応・取得不能な設定、既存出力先のエラーが利用者に分かる形で返る。

## 対象外

- Excel テンプレートへの記入、既存ブックへの追記。
- Tableau Workbook の編集・保存。
- このタスク内での `04` 定義書作成用 bat の作成。

## 実装メモ（2026-09-29）

- `TwbField.original_name`、`TwbPane.mark_color` / `get_continuous_colors()`、アクションの列挙・読み取り口を追加した。
- `get_definitions()` と `export_excel()` を公開し、7 定義の DataFrame と新規 `.xlsx` 出力を実装した。`pandas` / `openpyxl` の依存関係と `uv.lock`、公開仕様・README を更新した。
- 元・先が異なるフィルターアクションのフィールド対応は、Tableau 保存例で向きを確認できていないため空欄とする。セット・ナビゲーションの対象フィールドも未確認値を推測しない。
- 構文チェックと差分チェックを実施した。テストの追加・実行は今回の指示には含まれないため未実施。
