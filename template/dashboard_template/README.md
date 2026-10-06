# ダッシュボードテンプレート

テンプレートごとにフォルダを作り、Tableau が保存したファイルを配置します。

```text
template/dashboard_template/
  sales/
    template.twbx
  support/
    template.twb
    Image/logo.png
```

各フォルダには `template.twb` / `template.twbx` の一方だけを置いてください。
TWB の画像は同じテンプレート名フォルダ配下に相対パスで配置します。
TWBX は内部に TWB を1個だけ含め、必要画像をまとめて持つ形式です。
テンプレートの抽出データを取り込み先へコピーすることはありません。

HTML を出力後、デザインルールでフォルダ名とダッシュボードを選びます。
テンプレートを追加・変更したときは HTML を再出力してください。
複数ダッシュボードなら明示選択、単一なら自動選択です。
フォルダ名を変更したら YAML の `design.dashboard_template` も更新します。
不正なフォルダは一覧に出ず、消えた保存済み選択は「見つかりません」と表示されます。

```yaml
design:
  dashboard_template: sales
  dashboard_template_dashboard: Source dashboard
```

コンテナ・静的な文字・画像を取り込みます。シート・フィルター・パラメーターは
「グラフ」「フィルター」「パラメーター」の文字枠に変換します。
凡例・アクション・未対応オブジェクトは取り込まず、警告も表示しません。
文字内の動的参照は除去します。対応する書式と既定レイアウトだけが対象です。

通常のグラフや KPI カードは引き続き指定できます。
高さ200px のテンプレートと高さ900px の通常領域なら最終高さは1100px。
通常領域の y=80px のグラフは y=280px になり、x・幅・高さは維持します。
幅は両領域の最大値、左揃えで拡大縮小しません。
テンプレートの「グラフ」枠は残り、生成グラフの差し込み先にはしません。
生成エリアがない場合はテンプレートだけを適用します。KPI ツリーは別経路です。

画像は適用時には書き出さず、`save()` でハッシュ名を付けて保存します。
TWB は出力先の隣、TWBX は内部の TWB の隣に保存されます。
TWBX への保存には、取り込み先の Workbook も TWBX から開く必要があります。

```python
wb.export_html("config.html", template_root="template/dashboard_template")
wb.apply_config("config.yaml", template_root="template/dashboard_template")
wb.save("output.twb")
```
