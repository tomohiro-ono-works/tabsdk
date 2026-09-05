# 移行進捗（自動生成）

> **このファイルは `/spec-conformance` が生成します。手で編集しないでください。**
> 手で書き換えると、README.md と同じようにドリフトします。状態は常に実装から導出します。

- 生成日: 2026-09-05
- 対象: `docs/model_api_spec.md` §13 受け入れ条件
- テスト: **80 passed, 2 skipped**（`uv run --no-sync pytest -q --basetemp=tmp/pytest`）

## 前提

`connected*.py` の接続型モデルが**新 API**、`models.py` の dataclass 群と
`TwbWorkbook.list_*()` / `get_<単数形>()` / `update_*()` が**旧 API**。
仕様 §11 により旧 API の併存は違反ではないため、以下の判定は**新 API 側のみ**を対象とする。

## §13 受け入れ条件の判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| 公開 API に `list_*()` が存在しない | **PASS**（新 API） | `connected*.py` 4 ファイルで `def list_` が 0 件 |
| 公開取得 API に `identifier` と `by` が存在しない | **PASS** | `connected*.py` で `by: str` / `identifier` が 0 件 |
| 検索条件がキーワード専用の `id=` / `name=` に統一 | **PASS** | 標準シグネチャを踏襲 |
| `id` と `name` の同時指定が `ValueError` | **PASS** | `twbpatch/connected.py:56` |
| 公開モデルに `caption` が存在しない | **PASS**（新 API） | 接続型 `TwbField` は `id` / `name` のみ公開（`connected.py:805`〜） |
| リソース取得の `get_*()` が `list` を返す | **PASS** | 18 メソッドすべて `-> list[...]` |
| **公開の `update_*()` が存在しない** | **FAIL** | 下記 5 件 |
| `TwbColumn` と `column` が `TwbField` / `field` へ移行 | **進行中** | `TwbField`(`connected.py:805`) と `TwbColumn`(`models.py:35`) が併存。§11 により想定どおり |
| 属性アクセサの `get_*()` の戻り値 | **要目視** | 下記「仕様の空白」参照 |
| Dashboard タイル配置・座標計算・既存編集の非破壊性 | **要目視** | 静的検査では判定不能。`tests/test_connected_dashboard_api.py` で確認すること |
| `ResourceInUseError` / `DetachedModelError` の挙動 | **要目視** | 例外クラスは `errors.py` に定義済み。発生条件の網羅は目視 |

## FAIL: 公開の `update_*()` が 5 件残っている

仕様 §3.3 は「公開 `update_*()` は使用しない。モデル自身が所有する更新可能な値はすべて
`update()` のキーワード引数として受け取る」と定めている。以下は新 API 側の違反。

| 場所 | メソッド | 統合先 |
|---|---|---|
| `twbpatch/connected_dashboard.py:1183` | `TwbDashboardContainer.update_style()` | 同クラスの `update()`（`:1064`） |
| `twbpatch/connected_dashboard.py:1669` | `TwbDashboardZone.update_style()` | 同クラスの `update()`（`:1740` 付近） |
| `twbpatch/connected_worksheet.py:985` | `TwbWorksheet.update_table_style()` | 同クラスの `update()`（`:1636`） |
| `twbpatch/connected_worksheet.py:1137` | `TwbWorksheet.update_title_style()` | 同上 |
| `twbpatch/connected_worksheet.py:1810` | `TwbPane.update_customized_label()` | 同クラスの `update()`（`:2199`） |

いずれも対象クラスに `update()` が既に存在するため、キーワード引数への統合が可能。

## 仕様の空白（要判断）

上記 5 件と対になる形で、**リソースではなく表示属性を返す `get_*()` が 8 件**ある。

```
connected.py:347             TwbDatasource.get_field_grouping()   -> str | None
connected_worksheet.py:931   TwbWorksheet.get_table_style()       -> dict[str, Any]
connected_worksheet.py:1081  TwbWorksheet.get_title_style()       -> dict[str, Any]
connected_worksheet.py:1779  TwbPane.get_customized_label()       -> dict[str, str | None] | None
connected_worksheet.py:1894  TwbPane.get_mark_opacity()           -> float | None
connected_worksheet.py:2027  TwbPane.get_categorical_colors()     -> dict[str, str]
connected_dashboard.py:1180  TwbDashboardContainer.get_style()    -> dict[str, str]
connected_dashboard.py:1666  TwbDashboardZone.get_style()         -> dict[str, str]
```

仕様 §4.1「すべての公開 `get_*()` は `list` を返す」は**リソース取得**を想定した規定であり、
スタイルや不透明度のような**属性アクセサ**を対象にしているかが仕様上あいまい。
`update_*()` の統合方針もこの判断に依存するため、先に仕様側を決める必要がある。

**選択肢:**

1. 属性は `update()` / プロパティに寄せ、`get_*` 名を使わない（§3.3 に完全準拠）
2. 属性アクセサを §4 の適用外と仕様へ明記し、現状を追認する

## README のドリフト

`README.md` は旧 API の記述のままで、新 API を反映していない。

| README の記述 | 実装の現状 |
|---|---|
| `TwbColumn` を返却モデルとして説明（`README.md:236`） | 新 API は `TwbField`（`connected.py:805`） |
| 検索方法 `by` の節（`README.md:53`） | 新 API に `by` は無い。`id=` / `name=` に統一済み |
| `list_*` 系を前提とした取得 API の説明（`README.md:65`〜） | 新 API は `get_*()` |

新 API が利用者向けに露出している範囲を README へ反映する必要がある。

## 次にやること

1. 「仕様の空白」の 1 か 2 を決める（`update_*()` 5 件の扱いがこれに依存する）
2. 決定に沿って公開 `update_*()` を解消する
3. README を新 API の記述へ更新する
4. `要目視` 3 項目を、対応するテストで確認する
