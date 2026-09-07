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

「設定 YAML をダウンロード」で `twbpatch_config.yaml` が落ちる。

```python
wb = TwbWorkbook.open("template.twb")
wb.apply_config("twbpatch_config.yaml")
wb.save("step1.twb", overwrite=True)
```

### 2 周目 — ダッシュボードを組む

**焼き直した `step1.twb` から画面を出し直す。** ここが肝心で、
1 周目の `config.html` を使い回すと計算フィールドが候補に出ない。

```python
wb = TwbWorkbook.open("step1.twb")
wb.export_html("config2.html", overwrite=True)
```

`config2.html` でダッシュボードのタブを設定し、YAML を落として適用する。

```python
wb = TwbWorkbook.open("step1.twb")
wb.apply_config("twbpatch_config.yaml")
wb.save("output.twb", overwrite=True)
```

## 気をつけること

**2 周目の YAML は必ず作り直す。** `datasources.*.folders` は「元カラム名 → 表示名」
なので、適用済みの `.twb` へ 1 周目の YAML をもう一度渡すと、元カラム名が見つからず
`NotFoundError` になる。`calculations` だけは同名を上書きするので 2 度通しても平気。

**ダッシュボードは新規作成しかできない。** 画面は既存ダッシュボードを読み込まない。
`apply_config()` も `create_dashboard()` から始める。

**届かない設定はログに出る。** 受け手が無い節は警告ログへ名前を出して読み飛ばす。
`design` の色・余白・適用ボタンは `dashboard` を組むときに使うので、
`dashboard` が無い設定では届かない。

```python
import logging
logging.basicConfig(level=logging.WARNING)
```

## 何が届いて何が届かないか

| 画面の設定 | 受け手 |
|---|---|
| 全体のフォント | `set_default_font()` |
| メインカラー / サブカラー / 文字色 | グラフの色に `@main_color` と書くと解決される |
| 余白 多め / 少なめ | `build_report(content_style=)` |
| フィルターに「適用」ボタン | `build_report(filter_apply_button=)` |
| リネーム・フォルダ | `apply_field_config()` |
| 計算フィールド | `create_calculated_field()`。同名は式・型・役割・フォルダを上書き |
| ダッシュボードのヘッダー | `build_report(header_title=, header_height=, ...)` |
| 段とエリア | `draw_*()` でシートを作り `build_report()` で並べる |
| エリアのアクション | `create_action()`。フィルターと URL の 2 種 |

**アクションの実行方法は `on-select` しか実物で確かめていない。**
`on-hover` / `on-menu` は Tableau で一般に使われる値だが未確認（`docs/backlog.md` H-1）。
