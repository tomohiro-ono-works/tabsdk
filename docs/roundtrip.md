# 設定画面を使った作り方（2 周方式）

`export_html()` で設定画面を出し、画面で設定し、`apply_config()` で `.twb` へ焼く。
**計算フィールドを使う場合は 2 周する。**

- 画面そのものの仕様は `docs/html_screen_spec.md`
- 個々の API は `README.md` の §0 以降

## なぜ 2 周するのか

画面のグラフ設定は、**そのデータソースに実在するフィールド**から候補を出す。
1 周目で定義したばかりの計算フィールドは、まだ `.twb` に無いので候補に出ない。

式から役割（メジャー / ディメンション）とデータ型を推測する手もあるが、
`SUM([売上]) / SUM([利益])` のような式を解析して当てるのは外れやすい。
**1 周目で `.twb` に焼いてしまえば、2 周目には実在フィールドとして普通に出る。**
推測する処理そのものが要らなくなる（2026-09-06 決定）。

計算フィールドを使わないなら 1 周で終わる。

## 手順

### 1 周目 — データソースを整える

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")
wb.export_html("config.html", overwrite=True)
```

`config.html` をブラウザで開き、**データソースのタブだけ**を設定する。

- リネーム・フォルダ設定
- 計算フィールド

データソースタブの「設定 YAML をダウンロード」で `twbpatch_datasources.yaml` が落ちる。

```python
wb = TwbWorkbook.open("template.twb")
wb.apply_config("twbpatch_datasources.yaml")
wb.save("step1.twb", overwrite=True)
```

### 2 周目 — ダッシュボードを組む

**焼き直した `step1.twb` から画面を出し直す。** ここが肝心で、
1 周目の `config.html` を使い回すと計算フィールドが候補に出ない。

```python
wb = TwbWorkbook.open("step1.twb")
wb.export_html("config2.html", overwrite=True)
```

`config2.html` でダッシュボードのタブ（または KPI ツリーのタブ）を設定し、**そのタブの**「設定 YAML をダウンロード」で
落として適用する。ファイルはダッシュボードが `twbpatch_dashboard.yaml`、KPI ツリーが `twbpatch_kpi_tree.yaml` で、
どちらもデザインルールとデータソースの設定を含む。

```python
wb = TwbWorkbook.open("step1.twb")
wb.apply_config("twbpatch_dashboard.yaml")
wb.apply_config("twbpatch_kpi_tree.yaml")   # 両方作るなら続けて適用してよい
wb.save("output.twb", overwrite=True)
```

データソースの設定は 2 つのファイルに入っているので 2 回適用されるが、上書きになるだけで止まらない。
シート名・ダッシュボード名が 2 つのファイルでぶつかると止まるので、画面はダウンロード前にタブをまたいで検証する。

## 気をつけること

**データソースの設定は 2 度通しても止まらない。** `calculations` は同名を上書きし、`folders` / `renames` の元カラム名は
表示名が変わった後もフィールドの ID から引ける（2026-09-14 実測。以前の「`NotFoundError` になる」は今の実装と合わない）。

**ダッシュボード・KPI ツリーは 2 度通すと止まる。** 同じシート名が既にあるため `worksheet already exists` になる。
保存済みの `.twb` へ同じファイルをもう一度適用しない。

**ダッシュボードは新規作成しかできない。** 画面は既存ダッシュボードを読み込まない。
`apply_config()` も `create_dashboard()` から始める。

**届かない設定はログに出る。** 受け手が無い節は警告ログへ名前を出して読み飛ばす。
`design` の色・余白・適用ボタンは `dashboard` / `kpi_tree` を組むときに使うので、
どちらも無い設定では届かない。

```python
import logging
logging.basicConfig(level=logging.WARNING)
```

## 何が届いて何が届かないか

| 画面の設定 | 受け手 |
|---|---|
| 全体のフォント | `set_default_font()` |
| メインカラー / サブカラー / 文字色 | グラフの色に `@main_color` と書くと解決される |
| 余白 広い / 狭い | `build_report(content_style=)` |
| フィルターに「適用」ボタン | `build_report(filter_apply_button=)` |
| リネーム・フォルダ | `apply_field_config()` |
| リネーム（フォルダ未指定） | フィールドを解決して `field.update(name=)` |
| 計算フィールド | `create_calculated_field()`。同名は式・型・役割・フォルダを上書き。参照先から先に作るので表の並び順は問わない |
| ダッシュボードのヘッダー | `build_report(header_title=, header_height=, ...)` |
| 段とエリア | `draw_*()` でシートを作り `build_report()` で並べる |
| エリアのアクション | `create_action()`。フィルターと URL の 2 種 |
| KPI ツリーのノード | `draw_card()` でカードを作り `build_kpi_tree()` で並べる。余白は `content_style=` へ |
| KPI ツリーの親ノードの位置 | `build_kpi_tree(align=)`。上端ならエッジも描き、エッジの .hyper は `save()` が .twb の隣へ置く（指定は要らない） |

**アクションの実行方法は `on-select` しか実物で確かめていない。**
`on-hover` / `on-menu` は Tableau で一般に使われる値だが未確認（`docs/backlog.md` H-1）。

# ダッシュボードテンプレートを使う場合

`template/dashboard_template/sales/template.twb`（または `template.twbx`）を配置する。
TWB の画像は同じ `sales` フォルダ配下に相対パスで配置する。
`workbook.export_html("config.html", template_root=...)` でカタログを画面へ渡す。
デザインルールでテンプレートと内部ダッシュボードを選択し、通常通りグラフや KPI カードを指定する。

```yaml
design:
  dashboard_template: sales
  dashboard_template_dashboard: Source dashboard
```

`workbook.apply_config(config, template_root=...)` → `workbook.save(...)` で適用・画像保存する。
テンプレートのグラフは文字枠に変換され、指定した生成グラフはその下に追加される。
画像を含むテンプレートは TWBX にすると関連画像をまとめて管理できる。
テンプレート追加・フォルダ名変更後は HTML を再出力し、保存済み YAML のキーも更新する。
