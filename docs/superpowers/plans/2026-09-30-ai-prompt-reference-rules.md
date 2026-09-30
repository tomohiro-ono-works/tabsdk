# AI 用プロンプトの参照ルール Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 固定フォルダ内の Markdown ルールを HTML 生成時に取り込み、フィールド用 AI プロンプトでチェックした分類だけを編集可能なテキストエリアへ表示する。

**Architecture:** Python が `twbpatch/prompt_rules/` 直下の UTF-8 `.md` をファイル名順に読み、自己完結 HTML へ安全に埋め込む。ブラウザー側はファイル名のチェックボックスを作り、フィールド用プロンプト内の境界付き「参照ルール」欄だけを再構成する。計算フィールド用プロンプトと `export_html()` の公開シグネチャは変えない。

**Tech Stack:** Python 3.10 以上、標準ライブラリ、生成 HTML 内の JavaScript、pytest、hatchling。

**Spec:** `docs/tasks/J_ai_prompt_reference_rules_design.md`

## Global Constraints

- `docs/html_screen_spec.md` を画面仕様の正典とし、公開 API は `docs/model_api_spec.md` に従う。
- `develop` で作業し、`main` を変更せず、push しない。既存の無関係な変更には触れない。
- HTML は `file://` で単体動作し、外部参照やサーバーを必要としない。
- 元カラム・データ型・役割の入力と、`||` 区切りの出力 4 列、行数・行順の契約を保つ。
- 顧客・商品は手動で選ぶルール分類であり、Tableau データソース名の追加や分類の自動判定はしない。
- MD はプロンプトの参照資料のみで、設定 YAML の出力・適用や `.twb` の変更には使わない。
- テストは `tests/sample_minimal.twb` と `tmp_path` のみを使用する。

## Review Focus

- ファイル名や本文に `</script>`、HTML タグ、引用符があっても HTML の構造と JavaScript を壊さない（Task 1）。
- `.md` 以外、サブフォルダ内、追加順がばらばらなファイルを正しく除外・並べ替えする（Task 1）。
- 共通ルールを外す、全件を外す、複数分類を選ぶ操作で本文の重複や残留がない（Task 2）。
- 利用者が参照ルール欄の外を編集してもチェック操作で失わず、境界破損時は推測で置換しない（Task 2）。
- 計算フィールド用ダイアログでは分類チェックを表示せず、計算プロンプトを変更しない（Task 2）。

---

### Task 1: ルールファイルの読み込みと HTML への埋め込み

**Files:**
- Create: `twbpatch/prompt_rules/00-common-rules.md`
- Create: `twbpatch/prompt_rules/10-customer-data.md`
- Create: `twbpatch/prompt_rules/20-product-data.md`
- Modify: `twbpatch/html_export.py`（読み込み関数、埋め込み差し込み口）
- Test: `tests/test_export_html.py`

**Interfaces:**
- Produces: `_load_prompt_rules(directory: Path | None = None) -> list[dict[str, str | bool]]`。各要素は `name`、`text`、`default_checked` を持つ。`directory=None` はパッケージ内固定フォルダ。
- Produces: 生成 HTML の `const PROMPT_RULES = ...;`。Task 2 の JavaScript がこの配列を使う。

- [ ] **Step 1: 失敗するテストを書く。** `test_prompt_rules_load_fixed_files` で 3 ファイル・昇順・共通だけ既定選択・本文無加工を検証する。`test_prompt_rules_scan_direct_md_files_only` は `tmp_path` に `.md`、非 MD、サブフォルダを置く。`test_prompt_rules_escape_script_end` は `</script>` を含む MD の HTML 埋め込みを検証する。`test_prompt_rules_read_error_names_file` と `test_prompt_rules_empty_directory` で異常時と空フォルダを検証する。
- [ ] **Step 2: 失敗を確認する。** `uv run --no-sync pytest -q tests/test_export_html.py -k prompt_rules`。新規テストが実装未在のため失敗する。
- [ ] **Step 3: 実装する。** 固定フォルダの直下だけを `Path.iterdir()` で走査し、`.md` を UTF-8 で読む。`00-common-rules.md` のみ既定選択にする。既存 `_embed_json()` と同等の `</` エスケープで JavaScript リテラルへ埋め込む。3 つの MD には共通規則と、顧客・商品それぞれの適用対象・インデント構造・対応辞書の記入例を置き、実データとして未確認の用語は確定ルールにしない。
- [ ] **Step 4: 対象テストを通す。** `uv run --no-sync pytest -q tests/test_export_html.py -k prompt_rules`。全件 PASS。
- [ ] **Step 5: 配布物を確認する。** `uv build` 後、wheel と sdist の両方に 3 つの MD が入ることを確認する。入らない場合だけ `pyproject.toml` の hatch 設定を追加し再確認する。

### Task 2: チェックボックスとプロンプト欄の同期

**Files:**
- Modify: `twbpatch/html_export.py`（共有ダイアログの UI、JavaScript）
- Modify: `docs/html_screen_spec.md`（操作・再生成・境界破損時の挙動）
- Modify: `README.md`（ルールファイルの編集と HTML 再生成）
- Test: `tests/test_export_html.py`

**Interfaces:**
- Consumes: Task 1 の `PROMPT_RULES: Array<{name: string, text: string, default_checked: boolean}>`。
- Produces: フィールド用ダイアログのチェックボックス群と、境界付き `# 参照ルール` 欄。計算フィールド用ではチェック群を隠す。

- [ ] **Step 1: 失敗するテストを書く。** `test_prompt_rules_checkbox_ui` でファイル名・共通のみ既定選択・空配列時の非表示を検証する。`test_prompt_rules_replace_managed_section` で複数選択・全解除・同一ファイル重複なし・範囲外の手編集維持・境界欠損時の再生成案内を検証する。`test_prompt_rules_field_only` で開き直した際のチェック状態維持と選択行の再生成、計算プロンプト側のチェック群非表示を検証する。利用可能なブラウザー実行環境では `file://` 上の操作も確認する。
- [ ] **Step 2: 失敗を確認する。** `uv run --no-sync pytest -q tests/test_export_html.py -k prompt_rules`。新規 UI テストが失敗する。
- [ ] **Step 3: 実装する。** ダイアログにチェック群を追加し、`openPrompt(text, note)` の既存呼び出しと計算プロンプトを保ちながら、フィールド用でのみ選択済み MD を表示する。`<!-- twbpatch:reference-rules:start -->` と `<!-- twbpatch:reference-rules:end -->` で囲んだ範囲だけを再構成し、範囲外のテキストを保持する。全解除時は欄を削除する。マーカー欠損時はテキストを変更せず再生成を案内する。
- [ ] **Step 4: 対象テストを通す。** `uv run --no-sync pytest -q tests/test_export_html.py -k prompt_rules`。全件 PASS。
- [ ] **Step 5: 仕様と利用方法を更新する。** `docs/html_screen_spec.md` と `README.md` に、ファイル配置、選択動作、HTML 再生成が必要なことを記す。
- [ ] **Step 6: 全体を確認する。** `uv run --no-sync pytest -q`。失敗時はコマンド・結果・保存した出力を報告し、Task の許可なく追加調査・修正・再試行しない。skip は 0 件を確認する。

コミット前に `git status --short` で他セッションの変更を確認し、この計画で編集したファイルだけを扱う。

## 実施結果

- 固定フォルダの 3 つの Markdown、HTML への埋め込み、チェック操作を実装した。
- 追加テストは `tests/test_prompt_rules.py` に分離した。生成 JavaScript の操作はローカルの Node.js スモークテストで確認した。
- `uv build` の wheel と sdist に 3 ファイルが含まれることを確認した。
- レビューで見つかった `__TITLE__` の本文置換は回帰テストを追加して修正した。
- 最終検証: `uv run --no-sync pytest -q` は 549 passed、`git diff --check` はエラーなし。
