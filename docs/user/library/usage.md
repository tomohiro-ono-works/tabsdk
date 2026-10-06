# ライブラリ利用ガイド

Python のコードから `twbpatch` を使う方の資料です。
ランチャーと設定画面の操作だけで使う場合は[GUI 利用ガイド](../gui/usage.md)を参照してください。
メソッドごとの引数・戻り値は[公開 API リファレンス](api_reference.md)にまとめています。

KPI ツリーの接続線には、本体同梱の `twbpatch/assets/edge.hyper` を使います。
その元データは同じフォルダーの [edge.txt](../../../twbpatch/assets/edge.txt) です。
4 列・42 行のタブ区切りデータで、Tableau で元データへ手動接続する場合や Hyper を再作成する場合に使えます。
通常のツリー作成は Hyper を参照します。TXT への自動切り替えは行いません。

## ダッシュボードのデザインをテンプレートから取り込む

`template/dashboard_template/<フォルダ名>/template.twb` または `template.twbx` に
Tableau で作ったテンプレートを配置し、設定画面のデザインルールで選択できます。
コンテナ・静的な文字・画像を保持し、シート・フィルター・パラメーターを文字枠に変換します。
通常指定するグラフ・KPI カードはテンプレート全体の下に追加します。

```python
wb.export_html("config.html", template_root="template/dashboard_template")
wb.apply_config("config.yaml", template_root="template/dashboard_template")
wb.save("output.twb")
```

`template_root` を省略すると、このプロジェクトの `template/dashboard_template` を使います。
追加・変更後は HTML を再出力してください。
[配置・画像・YAML の詳しい手順](../../../template/dashboard_template/README.md)を参照してください。
レイアウト値は `dashboard.layout` で取得し、`dashboard.update(layout=layout)` で一括適用できます。
型は `twbpatch.dashboard_layout` の `DashboardLayout` / `LayoutNode` / `TextRun` です。

## 動作要件

- Python 3.10 以上
- `lxml` 5.0.0 以上
- `PyYAML` 6.0 以上
- `pandas` 2.0 以上
- `openpyxl` 3.1 以上

リポジトリを使う場合は、ルートで `uv sync` を実行して依存関係を入れます。
`uv` を使わない場合は `python -m pip install -e .` で開発用にインストールできます。

## 基本的な使い方

`TwbWorkbook.open()` でワークブックを開き、そこから各リソースを取ります。
取得は `get_<複数形>()` で、常にリストが返ります。

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")

for datasource in wb.get_datasources():
    print(datasource.name, datasource.source_type)

    for field in datasource.get_fields():
        print(field.name, field.datatype, field.formula)
```

`.twb` と `.twbx` のどちらも同じ API で開けます。

### 定義書を取得・Excel に出力

```python
from twbpatch import get_definitions, export_excel

definitions = get_definitions("sample.twbx")
sheet_detail = definitions["シート詳細"]  # pandas.DataFrame
export_excel("sample.twbx", "sample_definition.xlsx")
```

7 種類の定義を DataFrame で取得し、Excel には各定義を同名のシートとして新規出力します。既存の `.xlsx` は上書きしません。色やアクションの参照は Workbook に明示された情報のみ出力し、取得できない値は空欄です。
`シート詳細` はフィールド配置ごとの `field.table_calculation` / `field.discrete` 列と、ペインの透過率を含みます。フィルター設定は `シート詳細_フィルタ` に1フィールド1行で出力します。`パラメータ` にはデータ型を記録し、選択値および範囲指定の最小・最大・間隔は `パラメータ値` にカンマ区切りで出力します。
同じフィールドの `ペイン：色` はカテゴリ値や最小・中間・最大と色コードの対応をカンマ区切りで1行にまとめます。
定義書の行はシートごとに規定の順序で並べます。`フィールド` には Tableau の階層（ドリルパス）を表す `階層` 列も出力します。

Windows では `scripts/04定義書作成用.bat` をダブルクリックして Workbook を選択するか、Workbook を bat にドラッグ&ドロップできます。出力先を省略すると、入力と同じフォルダーに `<ワークブック名>_definition.xlsx` を新規作成して開きます。コマンドからは `scripts/04定義書作成用.bat "入力.twbx" "出力.xlsx"` と指定できます。既存の出力先は上書きしません。

### 編集と保存

モデルを取ってきて `update()` / `create_*()` を呼び、最後に `save()` します。
編集はメモリ上の XML だけを変え、**ファイルへ反映されるのは `save()` が成功したときだけ**です。

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")
datasource = wb.get_datasources(name="売上データ")[0]

datasource.create_calculated_field(
    name="粗利率",
    formula="SUM([粗利]) / SUM([売上])",
)
datasource.get_fields(name="売上")[0].update(name="売上高")

wb.save("output.twb", overwrite=True)
```

式の中の `[粗利]` のような**表示名は、保存前に Tableau の内部 ID へ変換されます**。
解決できない名前があれば `AmbiguousFormulaReferenceError` になります。

### 設定画面を HTML で出す

フィールドの一覧を調べて Python へ書き写す代わりに、画面で設定して YAML を落とせます。

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")
wb.export_html("config.html", title="売上分析 設定", overwrite=True)
```

出力した HTML は外部参照を持たず、そのままブラウザで開けます（オフライン可）。
画面はデータソース（表示名・フォルダ・計算フィールド）、全体の書式、ダッシュボードの構成、
KPI ツリーの 4 タブです。YAML はタブごとの「設定 YAML をダウンロード」で、そのタブで使う設定だけが落ちます
（ダッシュボードと KPI ツリーのファイルには、全体の書式とデータソースの設定も入ります）。

フィールドの「選んだ行から AI 用プロンプトを作る」では、
`template/prompt_rules/` 直下の Markdown ファイルを参照ルールとして選べます。
共通ルールは最初から選択され、顧客・商品などの分類は必要なものをチェックします。
命名・フォルダ・階層の共通方針は `00-common-rules.md` にあり、分類ごとの Markdown には固有の対応辞書と構造を記入します。
複数の分類を選んだ場合は、各ファイルの適用対象と条件に合う項目だけを参照します。
チェックを外すとそのファイルの本文だけがプロンプトから消えます。
ルールファイルは HTML を出力するときに読み込むため、ファイルを編集・追加・削除したら
`export_html()` を再実行してください。顧客・商品ファイルは記入例なので、実データに合わせて編集できます。

計算フィールドの「AI 用プロンプトを作る」には、
`template/calc_prompt_rules/` の Markdown だけを表示します。
`00-calculation-rules.md` は最初からチェック済みで、IIF・集計・ゼロ除算などの計算ルールを
プロンプトへ加えます。こちらもチェックで追加・削除でき、ファイル変更後は HTML の再生成が必要です。

### 設定画面が出した YAML を適用する

```python
wb = TwbWorkbook.open("template.twb")
wb.apply_config("twbpatch_dashboard.yaml")
wb.save("output.twb", overwrite=True)
```

適用されるのは次のとおりです。

| 節 | 何をするか |
|---|---|
| `design.font` | ワークブック全体の既定フォント |
| `datasources.*.folders` | 表示名の変更とフォルダ分類 |
| `datasources.*.renames` | フォルダへは入れず、表示名だけを変更 |
| `datasources.*.calculations` | 計算フィールドの作成。同名があれば式・データ型・役割・フォルダを上書き。式が参照する計算フィールドから先に作るので、並び順は問わない |
| `datasources.*.hierarchies` | 階層（ドリルダウン）の作成。`{階層名: {folder, fields}}`（`fields` の並びがドリルの順）。**上の 3 つの後**に作るので、改名後の名前や作ったばかりの計算フィールドを指せる。同名の階層があれば作り直す |
| `dashboard` | シートを作って並べ、アクションを張る |
| `kpi_tree` | ノードごとに KPI カードを作り、ツリー状に並べたダッシュボードを作る（`build_kpi_tree`）。`dashboard` と両方あればダッシュボードは 2 つ |

`design` の色・余白・フィルターの「適用」ボタンは、**ダッシュボードを組むときに使います**。
グラフの色に `@main_color` と書くと、デザインルールの色コードに置き換わります。
`dashboard` も `kpi_tree` も無い設定では届かないので、名前を警告ログへ出して読み飛ばします。
詳細は [docs/developer/html_screen_spec.md](../../developer/html_screen_spec.md)。

計算フィールドを画面で定義した場合は、**一度 `.twb` へ焼き直してから画面を出し直します。**
そうすると 2 周目にはグラフの項目候補として選べるようになります。
手順は [docs/user/library/roundtrip.md](roundtrip.md) にまとめています。

### 動くサンプル

`examples/build_dashboard.py` が同梱のサンプルです。入力は `examples/sample_ec.twb`、
出力は `outputs/` で、リポジトリの外を読み書きしません。

```bash
uv run python examples/build_dashboard.py
```

Windows では `scripts/tabsdk.bat` からも実行できます。メニューの 1 は設定 HTML の出力、
2 は YAML を適用した設定 HTML の出力、3 は YAML を適用したダッシュボード `.twb` の作成、
4 は Tableau Workbook から定義書 Excel の作成、9 は終了です。9 を選ぶと挨拶をランダムに表示して閉じます。
