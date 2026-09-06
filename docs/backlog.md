# twbpatch 課題バックログ

- 作成日: 2026-09-05
- 根拠: 実装の AST 解析、テストとの突き合わせ、git 状態の実測

推測は含めない。各項目に「根拠」として実測値を付す。

## この文書の役割

**ここは課題の一覧であって、作業手順書ではない。**
複数ステップに分かれるものは、着手前に**個別タスクへ分解して別ファイルへ切り出す**。

```
docs/backlog.md              ← 課題の一覧（このファイル）
docs/tasks/<ID>_<名前>.md    ← 個別タスクへ分解した作業計画
```

分解した作業計画には、最低限これを書く。

- Phase 分け（仕様確定 → 実装 → 呼び出し側の追随 → 検証）
- 各タスクの対象ファイルと行番号
- 完了条件（テストの期待値、`/spec-conformance` の判定変化）
- 仕様 §11 の移行規約に沿っているか（新 API 追加が先、旧 API 削除は後）

単発で着手できるものは分解せず、このファイルのまま実施してよい。

| 優先度 | 意味 |
|---|---|
| **高** | 利用者に見える不具合、またはデータ損失につながる |
| **中** | 仕様との乖離、または今後の作業コストを押し上げる |
| **低** | 整理・改善。急がない |

---

## 課題一覧

| ID | 優先度 | 課題 | 分解 | 切り出し先 |
|---|---|---|---|---|
| A-1 | **完了** | 新 API のモデルが `import` できない | 済 | 完了（2026-09-05） |
| A-2 | **完了** | 5 リソースが接続型モデル化されていない | 済 | 完了（2026-09-05） |
| A-3 | **完了** | 型注釈の漏れ | 不要 | 完了（2026-09-05） |
| A-4 | **完了** | `draw_*` が 2 箇所に定義されている | 済 | 完了（2026-09-05） |
| A-5 | 低 | `TwbWorkbook` に重複メソッド | 不要 | — |
| A-6 | **完了** | 公開 `update_*()` の廃止 | 済 | 完了（2026-09-05） |
| B-1 | **完了** | 4 メソッドが完全に未検証 | 済 | 完了（2026-09-05） |
| B-2 | 中 | 直接テストが無いメソッド 17 件 | **要** | 未 |
| B-3 | 中 | 仕様 §13 の 3 項目が静的検査で判定できない | **要** | 未 |
| B-4 | **完了** | テスト実行の前提を恒久化する | 不要 | 完了（2026-09-05） |
| C-1 | **完了** | サンプル 20 本が実 Tableau リポジトリを上書きする | — | G-2 で解消 |
| C-2 | **完了** | `outputs/` が `.gitignore` されていない | — | G-4 で解消 |
| D-1 | **完了** | 未コミットの変更が `main` に滞留している | 済 | 完了（2026-09-05） |
| D-2 | **完了** | ルート直下に未追跡ファイルが 46 件 | — | G-1 / G-2 で解消 |
| D-3 | **完了** | `.pytest_cache` が権限エラーを出し続けている | 不要 | `cache_dir` で迂回 |
| E-1 | 中 | 巨大モジュール 3 件 | **要** | 未 |
| E-2 | 低 | 旧 API の削除 | 保留 | 移行完了後に判断 |
| F-1 | 中 | README のドリフト | **要** | 未 |
| F-2 | 低 | `docs/` の文書体系が不明瞭 | 不要 | — |
| G-1 | **完了** | 未使用ファイルの削除（`.twb` / `.py` / `.md`） | 済 | 完了（2026-09-05） |
| G-2 | **完了** | サンプルスクリプトの削除 | 済 | `docs/tasks/G2_sample_inventory.md` |
| G-3 | **完了** | 展開用サンプルの作成 | 済 | `examples/build_dashboard.py` |
| G-4 | **完了** | `.gitignore` の整理 | 不要 | 完了（2026-09-05） |
| H-1 | 中 | ダッシュボードアクションの作成・更新・削除 | **採用** | 未 |
| H-2 | — | `create_datasource()` がない | **不採用** | — |
| H-3 | 低 | フォルダ名を変更できない | **採用** | 未 |
| H-4 | 中 | 階層を作れない | **採用** | 未 |
| H-4b | — | グループ・セット・ビン・ドリルパス | **未判定** | — |
| H-5 | 中 | 合計・小計を付けられない | **採用** | 未 |
| H-6 | 低 | 凡例・注釈・ツールチップ文章 | **保留** | 前提あり |
| H-7 | — | デバイスレイアウト（スマホ・タブレット） | **不採用** | — |
| H-8 | — | join / union / カスタム SQL / リレーション | **不採用** | 一旦見送り |
| H-9 | 中 | `.twbx` 形式で出力できない | **採用** | 未 |
| H-10 | 高 | 作れるグラフが 7 種類しかない | **採用** | 未 |
| H-11 | — | バッチ更新 API | **不採用** | — |
| H-12 | — | ストーリー | **不採用** | — |
| H-13 | 低 | ペインを削除できない | **未判定** | — |
| I-1 | 中 | リセットボタンの生成 | **採用** | 未 |
| I-2 | 高 | KPI ツリーダッシュボードの生成 | **採用** | 未 |
| I-3 | 中 | ダッシュボードのヘッダーメニュー生成 | **採用** | 未 |
| J-1 | 中 | データソースの内容を HTML で出力する | 済 | `docs/tasks/J_html_config.md` |
| J-2 | 高 | HTML 画面で設定し、設定ファイルを出力する | 済 | `docs/tasks/J_html_config.md` |
| J-3 | 中 | 設定ファイル形式の拡張 | 保留 | 範囲 b 以上で起票 |
| K-1 | 高 | コンテナ名の文字列で挙動が変わる | **要** | 未 |
| K-2 | 中 | ヘッダーの書式が固定 | **要** | 未 |
| K-3 | 中 | レイアウトの方向が固定 | **要** | 未 |
| K-4 | 中 | 既定の高さ・色が固定値 | **要** | 未 |
| K-5 | 中 | ワークシートグループの指定項目が 2 つだけ | **要** | 未 |
| K-6 | 中 | 帳票系 `draw_*` が表スタイルを引数で受けない | **要** | 未 |
| K-7 | 低 | 帳票生成時に合計・小計・ソートを指定できない | 保留 | H-5 に依存 |

分解が必要: 21 件 / 単発で着手可: 9 件 / 済: 1 件 / 保留: 2 件 / 不採用: 6 件 / 未判定: 2 件

**G 群は C-1 / C-2 / D-2 を置き換える。** 既存スクリプトを「修正して残す」のではなく
「削除して作り直す」方針に変わったため。

---

## A. 公開 API の整合

### A-7 【完了】`folder=` の書き味が揃っていない

`create_calculated_field(folder="Measure")` が `AttributeError` で落ちていた。
複数形の `create_calculated_fields()` と `create_yoy_calculated_fields()` は
文字列を受け付けるのに、単数形だけ `TwbFolder` しか受け付けなかった。

**仕様 §6.2 の例も `examples/build_dashboard.py` も文字列で書いている**ため、
書いてあるとおりに書くと動かない状態だった。

**原因**: フォルダ名を解決する処理が各メソッドへコピーされていて、単数形だけ
書き漏れていた。継承の失敗ではなく重複の問題。

**決定（2026-09-06・完了）**: **文字列で書けるほうへ揃える。**
仕様書とサンプルが既に文字列なので、そちらに実装を合わせた。

`TwbDatasource._resolve_folder()` に解決処理を一本化し、`folder=` を受け取る
3 メソッドすべてがそれを通る形にした。個々のメソッドで解決を書かないので、
同じ抜けが構造的に起きなくなる。異常系も揃った。

| 渡した値 | 例外 |
|---|---|
| 存在しないフォルダ名 | `NotFoundError` |
| 空文字 | `ValueError` |
| 文字列でも `TwbFolder` でもない | `TypeError` |
| 別データソースの `TwbFolder` | `ValueError` |

`tests/test_folder_argument.py` で 3 メソッド × 異常系を固定した。


### A-1 【完了】新 API のモデルが `import` できない

`twbpatch/__init__.py` は 8 クラスについて **旧 dataclass のほうを公開**している。

```python
from twbpatch import TwbWorksheet   # → models.py の dataclass（旧 API）
                                     #   connected_worksheet.TwbWorksheet ではない
```

**根拠**: `models.py` と `connected*.py` で同名クラスが 8 件重複。
`TwbDashboard` / `TwbDashboardAction` / `TwbDashboardZone` / `TwbDatasource` /
`TwbFolder` / `TwbParameter` / `TwbWorksheet` / `TwbWorksheetField`。
`__init__.py` は `TwbField` / `TwbPane` / `TwbDashboardContainer` の 3 つだけを
`connected*` から取り、残りは `from .models import (...)` で旧側を公開している。

**影響**: 新 API の利用者は接続型モデルを型注釈に書けない。
`isinstance` 判定も旧クラスに対して行われる。ドキュメントの記述と実際の import が食い違う。

**決定（2026-09-05・完了）**: **公開名を新 API へ切り替える。** 仕様 §11.1 に追記した。

```python
from twbpatch import TwbWorksheet          # 接続型モデル（新）
from twbpatch.models import TwbWorksheet   # dataclass（旧）
```

- 切り替えた 8 クラス: `TwbDatasource` / `TwbFolder` / `TwbParameter` / `TwbWorksheet` /
  `TwbWorksheetField` / `TwbDashboard` / `TwbDashboardZone` / `TwbDashboardAction`
- 旧 dataclass は `twbpatch.models` から引き続き import できる。改名も削除もしない（§11）
- 接続型モデルがまだ無い 8 クラス（`TwbColumn` / `TwbRelation` / `TwbRelationship` /
  `TwbReferenceLine` / `TwbWorksheetFilter` / `TwbFilterControl` /
  `TwbValidationMessage` / `TwbUnsupportedFeature`）は `models.py` のまま。
  うち 5 件は **A-2 で接続型モデル化すると自動的にこちらへ移る**
- `list_*()` の戻り値は変えていないので既存テストは影響を受けない

**「名前空間を分ける」を採らなかった理由**: トップレベルから 8 クラスが消えるため
`from twbpatch import TwbWorksheet` が `ImportError` になる。
利用者に毎回 `twbpatch.connected_worksheet` のような内部モジュール名を書かせることにもなる。

**「新 API に別名を付ける」を採らなかった理由**: `ConnectedWorksheet` のような名前が恒久的に残る。
移行が終われば不要になる区別を、公開名に焼き付けることになる。

**破壊的変更の影響**: `from twbpatch import TwbWorksheet` を型注釈に使っている外部コードだけ。
コード全体に `isinstance` 判定は 0 件で、ライブラリは未リリース。

### A-2 【完了】5 リソースが接続型モデル化されていない

以下は接続型モデルではなく **旧 dataclass をそのまま返している**。

| メソッド | 場所 | 返しているもの |
|---|---|---|
| ~~`TwbDatasource.get_relations()`~~ | — | **完了。`TwbRelation`（接続型・読み取り専用）を返す** |
| ~~`TwbDatasource.get_relationships()`~~ | — | **完了。`TwbRelationship`（接続型・読み取り専用）を返す** |
| ~~`TwbWorksheet.get_reference_lines()`~~ | — | **完了。`TwbReferenceLine`（接続型）を返す** |
| ~~`TwbWorksheet.get_filters()`~~ | — | **完了。`TwbWorksheetFilter`（接続型）を返す** |
| ~~`TwbDashboard.get_filter_controls()`~~ | — | **完了。`TwbFilterControl`（接続型）を返す** |

対応する接続型モデル（`TwbRelation` / `TwbRelationship` / `TwbReferenceLine` /
`TwbWorksheetFilter` / `TwbFilterControl`）が存在しないため、取得はできても
`update()` / `delete()` ができない。**仕様 §11 の残 Phase そのもの。**

**着手順の決定（2026-09-05）**: 依存の少ない `TwbRelation` からではなく、
**フィルタ系から**。I-1（リセットボタン）と K-1（フィルタコンテナ）で使うため、
後続の作業が一番進む。

#### フィルタ系 2 リソース【完了 2026-09-05】

**`TwbWorksheetFilter`**（`connected_worksheet.py`）

- 対象要素は `worksheet/table/view/filter[@column]`。`id` は XML 内部参照
  （`[ds1].[none:Region:nk]`）、`name` は解決済みのフィールド名
- 読み取りは既存の `_materialize_filter()` を使い回す。**実装を二重に持たない**
- `update(values=[...])` — 選択値の入れ替え。空リストは「すべての値」（`level-members`）へ戻す。
  既存の `groupfilter` を雛形に複製するので、`user:ui-*` の設定と名前空間の接頭辞が保たれる
- `delete()` — `filter` 要素と、`add_filter()` が置いた `slices` の参照を一緒に外す

**`TwbFilterControl`**（`connected_dashboard.py`）

- **`TwbDashboardZone` を継承する。** XML 上は `zone[@type-v2='filter']` そのもので、
  座標・スタイル・表示/非表示の `update()` と `delete()` は Zone の実装をそのまま使える
- 足したのは `column` / `field` / `role` / `mode` / `worksheet` と、
  参照先フィルタ由来の読み取り（`apply_scope` など）だけ
- フィルタ自体の変更は `TwbWorksheetFilter` 側で行う。同じ操作を 2 箇所に置かない

**書き込みの範囲**: `delete()` と `update(values=...)` まで。表示形式（単一/複数選択）や
適用範囲の変更は、要求している課題がまだ無いので入れていない。

#### 残り 3 リソース【完了 2026-09-05】

**`TwbReferenceLine`**（`connected_worksheet.py`）

- 対象要素は `pane/reference-line[@id]`。表示名を持たない要素なので `name` は `id` と同じ
- `update(formula=, scope=, label_type=)` — **`add_reference_line()` で指定できる値と同じ範囲**。
  `formula` は `average` / `median` / `minimum` / `maximum` のみ受け付け、小文字へ正規化する
- `delete()` — `add_reference_line()` はあるのに消せなかった欠落を埋める

**`TwbRelation` / `TwbRelationship`**（`connected.py`）— **読み取り専用**

- `update()` も `delete()` も持たない。**join / union / カスタム SQL の編集は H-8 として
  見送り済み**で、要求している課題が無い。追加する手段（`create_relation()` 等）も無いので、
  消せないことは欠落ではない
- リレーションは入れ子になるうえ `@id` が一意とは限らないため、走査順の添字で対象要素を解決する。
  `relation.py` に `relation_elements_in_order()` / `relations_in_order()` を足し、
  要素と materialize 結果の添字を対応させている
- 入れ子は `TwbRelation.get_children()` で辿る（§4.1 に従い `list` を返す）
- `export_json()` が dataclass の `asdict()` に依存していたため、
  `serialization.py` に `_serialize_relation()` / `_serialize_relationship()` を足した。
  **出力の形は変えていない**（テストで固定）

**ついでに解消した A-3**: `get_actions()` の戻り値注釈が `list[Any]` のままだったので
`list[TwbDashboardAction]` に直した。これで `twbpatch/` から `list[Any]` は無くなった。

### A-3 【完了】型注釈の漏れ

`TwbDashboard.get_actions()`（`connected_dashboard.py:726`）は
実体として `TwbDashboardAction` の接続型モデルを構築しているが、注釈が `list[Any]`。
**これは A-2 とは別で、注釈を直すだけで済む。**

`TwbWorksheet.add_reference_line()`（`:867`）の `-> Any` も要確認。

**決定（2026-09-05・完了）**: A-2 のついでに直した。

- `TwbDashboard.get_actions()` → `list[TwbDashboardAction]`
- `TwbWorksheet.add_reference_line()` → `TwbReferenceLine`
- `get_filters()` / `get_filter_controls()` / `get_reference_lines()` /
  `get_relations()` / `get_relationships()` は接続型モデル化に伴って実型が付いた

`twbpatch/` から `list[Any]` は無くなった。

### A-4 【完了】`draw_*` が 2 箇所に定義されている

`TwbWorkbook` のメソッド版 7 件と、`twbpatch/draw.py` のモジュール関数版 7 件が併存。
シグネチャは第 1・第 2 引数（`workbook` / `datasource`）以外同じ。

**根拠**: `grep -c '    def draw_' twbpatch/workbook.py` → 7、
`grep -c '^def draw_' twbpatch/draw.py` → 7。

どちらが正なのか仕様に記述がない。片方を薄いラッパーにするか、どちらかを非推奨にするかを決める。

**決定（2026-09-05・完了）**: **メソッド版を正とする。** 仕様 §11.2 に追記した。
他の API（`create_dashboard()` / `get_worksheets()`）と同じ書き味になるため。

- `twbpatch.draw` のモジュール関数は**実装の置き場**として残し、トップレベルの
  `twbpatch` からは公開しない（`from twbpatch import draw_sheet` は `ImportError`）
- 実装をメソッド側へ移していないのは、`workbook.py` をこれ以上大きくしないため（E-1）。
  メソッドは委譲だけを行う
- **メソッド版に `datasource` 引数を足した。** これが無いと項目を毎回
  `(データソース名, フィールド名)` のタプルで書く必要があり、関数版にできて
  メソッド版にできないことが残ってしまう。今は機能が同じで、書き方だけが 1 つになった
- 呼び出し側（テスト 2 ファイル）を追随済み

### A-5 【低】`TwbWorkbook` に重複メソッド

`unsupported_features()`（`workbook.py:166`）と `get_unsupported_features()`（`:169`）が同じもの。
新命名は後者。前者は旧 API として §9 に整理済みだが、削除時期を決める。

> **次のアクション**: 分解不要。E-2（旧 API の削除）に合流させる。

### A-6 【完了】公開 `update_*()` の廃止

2026-09-05 完了。作業計画（`docs/api_rename_plan.md`）は役目を終えたので削除した。
結果は `docs/api_reference.md` §8 に記録している。

- 公開 `update_*()` 5 件を `update(style=...)` / `update(table_style=...)` /
  `update(title_style=...)` / `set_customized_label()` へ統合し、**旧名は削除した**
- 引数を取らない属性アクセサ 7 メソッドをプロパティへ移し、**旧名は削除した**
- 仕様 §3.3 に属性グループの受け方、§4.1 に「`list` を返す規則の対象はリソース取得」を追記
- 呼び出し側（`draw.py` / `build_report()` / テスト / `examples/`）をすべて追随済み

旧名を残さなかったのは、この 5 + 7 件が接続型モデルに後から入った未リリースのメソッドで、
§11 が保護する旧 API（`TwbWorkbook.list_*()` と `models.py` の dataclass 群）ではないため。

---

## B. テストの空白

**2026-09-05 追記**: `tests/test_draw_api.py` の 2 件が実 Tableau リポジトリの絶対パスを
前提にしていて、常に skip されていた（CLAUDE.md の「テストが触ってよいのは
`sample_minimal.twb` と `tmp_path` のみ」にも反していた）。データソースの `@name` を
`federated.xxx` 形式にした `tmp_path` の fixture で再現し、**2 件とも実際に通るようにした。**
これで skip は 0 件。副次的に PreToolUse フックがこのファイルの編集を止めることも無くなった。


### B-1 【完了】4 メソッドが完全に未検証

テストからも SDK 内部からも一度も呼ばれていない。**動作未確認のまま公開されている。**

| メソッド | 場所 |
|---|---|
| `TwbDashboardContainer.add_filter()` | `connected_dashboard.py` |
| `TwbDashboardContainer.add_dashboard_object()` | `connected_dashboard.py` |
| `TwbWorksheet.add_filter()` | `connected_worksheet.py` |
| `TwbWorksheet.add_filter_slice()` | `connected_worksheet.py` |

**根拠**: `tests/` と `twbpatch/` の両方で呼び出し 0 件。

**結果（2026-09-05・完了）**: 4 件すべて実際に動かして確認した。3 件は仕様どおりに動き、
1 件は削除した。

| メソッド | 判定 |
|---|---|
| `TwbWorksheet.add_filter()` | 正常。`filter` 要素 + `groupfilter` + `slices` 参照を作る |
| `TwbDashboardContainer.add_filter()` | 正常。`zone[@type-v2='filter']` を作る |
| `TwbWorksheet.add_filter_slice()` | 正常。ただし**名前に反してフィルタを作らない**（下記） |
| `TwbDashboardContainer.add_dashboard_object()` | **削除した**（下記） |

直接テストは `tests/test_unverified_api.py` に置いた。
`add_filter()` の 2 件は `tests/test_connected_filter_api.py`（A-2）でも使っている。

#### `add_dashboard_object()` を削除した理由

`add_spacer()` と**引数も戻り値も処理も同一**で、`type-v2` に書く文字列が
`"empty"` か `"dashboard-object"` かの違いしかなかった。**これでしかできないことが無い。**

`twb-xml-probe` で参照ワークブックを調べたところ、

- `add_spacer()` が書く `type-v2="empty"` は**実物と一致**（10 件・属性も同じ）
- `add_text()` が書く `type-v2="text"` も一致（27 件）。`_add_object()` に不足属性は無い
- `type-v2="dashboard-object"` は**参照ワークブックに 1 件も無い**。
  このファイルは Tableau 18.1 で、ダッシュボードオブジェクトが入る前のバージョン。
  **実機で開けるか確認する手段が無い**

空の枠は `add_spacer()` で足りる。中身を持つオブジェクト（ナビゲーションボタン、
Web ページ、拡張機能）が必要になったら、種類ごとに `type-v2` も引数も別物になるので、
**I-3（ヘッダーメニュー）で設計し直す。**

#### `add_filter_slice()` の名前と挙動のずれ（記録）

名前は `add_filter()` と対に見えるが、**実際は逆でフィルタを外す**。
`filter` 要素を削除して `slices` へ列参照を登録する。`workbook.set_filter()` の下請け。
動作は仕様どおりなので B-1 では直していない。改名するなら A-6 と同じ扱いになる。

#### 付随して分かったこと

`friendly-name` 属性は Tableau 18.1 では 1 件も出現しない（後発機能）。
`_add_object()` は指定時のみ付けているので、後方互換上の問題は無い。

### B-2 【中】直接テストが無いメソッド 17 件

接続型モデルの公開メソッド 82 件中 17 件がテストから直接呼ばれていない。
うち 8 件は `draw.py` 経由で間接的に実行されている（`set_mark_color` / `set_mark_size` /
`set_mark_opacity` / `set_mark_sizing` / `set_label_style` / `set_continuous_colors` /
`set_categorical_colors` / `set_axis_visibility`）。

間接実行は「壊れたら気づく」だけで、**引数の境界値や異常系は検証されていない**。

> **次のアクション**: **個別タスクに分解する。** B-1 の 4 件を除いた 13 件を、
> クラス単位（`TwbPane` 系 6 件 / `TwbWorksheet` 系 3 件 / その他）でまとめる。
> B-1 の完了後に着手する。

### B-3 【中】仕様 §13 の 3 項目が静的検査で判定できない

`docs/migration_status.md` で `要目視` としているもの。

- Dashboard タイル配置・座標計算・既存編集の非破壊性
- `ResourceInUseError` の発生条件の網羅
- `DetachedModelError` の発生条件の網羅

**これらを検証するテストを追加すれば、`/spec-conformance` が自動判定できるようになる。**

> **次のアクション**: **個別タスクに分解する。** 3 項目それぞれで検証内容が全く異なる。
> 特に「既存 Dashboard 編集の非破壊性」は、仕様 §6.13 の
> 「未対応属性・対象外 Zone・デバイスレイアウトを暗黙に削除しない」を
> XML 差分で確認する必要があり、単体で 1 タスクになる。

### B-4 【低】テスト実行の前提を恒久化する

素の `pytest` は `tmp_path` fixture の `PermissionError` で 69 errors になる。
`--basetemp=tmp/pytest` が必須。現状は `CLAUDE.md` に記載しているだけ。

`pyproject.toml` の `[tool.pytest.ini_options]` に `addopts` を入れれば、
人間が手で叩いても同じ結果になる。**ただしアプリ側の設定変更なので要判断。**

**決定（2026-09-05・完了）**: 入れる。`pyproject.toml` の `[tool.pytest.ini_options]` へ
`addopts = "--basetemp=tmp/pytest"` と `cache_dir = "tmp/pytest_cache"` を追加した。
`cache_dir` は D-3 の迂回策を兼ねる。以降は素の `uv run --no-sync pytest -q` で通る。
`CLAUDE.md` の「`--basetemp` を手で付ける」という記述も更新済み。

---

## C. データ損失リスク

### C-1 【高】サンプルスクリプト 20 本が実 Tableau リポジトリを上書きする

ルート直下の `*_sample.py` / `*_build.py` は全 20 本が
`C:\Users\...\マイ Tableau リポジトリ\ワークブック\` を読み書きし、
全 20 本が `save(..., overwrite=True)` を呼ぶ。git 管理外のため復元できない。

**現状**: PreToolUse フックが Claude による実行を阻止している。
**根本対応**: `SOURCE` / `OUTPUT` を `outputs/` 配下へ変更する。フックは「うっかり」を
止めるだけで、スクリプト自体を安全にはしない。

> **次のアクション**: **G-2 / G-3 へ移管。** 修正して残すのではなく、削除して作り直す方針。
> この項目は「なぜ削除するのか」の根拠として残す。

### C-2 【中】`outputs/` が `.gitignore` されていない

生成物 5 ファイル・約 1.3MB（200〜390KB の `.twb`）が未追跡のまま置かれている。
`git add -A` 一発で巨大な XML がリポジトリへ入る。

**根拠**: `git check-ignore outputs/` → 該当なし。

> **次のアクション**: **G-4 へ移管。**

---

## D. リポジトリ衛生

### D-1 【中】未コミットの変更が `main` に滞留している

14 ファイル・**+1,449 / −229 行**が未コミット。ブランチは `main`、GitHub リモートあり。

**根拠**: `git diff --shortstat`。
対象は `README.md` / `pyproject.toml` / `tests/test_smoke.py` / `twbpatch/` 12 ファイル。

作業単位に分けてコミットしないと、レビューも巻き戻しもできない。

**決定（2026-09-05・完了）**

- **ブランチ方針**: `main` 直コミットは避け、`chore/phase0-cleanup` を切ってそこへ積む。push はしない。
- **粒度**: 5 コミット。①設定とリポジトリ整理 ②接続型モデル API ③テスト ④文書 ⑤サンプル。
- **これ以上割らない理由**: 新モジュール 12 本はすべて `workbook.py:69` の
  `from .serialization import serialize_workbook` と `__init__.py` の
  `from .connected import ...` を経由して連結している。機能単位で割ると、
  途中のコミット単体ではテストが通らない。
- **agent 系はコミットしない**: `.claude/` と `CLAUDE.md` は追跡対象から外す（G-4 で反映）。
  エージェントの作業用設定であってライブラリの成果物ではないため。
  `git add -A` は使わず、対象を明示して stage する。

### D-2 【低】ルート直下に未追跡ファイルが 46 件

`.py` 41 件、`.md` 5 件。サンプル・検証スクリプト・差分メモが混在している。

- 残すもの → `examples/` などへ移動して追跡する
- 使い捨て → 削除するか `.gitignore` に入れる

> **次のアクション**: **G-1 / G-2 へ移管。**

### D-3 【低】`.pytest_cache` が権限エラーを出し続けている

`pytest` 実行のたびに `could not create cache path ... [WinError 183]` が出る。
7 月 8 日作成のディレクトリで、現在は読み取りもできない。作り直すか除外する。

**決定（2026-09-05・完了）**: 「削除して作り直す」は**できなかった**ので「除外」を採った。

`.pytest_cache` は ACL が壊れていて、`Remove-Item -Recurse -Force` も `takeown /f` も
`Access is denied`。所有権の取得に管理者権限が要る。ディレクトリはその場に残したまま、
`pyproject.toml` の `cache_dir = "tmp/pytest_cache"` でキャッシュ先を `tmp/` 配下へ逃がした（B-4 と同時）。

消したい場合は管理者の PowerShell で:

```powershell
takeown /f .pytest_cache /r /d y
Remove-Item -Recurse -Force .pytest_cache
```

---

## E. 保守性

### E-1 【中】巨大モジュール 3 件

| ファイル | 行数 |
|---|---|
| `twbpatch/connected_worksheet.py` | 2,495 |
| `twbpatch/connected_dashboard.py` | 1,918 |
| `twbpatch/connected.py` | 1,277 |

3 ファイルで全体（11,361 行）の **50%** を占める。
1 ファイルを開くだけでコンテキストを大きく消費し、変更の影響範囲も追いにくい。

クラス単位（`TwbWorksheet` / `TwbPane` / `TwbWorksheetField`）での分割が候補。
**ただし分割は移行（A-2）が落ち着いてからのほうが衝突が少ない。**

> **次のアクション**: **個別タスクに分解する。ただし着手は A-2 完了後。**
> ファイル 3 件それぞれで分割単位が異なるため、1 ファイル 1 タスク。
> 分割は import の循環を生みやすいので、依存関係の調査を Phase 0 に置くこと。

### E-2 【低】旧 API の削除

仕様 §11 により、新 API の全 Phase 完了後にまとめて判断する。対象は
`TwbWorkbook` の旧メソッド 29 件と `models.py` の投影 dataclass 14 件。
**現時点では着手しない。** 完了条件を明確にするための記録として置く。

> **次のアクション**: 保留。A-1 / A-2 / A-6 がすべて完了した時点で、分解要否を再判断する。

---

## F. ドキュメント

### F-1 【中】README のドリフト

新 API を反映していない。

| README の記述 | 出現回数 |
|---|---|
| `caption` | 22 |
| `by=`（検索方法） | 14 |
| `TwbColumn` | 4 |
| `list_datasources` / `list_worksheets` | 3 |

いずれも新 API には存在しない、または `name` / `id=` へ置き換わっている。
A-6 の改名対象は README に 1 件も出てこないため、A-6 起因のドリフトはない。**全面改訂は未着手。**

> **次のアクション**: **個別タスクに分解する。ただし着手は API 確定後。**
> README は 526 行 / 28 節あり、節単位でタスク化する。
> `docs/api_reference.md` が目標形なので、それを正として節ごとに突き合わせる。

### F-2 【低】`docs/` の文書体系が不明瞭

7 文書あるが、役割と鮮度の関係が書かれていない。

| ファイル | 役割 | 最終更新 |
|---|---|---|
| `model_api_spec.md` | 正典 | 8/23 |
| `requirements.md` | 初期要件 | 7/9 |
| `metadata_api_scope.md` | 個別改修の範囲 | 7/10 |
| `api_reference.md` | 目標形のリファレンス | 9/5 |
| `migration_status.md` | 自動生成の進捗 | 9/5 |
| `backlog.md` | 課題一覧（本ファイル） | 9/5 |

`requirements.md` と `metadata_api_scope.md` は正典に取り込み済みか、まだ有効かが不明。

> **次のアクション**: 分解不要。`docs/README.md` で索引を作り、役割終了分をアーカイブする。
> `docs/tasks/` は作成済み（`J_html_config.md` / `G2_sample_inventory.md`）。

---

## G. 整理と再パッケージ

C-1 / C-2 / D-2 を置き換える。既存のサンプルを直して残すのではなく、**削除して作り直す**。

### G-1 【中】未使用ファイルの削除（`.twb` / `.py` / `.md`）

リポジトリに残っている生成物・検証用ファイル・作業メモを削除する。

**候補**（実測）

| 対象 | 件数 / サイズ |
|---|---|
| `outputs/` の生成 `.twb` / `.twbr` | 6 件・約 1.5MB |
| `outputs/ec_site_test/` の生成物 | `.twb` 4 件・`.csv` 2 件 |
| ルート直下の差分メモ `.md` | 3 件（`ECサイト分析_..._diff*.md`） |
| ルート直下の検証用 `.py` | `field_organization_test.py` など |
| `workbook/test.ipynb` | 1 件（追跡済み） |
| `workbook/*.twbx` | 1 件・2.5MB（追跡済み。参照用として残すか要判断） |

**決定（2026-09-05・完了）**

線引きは「テストまたは仕様書から参照されているか」。実測したところ、下記はいずれも参照 0 件だった。

| 対象 | 判断 |
|---|---|
| `outputs/` の生成物すべて（`ec_site_test/` 含む・約 1.7MB） | 削除 |
| ルート直下の差分メモ `.md` 3 件 | 削除 |
| ルート直下の検証用 `.py`（`field_organization_test.py` ほか） | 削除（G-2 の 20 本に含む） |
| `ec_site_fields.yaml` | 削除（書式は `examples/sample_ec_fields.yaml` へ引き継ぎ） |
| `workbook/~RETAIL...twbr`（Tableau の復元残骸・未追跡） | 削除 |
| `workbook/test.ipynb`（追跡済み） | **削除** |
| `workbook/*.twbx`（追跡済み・2.5MB） | **残す**（参照用） |

`.twbx` を残したのは、追跡済みファイルを消しても過去のコミットにデータが残るため
**リポジトリの容量が減らない**から。削除の利得がなく、参照用として使う可能性がある。

### G-2 【高】サンプルスクリプトの削除

ルート直下の `*_sample.py` / `*_build.py` **20 本**を削除する。

**理由**: 全 20 本がリポジトリ外の実 Tableau リポジトリを `overwrite=True` で書き換える。
修正して残すより、G-3 で作り直すほうが安全かつ確実。

**副次的な効果**: 削除後は C-1 のデータ損失リスクが消える。
PreToolUse フック（`.claude/hooks/`）の役割も再評価できる。

**決定（2026-09-05・完了）**: 20 本すべてと `ec_site_fields.yaml` を削除した。

- 知見は削除前に `docs/tasks/G2_sample_inventory.md` へ書き出した（6 パターンに整理）。G-3 の入力。
- **PreToolUse フックは残す**。対象スクリプトは消えたが、フックは
  「リポジトリ外の絶対パスを指す `.twb` / `.twbx` への書き込み」を汎用的に止めるので、
  今後書くコードにも効く。役割は「20 本を守る」から「うっかりを止める」へ変わった。
- 新しい `examples/build_dashboard.py` はリポジトリ内で完結するためフックに掛からない。

### G-3 【中】展開用サンプルの作成

配布・共有できるサンプルを新規に作る。

**満たすべき条件**

- 入力はリポジトリ同梱のもの（`tests/sample_minimal.twb` など）だけを使う
- 出力はリポジトリ内（`outputs/` など）に閉じる
- 環境依存の絶対パスを持たない
- そのまま実行して動く

置き場所（`examples/` など）、対象とする API の範囲、README からの参照方法を決める。

**決定（2026-09-05・完了）**: Phase 0 で前倒し実施した。

- **置き場所**: `examples/`
- **本数**: **1 本**（`examples/build_dashboard.py`）。旧サンプル 20 本は重複が多く、
  内容は 6 パターンに縮まったため、パターンごとに分けず 1 本へまとめた
- **入力**: `examples/sample_ec.twb` を新規に作った。
  **`tests/sample_minimal.twb` は使えない。** measure 2 列だけでディメンションが無く、
  `draw_sheet` / `draw_crosstab` / `draw_quadrant` などが動かせないため
- **出力**: `outputs/`（`.gitignore` 済み）
- **カバー範囲**: フィールド整理 / 計算フィールド / `draw_*` 7 種 / 表スタイル /
  `build_report()` と `create_container()` の 2 通り / ペイン直接操作
- **README からの参照**: 未実施。README は全編が旧 API のままなので **F-1 の全面改訂と同時**にする

実行して 8 シート・2 ダッシュボード・検証エラー 0 を確認済み。

### G-4 【中】`.gitignore` の整理

生成物と成果物の線引きを決めて反映する。

**現状の論点**

- `outputs/` が未設定。生成 `.twb` が `git add -A` で入る
- `tmp/` は設定済み（37 行目）。テストの `--basetemp` がここを使う
- `.codex/` と `.agents/` を ignore しているが、両ディレクトリは空
- G-3 の `examples/` は追跡対象にする

**決定（2026-09-05・完了）**

| 追加 | 理由 |
|---|---|
| `outputs/` | 生成 `.twb` を追跡しない。`examples/` の出力先 |
| `.claude/` | エージェントの作業用設定。ライブラリの成果物ではない |
| `CLAUDE.md` | 同上 |

- `.codex/` と `.agents/` は空のままだが、同じ「agent 系は追跡しない」方針なので残す。
- `examples/` は追跡対象（ignore しない）。
- `tmp/` は既存のまま。`--basetemp` と `cache_dir` の両方がここを使う（B-4 / D-3）。

---

## H. 機能追加

既存機能の不具合ではなく、**まだ無いもの**。実装が「未対応」と明示している箇所、
CRUD が欠けているモデル、Tableau の概念で実装に登場しないものから洗い出した。

## H 群の採否（2026-09-05 判定）

| やりたいこと | 判定 | 備考 |
|---|---|---|
| クリックでフィルタが効く**アクション**を作る | **採用** | ダッシュボードアクションのみ対応する。他の種類は対象外 |
| **データソースを新規に作る** | **不採用** | カラムの自動生成が難しい。特に SQL の場合 |
| **フォルダ名を変更する** | **採用** | |
| **階層**を作る | **採用** | |
| グループ・セット・ビン・ドリルパス | **未判定** | 階層と同じ扱いにするか要判断 |
| **合計・小計**を付ける | **採用** | |
| 凡例・注釈・**ツールチップの文章** | **保留** | 太字・文字サイズなど**書式指定の表記ルールを先に決める**のが前提 |
| スマホ・タブレット用レイアウト | **不採用** | 不要 |
| join / union / カスタム SQL / リレーション | **不採用** | 一旦見送り |
| **`.twbx` で出力する** | **採用** | |
| **折れ線・円・積み上げ棒**などのグラフ | **採用** | **グラフごとに引数のルールを決める**のが前提 |
| 100 個まとめて更新する | **不採用** | 不要 |
| ストーリー | **不採用** | 不要 |
| ペインを削除する | **未判定** | |

**採用 7 / 不採用 5 / 保留 1 / 未判定 2**

採用したものは以下に残す。不採用のものも「なぜ見送ったか」を記録として残す。

### H-1 【中】ダッシュボードアクションが読み取り専用

`TwbDashboardAction` はプロパティ 9 個だけで、`update()` も `delete()` も無い。
`create_*` も存在しない。**アクションの取得はできるが、作成・変更・削除ができない。**

**根拠**: 接続型モデル 11 クラス中、`update()` / `delete()` の両方を欠くのは
`TwbDashboardAction` のみ。`grep 'def create_dashboard_action'` → 0 件。

対象はフィルタアクション、ハイライトアクション、URL アクション、パラメータアクション。

> **次のアクション**: 個別タスクに分解する。アクション種別ごとに XML 構造が異なる。

### H-2 【中】`create_datasource()` がない

`TwbWorkbook` に `create_worksheet` / `create_dashboard` / `create_parameter` はあるが、
**データソースを新規作成する API が無い**。既存ワークブックのデータソースを流用するしかない。

**根拠**: `grep 'def create_datasource'` → 0 件。

> **次のアクション**: 個別タスクに分解する。接続種別（BigQuery / Excel / CSV）ごとに
> 必要な XML が違う。`update(source=...)` の既存実装が土台になる。

### H-3 【低】一部モデルに CRUD の欠け

| モデル | 欠けているもの | 影響 |
|---|---|---|
| `TwbFolder` | `update()` | フォルダ名を変更できない |
| `TwbPane` | `delete()` | ペインを削除できない |

**根拠**: 接続型モデルの CRUD 有無を AST で走査した結果。

> **次のアクション**: 分解不要。既存の `update()` / `delete()` 実装に倣うだけ。

### H-4 【中】グループ・セット・ビン・階層・ドリルパスが未対応

Tableau の主要なフィールド概念のうち、実装にほとんど登場しないもの。

| 概念 | 実装内の出現 |
|---|---|
| ビン (`bin`) | **0 箇所** |
| ドリルパス (`drill-path`) | **0 箇所** |
| 階層 (`hierarchy`) | 1 箇所 |
| セット (`set`) | 2 箇所 |
| グループ (`group`) | 3 箇所 |

計算フィールドとフォルダは扱えるが、これらは取得も編集もできない。

> **次のアクション**: 個別タスクに分解する。概念ごとに独立。まず「取得だけ」を通してから
> 編集へ進むほうが安全。

### H-5 【中】合計・小計が未対応

`total` / `subtotal` の出現は実装内 **0 箇所**（`validator.py` の要素順定義を除く）。

**根拠**: `docs/requirements.md:253` に「ソート、合計、小計は将来拡張とすること」と明記。
ソート（`add_sort()`）だけが実装済みで、合計・小計は未着手。

> **次のアクション**: 個別タスクに分解する。要件に予告済みの機能。

### H-6 【低】凡例・注釈・ツールチップ編集が未対応

| 概念 | 実装内の出現 |
|---|---|
| 凡例 (`legend`) | **0 箇所** |
| 注釈 (`annotation`) | **0 箇所** |
| ツールチップ (`tooltip`) | 3 箇所（エンコーディングとしての配置のみ） |

ツールチップは「どのフィールドを載せるか」は指定できるが、**表示テキストの編集はできない**。

> **次のアクション**: 個別タスクに分解する。凡例はダッシュボードのゾーン種別、
> 注釈はワークシート配下と、置き場所が異なる。

### H-7 【低】デバイスレイアウトの編集 API がない

`device-layout` の出現は実装内 **0 箇所**。

仕様 §13 は「デバイスレイアウトが暗黙に削除・変更されない」ことを受け入れ条件に挙げており、
**保護はするが編集はできない**状態。スマートフォン・タブレット向けレイアウトを扱えない。

> **次のアクション**: 個別タスクに分解する。まず現状の保護が実際に効いているかの検証（B-3）が先。

### H-8 【中】データ接続の編集に制約がある

`unsupported.py` が実行時に警告として検出しているもの。

| 対象 | 現状 |
|---|---|
| join | 編集不可 |
| union | 編集不可 |
| カスタム SQL | 読み取り専用 |
| federated connection（リレーションシップ） | 未対応の可能性ありと警告 |
| hyper 抽出 | 保持するが編集しない |

**根拠**: `twbpatch/unsupported.py` の 5 チェック。

> **次のアクション**: 個別タスクに分解する。5 項目それぞれ難度が大きく異なる。
> カスタム SQL の書き換えは比較的単純、join / union の編集は物理レイヤの再構築を伴う。

### H-9 【低】`.twb` → `.twbx` へ変換保存できない

`.twbx` 保存は「`.twbx` から開いたワークブック」でのみ可能。

```python
raise SaveError(".twbx 保存には .twbx から開いたワークブックが必要です。")
```

**根拠**: `twbpatch/workbook.py:148`。

`.twb` から作った成果物を配布用の `.twbx` にまとめられない。

> **次のアクション**: 分解不要。同梱データの解決方針だけ決めれば実装は単純。

### H-10 【中】`draw_*` のグラフ種類が 7 種のみ

現状: `draw_sheet` / `draw_bar` / `draw_yoy` / `draw_card` / `draw_quadrant` /
`draw_crosstab` / `draw_colored_yoy_sheet`。

`mark_type` を手で設定すれば他のグラフも作れるが、**定型 API としては未整備**。
折れ線、積み上げ棒、円、面、ヒストグラム、二重軸、ツリーマップ、地図などが候補。

このライブラリの方向性（定型ワークシート作成 API の拡張／`requirements.md:6`）に直結する。

> **次のアクション**: 個別タスクに分解する。1 グラフ種 = 1 タスク。
> 需要の高いものから決める必要があるため、まず対象の優先順位付けを行う。

### H-11 【低】バッチ API が未設計

仕様 §5.2 に「複数件の一括更新・一括削除が必要になった場合は、通常の CRUD とは別の
バッチ API として設計する」と記載があるが、**未着手**。

現状、100 フィールドの改名は 100 回の `update()` になる。

> **次のアクション**: 個別タスクに分解する。実際に遅いか、`is_dirty` や原子性（§5.5）を
> どう扱うかの設計判断が先。

### H-12 【低】ストーリーが未対応

`story` の出現は実装内 **0 箇所**。ストーリーを含むワークブックを開いた場合の
挙動が未検証（保持されるのか、失われるのか）。

> **次のアクション**: 個別タスクに分解する。まず「保持されるか」の検証から。
> 失われるなら `unsupported.py` の検出対象に追加するのが先。

---

## I. 新規要望（部品を組み合わせて作る機能）

H 群が「Tableau の機能に対応する」話なのに対し、I 群は
**既存 API を組み合わせて、完成物を一発で生成する**高水準の機能。`draw_*` の延長線上にある。

### I-1 【中】リセットボタンの生成

ダッシュボード上のフィルタを一括で解除するボタンを自動生成する。

**Tableau 上での作り方**（参照: https://note.com/nene_tani/n/n54871c0ee3a1 ）

1. 文字列定数の計算フィールドを作る（例: `'フィルターをリセット'`）
2. それをテキストに配置した専用ワークシートを作る（フォント・サイズ・色・中央寄せ）
3. ダッシュボードへ配置する
4. フィルタアクションを設定する
   - ソースシート: リセット用シートのみ
   - 実行対象: 選択
   - ターゲットシート: リセット用シート以外すべて
   - 選択解除時: すべての値を表示
   - 対象フィルタ: ダッシュボード上のフィルタを個別指定

**依存**: 手順 4 に **H-1（ダッシュボードアクションの作成）が必須**。H-1 の後に着手する。

> **次のアクション**: 個別タスクに分解する。ボタンの見た目（文字・色・サイズ）を
> どこまで引数で受けるかを決める。

### I-2 【高】KPI ツリーダッシュボードの生成

指標を階層構造で定義すると、その通りのツリー型ダッシュボードを生成する。

**参照**: https://public.tableau.com/views/KPI_16405431603270/sheet0

**要件**

- 指標を階層構造（親子関係）で受け取る
- **左から右**へ展開するツリーとして配置する
- ノードごとに複数種類のワークシートを自動生成する
  - 達成 / 未達 / アラートの状態表示
  - 実数値
  - 評価指標
  - 棒グラフ
- 生成したシートをツリー状にダッシュボードへ配置する

**依存**: `draw_card` と `draw_bar` は流用できる。配置は `TwbDashboardContainer` の
タイル配置（`direction` / `order` / `weight`）で組む。
**階層構造の受け取り方**は H-4（階層）とは別問題（こちらは指標の親子関係であって Tableau の階層ではない）。

> **次のアクション**: 個別タスクに分解する。規模が大きい。
> 「入力の階層定義フォーマット」「ノード1個分のシート群」「ツリー配置ロジック」の3つに割れる。

### I-3 【中】ダッシュボードのヘッダーメニュー生成

ダッシュボード上部にヘッダー領域を作り、アイコンとリンクを並べる。

**要件**（詳細は未確定）

- アイコンの配置
- リンク（URL アクション、または他ダッシュボードへの遷移）

**依存**: 画像配置は `add_image()` が既にある。リンクは **H-1（アクション作成）**が必要になる可能性が高い。

> **次のアクション**: 個別タスクに分解する。まずアイコン画像をどう渡すか
> （ファイルパス / 埋め込み）と、リンクの種類（URL / ダッシュボード遷移）を確定させる。

---

## J. 設定を画面で行う仕組み

**課題**: ダッシュボードを組むには、まずデータソースにどんなフィールドがあるかを調べ、
その結果を Python コードへ手で書き写す必要がある。フィールドが数十個あると現実的でない。

**着想**: データソースの内容を HTML で出力し、**画面上で設定して設定ファイルを吐かせる**。

### 既にある部品

真ん中の「人が手で書く」以外は揃っている。

```
.twb  →  export_json()  →  ［人が YAML を手書き］  →  apply_field_config(yaml)  →  .twb
         実装済み              ← ここが手作業            実装済み
```

- `TwbWorkbook.export_json()`: ワークブックの内容を辞書で取り出す
- `TwbDatasource.apply_field_config(yaml)`: 表示名とフォルダを一括適用する
- `ec_site_fields.yaml`: 設定ファイルの実例

### 想定する流れ

```
1. Python: wb.export_html("fields.html")
2. ブラウザで fields.html を開く → 表示名・フォルダを画面で編集
3. 「出力」ボタン → fields.yaml をダウンロード
4. Python: datasource.apply_field_config("fields.yaml") → wb.save(...)
```

**サーバを立てない。** ブラウザからファイルをダウンロードして Python に渡すだけなら、
ライブラリに新しい依存が増えない。

### J-1 【中】データソースの内容を HTML で出力する

読み取り専用。データソース、フィールド一覧（表示名・型・役割・計算式・所属フォルダ）、
ワークシート、ダッシュボードを一覧できる HTML を出す。

**これだけでも「調べるのが面倒」は半分解決する。** `export_json()` の結果を
HTML に整形するだけなので、実装は軽い。

> **次のアクション**: 個別タスクに分解する。何を載せるか（フィールドだけ / ワークブック全体）を決める。

### J-2 【高】HTML 画面で設定し、設定ファイルを出力する

J-1 の HTML に編集機能を付ける。画面で設定した内容を YAML / JSON でダウンロードさせる。

**最初に決めること: どこまで画面で設定させるか**

| 範囲 | 内容 | 備考 |
|---|---|---|
| a | フィールドの表示名・フォルダ割り当て | 今の `apply_field_config` がそのまま使える。**最小構成** |
| b | a + 計算フィールドの定義 | 設定ファイル形式の拡張（J-3）が必要 |
| c | b + ワークシート構成（どのグラフを何で作るか） | `draw_*` の引数を画面で組む |
| d | c + ダッシュボードのレイアウト | 事実上 Tableau Desktop の再実装。**やりすぎ** |

**a から始めて、必要になったら広げる**のが現実的。

> **次のアクション**: 個別タスクに分解する。まず範囲（a〜d）を決める。

### J-3 【中】設定ファイル形式の拡張

現在の形式は `フォルダ名 → {元のフィールド名: 表示名}` の入れ子辞書だけ。

```yaml
"Orders++ (sample_-_superstore)":
  Dim商品:
    Category: カテゴリ
```

**表現できないもの**

- 計算フィールドの定義（式、データ型、書式）
- フィールドの役割（ディメンション / メジャー）、連続 / 不連続
- 表示順（現状は YAML の記述順に依存する）
- 非表示フラグ

J-2 を範囲 b 以上にするなら、先にこの拡張が必要。

> **次のアクション**: 個別タスクに分解する。J-2 の範囲決定に依存する。
> 既存の `ec_site_fields.yaml` と後方互換を保つかも決める。

---

## K. 帳票作成 API のパラメータ拡張

対象は `TwbDashboard.build_report()`（`twbpatch/connected_dashboard.py:766`、**214 行**）と、
帳票系の `draw_crosstab()` / `draw_sheet()` / `draw_colored_yoy_sheet()`。

**現状**: 引数は 7 個しかなく、レイアウトと書式の大部分が実装内に固定されている。
細かく調整したい場合、生成後に `TwbDashboardContainer` を取り直して手で直すしかない。

```python
build_report(
    dashboard_name, struct, container_sizes=None, content_style=None,
    header_height=43, header_background_color="#c0c0c0", header_font_color="#333333",
)
```

### K-1 【高】コンテナ名の文字列で挙動が変わる

`struct` のキー（コンテナ名）に特定の日本語が含まれるかどうかで、動作が分岐している。

| 判定 | 場所 | 効果 |
|---|---|---|
| `"フィルタ" in container_name` | `:791` `:916` `:921` `:931` | フィルタ用コンテナとして扱う。高さ既定 50、均等配分しない |
| `"スコア" in container_name` | `:918` | 高さ既定 250 |
| 上記以外 | — | 高さ既定 300 |

**問題**

- コンテナ名は**画面に出る表示名**。それが制御フラグを兼ねている
- 英語名（`"filter"`）では動かない
- 「売上フィルタ状況」のように、意図せず部分一致して挙動が変わる
- 表示名を変えたらレイアウトが変わる

**方向性**: 種別を明示的な引数で受ける
（例: `{"名前": {"kind": "filter", "items": [...]}}`）。表示名との分離。

> **次のアクション**: 個別タスクに分解する。**K 群の中で最優先。** 他の拡張はこの構造の上に乗る。
> 現行の書き方と後方互換を保つか、破壊的変更にするかを先に決める。

### K-2 【中】ヘッダーの書式が固定

ヘッダーは必ず 1 つ付き、書式のほとんどが実装内に埋め込まれている（`:872` 付近）。

| 項目 | 現状 | 引数で変えられるか |
|---|---|---|
| 表示テキスト | `dashboard_name` と同じ | **不可** |
| 文字サイズ | `16` 固定 | **不可** |
| 太字 | `True` 固定 | **不可** |
| 余白 | `margin: 0` / `padding: 8` 固定 | **不可** |
| 枠線 | `border_style: "none"` 固定 | **不可** |
| ヘッダー自体の有無 | 常に付く | **不可** |
| 高さ / 背景色 / 文字色 | — | 可 |

> **次のアクション**: 個別タスクに分解する。I-3（ヘッダーメニュー）と設計が重なるため、
> **同時に検討する**。

### K-3 【中】レイアウトの方向が固定

3 階層すべて方向が決め打ち。

| 階層 | 方向 | 場所 |
|---|---|---|
| 外枠 | `vertical` 固定 | `:868` |
| 各コンテナ | `horizontal` 固定 | 各行を横並びにする |
| グループ内 | `vertical` 固定 | 縦積み |

横長の帳票は作れるが、**縦に並べる帳票が作れない**。`weight` も `1` 固定で比率を変えられない。

> **次のアクション**: 個別タスクに分解する。K-1 の構造変更に合わせて設計する。

### K-4 【中】既定の高さ・色が固定値

`container_sizes` で個別に上書きはできるが、**既定値そのものを変えられない**。

| 対象 | 既定値 |
|---|---|
| フィルタ行の高さ | 50 |
| スコア行の高さ | 250 |
| その他の行の高さ | 300 |
| 本文の背景色 | `#f5f5f5`（`_DEFAULT_REPORT_CONTENT_STYLE`、`:27`） |
| ワークシートの背景色 | `#ffffff`（`_DEFAULT_REPORT_WORKSHEET_STYLE`） |

毎回すべてのコンテナ名を `container_sizes` に列挙しないと、既定値から離れられない。

> **次のアクション**: 個別タスクに分解する。既定値をまとめて差し替える引数
> （テーマ・プリセット）として受けるのが自然。

### K-5 【中】ワークシートグループの指定項目が 2 つだけ

`struct` の中でワークシートをグループ化するとき、辞書で受け付けるキーは
`items` と `fixed_size` のみ。それ以外はエラーになる。

```python
if set(item) - {"items", "fixed_size"}:
    raise ValueError("worksheet group supports only items and fixed_size")
```

`weight`（比率）、`direction`（方向）、`friendly_name`（コンテナ名）、
`style`（背景色など）を指定できない。

> **次のアクション**: 個別タスクに分解する。K-1 / K-3 と同じ構造変更の一部。

### K-6 【中】帳票系 `draw_*` が表スタイルを引数で受けない

`TwbWorksheet` には表スタイルを設定する機能があるのに、
`draw_crosstab()` / `draw_sheet()` の引数からは指定できない。

| 設定できる項目 | 指定方法 |
|---|---|
| ヘッダー背景色 / 太字 / 文字色 / 行の縞 / 列幅 | 生成後に `update_table_style()` を別途呼ぶ |

2 段階になるうえ、`draw_*` の戻り値を受けて追加で呼ぶ必要がある。
**A-6（`update_*()` の改名）が完了したら `update(table_style=...)` になる点にも注意。**

> **次のアクション**: 個別タスクに分解する。H-10（グラフ種類の追加）で
> 引数ルールを決めるので、**そこに合流させる**のが効率的。

### K-7 【低】帳票生成時に合計・小計・ソートを指定できない

ソートは `add_sort()` で生成後に設定できるが、`draw_*` の引数にはない。
合計・小計はそもそも未実装（H-5）。

> **次のアクション**: 保留。**H-5（合計・小計）の実装後**に、引数として露出させるか判断する。

---

## 着手順の目安

依存関係だけを示す。優先順位の決定はしない。

```
D-3 (.pytest_cache 作り直し)      ← 単独。すぐできる
D-1 (未コミット分の整理)          ← 他の作業の前提になる
    ↓
G-2 (サンプル削除) → G-1 (未使用ファイル削除) → G-3 (展開用サンプル作成) → G-4 (gitignore 整理)
    ※ この順で C-1 / C-2 / D-2 が解消する
    ↓
A-6 (改名)                       ← 完了（2026-09-05）
A-4 (draw_* の一本化)            ← 仕様確定を含む
    ↓
A-1 (公開名前空間の整理) ←→ A-2 (5 リソースの接続型モデル化)
                                  相互に方針が依存する。同時に設計する
    ↓
B-1 → B-2 (テスト追加)            ← A-2 完了後に一緒に書くのが効率的
B-3 (§13 の要目視 3 項目)
    ↓
E-1 (モジュール分割)              ← 移行完了後
F-1 (README 全面改訂)             ← 最後。API が固まってから
E-2 (旧 API 削除の判断)
```

`C-1` + `D-2`（サンプルの出力先とファイル整理）はまとめて 1 タスク。
`B-4`（pytest 設定）と `F-2`（文書整理）は上記の流れとは独立に実施できる。
