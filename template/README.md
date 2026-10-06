# テンプレートと AI 用ルール

編集するテンプレートとルールは、このフォルダにまとめています。

| フォルダ | 役割 | 編集するもの |
|---|---|---|
| `dashboard_template/` | ダッシュボードの見た目・配置を取り込む | テンプレートごとの TWB / TWBX と画像 |
| `prompt_rules/` | フィールドの命名・フォルダ・階層を AI に考えてもらう際の参照ルール | Markdown ファイル |
| `calc_prompt_rules/` | 計算フィールドを AI に考えてもらう際の参照ルール | Markdown ファイル |

## ダッシュボードテンプレート

[配置・画像・YAML の手順](dashboard_template/README.md)に沿って、テンプレートごとのフォルダを作ります。
元データの定義や抽出データは、取り込み先へコピーしません。

## AI 用ルール

- `prompt_rules/00-common-rules.md` は共通の命名・フォルダ・階層ルールです。
- `prompt_rules/10-customer-data.md` と `20-product-data.md` は分類ごとの記入例です。
- `calc_prompt_rules/00-calculation-rules.md` は集計・IIF・ゼロ除算などの計算ルールです。

HTML 出力時に各フォルダ直下の `.md` をファイル名順で読み込みます。
ルールを編集・追加・削除したら、設定 HTML を再出力してください。
画面での使い方は[GUI 利用ガイド](../docs/user/gui/usage.md#テンプレートと-ai-用ルール)、
コードからの出力は[ライブラリ利用ガイド](../docs/user/library/usage.md#設定画面を-html-で出す)を参照してください。

開発元はこのルートフォルダです。配布パッケージには AI 用ルールを同梱し、
リポジトリを展開していない環境でも既定のルールを利用できます。
