# twbpatch

既存の Tableau `.twb` / `.twbx` を読み込み、データソース・フィールド・計算フィールド・
フォルダ・ワークシート・ダッシュボードなどを取得して編集し、保存する Python ライブラリです。

**この 1 ファイルが公開 API の全体です。** 前半が使い方、後半（§0 以降）が
シンボルごとのリファレンスになっています。

| 見たいもの | 場所 |
|---|---|
| まず動かす | [基本的な使い方](#基本的な使い方) |
| 画面で設定して `.twb` を作る | [設定画面を HTML で出す](#設定画面を-html-で出す) |
| クラスとメソッドの一覧 | [§3 接続型モデル](#3-接続型モデル) |
| 設計の決まりごと（正典） | [docs/model_api_spec.md](docs/model_api_spec.md) |

## 動作要件

- Python 3.10 以上
- `lxml` 5.0.0 以上
- `PyYAML` 6.0 以上

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
`twbpatch/prompt_rules/` 直下の Markdown ファイルを参照ルールとして選べます。
共通ルールは最初から選択され、顧客・商品などの分類は必要なものをチェックします。
チェックを外すとそのファイルの本文だけがプロンプトから消えます。
ルールファイルは HTML を出力するときに読み込むため、ファイルを編集・追加・削除したら
`export_html()` を再実行してください。顧客・商品ファイルは記入例なので、実データに合わせて編集できます。

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
詳細は [docs/html_screen_spec.md](docs/html_screen_spec.md)。

計算フィールドを画面で定義した場合は、**一度 `.twb` へ焼き直してから画面を出し直します。**
そうすると 2 周目にはグラフの項目候補として選べるようになります。
手順は [docs/roundtrip.md](docs/roundtrip.md) にまとめています。

### 動くサンプル

`examples/build_dashboard.py` が同梱のサンプルです。入力は `examples/sample_ec.twb`、
出力は `outputs/` で、リポジトリの外を読み書きしません。

```bash
uv run python examples/build_dashboard.py
```

Windows では `scripts/tabsdk.bat` からも実行できます。メニューの 1 は設定 HTML の出力、
2 は YAML を適用した設定 HTML の出力、3 は YAML を適用したダッシュボード `.twb` の作成です。

---

# 公開 API リファレンス

根拠は [docs/model_api_spec.md](docs/model_api_spec.md)（正典）と実装からの AST 抽出。
以下の `§` は**このファイル内の節番号**を指します。

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
| 属性の設定 | `set_<対象>()` | `set_categorical_colors()` / `set_axis_visibility()` |

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
| `save` | `path: str, *, validate: bool = True, overwrite: bool = False` | `None` | 保存。`validate=True` なら検証に失敗した時点で書き込まない。`overwrite=False` で既存ファイルへの上書きを拒否。KPI ツリーのエッジ（`build_kpi_tree(edges=True)`）があれば、同梱の `twbpatch_kpi_tree_edge.hyper` を .twb の隣（.twbx なら中）へ置く |
| `reload` | — | `TwbWorkbook` | 未保存の変更を破棄して再読込。既存の接続型モデルは無効化され、以降の操作は `DetachedModelError` |
| `validate` | — | `list[TwbValidationMessage]` | 現在の XML ツリーを検証し、問題を列挙する |
| `get_unsupported_features` | — | `list[TwbUnsupportedFeature]` | SDK が未対応の Tableau 機能を列挙する |
| `export_json` | — | `dict` | 公開値のみを組み立てて辞書化する。非公開コンテキストと `caption` は含めない |
| `export_html` | `path: str \| Path, *, title: str = "twbpatch 設定", overwrite: bool = False, config: str \| Path \| dict \| None = None` | `Path` | 設定画面の HTML を 1 ファイル出力する。外部参照なしで単体で開ける。`config` に設定 YAML を渡すと、**`.twb` に残らないデザインルール・ダッシュボード・KPI ツリーを画面へ戻す**（2026-09-21）。仕様は `docs/html_screen_spec.md` |
| `apply_config` | `config: str \| Path \| dict, *, field_grouping: str = "folder"` | `TwbWorkbook` | 設定画面が出力した YAML を適用する。`design` / `datasources` / `dashboard` / `kpi_tree` の全節に対応。届かない設定は警告ログを出して読み飛ばす |

### 2.3 リソース取得・作成

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_datasources` | `*, id=None, name=None` | `list[TwbDatasource]` | データソース一覧。`Parameters` は除外される |
| `get_worksheets` | `*, id=None, name=None` | `list[TwbWorksheet]` | ワークシート一覧 |
| `get_dashboards` | `*, id=None, name=None` | `list[TwbDashboard]` | ダッシュボード一覧 |
| `get_parameters` | `*, id=None, name=None, include_hidden: bool = False` | `list[TwbParameter]` | パラメータ一覧。内部用の hidden は既定で除外 |
| `create_worksheet` | `*, name: str, visible: bool = True` | `TwbWorksheet` | 空のワークシートを作成 |
| `create_dashboard` | `*, name: str, width: int = 1200, height: int = 800, sizing_mode: str = "fixed"` | `TwbDashboard` | ダッシュボードを作成 |
| `create_hyper_datasource` | `*, name: str, path: str, fields: list[dict]` | `TwbDatasource` | **Tableau 抽出（.hyper）専用**のデータソースを作成。.hyper の中身は読めないので列は `fields=[{"name", "datatype", "role"}, ...]` で宣言する。`datatype` は `string` / `integer` のみ。CSV / Excel などは作れない |
| `create_parameter` | `*, name: str, value: object, datatype: str = "string", domain_type: str = "any", allowable_values=None, min_value=None, max_value=None, step_size=None, hidden: bool = False` | `TwbParameter` | パラメータを作成。`domain_type` は `any` / `list` / `range` |
| `add_filter` | `field: FieldInput, *, scope="worksheet", worksheets=None` | `list[TwbWorksheetField]` | **フィルターの入口。** `scope="worksheet"` は各シートの filters シェルフへ、`scope="datasource"` はデータソースフィルター（`shared-views`）を作って各シートにスライスを足す。`worksheets=None` はそのデータソースを使う全シート。戻り値は `container.add_filter()` へそのまま渡せる（`scope="datasource"` では空リスト） |

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
| `draw_sheet` | `*, name, items=None, bar_metrics=None, color_metrics=None, bar_colors=None, color_starts=None, color_ends=None, item_shelf="rows", title=None, visible=True` | 帳票。`items` を指定シェルフへ並べる。**メジャーは集計してからディメンション（不連続）として置く**（2026-09-21。値を並べる表なので、連続の軸ではなく文字として出す）。数字は右・文字は左に揃える。表ヘッダー（フィールドラベル）は薄い灰色 `#f0f0f0`。行の縞模様は消す。ダッシュボードでは「幅を合わせる」で表示する。`bar_metrics` / `color_metrics` で棒・色帯の列を足す（下記） |
| `draw_bar` | `*, name, item=None, metric, sub_metric=None, line_metric=None, item_shelf="rows", aggregation="auto", descending=True, bar_color=None, sub_bar_color=None, line_color=None, title=None` | 棒グラフ。`item` 別に `metric` を集計して並べる。`item` を省くと棒 1 本。`sub_metric` はバーインバー、`line_metric` は二重軸の折れ線（下記）。ダッシュボードでは向きに合わせて表示倍率を変える: `item_shelf="rows"`（既定、横棒）は「幅を合わせる」、`item_shelf="columns"`（縦棒）は「高さを合わせる」（2026-09-22） |
| `draw_card` | `*, name, main_metric, mode="sub_metric", sub_metric=None, budget_metric=None, budget_threshold=1.0, achieved_color="#2f9e44", missed_color="#e03131", main_color="#602fff", value_color="#333333", budget_value_color="#666666", title_background_color=None, vertical_alignment="center", main_aggregation="auto", sub_aggregation="auto", budget_aggregation="auto", folder=None` | KPI カード。`mode="sub_metric"` は主指標と補助指標を大きく表示。`mode="budget"` は予実比較で、`budget_metric` が `budget_threshold` 以上なら `achieved_color`、未満なら `missed_color` で出す（下記）。`folder` は `mode="budget"` が作る計算フィールドの入れ先（例: `"41_KPIカード"`） |
| `draw_quadrant` | `*, name, item, x_metric, y_metric, size_metric, colors=(4色), x/y/size_aggregation="auto", opacity=0.6, title=None` | 散布図の四象限。中央値で区切り4色に塗り分ける。`{シート名}_四象限` を作る（下記）。外れ値を除くパラメータ `{シート名}_中央比率`（初期値 0.95。X・Y それぞれ中央値を中心に中央の 95% だけ残す）と `{シート名}_売上閾値`（初期値 0。集計後のサイズ指標がこの値以上の点だけ残す）も作り、真偽値の計算フィールドを True だけ残す条件にする。`build_report()` は 2 つを右上に浮動で横並びにする（2026-09-24。Tableau で動作確認済み） |
| `draw_crosstab` | `*, name, x_item, y_item, color_metric, label_metric, color/label_aggregation="auto", min_color=None, mid_color=None, max_color=None, title=None` | ヒートマップ付きクロス集計 |

**帳票の中の棒と色付け**（2026-09-22 追加）。`bar_metrics` は棒の列、`color_metrics` は
色帯の列として**横に足す**。棒はメジャーを連続で置いて軸を隠すだけ。色帯は
`{シート名}_色帯{n}`（`MIN(1)`）の軸を 0〜1 に固定して隠し、`{シート名}_色帯幅{n}`
（`MIN(-1)`）を長さにしたガントバーを置いて、色にメジャーを載せる（セル幅いっぱいの帯）。
軸は重ねず横に並べる（`fold` を書かない）ので、列は何本でも足せる。
**棒・色帯の列の項目名だけ Tableau が出さない**ので、その分だけ浮動テキストでヘッダーの帯へ重ねる
（`build_report()` が行う）。列幅は「ゾーンの幅 − 余白 ÷ 列数」の暫定値で、同じ幅を
ワークシートの列にも書く。幅も位置も概算で、あとから Tableau で直す前提。
**どちらの列も値をラベルで出し、右に揃える。** 色は列ごとに指定する。
**棒は 1 色（`bar_colors`）、色帯は 2 色**（`color_starts` が薄い側、`color_ends` が濃い側）。
2 色は `<preferences>` の独自パレット（`ordered-sequential`）として書く。

**棒グラフの二重軸**（2026-09-22 追加）。`sub_metric` でバーインバー（軸を同期し、
内側の棒を細くする）、`line_metric` で二重軸の折れ線（単位が違うので軸は同期しない）。
`TwbWorksheet.set_dual_axis()` がシェルフを `+` で連結して 2 本目の軸に `fold="true"` を書き、
軸ごとのペインがマークの種類・色・太さを持つ。

**Tableau の二重軸は 2 軸まで**なので、3 つそろえたときは棒の軸を
`TwbWorksheet.add_measure_values()` でメジャーバリューにまとめ（メジャーネームで色分け、
`TwbPane.update(stacked=False)` でスタックを外して重ねる）、折れ線を 2 本目の軸にする。
このときは棒 2 本が同じ太さ・メジャーネームの配色になり、`bar_color` / `sub_bar_color` は効かない。

**KPI カードの予実比較モード**（2026-09-21 追加）。ラベルの文字色は値ごとに
1 色しか書けないため、**条件の数だけ計算フィールドを作る。**
条件ごとに率と文言の 2 つを作る。
`{シート名}_達成` = `IF <予算比の式> >= <境界値> THEN <予算比の式> END`（パーセント表示）、
`{シート名}_達成判定` = `IF … THEN "達成" END`（文字列）。`{シート名}_未達` は `<` の対。
条件に合わない側は NULL になり表示されないので、達成なら `achieved_color`、
未達なら `missed_color` で「105% 達成」だけが見える。
**率と文言は書式が違うので run を分ける**（2026-09-22）。率は太字なしで
`budget_value_color`、文言は太字で `achieved_color` / `missed_color`。
**率は連続（`:qk`）、文言は文字列なので不連続（`:nk`）で置く。**
`mode="budget"` と `sub_metric` は併用できない。
**`folder=` を渡すとこの 4 本を同じフォルダへ入れる**（無ければ作る、2026-09-22）。

**`draw_*` が作る計算フィールドは、同名があれば作り直す**（2026-09-22 に四象限も統一）。
カードの `{シート名}_達成` ほか 3 本と、四象限の `{シート名}_四象限` が対象。
シートの持ち物なので、指標を変えて描き直したときに古い式が残らないようにする。
設定 YAML の `calculations` 節で同じ名前を定義していても、こちらが優先される。
**同名のシートが残っているときは、計算フィールドを触る前に
`worksheet already exists` で止める**（そのシートが参照していて消せないため）。

### 2.4.1 KPI ツリーの配置（`build_kpi_tree`）

既にあるシート（通常は `draw_card` の KPI カード）を、指標の親子関係のツリーとして
左から右へ並べたダッシュボードを作る。**シートは作らない。** 戻り値は `TwbDashboard`。

| メソッド | 引数 | 説明 |
|---|---|---|
| `build_kpi_tree` | `*, dashboard_name, root: KpiNode, align="center", edges: bool = False, edge_hyper: str \| None = None, content_style: dict \| None = None, spacing_scale=1.0, border_color=None` | `align` は親カードの位置で `"center"`（子の範囲の縦中央）/ `"top"`（上端）。`edges=True` でエッジ（線）を描く（`align="top"` のときだけ）。`content_style` は台紙の書式で、`build_report` と同じく既定に重ねる |

`KpiNode(worksheet, children=[])` は `twbpatch` から import する値オブジェクト。
`children` が空のノードがツリーの末端になる。

- ノードは 横 200 × 縦 150 固定。ダッシュボードの大きさは ツリーの深さ × 200、末端ノードの数 × 150 に、周りの余白 8 ずつを足したものになる
- 見た目はダッシュボードの `build_report` と同じ。灰色の台紙に白いカード（内側の余白 0・角の丸み 8）を置き、カードのタイトルは帯（背景色）だけ出す
- 同じシートを 2 つのノードに置く、別ワークブックのシートを渡すと例外。このときダッシュボードは作られない
- **エッジ（線）**: `edges=True` で描く。座標の .hyper はライブラリに同梱したものを使い、**`save()` が .twb の隣
  （.twbx なら中）へ `twbpatch_kpi_tree_edge.hyper` として置く**ので、ファイルを用意する必要はない。自前の .hyper を使うときは
  `edge_hyper="edge.hyper"` のように .twb から見たパスを渡す（こちらはコピーしない）。
  データソース「KPIツリーのエッジ」が無ければ作り、あれば使い回す。親ノードごとに `エッジ|<親のシート名>` という非表示のシートを作り、
  カードと子の列のあいだに幅 60px で置く。ダッシュボードの幅は その分だけ広がる。1 つの親の下の末端は 7 つまで

```python
from twbpatch import KpiNode

card = lambda name, metric: workbook.draw_card(datasource, name=name, main_metric=metric)
workbook.build_kpi_tree(
    dashboard_name="KPIツリー",
    root=KpiNode(card("売上", "Sales"), [
        KpiNode(card("利益", "Profit"), [KpiNode(card("数量", "Quantity"))]),
        KpiNode(card("値引率", "Discount")),
    ]),
    align="top",
)
```

### 2.4.2 ウォーターフォール（`add_index_relation` / `build_waterfall_metric` / `build_waterfall_chart`）

ウォーターフォールグラフの実装ロードマップ（2026-09-22 検討）: ①データソースへ
`1=1` のクロスジョインでリレーションを追加 → ②指標を縦持ちに変換 → ③ガントチャート指標を
作成 → ④ウォーターフォールグラフを作成。①②③④とも実装済み。

**入力と出力（3関数のつながり）**

| 関数 | 入力 | 出力 |
|---|---|---|
| ① `add_index_relation` | `datasource`（対象データソース）、`join_to`（既存フィールド、そのフィールドが属するテーブルへリレーションを足す）、`path`（書く .txt のパス）、`column`（既定 `"連番"`）、`max_index`（既定 20）、`folder`、`overwrite`（既定 `False`） | `TwbField`（連番フィールド。②の `index=` へそのまま渡す） |
| ②③ `build_waterfall_metric` | `datasource`、`name`（生成する4フィールドの接頭辞）、`index`（①の出力、または同じ意味のフィールド）、`metrics`（縦持ちにしたい指標のリスト）、`connectors`、`landing`、`folder` | `WaterfallMetric`（`.value`/`.label`/`.kind`/`.size` の4 `TwbField` と、`.count`/`.used_index` の2 `int`。④の `metric=` へそのまま渡す） |
| ④ `build_waterfall_chart` | `datasource`、`name`（作るワークシート名）、`index`（①と同じフィールド）、`metric`（②③の出力）、`increase_color`/`decrease_color`/`connector_color`/`landing_color` | `TwbWorksheet`（組み上がったウォーターフォールのシート） |
| ①〜④一括 `build_waterfall` | `datasource`、`name`、`metrics`（メジャーの複数選択）、`connectors`、`landing`、`increase_color`/`decrease_color`/`landing_color`、`title`、`visible`、`folder` | `TwbWorksheet`（設定画面向け。`index`/`join_to`/`path`/`connector_color` を渡さずに済む） |

①の出力（`TwbField`）と②③の出力（`WaterfallMetric`）を、そのまま次の関数へ渡すだけで
一通り作れる（下のコード例のとおり）。設定画面から使うときは、この 3 手順の代わりに
`build_waterfall`（下記）を 1 回呼ぶだけでよい。

**①は `add_index_relation` が担う。** twbpatch が組み立てられないのは `<extract>` の
中身（.hyper のバイナリ）だけで、`<connection>` の物理リレーションと `<object-graph>` の
論理オブジェクト・`1=1` の `<relationship>` は純粋な XML 操作なので自動化できる
（`examples/ウォーターフォール.twb` の `edge.txt` の追加を実測した形で書く）。追加した表を
実際にクエリへ使うには、Tableau で開いて一度「データソースの更新」（抽出の更新）をする
必要があるが、これは抽出済みのデータソースへ表を足したときの通常の手順で twbpatch 特有の
制約ではない。

**②③は `build_waterfall_metric` が担う。** ①で足した連番フィールド（`index=`）を受け取り、
選んだ指標（`metrics=`、並び順に連番 1, 2, 3... を割り当てる）を縦持ちに変換する
4 つの計算フィールドを作る。値が 0 以上なら「増加」、負なら「減少」と動的に判定する。
**合計（終了）バーは作らない**（2026-09-23。実測した手作業の例には無かったため外した。
要るときは `metrics` へ合計の計算フィールドを 1 つ足して渡せばよい）。`size`（`-値`）は
③のガントバー用（実測した手作業の例の符号反転に合わせる）。

**③はもう1つ、`TwbWorksheet.add_field(running_total=True)` も担う**（2026-09-23）。
シェルフに置いたピルへ Tableau の「累計」クイック表計算（`<table-calc type="CumTotal">`）を
掛ける。別の計算フィールドは作らない（実測した手作業の例と同じ形）。`shelf` は
`rows`/`columns` のみ、`aggregation` が必須で `table_calculation`/`date_level` とは併用できない。

**④は `build_waterfall_chart` が担う。** `index` と②③の `WaterfallMetric` を受け取り、
ワークシートを組む: `index` だけを列へ、`metric.value` を `running_total=True` で行へ、
マークはガントチャート、色は `metric.kind`（`increase_color` / `decrease_color` /
`connector_color` で色指定）、サイズは `metric.size`、ラベルは `metric.label`。
**`metric.label` は列に置かない**（2026-09-23、実機で確認して変更。`index` だけで列の
位置は決まり、ラベルのマークだけで表示できる）。**累計の計算対象は「特定のディメンション」
で `index`・`metric.label` の両方を明示する**（`running_total_fields=[index, metric.label]`。
列に置いていない `metric.label` も対象にできる）。**連番は `1..metric.used_index` だけに
絞るフィルタを作る**（①の連番テーブルは `max_index` まで容量を持つが、`metrics` で
使わなかった分は値が NULL になるだけで残ってしまうため）。**`index`（連番）の見出しは
隠す**（軸に 1, 2, 3... という数字が出ても意味が無いため。ラベルのマークで項目名を出す）。
セル幅・回転したラベルなどは未実装（構造が先、見た目は後で足す方針）。

**①のリレーションを Tableau に認識させるには、`object-graph` の `<object>` へ
`context="extract"` の `<properties>` も要る**（2026-09-23、実機で確認）。無いと
リレーションシップ画面でその表が未接続に見える（`<extract>` 自体は変えないので、値は
「データソースの更新」まで入らないが、リレーションの構造は最初から見える）。

**`build_waterfall_metric(connectors=True)`**（2026-09-23）は奇数番号（1, 3, 5, ...）に
指標を割り当て、間の偶数番号（2, 4, ...）を値 0 の「連結」枠にする。値 0 の Gantt バーは
長さが無いので、太さ（`mark_size`）だけの薄い横線に見える——実機で確認済み。種別は 0 の
ときだけ固定で `"連結"`、`build_waterfall_chart` は `connector_color`（既定 `#cccccc`）を
これに割り当てる。

**`build_waterfall_metric(landing=True)`**（2026-09-23、ユーザーの手作業の例に合わせて
追加）は連番の続きにもう 1 枠足し、選んだ指標すべての合計を**マイナス**で入れる
（`-<式1>-<式2>-...`）。累計がちょうど 0 まで戻る「着地」バーになる。項目名・種別は
固定で `"着地"`（`connectors` の判定より先に見る）。`connectors=True` と併用すると、
着地の手前にも連結枠を挟む。`build_waterfall_chart` は `landing_color`（既定 `#4263eb`）を
これに割り当てる。

`WaterfallMetric.used_index` は実際に使う連番の上限（`connectors`/`landing` の組み合わせで
変わる）で、`build_waterfall_chart` のフィルタに使う。

`add_index_relation` / `build_waterfall_metric` は両方とも `folder=` でフォルダへ
入れられる（無ければ作る）。

| メソッド | 主な引数（先頭に省略可能な `datasource`） | 説明 |
|---|---|---|
| `add_index_relation` | `*, join_to: FieldInput, path: str, column="連番", max_index=20, folder=None, overwrite=False` | 連番（1〜`max_index`）だけを持つ .txt を `path` へ書き、`join_to` の属するテーブルへ `1=1` でクロスジョインする。`overwrite=True` は既存の同名ファイルを上書きする（既定は `ValueError`） |
| `build_waterfall_metric` | `*, name, index: FieldInput, metrics: list[FieldInput], aggregation="auto", folder=None, connectors=False, landing=False` | `{name}_値`（measure）・`{name}_項目名`（dimension）・`{name}_種別`（dimension、"増加"/"減少"、`connectors=True` なら "連結" も、`landing=True` なら "着地" も）・`{name}_サイズ`（measure、`-値`）の 4 計算フィールドを作る |
| `build_waterfall_chart` | `*, name, index: FieldInput, metric: WaterfallMetric, increase_color="#2f9e44", decrease_color="#e03131", connector_color="#cccccc", landing_color="#4263eb", title=None, visible=True` | ウォーターフォールグラフのワークシートを組む（下記） |

```python
index_field = workbook.add_index_relation(
    datasource,
    join_to="前月残",
    path="waterfall_index.txt",
    folder="40_WF",
)
metric = workbook.build_waterfall_metric(
    datasource,
    name="残高",
    index=index_field,
    metrics=["前月残", "今月売上", "今月原価"],
    folder="40_WF",
)
worksheet = workbook.build_waterfall_chart(
    datasource,
    name="ウォーターフォール",
    index=index_field,
    metric=metric,
)
```

**`build_waterfall_chart` は `draw_*` ではなく `build_*`。** `metric` が単純な `FieldInput`
ではなく `build_waterfall_metric()` の戻り値（`WaterfallMetric`）を取るため、HTML 設定画面の
汎用フィールド選択 UI では表せない（`build_kpi_tree()` が `draw_*` を名乗らないのと同じ理由）。

#### `build_waterfall`: 設定画面向けの一括版（2026-09-23 追加）

設定画面のダッシュボードタブに「ウォーターフォール」というグラフ種類を追加した。
①〜④を毎回別々に書くのは画面から使いにくいため、`metrics`（メジャーの複数選択）だけを
受け取って 1 回でまとめて組む関数を別に用意した。

```python
worksheet = workbook.build_waterfall(
    datasource,
    name="残高",
    metrics=["前月残", "今月売上", "今月原価"],
    connectors=True,
    landing=True,
)
```

- **連番テーブルはデータソースにつき 1 つだけ作り、複数のウォーターフォールで使い回す**
  （共有テーブル方式）。列名は固定で `"連番"`、容量は固定で `21`（指標 10 個 +
  `connectors` + `landing` の最大構成がちょうど収まる数）。**データソースに `"連番"` が
  あるかどうかだけで①をスキップするか判断する。** 無ければ `.txt` の保存先にワークブックを
  開いた元ファイルの隣の固定名 `twbpatch_waterfall_index.txt` を、`add_index_relation`
  の `overwrite=True` を付けて作る。`apply_config()` は毎回 source の `.twb` を開き直して
  別名で保存する運用があり得るため（source 自体は変わらないので対象データソースは
  毎回「連番」を持たない）、`.txt` は前回分が残っていることがある。中身は常に同じ
  （1..21）なので上書きしてよい。`join_to` は `metrics` の中から
  計算フィールドでないものを探して使う（計算フィールドは `<extract>` の cols マップに
  乗らず `join_to` にできないため。`metrics` に無ければデータソース全体から探す）
- **計算フィールドはウォーターフォールごとに個別に作る**（`name` で名前空間を分ける）
- **`connector_color` は画面に出さない固定値 `#cccccc`。** 連結線は薄い線という
  位置づけで色を変える需要が薄いため、画面には `increase_color`/`decrease_color`/
  `landing_color` の 3 色だけを出す
- `metrics` が長すぎて連番テーブルの容量（21）を超える構成は、計算フィールドを作る前に
  `ValueError` で止める
- 画面側は `_CHART_LABELS`（`html_export.py`）に `"build_waterfall": "ウォーターフォール"`
  を追加し、`config_apply.py` の `_draw_area()` は `chart` が `draw_` で始まらない名前も
  通せるよう、明示的なホワイトリスト（`_EXTRA_CHARTS`）で許可する

### 2.4.3 インフォメーション: `draw_info`（2026-09-23 追加）

アイコン + カスタムツールヒント（マウスを乗せると出る自由な説明文）だけの小さな
ワークシートを作る。`outputs/waterfall_chart_test10.twb` の手作業の `"info"` シートを
実測して作った。

```python
worksheet = workbook.draw_info(
    datasource,
    name="info",
    icon="setting",              # "info" / "quest" / "setting" / "attention"
    heading="説明",
    text="この指標は前月末時点の残高です。",
)
```

| 引数 | 説明 |
|---|---|
| `datasource` | 省略可（ワークブックに 1 つしか無ければ自動解決、複数あれば `ValueError`） |
| `name` | ワークシート名 |
| `text` | ツールヒントの本文（必須、複数行可） |
| `icon` | 既定 `"info"`。`"quest"`＝疑問、`"setting"`＝設定、`"attention"`＝注意 |
| `heading` | ツールヒントの太字見出し。既定 `"説明"` |
| `color` | マークの色。既定 `#e15759` |
| `folder` | ダミーの計算フィールドを入れるフォルダ |

- **行・列にデータを置かず、`STR(1)` のダミー計算フィールドを 1 つだけツールヒントの
  シェルフに置く。** マーク自体はデータを使わない固定のシェイプ（画像）と固定色だけで
  表現する
- **ダミーの計算フィールドはデータソースにつき 1 つを複数の `draw_info()` で共有する**
  （名前は固定 `"インフォメーション_key"`。ウォーターフォールの共有連番と同じ考え方）
- **アイコン画像はワークブックに埋め込まれない。** `<style-rule element="mark">` の
  `<format attr="shape" value="webinfo/xxxxx.png">` として、Tableau 側の
  シェイプパレット（`形状/webinfo/` フォルダ）を参照するだけ。そのパレットと画像が
  無い環境で開くと、Tableau は既定のシェイプを代わりに表示する（開けなくなるわけではない）
- カスタムツールヒントは `<pane><customized-tooltip><formatted-text>` に、見出しを
  太字の `<run bold="true">`、本文を別の `<run>` として書く（見出しがあるときは本文の
  先頭に改行を 1 つ入れる。実測どおり）
- ダッシュボードに置いたときの内側の余白は `draw_card` と同じ `0`
  （`_CHART_ZONE_PADDING["draw_info"]`。実測した手作業のシートは余白の無い小さい
  ゾーンだったため）

#### 設定画面: グラフのエリア／KPI ツリーのノードに「インフォメーションを追加」（2026-09-23 追加）

`draw_info()` は画面の「グラフ種類」プルダウンには出さない（`_HIDDEN_FROM_CHART_LIST`）。
代わりに、**既存のグラフに説明アイコンを重ねる**「インフォメーションを追加」
チェックボックスを画面に追加した（2026-09-23、ユーザーの要望でグラフ種類の選択肢からは
外した）。KPI ツリーのノードにも同じチェックボックスが出る。

```yaml
areas:
  - kind: worksheet
    sheet: 売上推移
    chart: draw_bar
    params: {...}
    info:
      text: "この指標は前月末時点の実績です。"
      icon: "info"       # "info" / "quest" / "setting" / "attention"
      heading: "説明"     # 省略可
      color: "#e15759"   # 省略可
```

- **受け手（`config_apply.py` の `_apply_info()`）は `build_report()` / `build_kpi_tree()`
  の後で処理する。** 対象シートが実際にどこへ Tiled 配置されるかは、レイアウトを
  組み終えるまで px 位置が決まらないため
- 対象シートのゾーン（`dashboard.get_zones()` から `worksheet_id` で検索）の
  **右上へ 30px 四方・余白 4px** で `add_floating_worksheet()`（既存 API、浮動配置）を
  使って重ねる。ワークシート名は固定で `info|<対象シート名>`
- 画面の本文はテキストエリア（複数行）。`_param_kind()` に `name == "text"` の特例で
  `"textarea"` を追加した
- アイコンの選択肢・各入力の既定値は `DRAW_SPECS["draw_info"]` からそのまま読む
  （画面側に二重に持たない）

### 2.5 その他

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `set_default_font` | `font: str` | `TwbWorkbook` | ワークブック既定フォントを設定 |
| `apply_field_config` | `yaml_path: str \| Path, *, field_grouping: str = "folder"` | `TwbWorkbook` | YAML の定義に沿ってフィールド名・フォルダを一括適用 |

### 2.6 メタデータの一括読み取り（旧 API の残り 4 件）

**接続型モデルではなく `models.py` の投影 dataclass を返す。** 新 API に同じ情報を
取る手段が無いため残している（§9、`docs/backlog.md` L-6）。穴が埋まったら消す。
2026-09-13 にゾーンとアクションの穴の一部を埋めた（§3.10 / §3.11）。消すかどうかは未判断。

| メソッド | 引数 | 戻り値 | 新 API に無いもの |
|---|---|---|---|
| `list_dashboard_zones` | `dashboard=None, *, by="auto", width_px=None, height_px=None, include_device_layouts=False` | `list[TwbDashboardZone]` | デバイスレイアウト（raw 座標・px 換算・`parent_id` / `depth` は §3.10 で読める） |
| `list_dashboard_actions` | `dashboard=None, *, by="auto"` | `list[TwbDashboardAction]` | 無し（除外シートと `details` は §3.11 で読める） |
| `list_dashboard_fields` | `dashboard=None, *, by="auto", max_filter_value_chars=40` | `list[TwbWorksheetField]` | `max_filter_value_chars` |
| `list_worksheet_fields` | `worksheet=None, *, by="auto", max_filter_value_chars=40` | `list[TwbWorksheetField]` | `values` / `mark_type` / `category` / `type` |

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
| `source` | `Source` | 接続先の値オブジェクト（§5） |
| `field_grouping` | `str \| None` | フィールドの grouping 方式 |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbField]` | 所有フィールド一覧 |
| `get_folders` | `*, id=None, name=None` | `list[TwbFolder]` | フォルダ一覧 |
| `get_drill_paths` | `*, id=None, name=None` | `list[TwbDrillPath]` | 階層（ドリルパス）一覧 |
| `create_drill_path` | `*, name: str, fields: list[FieldInput], folder=None, create_folder_if_missing=False` | `TwbDrillPath` | 階層を1つ作成。`fields` の順がドリルの階層順。2つ以上が要る。`folder=` を渡すと `type="drillpath"` の項目として入れ、**階層に入れたフィールドの `folder-item` は取り除く** |
| `create_group` | `*, field: FieldInput, groups: dict[str, list[str]], name=None, folder=None, create_folder_if_missing=False` | `TwbField` | 値をまとめたグループフィールドを1つ作成。`groups` は グループ名 → まとめる値。**まとめない値は書かなくてよい**（Tableau が単独扱いする）。`name` 既定は `<元フィールド名> (グループ)` で、**caption ではなく内部 ID になる**。元フィールドは文字列型のみ |
| `get_relations` | `*, id=None, name=None` | `list[TwbRelation]` | 物理テーブルの結合構造 |
| `get_relationships` | `*, id=None, name=None` | `list[TwbRelationship]` | 論理リレーションシップ |
| `create_folder` | `*, name: str` | `TwbFolder` | フォルダを作成 |
| `create_calculated_field` | `*, name, formula, datatype="real", role="measure", discrete=False, folder=None, hidden=False, number_format=None, table_calculation=None, formula_ref="auto", strict=True, ref_map=None, create_folder_if_missing=False` | `TwbField` | 計算フィールドを1件作成。`formula` 内の表示名は保存前に `id` へ変換される |
| `create_calculated_fields` | `*, calculations: dict, folder=None, role="measure", discrete=False, strict=True, create_folder_if_missing=False` | `list[TwbField]` | 計算フィールドを一括作成 |
| `set_filter` | `*, field: TwbField` | `TwbDatasource` | データソースレベルのフィルタを設定 |
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
| `move_to_folder` | `folder: str \| TwbFolder, *, create_folder_if_missing=False` | `TwbField` | フォルダへ移動。フォルダ名でも `TwbFolder` でも渡せる。同一データソースのフォルダのみ |
| `remove_from_folder` | — | `TwbField` | フォルダから外す |
| `delete` | — | `None` | 削除。計算式・配置・フィルタ等から参照されていれば `ResourceInUseError` |

**`folder=` は無ければ `NotFoundError`。** 暗黙には作らない。`create_folder_if_missing=True`
を渡したときだけ、その名前でフォルダを作って割り当てる。`folder=` を取る 5 メソッド
（`create_calculated_field` / `create_calculated_fields` /
`create_drill_path` / `create_group` / `move_to_folder`）で規則は同じ。

### 3.3 `TwbFolder`

**変数**: `id: str` / `name: str` / `datasource_id: str`

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbField]` | 収容しているフィールド |
| `update` | `*, name=UNSET` | `TwbFolder` | 改名。同名があれば `ValueError`。`<folder-item>` はフィールドと階層を指すので追随は要らない |
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
| `lines_visible` | `bool` | 書式の「線」（グリッド線・ゼロ線・ドロップライン・参照線・軸の線と目盛）が消されていなければ `True` |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbWorksheetField]` | 配置済みフィールド（軸・ペイン・フィルタ） |
| `get_panes` | `*, id=None, name=None` | `list[TwbPane]` | ペイン一覧。複数ある場合は対象を明示的に選ぶ |
| `get_reference_lines` | `*, id=None, name=None` | `list[TwbReferenceLine]` | リファレンスライン |
| `get_filters` | `*, id=None, name=None` | `list[TwbWorksheetFilter]` | フィルタ設定 |
| `add_field` | `field: TwbField, *, shelf: str, aggregation=None, discrete=None, table_calculation=UNSET, table_calculation_field=None, date_level=None, running_total=False, running_total_fields=None` | `TwbWorksheetField` | 既存フィールドをシェルフへ配置。`shelf` は `rows` / `columns` / `pages` / `filters`。`running_total=True` は「累計」クイック表計算（`shelf` が `rows`/`columns` のときだけ、`aggregation` 必須、`table_calculation`/`date_level` とは併用不可。ウォーターフォールのガントバー向け、2026-09-23）。`running_total_fields` を渡すと「特定のディメンション」で計算対象を明示する（列に置いていないフィールドも対象にできる。参照に `:2` が付く） |
| `add_filter` | `field: TwbField` | `TwbWorksheetField` | フィルタとして配置 |
| `add_filter_slice` | `field: TwbField` | `TwbWorksheet` | スライス用フィルタを追加 |
| `add_sort` | `field: TwbField, *, by: TwbField, direction="descending", aggregation="sum"` | `TwbWorksheet` | 指定フィールドで並べ替え |
| `add_measure_values` | `*, shelf: str, fields: list[FieldInput], aggregation=None, aggregations=None, color=True` | `TwbWorksheetField` | メジャーバリュー（`[Multiple Values]`）を 1 本のピルとして置き、1 つの軸へメジャーを何本でも並べる。集計は `aggregation` で全体に、`aggregations` で 1 つずつ。中身は `[:Measure Names]` へのカテゴリフィルタ、`<slices>` への追加、色への割り当ての 3 点セット。戻り値はそのまま `set_dual_axis()` へ渡せる |
| `set_dual_axis` | `*, shelf: str, fields: list[TwbWorksheetField], synchronized=True` | `TwbWorksheet` | 同じシェルフのメジャーを二重軸（重ねた軸）にする。シェルフを `+` で連結し、2 本目以降の軸へ `fold="true"`（`synchronized="true"` が軸の同期）を書き、軸ごとのペインを作る。マークの種類・色・太さは `get_panes()`（土台 → 各軸の順）から `TwbPane.update()` で指定する |
| `set_subtotal_visibility` | `*, field: TwbWorksheetField, visible=True` | `TwbWorksheet` | 行・列に配置したフィールドへ小計を付ける / 外す |
| `add_reference_line` | `*, field: TwbWorksheetField, pane: TwbPane \| None = None, formula="median", scope="per-table", label_type="value", probability=95, z_order=1` | `TwbReferenceLine` | リファレンスラインを 1 本引く。**Pane が複数あるワークシートでは `pane=` が要る**（仕様 §6.7）。1 つなら省略できる |
| `set_axis_visibility` | `*, field: TwbWorksheetField, visible: bool` | `TwbWorksheet` | 軸の表示 / 非表示 |
| `set_axis_range` | `*, field: TwbWorksheetField, min_value=None, max_value=None, reverse=False` | `TwbWorksheet` | 軸の範囲の固定と反転。`min_value` と `max_value` は両方指定か両方省略。すべて省略すると自動の範囲に戻す |
| `update` | `*, name=UNSET, visible=UNSET, title=UNSET, table_style=UNSET, title_style=UNSET, grand_totals=UNSET, lines_visible=UNSET` | `TwbWorksheet` | 自身を更新。**旧 `update_table_style()` / `update_title_style()` を統合**。`lines_visible=False` で書式の「線」をまとめて消す |
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
| `line_interpolation` | `str` | 線マークの補間。`"linear"`（既定）/ `"step"`（階段） |
| `customized_label` | `dict \| None` | カスタムラベル構成 |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | `*, id=None, name=None` | `list[TwbWorksheetField]` | このペインに配置されたフィールド |
| `add_field` | `field: TwbField, *, encoding: str, aggregation=None, discrete=None, table_calculation=None, table_calculation_field=None` | `TwbWorksheetField` | エンコーディングへ配置。`encoding` は `color` / `label` / `tooltip` / `size` / `shape` / `detail` / `path` / `angle` |
| `set_customized_label` | `*, main_metric: TwbWorksheetField, sub_metric: TwbWorksheetField \| None, main_color: str, value_color="#333333", sub_metrics=None, sub_value_color="#666666", vertical_alignment="center"` | `TwbPane` | カード用のラベル構成を組み立てる。文字の大きさは指標名 12 / メイン指標 16 / サブ指標 10 / 予実比較の行 12。`sub_metrics` の組は先頭が値（太字なし・`sub_value_color`）、2 つ目以降が文言（太字・組の色）。**旧 `update_customized_label()`。自身の値の更新ではなく他フィールドを受け取る操作のため動詞名へ** |
| `get_categorical_colors` | `field: TwbWorksheetField` | `dict[str, str]` | カテゴリ別の色割り当てを取得 |
| `set_categorical_colors` | `field: TwbWorksheetField, colors: dict[str, str]` | `TwbPane` | カテゴリ別の色を設定 |
| `set_continuous_colors` | `field: TwbWorksheetField, *, min_color, mid_color, max_color` | `TwbPane` | 連続値の3色グラデーションを設定 |
| `update` | `*, mark_type=UNSET, mark_color=UNSET, mark_size=UNSET, mark_opacity=UNSET, mark_scaling=UNSET, stacked=UNSET, label_style=UNSET, line_interpolation=UNSET` | `TwbPane` | 自身の値を更新。`label_style` は `show` / `cull` / `align`（ラベルの揃え）。`stacked` はマークの積み上げ（`<view><breakdown>` の `on` / `off`。既定の `auto` では棒が積み上がるので、重ねるなら `False`）。**旧 `set_mark_color()` / `set_mark_size()` / `set_mark_opacity()` / `set_mark_sizing()` / `set_label_style()` を統合済み（A-9）** |

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
| `worksheet_id` | `str` | 配置先のワークシート |
| `role` | `str \| None` | 参照先フィールドの `dimension` / `measure` |
| `attrs` | `dict[str, str]` | 配置を表す XML 要素の属性そのまま |

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
| `create_action` | `*, kind, name, source, targets=None, field=None, url=None, activation="on-select", clear_selection="show_all"` | `TwbDashboardAction` | アクションを1件作成。`kind` は `filter` / `url` |
| `create_container` | `*, direction="horizontal", friendly_name=None, distribute_evenly=False` | `TwbDashboardContainer` | 最上位コンテナを作成 |
| `add_floating_worksheet` | `worksheet: TwbWorksheet, *, x=0, y=0, width=600, height=400, show_title=True` | `TwbDashboardZone` | 浮動配置。タイル配置とは明示的に別 API |
| `add_floating_text` | `text: str, *, x=0, y=0, width=200, height=24, font_size=12, font_color="#333333", bold=False, align="left", style=None` | `TwbDashboardZone` | テキストを浮動で置く（2026-09-22 追加）。位置と大きさは px。`align` は `left` / `center` / `right`。シートの上へ文字を重ねたいとき（帳票の項目名など）に使う |
| `add_floating_parameter_control` | `parameter: str, *, x=0, y=0, width=160, height=48` | `TwbDashboardZone` | パラメータコントロールを浮動で置く（2026-09-24 追加）。`parameter` はパラメータ名。`type-v2="paramctrl"`・`mode="compact"` の zone を `<zones>` 直下へ書く |
| `build_report` | `*, dashboard_name, struct, container_sizes=None, content_style=None, header_title=None, header_height=43, header_background_color="#c0c0c0", header_font_color="#333333", filter_apply_button=False, spacing_scale=1.0, border_color=None` | `TwbDashboard` | 構造定義から帳票レイアウトを一括構築。ゾーンの余白は描いたグラフの種類で決まる（カード 0 / 帳票 8 / それ以外 16、角の丸み 8）。`spacing_scale` はその余白の倍率、`border_color` は枠線の色（省略時は枠線なし。引くときは solid・幅 2）。
置いたフィルタは名称を太字・文字 10 にする。`header_title` を省略するとヘッダーにダッシュボード名を書く。`filter_apply_button=True` で置いたフィルタすべてに「適用」ボタンを付ける |
| `update` | `*, name=UNSET, visible=UNSET` | `TwbDashboard` | 自身を更新 |
| `delete` | — | `None` | 削除 |

`struct` は `{段の名前: {"items": [...], "height": ..., "distribute_evenly": ...}}`。段は上から順に並び、
中の項目は左から順に並ぶ。**段の名前は表示名であって、挙動は変えない**（K-1、2026-09-07）。
何を置くかは**項目ごとの区分値 `kind`** で指定する。省略できない。

```python
struct={
    "上段": {
        "height": 50,
        "items": [
            {"kind": "filter", "field": ("売上データ", "地域")},
            {"kind": "worksheet", "sheet": "SheetA"},
        ],
    },
    "下段": {
        "distribute_evenly": False,
        "items": [
            {"kind": "worksheet", "sheets": ["SheetB", "SheetC"], "fixed_size": 200},
            {"kind": "worksheet", "sheet": "SheetD"},
        ],
    },
}
```

**1 つの段にグラフとフィルタを混ぜられる。** 設定画面もエリアごとに種別を選ばせている。

| 項目 | キー | 意味 |
|---|---|---|
| `kind="worksheet"` | `sheet` | ワークシート 1 枚をそのまま段へ置く |
| | `sheets` + `fixed_size` | ワークシートを縦に積んだ列にする（1 枚でも列になる）。`fixed_size` は列の幅 |
| `kind="filter"` | `field` | `("データソース名", "フィールド名")`。事前に `workbook.add_filter()` が要る |

段の高さは `height` → `container_sizes[段の名前]` → 既定 300 の順。

段の幅の割り方は `distribute_evenly` で選ぶ（2026-09-21）。`True` は Tableau の
「均等に配布」で、**このとき項目の `fixed_size`（幅）は効かない**（Tableau 自身も
両方は書かない）。`False` なら指定した px がそのまま幅になり、余りは段の末尾に
足した空きゾーンが吸う。省略時は「幅指定が無く、並べたワークシートが 2 つ以上あり、
フィルタが無い」ときだけ均等配分する。

`create_action()` の `source` と `targets` は、**このダッシュボードに置かれている
ワークシート名**。XML では「除外するシート」で書かれるが、呼び出し側は含める側を渡す。

| `kind` | 必要な引数 | 使えない引数 |
|---|---|---|
| `"filter"` | `source`（1 枚）、`targets`、`field=("データソース名", "フィールド名")` | `url` |
| `"url"` | `source`（1 枚以上）、`url` | `targets` / `field` |

`activation` は `on-select` / `on-hover` / `on-menu`、`clear_selection` は
`show_all` / `exclude`（フィルタのみ）。**実測できているのは `on-select` と
`show_all` だけ**で、残りは Tableau で一般に使われる値。

対象シートやフィールドを変えるときは、消して作り直す。組み立て直しになるため
`TwbDashboardAction.update()` には含めない。

### 3.8b `TwbDrillPath`

データソースに置かれた階層（`drill-paths/drill-path[@name]`）。
`<drill-path>` は `name` しか持たないため、**公開 `id` と `name` は同じ値**になる
（Worksheet と同じ扱い、仕様 §3.5）。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str` | 階層名。角括弧は付かない |
| `datasource_id` | `str` | 所属データソースの `id` |
| `field_ids` | `list[str]` | 並ぶフィールドの内部 ID。**ドリルの階層順** |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_fields` | — | `list[TwbField]` | 並ぶフィールド。順序は階層順で、XML の出現順ではない |
| `update` | `*, name=UNSET, fields=UNSET` | `TwbDrillPath` | 改名するとフォルダの `folder-item` も追随する |
| `delete` | — | `None` | 階層を消す。**含まれていたフィールドは消さない** |

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
| `add_filter` | `*, field: TwbWorksheetField, mode="checkdropdown", show_apply=False, order=None, weight=1` | `TwbDashboardZone` | フィルタコントロールを配置。`show_apply=True` で「適用」ボタンを付ける |
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
| `x_raw` / `y_raw` / `width_raw` / `height_raw` | `int` | Tableau が XML に書く座標。ダッシュボードの幅・高さを 100000 とした比率 |
| `dashboard_id` | `str` | 所属ダッシュボード |
| `sizing_mode` / `dashboard_width_px` / `dashboard_height_px` | `str` / `int \| None` | 所属ダッシュボードのサイズ。自動サイズなら幅・高さは `None` |
| `parent_id` / `depth` | `str \| None` / `int` | 入れ子の親ゾーンと深さ（最上位は `None` / `0`） |
| `type` / `param` | `str \| None` | XML の `type-v2`（無ければ `type`）/ コンテナの向き（`horz` / `vert`） |
| `mode` / `show_caption` / `show_apply` | `str \| None` / `bool \| None` | フィルタカードの表示形式・見出し・「適用」ボタン |
| `url` | `str \| None` | Web ページゾーンの URL |
| `is_fixed` / `is_scaled` | `bool \| None` | XML の `is-fixed` / `is-scaled`。書かれていなければ `None` |
| `attrs` | `dict[str, str]` | `<zone>` の属性そのまま |

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `to_px` | `*, width: int, height: int` | `tuple[int, int, int, int]` | 任意のキャンバスサイズで raw 座標を px 換算する。自動サイズのダッシュボードでも使える |
| `update` | `*, order=UNSET, weight=UNSET, x=UNSET, y=UNSET, width=UNSET, height=UNSET, show_title=UNSET, show_apply=UNSET, fixed_size=UNSET, friendly_name=UNSET, hidden=UNSET, style=UNSET` | `TwbDashboardZone` | 自身を更新。**旧 `update_style()` を統合**。タイル配置に `x`/`y`、浮動配置に `order`/`weight` を渡すと `ValueError`。`show_apply` はフィルタ zone 専用で、`False` は属性を削除する（Tableau が既定で書かないため） |
| `delete` | — | `None` | **配置だけ**を削除。ワークシート本体は削除しない |

### 3.11 `TwbDashboardAction`

作成は `TwbDashboard.create_action()`。

**変数**: `id` / `name` / `type: str \| None` / `activation: str \| None` / `command: str \| None` /
`source_worksheet_ids: list[str]` / `target_worksheet_ids: list[str]` / `links: list[dict]` / `params: dict[str, str]` /
`excluded_source_worksheet_ids: list[str]` / `excluded_target_worksheet_ids: list[str]`（**Tableau は対象シートを除外リストで書く**）/
`dashboard_id` / `source_type` / `target_type` / `source_dashboard_id` / `target_dashboard_id: str \| None` /
`attrs: dict[str, str]`（`<action>` の属性）/ `details: dict`（`<action>` の中身を属性と子要素ごと辞書にしたもの）

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `update` | `*, name=UNSET, activation=UNSET, clear_selection=UNSET, url=UNSET` | `TwbDashboardAction` | 自身のスカラー値を更新。`clear_selection` は `filter`、`url` は `url` の種別でのみ有効 |
| `delete` | — | `None` | 削除。他のアクションには触れない |

### 3.12 `TwbRelation`

データソースの物理テーブルと結合。`TwbDatasource.get_relations()` が返す。
入れ子は `get_children()` で辿る（返るのはルートだけ）。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` | `str \| None` | `@id` → `@name` → 論理テーブルの `id` の順で決まる |
| `name` | `str \| None` | XML の `@name`。無いこともある |
| `datasource_id` | `str` | 所属データソースの `id` |
| `type` | `str \| None` | `<relation type>`。`text` はカスタム SQL |
| `table` | `str \| None` | 物理テーブル名 |
| `connection` | `str \| None` | 接続の内部 ID |
| `join` | `str \| None` | 結合種別（`inner` / `left` など） |
| `custom_sql` | `str \| None` | カスタム SQL の本文 |
| `scope` | `str \| None` | どちらの層から採ったか。物理側は `connection`、論理側は `object-graph` |
| `logical_table` / `logical_table_id` | `str \| None` | 属する論理テーブル |
| `clauses` | `list[dict[str, object]]` | `<relation>` 以外の子要素をそのまま記録したもの（結合条件など） |
| `attrs` | `dict[str, str]` | 上に出ていない XML 属性 |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `get_children` | — | `list[TwbRelation]` | 直下の子。結合は木になる |

### 3.13 `TwbRelationship`

論理テーブル間のリレーションシップ。`TwbDatasource.get_relationships()` が返す。
物理結合（`TwbRelation`）とは別の層で、Tableau 2020.2 以降のデータモデルにあたる。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str \| None` | XML の `@name` |
| `datasource_id` | `str` | 所属データソースの `id` |
| `left_object` / `right_object` | `str \| None` | つながる論理テーブルの表示名。`<object-graph>` の `caption` から引く |
| `left_object_id` / `right_object_id` | `str \| None` | 同じものの内部 ID |
| `expression` | `dict[str, object] \| None` | 結合条件の式。入れ子の辞書 |
| `attrs` | `dict[str, str]` | 上に出ていない XML 属性 |

### 3.14 `TwbReferenceLine`

ワークシートのリファレンスライン。`TwbWorksheet.get_reference_lines()` が返す。
作成は `TwbWorksheet.add_reference_line()`。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str` | `<reference-line>` の識別子。`@name` を持たないため同じ値 |
| `worksheet_id` | `str` | 所属ワークシートの `id` |
| `axis_field_id` | `str \| None` | 軸のフィールドの XML 内部参照（`[ds1].[none:Sales:qk]` の形） |
| `axis_name` | `str \| None` | 軸のフィールドの表示名 |
| `axis_role` | `str \| None` | 軸の役割（`measure` など） |
| `value_field_id` / `value_name` / `value_role` | `str \| None` | 値のフィールドについて同じもの |
| `formula` | `str \| None` | 集計方法。`add_reference_line()` が受けるのは `average` / `median` / `minimum` / `maximum` |
| `scope` | `str \| None` | 適用範囲。`add_reference_line()` の既定は `per-table` |
| `label_type` | `str \| None` | ラベルの出し方。既定は `value` |
| `tooltip_type` | `str \| None` | ツールチップの出し方 |
| `attrs` | `dict[str, str]` | 上に出ていない XML 属性 |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `update` | `*, formula=UNSET, scope=UNSET, label_type=UNSET` | `TwbReferenceLine` | `add_reference_line()` で指定できる値を後から変える |
| `delete` | — | `None` | 削除 |

`*_caption` は `*_name` へ、`*_column` は `*_field_id` へ改名済み（A-10、2026-09-07）。
`models.py` の旧 dataclass は §11 の移行規約により古い名前のまま残る。

### 3.15 `TwbWorksheetFilter`

ワークシートに掛かっているフィルタ。`TwbWorksheet.get_filters()` が返す。
作成は `TwbWorksheet.add_field(shelf="filters")`。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `id` / `name` | `str` | フィルタの識別子 |
| `worksheet_id` | `str` | 所属ワークシートの `id` |
| `field` | `str \| None` | フィルタ対象の解決済みフィールド名 |
| `role` | `str \| None` | `dimension` / `measure` |
| `filter_class` | `str \| None` | `<filter class>` の値。実測した .twb では `categorical` |
| `filter_group` | `str \| None` | フィルタグループ |
| `domain` | `str \| None` | 値の母集合を表す XML 属性 |
| `enumeration` | `str \| None` | 列挙の仕方 |
| `value_scope` / `value_scope_label` | `str \| None` | 値の範囲と、その表示用ラベル |
| `apply_scope` / `apply_scope_label` | `str \| None` | 適用範囲と、その表示用ラベル |
| `selection_type` | `str \| None` | 選択の仕方（単一 / 複数） |
| `values` | `list[str]` | 選択されている値 |
| `functions` | `list[str]` | `<groupfilter function>` の値。実測した .twb では `level-members` |
| `attrs` | `dict[str, str]` | 上に出ていない XML 属性 |

**メソッド**

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `update` | `*, values=UNSET` | `TwbWorksheetFilter` | 選択値を差し替える |
| `delete` | — | `None` | フィルタを外す |

### 3.16 `TwbFilterControl`

ダッシュボードに置かれたフィルタカード。`TwbDashboard.get_filter_controls()` が返す。
**`TwbDashboardZone` を継承する**ので、§3.10 のゾーン変数（`x` / `y` / `width` /
`height` / `order` / `weight` / `style` など）と `update()` / `delete()` をそのまま持つ。
ここに挙げるのは、フィルタとして足されている分だけ。

**変数**

| 変数 | 型 | 説明 |
|---|---|---|
| `column` | `str \| None` | フィルタ対象の XML 内部参照 |
| `field` | `str \| None` | フィルタ対象の解決済みフィールド名 |
| `worksheet` / `worksheet_id` | `str \| None` | フィルタの出どころのワークシート |
| `role` | `str \| None` | `dimension` / `measure` |
| `mode` | `str \| None` | 表示形式（`checkdropdown` など） |
| `filter_class` / `domain` / `enumeration` | `str \| None` | §3.15 と同じ意味 |
| `value_scope` / `value_scope_label` | `str \| None` | 同上 |
| `apply_scope` / `apply_scope_label` | `str \| None` | 同上 |
| `selection_type` | `str \| None` | 同上 |
| `values` | `list[str]` | 選択されている値 |
| `show_apply` | `bool \| None` | 「適用」ボタンを出すか。`update(show_apply=)` で変える |
| `show_caption` | `bool \| None` | フィルタカードの見出しを出すか。**ゾーンの `show_title` とは別の属性**（§3.2） |

---

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

## 9. 旧 API の削除（E-2・完了）

**2026-09-07 に `TwbWorkbook` の旧メソッド 25 件を削除した。** 新 API に完全な代替が
あるものだけを対象にし、代替の無い 4 件は残している。

**削除したもの**

```
list_dashboards, list_dashboard_filter_controls, list_worksheets, list_reference_lines,
list_filters, list_datasources, list_relations, list_relationships, list_parameters,
list_columns, get_dashboard, get_worksheet, get_datasource, get_column,
update_source, update_column, update_formula, rename_field, reset_field_caption,
move_field_to_folder, remove_field_from_folder, move_column_to_folder,
unsupported_features, set_filter, create_calculated_field（位置引数版）
```

検索方法の `by="auto"` も一緒に消えた。新 API は `id=` / `name=` に統一されている。
移行先の対応は仕様 `docs/model_api_spec.md` §12 を見る。

**残しているもの（4 件）**

| メソッド | なぜ残すか |
|---|---|
| `list_dashboard_zones()` | デバイスレイアウトの読み取りが新 API に無い（raw 座標・px 換算・`parent_id` / `depth` は 2026-09-13 に `TwbDashboardZone` へ足した） |
| `list_dashboard_actions()` | 穴は埋まった（2026-09-13、`TwbDashboardAction.excluded_*_worksheet_ids` / `details`）。消すかどうかは未判断 |
| `list_dashboard_fields()` | `max_filter_value_chars=` が新 API に無い |
| `list_worksheet_fields()` | フィールドの `values` / `mark_type` / `category` / `type` が新 API に無い |

**これらは新 API に穴埋めしてから消す**（`docs/backlog.md` L-6）。
戻り値は `models.py` の投影 dataclass のままで、接続型モデルではない。

**`models.py` の dataclass**

投影層（`column.py` / `worksheet.py` / `filter.py` など 14 モジュール）が返す型として
残る。**削除できない。** 接続型モデルの `_snapshot()` がこれを読んでいる。

公開しているのは新 API の戻り値になるものだけ。`TwbValidationMessage`（`validate()`）、
`TwbUnsupportedFeature`（`get_unsupported_features()`）、接続先の 4 クラス
（`datasource.source`）。`TwbColumn` は旧メソッドの戻り値だったので、削除に合わせて
`__all__` から外した。
