# ドキュメント一覧

初期セットアップ、GUI 利用者、コードでライブラリを使う利用者、本体の開発者で資料を分けています。
初めて使う場合は、セットアップの後に、自分の利用方法に合ったガイドを参照してください。

## 初期セットアップ：setup/

| 資料 | 内容 |
|---|---|
| [Windows 初期セットアップ](setup/windows_setup.md) | uv の導入、ダウンロード、依存関係の導入、ランチャー起動 |

## 利用者向け：user/

### GUI 利用者：user/gui/

| 資料 | 内容 |
|---|---|
| [GUI 利用ガイド](user/gui/usage.md) | ランチャーのメニュー、設定画面、計算フィールドからグラフを作る流れ、テンプレート、定義書 |

### ライブラリをコードで利用：user/library/

| 資料 | 内容 |
|---|---|
| [ライブラリ利用ガイド](user/library/usage.md) | Python での Workbook の参照・編集・保存、定義書出力、設定 HTML、YAML の適用 |
| [公開 API リファレンス](user/library/api_reference.md) | 利用できるクラス・メソッド・引数・戻り値 |
| [設定画面を使った作り方](user/library/roundtrip.md) | 計算フィールドを作り、画面を再出力してグラフへ使う手順 |

テンプレートの編集については、[テンプレート一覧](../template/README.md)と
[ダッシュボードテンプレートの配置手順](../template/dashboard_template/README.md)を参照してください。

## 本体の開発者（我々用）：developer/

tabsdk 本体（Python パッケージ名は `twbpatch`）の設計・実装・検証に使う資料です。

| 資料 | 内容 |
|---|---|
| [API 設計仕様](developer/model_api_spec.md) | 公開 API の設計規則・契約の正典 |
| [設定画面の仕様](developer/html_screen_spec.md) | 画面の構成、設定項目、出力する YAML と復元動作 |
| [要件](developer/requirements.md) | SDK と定義書出力などの要件 |
| [メタデータ API の範囲](developer/metadata_api_scope.md) | 表示状態・参照線・フィルター取得の対象範囲 |
| [バックログ](developer/backlog.md) | 課題、調査根拠、決定と対応状況 |
| [ロードマップ](developer/roadmap.md) | 開発の進め方・課題間の関係 |
| [移行状況](developer/migration_status.md) | API 移行時の検証記録。生成時点の内容 |

### 作業記録：developer/tasks/

ここは設計・実装・調査・検証の記録です。現在の利用方法は利用ガイド、
現在の実装契約は API 設計仕様と設定画面の仕様を優先してください。

| 資料 | 内容 |
|---|---|
| [サンプルの知見整理](developer/tasks/G2_sample_inventory.md) | 旧サンプルから抽出した API の組み合わせ |
| [合計・小計](developer/tasks/H5_totals.md) | XML 構造と API の設計根拠 |
| [KPI ツリー](developer/tasks/I2_kpi_tree.md) | KPI ツリーの設計・実装記録 |
| [AI 用ルールの設計](developer/tasks/J_ai_prompt_reference_rules_design.md) | 参照ルールの配置・選択・プロンプトへの反映 |
| [設定画面の実装記録](developer/tasks/J_html_config.md) | HTML 設定画面の開発経緯 |
| [定義書出力](developer/tasks/M1_tableau_definition_export.md) | DataFrame・Excel 出力 API の設計・検証 |
| [ダッシュボードテンプレートの要件](developer/tasks/dashboard_layout_template_requirements.md) | テンプレートの配置、取り込み、保持する内容 |
| [テンプレートのユーザー確認手順](developer/tasks/dashboard_template_user_test.md) | 開発時の検証用ファイルを使った画面・Tableau 表示・YAML 往復の確認 |
| [リリース準備の監査記録](developer/tasks/release_readiness_2026-10-06.md) | 公開情報・不要ファイル・検証・main 反映前の監査 |
