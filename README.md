# twbpatch

Tableau の `.twb` / `.twbx` を読み込み、データソース・フィールド・計算式・
ワークシート・ダッシュボードを参照、編集、保存する Python ライブラリです。
設定画面の HTML 出力、定義書の Excel 出力、ダッシュボードの生成にも対応します。

## はじめに

1. Windows で使い始める場合は、[初期セットアップ](docs/setup/windows_setup.md)に沿って環境を用意します。
2. ランチャーと設定画面を使う場合は、[GUI 利用ガイド](docs/user/gui/usage.md)を参照してください。
3. Python のコードから使う場合は、[ライブラリ利用ガイド](docs/user/library/usage.md)と[公開 API](docs/user/library/api_reference.md)を参照してください。

Python 3.10 以上が必要です。依存関係とインストール方法は
[利用ガイドの動作要件](docs/user/library/usage.md#動作要件)に記載しています。

## 最小の利用例

```python
from twbpatch import TwbWorkbook

workbook = TwbWorkbook.open("examples/sample_ec.twb")
for datasource in workbook.get_datasources():
    print(datasource.name, datasource.source_type)
```

## 資料

| 読者・目的 | 資料 |
|---|---|
| 初めて使う | [Windows 初期セットアップ](docs/setup/windows_setup.md) |
| GUI で操作する | [GUI 利用ガイド](docs/user/gui/usage.md) |
| Python のコードで利用する | [ライブラリ利用ガイド](docs/user/library/usage.md)、[計算フィールドと設定画面の往復](docs/user/library/roundtrip.md) |
| Python のクラス・メソッド・引数を調べる | [公開 API リファレンス](docs/user/library/api_reference.md) |
| 本体の開発者が仕様を確認する | [API 設計仕様](docs/developer/model_api_spec.md)、[設定画面の仕様](docs/developer/html_screen_spec.md) |
| 資料の種類と開発記録を探す | [ドキュメント一覧](docs/README.md) |

## テンプレート

編集するテンプレートと AI 用ルールは、ルートの `template/` にまとめています。

| フォルダ | 用途 |
|---|---|
| `template/dashboard_template/` | ダッシュボードの見た目・配置 |
| `template/prompt_rules/` | フィールドの命名・フォルダ・階層の AI 用ルール |
| `template/calc_prompt_rules/` | 計算フィールドの AI 用ルール |

[テンプレートの種類](template/README.md)と
[ダッシュボードテンプレートの配置手順](template/dashboard_template/README.md)を参照してください。
テンプレートやルールを変更したら、設定 HTML を再出力します。
