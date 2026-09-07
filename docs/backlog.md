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
| A-7 | **完了** | `folder=` の書き味が揃っていない | 不要 | 完了（2026-09-06） |
| A-8 | **完了** | フィールド指定の書き味が揃っていない | 済 | 完了（2026-09-06） |
| A-9 | **完了** | 自分の値を変える `set_*` が `update()` の外にある | 済 | 完了（2026-09-06） |
| A-10 | **完了** | 仕様書の中で書き方が食い違っている | 不要 | 2 件とも解消（2026-09-07） |
| B-1 | **完了** | 4 メソッドが完全に未検証 | 済 | 完了（2026-09-05） |
| B-2 | **完了** | 直接テストが無いメソッド 4 件 | 不要 | 直接テスト 38 件。**実バグ 3 件を発見して修正**（2026-09-07） |
| B-3 | **完了** | 仕様 §13 の 3 項目が静的検査で判定できない | **要** | テスト 15 件を追加（2026-09-07） |
| B-4 | **完了** | テスト実行の前提を恒久化する | 不要 | 完了（2026-09-05） |
| C-1 | **完了** | サンプル 20 本が実 Tableau リポジトリを上書きする | — | G-2 で解消 |
| C-2 | **完了** | `outputs/` が `.gitignore` されていない | — | G-4 で解消 |
| D-1 | **完了** | 未コミットの変更が `main` に滞留している | 済 | 完了（2026-09-05） |
| D-2 | **完了** | ルート直下に未追跡ファイルが 46 件 | — | G-1 / G-2 で解消 |
| D-3 | **完了** | `.pytest_cache` が権限エラーを出し続けている | 不要 | `cache_dir` で迂回 |
| D-4 | 中 | 改修完了後にリポジトリを作り直す | 不要 | 未（改修完了後に着手） |
| E-1 | 中 | 巨大モジュール 3 件 | **要** | 未 |
| E-2 | **完了** | 旧 API の削除 | **要** | 25 件削除（2026-09-07）。**残り 4 件は L-6 待ち** |
| F-1 | **完了** | README のドリフト | **要** | `api_reference.md` を統合（2026-09-07） |
| F-2 | 低 | `docs/` の文書体系が不明瞭 | 不要 | — |
| F-3 | **完了** | `api_reference.md` に投影モデル 5 クラスの節が無い | 不要 | §3.12〜3.16（2026-09-07） |
| G-1 | **完了** | 未使用ファイルの削除（`.twb` / `.py` / `.md`） | 済 | 完了（2026-09-05） |
| G-2 | **完了** | サンプルスクリプトの削除 | 済 | `docs/tasks/G2_sample_inventory.md` |
| G-3 | **完了** | 展開用サンプルの作成 | 済 | `examples/build_dashboard.py` |
| G-4 | **完了** | `.gitignore` の整理 | 不要 | 完了（2026-09-05） |
| H-1 | **完了** | ダッシュボードアクションの作成・更新・削除 | **採用** | フィルタと URL の 2 種（2026-09-07） |
| H-2 | — | `create_datasource()` がない | **不採用** | — |
| H-3 | 低 | 一部モデルに CRUD の欠け | **採用** | フォルダは L-1 で完了。**残りはペインの削除（L-4）** |
| H-4 | **完了** | グループ・セット・ビン・階層が未対応 | **採用** | 階層は L-2、グループは L-5 で完了（2026-09-07）。セット・ビンは対象外 |
| ~~H-4b~~ | — | グループ（セット・ビンは対象外） | — | **L-5 へ統合（2026-09-07）。** 本文は L-5 |
| H-5 | **完了** | 合計・小計を付けられない | 済 | `docs/tasks/H5_totals.md`（2026-09-06） |
| H-6 | 低 | 凡例・注釈・ツールチップ文章 | **保留** | 前提あり |
| H-7 | — | デバイスレイアウト（スマホ・タブレット） | **不採用** | — |
| H-8 | — | join / union / カスタム SQL / リレーション | **不採用** | 一旦見送り |
| H-9 | 中 | `.twbx` 形式で出力できない | **採用** | 未 |
| H-10 | 中 | 作れるグラフが 7 種類しかない | **採用** | 未（設定画面の前提ではない） |
| H-11 | — | バッチ更新 API | **不採用** | — |
| H-12 | — | ストーリー | **不採用** | — |
| ~~H-13~~ | — | ペインを削除できない | — | **L-4 へ統合（2026-09-07）。** 本文は L-4 |
| I-1 | 中 | リセットボタンの生成 | **採用** | 未 |
| I-2 | 高 | KPI ツリーダッシュボードの生成 | **採用** | **次回リリース**（2026-09-07 決定） |
| I-3 | 中 | ダッシュボードのヘッダーメニュー生成 | **採用** | **次回リリース**（前提の L-3 と同時） |
| J-1 | **完了** | データソースの内容を HTML で出力する | 済 | 完了（2026-09-06） |
| J-2 | **完了** | HTML 画面で設定し、設定ファイルを出力する | 済 | 画面・受け手とも完了（2026-09-07） |
| J-3 | **完了** | 設定ファイル形式の拡張（受け手） | 済 | `apply_config()`（2026-09-07） |
| J-4 | **完了** | HTML 画面でダッシュボードを設定する | 済 | 画面・受け手とも完了（2026-09-07） |
| J-5 | **完了** | デザインルールの設定をダッシュボードへ届ける | 不要 | フィルタの「適用」ボタンを追加（2026-09-07） |
| K-1 | **完了** | コンテナ名の文字列で挙動が変わる | **要** | 区分値 `kind` で制御する形にした（2026-09-07） |
| K-2 | 中 | ヘッダーの書式が固定 | **要** | 未 |
| K-3 | 中 | レイアウトの方向が固定 | **要** | 未 |
| K-4 | 中 | 既定の高さ・色が固定値 | **要** | 未 |
| K-5 | 中 | ワークシートグループの指定項目が 2 つだけ | **要** | 未 |
| K-6 | 中 | 帳票系 `draw_*` が表スタイルを引数で受けない | **要** | 未 |
| K-7 | 低 | 帳票生成時に合計・小計・ソートを指定できない | **要** | 未（**保留解除 2026-09-06**: H-5 完了） |
| L-1 | **完了** | `TwbFolder` の名前を変えられない | 不要 | `update(name=)`（2026-09-07） |
| L-2 | **完了** | 階層（ドリルパス）を扱えない | **要** | `TwbDrillPath`（2026-09-07） |
| L-3 | 中 | ナビゲーションアクションを作れない | 不要 | **次回リリース**（2026-09-07 決定） |
| L-4 | 低 | ペインを削除できない | 不要 | 未（H-13 の採否待ち） |
| L-5 | **完了** | グループを作れない | 不要 | `create_group()`（2026-09-07）。セット・ビンは対象外 |
| L-6 | 中 | ダッシュボード読み取りの穴 4 件 | **要** | 未（**E-2 の残り 4 件の前提**） |

**残り 19 件**（要分解 8 / そのまま着手可 11）。
完了 37 件 / 保留 1 件 / 不採用 5 件 / 他課題へ統合 2 件。全 64 件（2026-09-07 実測）。

| 優先度 | 残り |
|---|---|
| 高 | 1 件（I-2 KPI ツリー。**次回リリースへ送付済み**） |
| 中 | 13 件 |
| 低 | 5 件 |

**E-2（旧 API の削除）は完了。** 25 件を消し、代替の無い 4 件は L-6 として起票した。

**今回のリリース分は片づいた。** 残り 18 件は次回以降で、うち 3 件は
次回リリースへ送付済み（L-3 / I-3 / I-2）。

**うち 3 件は次回リリースへ送った**（L-3 ナビゲーションアクション、I-3 ヘッダーメニュー、
I-2 KPI ツリー）。**今回のリリースに残るのは仕上げの作業だけ**になった。

**L 群 5 件はクラス方式の欠落**で、H-3 / H-4 / I-3 の前提になる。
API 方式はクラス方式の上にしか建てられない（仕様 §2.0）ため、機能を作る前に埋める。
**残りは L-3（次回リリース）と L-4（H-13 の採否待ち）の 2 件。**
L-1 は H-3 を、L-2 と L-5 は H-4 を解決した。

**G 群は C-1 / C-2 / D-2 を置き換える。** 既存スクリプトを「修正して残す」のではなく
「削除して作り直す」方針に変わったため。

---

## L. クラス方式の欠落

**API 方式はクラス方式の上にしか建てられない（仕様 §2.0）。** ここに挙げたものは
「XML には書けるはずなのに、書くためのモデル・メソッドが無い」箇所。残りの機能追加が
この上に乗るため、**該当する機能を作る前にここを埋める**。

2026-09-07 に実装を走査して洗い出した。判定は「その XML を書く公開メソッドが 1 つも無い」こと。

| ID | 欠けているもの | 今の状態 | これが要る機能 |
|---|---|---|---|
| ~~L-1~~ | ~~`TwbFolder.update()`~~ | **完了 2026-09-07** | H-3 |
| ~~L-2~~ | ~~階層（`drill-paths`）のモデル~~ | **完了 2026-09-07**。`TwbDrillPath` | H-4 |
| L-3 | ナビゲーションアクション | 読み取りは種別を返す（`dashboard_action.py:54`）が、`create_action()` は `filter` / `url` の 2 種のみ | I-3 |
| L-4 | `TwbPane.delete()` | ペインを消せない | H-13（未判定） |
| L-6 | ダッシュボード読み取りの 4 項目 | 旧 `list_dashboard_*()` にしかない。**新 API に手段が無い** | E-2 の残り |
| ~~L-5~~ | ~~グループのモデル~~ | **完了 2026-09-07**。`create_group()` | H-4 |

**この 5 件はいずれも「読めるが書けない」か「読み書きどちらも無い」。**
フィルタの「適用」ボタン（J-5）と同じ形の欠落で、あのときは `show-apply` が
読み取り専用だった。同じ手順で 3 件を埋めた（L-1 / L-2 / L-5）。

1. `twb-xml-probe` で Tableau が実際に書く XML を実測する
2. クラス方式に書き込みを足す（`create_*` / `update()` / `delete()`）
3. その上で API 方式（`draw_*` / `build_report()` / `apply_config()`）から使えるようにする

### L-1 【完了】`TwbFolder` の名前を変えられない

`TwbFolder` の公開メソッドは `delete()` と `get_fields()` だけ。他の接続型モデルは
すべて `update()` を持つ（仕様 §3.3）。フォルダだけ自分の値を変えられない。

XML は `<folder name="...">` で、フォルダ名がそのまま識別子を兼ねる。**改名すると
`<folder-item>` の参照ではなく `<folder>` 自体の `@name` が変わる**ため、
同名衝突の検証が要る。`TwbField.update(name=)` と同じ形にする。

**完了（2026-09-07）。** `update(name=)` を足した。同名があれば `ValueError`。
`<folder-item>` はフィールドと階層を指しているだけなので、改名の追随は要らなかった。
H-3（フォルダ名を変更できない）も本課題で解決した。

### L-2 【完了】階層（ドリルパス）を扱えない

`drill-paths` は要素順の定義（`connected_worksheet.py:151` / `folder.py:44` /
`validator.py:38`）に名前が出るだけで、**読み取りモデルすら無い**。

**XML の形は実測済み（2026-09-07、`workbook/hierarchy_group_sample.twb`）。**

```xml
<drill-paths>
  <drill-path name="カテゴリ">
    <field>[Category]</field>
    <field>[Sub-Category]</field>
  </drill-path>
</drill-paths>
```

| 分かったこと | 内容 |
|---|---|
| 置き場所 | `datasource` 直下。`column-instance` の後、`folders-common` の前 |
| `name` | **表示名そのまま**（角括弧なし）。内部 ID ではない |
| `<field>` | 属性なし。テキストに**内部 ID を角括弧付き**で、ドリルの階層順に並べる |
| フォルダとの関係 | `<folder-item name="カテゴリ" type="drillpath">` で入る。**階層に入ったフィールドは個別の folder-item を持たなくなる** |
| `<column>` 側 | **何も増えない。** 階層メンバーであることを示す属性は付かない |
| ワークシート側 | **何も増えない。** 階層は datasource 直下に完結する |

**読み込み側の不具合を先に直した（2026-09-07）。**
`validator.py` が drillpath の folder-item を列名と照合して `folder_item_missing` の
誤警告を出していた（`save(validate=True)` に影響）。`references.py` も
folder-item を `type` で区別していなかった。

**完了（2026-09-07）。** `TwbDrillPath` を新設した（`twbpatch/drill_path.py`）。

- `datasource.get_drill_paths()` / `create_drill_path(name=, fields=, folder=)`
- `TwbDrillPath.update(name=, fields=)` / `delete()` / `get_fields()` / `field_ids`
- `fields` の順がドリルの階層順。2 つ以上が要る
- `folder=` を渡すと `type="drillpath"` で入れ、**階層に入れたフィールドの
  `folder-item` は取り除く**（Tableau がそう書くため）
- 改名すると `folder-item` の名前も追随する。`delete()` は階層だけを消し、
  フィールドは残す

> **残り**: H-4（階層を作れない）は本課題で解決した。実施時に統合する。

### L-3 【中】ナビゲーションアクションを作れない

**次回リリースで対応する（2026-09-07 決定）。** 今回のリリースには入れない。

ナビゲーションアクション = Tableau の「シートに移動」。ダッシュボード上の要素を
クリックすると**別のシートやダッシュボードへ画面が切り替わる**。フィルタアクションが
同じ画面の中で他のシートを絞るのに対し、こちらは画面そのものを移動する。

`create_action()` の `kind` は `filter` と `url` の 2 種（`action_writer.py:24`）。
読み取り側は `navigation` を返せる（`dashboard_action.py:54`）ので、**読めるが書けない**。

**先送りにした理由**: XML の形が未確認で、実物のワークブックが要る。設定画面も
ナビゲーションを出していないため、今のリリース範囲では使い道が無い。

> **次回リリースでやること**
>
> 1. ナビゲーションアクションを含む `.twb` をもらう（アクションのときと同じ手順）。
>    ダッシュボード 2 枚と、片方から片方へ飛ぶアクション 1 つがあれば足りる
> 2. `twb-xml-probe` で `<command command="tsc:...">` の値と `<param>` を調べる
> 3. `ACTION_KINDS` に `navigation` を足す。フィルタ・URL と同じ作りにできるはず
> 4. 設定画面のアクション設定に「シートに移動」を足す（今は種類が 2 つ）
> 5. I-3（ヘッダーメニュー）を同時に進める。**リンクにこのアクションが要るため**

### L-4 【低】ペインを削除できない

`TwbPane` は `add_field()` / `update()` / `set_*()` を持つが `delete()` が無い。
他の接続型モデルはすべて `delete()` を持つ（仕様 §5.3）。

二重軸を解除する、余分なペインを畳む、といった操作ができない。

> **次のアクション**: H-13 の採否を先に決める。採用するなら分解不要。
> 参照中の配置がある場合の `ResourceInUseError` の扱いを決める。

### L-5 【完了】グループを作れない

**セットとビンは対象外にした（2026-09-07 決定）。** グループだけを扱う。

**`<group>` 要素ではなかった。** Tableau のグループは `<column>` +
`<calculation class="categorical-bin">` で書かれる（実測、
`workbook/hierarchy_group_sample.twb`）。

```xml
<column datatype="string" name="[カテゴリ (グループ)]" role="dimension" type="nominal">
  <calculation class="categorical-bin" column="[Category]" new-bin="true">
    <bin default-name="true" value="&quot;Furniture と Office Supplies&quot;">
      <value>"Furniture"</value>
      <value>"Office Supplies"</value>
    </bin>
  </calculation>
</column>
```

階層からもこの内部 ID で参照されていた（`<field>[カテゴリ (グループ)]</field>`）。

| 分かったこと | 内容 |
|---|---|
| 置き場所 | 普通の `<column>` と同列。データソース直下 |
| `name` | `[元フィールドの表示名 (グループ)]`。**日本語の表示名がそのまま内部 ID になる**。`caption` 属性は無い |
| `calculation/@column` | 元フィールドの内部 ID。`@new-bin="true"` |
| `<bin>` | **まとめた 1 グループにつき 1 件。** まとめなかった値は書かれない（Tableau が暗黙に単独扱い） |
| 値の書式 | メンバーもグループ名も**ダブルクォート込みの文字列**（`"Furniture"`） |
| `default-name="true"` | グループ名を自動生成に任せた印 |

`groupfilter` はグループ機能とは無関係（通常のフィルタの子要素）。

**完了（2026-09-07）。** `twbpatch/group.py` と
`datasource.create_group(field=, groups=, name=, folder=)` を作った。

- `groups` は **グループ名 → まとめる値** の辞書。`<bin>` が 1 グループにつき 1 件出る
- `name` 既定は `<元フィールド名> (グループ)`。**caption は付けず内部 ID にする**
  Tableau の書き方に合わせた（仕様 §3.2 に例外として明記）
- 元フィールドは**文字列型のみ**。他の型は実測が無いので `UnsupportedFeatureError`
- グループ名もメンバーも `"..."` で囲んで書くため、値に `"` を含むと弾く
- `default-name="true"` は Tableau に名前を任せた印なので付けない
- 検証を直した。`categorical-bin` の `<calculation>` に `formula` が無いのは正しい
  形なので `formula_empty` を出さない。caption が無いのも同様

> **残り**: 更新と削除は未対応。削除は `field.delete()`（普通の `<column>` なので通る）。
> メンバーの入れ替えは作り直しになる。要望が出るまで足さない。

### L-6 【中】ダッシュボード読み取りの穴 4 件

**E-2 で旧 API を消したとき、これだけ消せなかった。** 新 API に同じ情報を取る手段が
無く、消すと読み取り能力が減るため。**穴を埋めてから旧メソッドを消す。**

| 残っている旧メソッド | 新 API に無いもの |
|---|---|
| `list_dashboard_zones()` | デバイスレイアウト（`include_device_layouts=True`）、raw 座標（`x_raw` など）、任意サイズでの px 換算（`width_px=` / `height_px=`）、`parent_id` / `depth` / `layout` / `sizing_mode` / `is_fixed` / `is_scaled` |
| `list_dashboard_actions()` | `excluded_source_worksheets` / `excluded_target_worksheets` / `details` / `source_dashboard` |
| `list_dashboard_fields()` | `max_filter_value_chars=`（長いフィルタ値の丸め） |
| `list_worksheet_fields()` | フィールドの `values` / `mark_type` / `category` / `type` / `attrs` |

**いちばん重いのはデバイスレイアウト。** `get_zones()` は既定レイアウトしか返さず、
`devicelayouts` を読むモデルが無い（`connected_dashboard.py:234` は挿入位置の計算に
使っているだけ）。仕様 §6.13 は「デバイスレイアウトを暗黙に変更しない」と書いているが、
**読む手段は用意していない。**

除外リストは Tableau の書き方そのものなので、読めないと「どのシートが対象か」を
生の XML から判断することになる（`create_action()` は書ける）。

> **次のアクション**: **個別タスクに分解する。** 4 項目は持ち主が違う。
>
> 1. `TwbDashboardZone` に raw 座標と `parent_id` / `depth` を足す（既存の投影に値はある）
> 2. デバイスレイアウトのモデルを新設する。`dashboard.get_device_layouts()` か
>    `get_zones(layout=...)` かを先に決める
> 3. `TwbDashboardAction` に `excluded_*` を足す（`dashboard_action.py:185` に値はある）
> 4. `values` の丸めは表示の都合なので、モデルに持たせず呼び出し側で切る案もある

---

## A. 公開 API の整合

### A-9 【完了】自分の値を変える `set_*` が `update()` の外にある

`worksheet.update(name=...)` と `worksheet.set_title(...)` のように、同じ
「自分の値を変える」操作で書き方が 2 通りあった。A-6 は `update_*()` だけを
対象にしたため、`set_*` 形式が残っていた。

**決定（2026-09-06・完了）**: `update()` へ統合する。旧名は残さない（A-6 と同じ理由）。

| 旧名 | 新名 |
|---|---|
| `TwbWorksheet.set_title(title)` | `update(title=...)` |
| `TwbPane.set_mark_color(color)` | `update(mark_color=...)` |
| `TwbPane.set_mark_size(size)` | `update(mark_size=...)` |
| `TwbPane.set_mark_opacity(opacity)` | `update(mark_opacity=...)` |
| `TwbPane.set_mark_sizing(scaling=)` | `update(mark_scaling=...)` |
| `TwbPane.set_label_style(show=, cull=)` | `update(label_style={...})` |

`label_style` はキー集合が固定なので `LabelStyle` を `TypedDict` で定義した（§3.3）。

**統合しなかったもの**: `set_customized_label()` / `set_axis_visibility()` /
`set_categorical_colors()` / `set_continuous_colors()` は**他モデルを引数に取る**ため、
§3.3 で動詞名を維持する側に当たる。

### A-8 【完了】フィールド指定の書き味が揃っていない

API 方式（`draw_*`）はフィールドを名前・タプル・オブジェクトの 3 通りで受けるが、
クラス方式（`worksheet.add_field()` など）は `TwbField` オブジェクトしか受け付けない。

```python
workbook.draw_bar(name="棒", item=("売上データ", "カテゴリ"), metric=("売上データ", "売上"))

field = datasource.get_fields(name="カテゴリ")[0]   # クラス方式は 2 行必要
worksheet.add_field(field, shelf="rows")
```

**A-7 と同じ構図**。解決処理が 1 箇所に無く、`draw.py` の `_resolve_fields()` だけが
規則を持っている。対象は `TwbField` を受け取る 7 メソッド（実測）。

`TwbWorksheetField`（シェルフ配置）を受け取る 6 メソッドは、フィールドそのものではなく
配置を指すため対象外とする。

**A-7 より大きい**。フィールドはデータソースが複数あると名前だけで決まらないため、
素の文字列をどう扱うかの決定が先に要る。

**決定と結果（2026-09-06・完了）**: 仕様 §5.4a に追記した。

- 引数は 1 つで 3 通りの型を受ける。`field=` と `field_name=` に分けない
- 引数はキーワード専用。位置引数を許さない（破壊的変更）
- 素の文字列は、そのワークシートが依存しているデータソースから探す。
  依存が無ければワークブックのデータソースが 1 つのときだけ許し、
  複数なら `AmbiguousCaptionError`
- 解決処理は `twbpatch/field_input.py` へ集約。`draw.py` の `_resolve_fields()` も
  ここを通す薄いラッパーにした

対象は `worksheet.add_field` / `add_filter` / `add_filter_slice` / `add_sort` /
`pane.add_field` と、`table_calculation_field` / `by`。
`tests/test_field_argument.py` で固定した。

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

### A-10 【完了】仕様書の中で書き方が食い違っている

`/spec-conformance` が見つけた、**仕様書どうしの矛盾**。実装の問題ではない。

| 箇所 | 内容 | どちらが正か |
|---|---|---|
| ~~§6.6 / §12 のサンプル~~ | ~~`worksheet.add_field(region, shelf="columns")` と第 1 引数を位置で渡している~~ | **解消（2026-09-07）。** §2.0 / §6.6 / §12 の 5 箇所を `field=` 付きに直した |
| ~~§3.2 と `TwbReferenceLine`~~ | ~~`axis_caption` / `value_caption` がモデル側に残り、JSON 出力名と食い違う~~ | **解消（2026-09-07）。** `axis_field_id` / `axis_name` / `value_field_id` / `value_name` へ改名した。`models.py` の旧 dataclass は §11 により改名しない |

`folder=` の食い違い（§6.3 と実装）は **2026-09-07 に解消済み**。
文字列と `TwbFolder` の両方を受ける形で、仕様書・実装・テストを揃えた。

**完了（2026-09-07）。** 2 件とも解消した。`*_caption` の改名は F-3 の判断材料が
出そろう前に済んだため、F-3 は A-10 の完了を待たずに書ける。

### A-5 【低】`TwbWorkbook` に重複メソッド

`unsupported_features()`（`workbook.py:166`）と `get_unsupported_features()`（`:169`）が同じもの。
新命名は後者。前者は旧 API として §9 に整理済みだが、削除時期を決める。

> **次のアクション**: 分解不要。E-2（旧 API の削除）に合流させる。

### A-6 【完了】公開 `update_*()` の廃止

2026-09-05 完了。作業計画（`docs/api_rename_plan.md`）は役目を終えたので削除した。
結果は `README.md` §8 に記録している。

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

### B-2 【完了】直接テストが無いメソッド 4 件

**2026-09-07 に再計測した。** 起票時は「公開メソッド 82 件中 17 件」だったが、
A-6 と A-9 で `update_*()` / `set_*()` を `update()` へ畳んだ結果、
統合先の `update()` がテスト済みだったため未テストの塊がそのまま消えた。

| 見方 | 起票時 | 2026-09-06 | 2026-09-07 |
|---|---|---|---|
| 接続型モデルの公開メソッド（プロパティを除く） | 82 件 | 69 件（名前は 40 種） | **73 件**（名前は 42 種） |
| テストが直接呼んでいない | 17 件 | 3 件 | **3 件** |
| テスト中に一度も実行されない | 未計測 | 1 件 | **1 件** |

メソッドが増えたのは `create_action()` / `add_reference_line()` などを足したため。
未検証の 4 件は 2026-09-06 から変わっていない。

**完了（2026-09-07）。** 4 件すべてに直接テストを書いた（38 件）。

| メソッド | テスト |
|---|---|
| `TwbWorksheet.set_axis_visibility` | `tests/test_axis_visibility.py`（9 件） |
| `TwbPane.set_categorical_colors` / `set_continuous_colors` | `tests/test_pane_colors.py`（15 件） |
| `TwbDashboard.update` | `tests/test_dashboard_update.py`（15 件） |

**書いてみて実バグが 3 件出た。** どれも間接実行では踏まない経路だった。

| 見つかったもの | 内容 |
|---|---|
| `TwbDashboard.update(visible=False)` | `<window>` を属性だけで作っていた。`<viewpoints>` `<active>` `<simple-id>` が無く、**保存すると検証エラーで落ちる**。中身はシートから作るので、シートが 1 枚も無いダッシュボードは隠せない旨の例外に変えた |
| `_sync_dashboard_window()` | シートを足すたび window を作り直すが `hidden` を引き継がず、**非表示にした後にシートを足すと表示へ戻っていた** |
| `TwbPane.set_categorical_colors` / `set_continuous_colors` | Pane の id はシート内の連番なので、**別シートの配置を渡しても「同じ Pane」と判定していた**。シートも見るようにした |

`TwbDashboard.update(name=)` は、表示名が変わらないときに `caption` を書き足して
`is_dirty` を立てていた。同じ値なら書かない形へ揃えた（L-1 と同じ扱い）。

**計測方法**（再現用）

- 公開メソッド: `connected*.py` を AST で走査し、`_` 始まりと `@property` を除く
- 直接呼び出し: `tests/*.py` の本文に `.<メソッド名>(` があるか
  （同名メソッドを持つクラスが複数ある場合、1 つでも呼ばれていれば「呼ばれた」と数える。
  クラス単位の精査は本課題の実施時に行う）
- 実行の有無: `sys.settrace` の `call` イベントを拾いながら `pytest` を通す

> **次のアクション**: **分解不要。** 4 件と規模が小さくなったので、このまま実施してよい。
> 優先は `TwbDashboard.update`（一度も実行されていない）。

### B-3 【完了】仕様 §13 の 3 項目が静的検査で判定できない

`/spec-conformance` が `要目視` と判定するもの（2026-09-07 時点で 3 件）。
**`docs/migration_status.md` は毎回全文を作り直すので、検証の中身はここに置く。**

| 条件 | 何が確認できないか | 足すべきテスト |
|---|---|---|
| #20 既存 Dashboard 編集の局所性 | `copy.deepcopy` + `_replace_if_changed()` の部分置換だが、変更が対象コンテナ配下に限られる保証が無い | 浮動 Zone・デバイスレイアウト・SDK が解釈しない属性を持つ Dashboard を `tmp_path` に組み、`container.add_worksheet()` の前後で**対象外要素の XML が完全一致**することを確認する |
| #21 未対応属性・対象外 Zone・デバイスレイアウトの保持 | 保持を保証する検査もテストも無い | 同上。仕様 §6.13 が根拠 |
| #41 新旧 API の XML 出力が同等 | 突き合わせる比較テストが無い | `rename_field()` / `update_formula()` / `move_field_to_folder()` / `create_calculated_field()` の 4 つを旧 API と新 API で別々の Workbook へ適用し、`ET.tostring()` の一致を確認する |

**完了（2026-09-07）。** 3 件ともテストにした。

| 条件 | テスト |
|---|---|
| #20 / #21 | `tests/test_dashboard_edit_locality.py`（7 件） |
| #41 | `tests/test_old_new_api_equivalence.py`（8 件） |

**#20 / #21 は木全体で判定する形にした。** 既存の
`test_existing_dashboard_edits_only_target_container_subtree` は要素を名指しで
見ていて、「見ていない場所が変わっていない」ことは言えなかった。編集後の
`<dashboard>` の対象ゾーンだけを編集前へ差し戻し、それで全体が一致するなら
**変更は対象ゾーンの中だけ**だったと言える。編集が起きていないと素通りするので、
差し戻す前に「編集前と違う」ことも確かめている。

ダッシュボードの外で変わってよいのは `<windows>` だけ（載せたシートの
viewpoint が増える）。それも別テストで固定した。

**#41 は同じワークブックを 2 つ開いて突き合わせる。** 旧 API と新 API を
それぞれに掛け、`ET.tostring()` の一致を見る。改名・caption 解除・式の更新・
フォルダ移動・計算フィールドの作成（フォルダ指定あり / なし）と、
それらを続けて掛けた場合を対象にした。

### B-4 【完了】テスト実行の前提を恒久化する

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

### C-1 【完了】サンプルスクリプト 20 本が実 Tableau リポジトリを上書きする

ルート直下の `*_sample.py` / `*_build.py` は全 20 本が
`C:\Users\...\マイ Tableau リポジトリ\ワークブック\` を読み書きし、
全 20 本が `save(..., overwrite=True)` を呼ぶ。git 管理外のため復元できない。

**現状**: PreToolUse フックが Claude による実行を阻止している。
**根本対応**: `SOURCE` / `OUTPUT` を `outputs/` 配下へ変更する。フックは「うっかり」を
止めるだけで、スクリプト自体を安全にはしない。

> **次のアクション**: **G-2 / G-3 へ移管。** 修正して残すのではなく、削除して作り直す方針。
> この項目は「なぜ削除するのか」の根拠として残す。

### C-2 【完了】`outputs/` が `.gitignore` されていない

生成物 5 ファイル・約 1.3MB（200〜390KB の `.twb`）が未追跡のまま置かれている。
`git add -A` 一発で巨大な XML がリポジトリへ入る。

**根拠**: `git check-ignore outputs/` → 該当なし。

> **次のアクション**: **G-4 へ移管。**

---

## D. リポジトリ衛生

### D-1 【完了】未コミットの変更が `main` に滞留している

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

**決定の変更（2026-09-06）: 作業ブランチを `develop` の 1 本にする。**

`chore/phase0-cleanup` を `develop` へ改名し、`feature/h5-totals` は取り込んで削除した。
複数セッションが並行して作業してもブランチは分けない。**分けても結局同じ場所に集まる
だけで、合流の手間が増えたため。** `main` は origin と同期した状態で置いておく。
push しないのは従来どおり（公開のタイミングは D-4）。

### D-2 【完了】ルート直下に未追跡ファイルが 46 件

`.py` 41 件、`.md` 5 件。サンプル・検証スクリプト・差分メモが混在している。

- 残すもの → `examples/` などへ移動して追跡する
- 使い捨て → 削除するか `.gitignore` に入れる

> **次のアクション**: **G-1 / G-2 へ移管。**

### D-3 【完了】`.pytest_cache` が権限エラーを出し続けている

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

### D-4 【中】改修完了後にリポジトリを作り直す

**着手条件: 今回の一連の改修（Phase 1〜3）が終わってから。** 途中でやらない。

**なぜ作り直すか**

| 理由 | 内容 |
|---|---|
| メールアドレスの露出 | `origin/main` の公開済み 3 コミット（`49996d4` / `82a549a` / `8861511`）の author に個人のメールアドレスが入っている。**push 済みなので GitHub 上で公開状態** |
| 履歴の性質 | 初期の履歴は、実験と手戻りがそのまま残っている。公開する形として整っていない |

**すでに対処済みのこと（2026-09-06）**

- リポジトリ単位で `git config user.email` を
  `59932056+tomohiro-ono-works@users.noreply.github.com` に変更した。**以降のコミットは露出しない**
- 未 push の 25 コミットは `git filter-branch` で author / committer を書き換え済み。
  内容の差分はゼロであることを確認した（`backup/pre-email-rewrite` との比較が空）

**残っている問題**

公開済み 3 コミットは、履歴を書き換えても**完全には消えない**。
GitHub は force-push 後も古いコミットを一定期間参照でき、API や外部のミラーにも残りうる。
確実に消すには、**新しいリポジトリを作って履歴ごと入れ替える**しかない。

**決めること**

| # | 論点 |
|---|---|
| 1 | 履歴を引き継ぐか、1 コミットから始めるか |
| 2 | 今のリポジトリを削除するか、private にして残すか |
| 3 | 公開のタイミング（README 全面改訂 = F-1 の後か） |

> **次のアクション**: 改修が終わってから着手する。それまでは起票だけ。
> 新しいコミットは noreply になっているので、**急ぐ必要は無い**。

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

### E-2 【完了】旧 API の削除

**保留解除（2026-09-07）。** A-1 / A-2 / A-6 がすべて完了し、条件を満たした。
まだ push しておらず（未 push 77 コミット）**外部利用者がいない**ため、
破壊的変更のコストはほぼゼロ。

#### 対象（2026-09-07 実測）

| 層 | 中身 | 件数 | 消せるか |
|---|---|---|---|
| A | `TwbWorkbook` の旧メソッド | 27 | 消せる |
| B | A に付いている `by=` 引数 | A に同梱 | A と同時 |
| C | `models.py` の dataclass | 20 | **消せない。** 公開停止のみ |

A の 27 件は `list_*` 14 / `get_<単数形>` 4 / `update_*` 3 / その他 6。
これとは別に `set_filter` と `create_calculated_field` が新旧同名で並存する。

```
list_dashboards list_dashboard_fields list_dashboard_zones list_dashboard_actions
list_dashboard_filter_controls list_worksheets list_worksheet_fields list_reference_lines
list_filters list_datasources list_relations list_relationships list_parameters list_columns
get_dashboard get_worksheet get_datasource get_column
update_source update_column update_formula
rename_field reset_field_caption move_field_to_folder remove_field_from_folder
move_column_to_folder unsupported_features
```

#### 消すと起きること

| # | 内容 | 状態 |
|---|---|---|
| 1 | `TwbWorkbook.set_filter()` は旧 API 扱いだが**新 API より仕事が多い**（データソースフィルター＋使用シート全部へのスライス追加）。`config_apply.py` と `examples/build_dashboard.py` が使っている | **解決済み。** `add_filter()` を新設し、両方の呼び出し元を移した |
| 2 | `create_calculated_field` に挙動差が 2 つ。旧は `folder=` が無ければ**作る**（`create_if_missing=True`）／新は `NotFoundError`。旧 `strict=False` ／新 `strict=True` | **解決済み。** 既定はエラーのまま、`create_folder_if_missing=True` で作れるようにした（`folder=` を取る 6 メソッド共通）。`strict` は新の `True` のまま |
| 3 | `models.py` の 20 クラスは投影層 14 モジュールが返す型。**削除不可** | **解決済み。** `__all__` が公開する `models.py` のクラスは 7 個だけで、うち 6 個は新 API の戻り値なので残す。`TwbColumn` は**旧メソッドを消すと公開 API から到達不能**になるため、削除と同時に `__all__` から外す |
| 4 | テスト 8 ファイル / 22 関数が旧 API を直接呼ぶ。`test_old_new_api_equivalence.py`（B-3 #41）は**存在意義ごと消える** | 書き直しが要る |
| 5 | 内部の自己参照 2 箇所（`workbook.py:641` / `:853`）| まとめて消せば解決 |

`export_json()` / `export_html()` / `serialize_workbook()` は新 API だけで組まれていて
影響しない（実測）。

#### 実施結果（2026-09-07）

**25 件を削除した。** 新 API に完全な代替があるものだけを対象にした。

```
list_dashboards list_dashboard_filter_controls list_worksheets list_reference_lines
list_filters list_datasources list_relations list_relationships list_parameters
list_columns get_dashboard get_worksheet get_datasource get_column
update_source update_column update_formula rename_field reset_field_caption
move_field_to_folder remove_field_from_folder move_column_to_folder
unsupported_features set_filter create_calculated_field（位置引数版）
```

`TwbWorkbook` の公開メソッドは 54 → 30 件、`workbook.py` は 932 → 683 行になった。
`by="auto"` も一緒に消えた。`TwbColumn` は到達不能になったので `__all__` から外した
（`models.py` には投影層の戻り値として残る）。

**残した 4 件は L-6 へ。** `list_dashboard_zones()` / `list_dashboard_actions()` /
`list_dashboard_fields()` / `list_worksheet_fields()` は、新 API に同じ情報を取る
手段が無い。消すと読み取り能力が減るため、穴を埋めてから消す。

**テストの整理**

| 対象 | 扱い |
|---|---|
| `test_old_new_api_equivalence.py` | 削除。旧 API が消えて役目が終わった（B-3 #41） |
| 「旧 `list_*()` は旧 dataclass を返す」を確かめる 3 件 | 削除。§11 の併存規約そのものが終わった |
| `test_smoke.py` | 新 API へ全面書き直し |
| `test_dashboard_worksheet.py` / `test_forward_metadata.py` / `test_dashboard_zone_action.py` | 新 API へ書き直し。残した 4 件を使う箇所はそのまま |
| `test_public_namespace.py` / `test_connected_final_api.py` | 「消えたこと」を確かめる形へ反転 |

書き直しで分かった差も記録しておく。

- 新 `referenced_fields` は内部 ID を返す（旧 `referenced_columns` は表示名）
- 新 `TwbFilterControl.width` はダッシュボードのサイズから px 換算するので、
  `<size>` の無いワークブックでは `None`（旧は生の属性値）
- ワークシートは `caption` を表示名に使わない。`get_worksheets(name=)` ではなく
  `id=` で引く（仕様 §3.2）

---

## F. ドキュメント

### F-1 【完了】README のドリフト

新 API を反映していない。

| README の記述 | 出現回数 |
|---|---|
| `caption` | 22 |
| `by=`（検索方法） | 14 |
| `TwbColumn` | 4 |
| `list_datasources` / `list_worksheets` | 3 |

いずれも新 API には存在しない、または `name` / `id=` へ置き換わっている。
A-6 の改名対象は README に 1 件も出てこないため、A-6 起因のドリフトはない。**全面改訂は未着手。**

**ドリフトは一方向。** README に書かれていて実装に存在しないシンボル・引数は 0 件で、
旧 dataclass の属性表は実装と完全に一致する。問題は**新 API がまるごと未記載**なこと。

`__all__` のうち README に一度も現れないもの: `write_dicts_csv` / `TwbField` / `TwbPane` /
`TwbDashboardContainer` / `AmbiguousFormulaReferenceError` / `DetachedModelError` /
`ResourceInUseError` / `ResourceReference`。

**完了（2026-09-07）。`docs/api_reference.md` を README へ統合し、リファレンスを
1 か所にした。**

節ごとに突き合わせる案は採らなかった。README と `api_reference.md` の両方を
網羅型にすると**同じ表を 2 か所で持つ**ことになり、次のドリフトを自分で作るため。

| 変えたこと | 内容 |
|---|---|
| 構成 | 前半が使い方、後半（§0〜§9）が全シンボルのリファレンス。840 行 |
| 旧 API の表 | 削除。§9 に名前の一覧だけ残し、対応表は仕様 §12 を引く |
| 使い方の例 | `list_datasources()` / `by=` の旧 API から新 API へ書き直した |
| `docs/api_reference.md` | **削除。** 参照していた 5 文書のリンクを README へ向け直した |

`__all__` の 36 シンボルが README に全部載っていることを実測で確認した。
`/spec-conformance` は `__all__` と README を突き合わせるので、この統合で
**リファレンスの網羅性がそのまま自動検査の対象になる**。

### F-3 【完了】`docs/api_reference.md` に投影モデル 5 クラスの節が無い

`__all__` の 35 シンボルのうち、次の 5 クラスだけプロパティの節が無い。
§3 は `TwbDashboardAction` で終わっている。

| クラス | 未記載のプロパティ |
|---|---|
| `TwbRelation` | `attrs` / `clauses` / `connection` / `join` / `logical_table` / `logical_table_id` / `get_children()` |
| `TwbRelationship` | `attrs` / `expression` / `left_object` / `left_object_id` / `right_object` / `right_object_id` |
| `TwbReferenceLine` | `attrs` / `axis_field_id` / `axis_name` / `axis_role` / `tooltip_type` / `value_field_id` / `value_name` / `value_role` |
| `TwbWorksheetFilter` | `attrs` / `apply_scope` / `apply_scope_label` / `enumeration` / `filter_class` / `filter_group` / `functions` / `selection_type` / `value_scope` / `value_scope_label` |
| `TwbFilterControl` | `apply_scope` / `apply_scope_label` / `enumeration` / `filter_class` / `selection_type` / `show_caption` / `value_scope` / `value_scope_label` |

**完了（2026-09-07）。** §3.12〜3.16 として書いた。**`__all__` の 36 シンボルは
これで全部が `api_reference.md` に載った**（実測）。

- `TwbFilterControl` は `TwbDashboardZone` を継承するので、ゾーン側の変数と
  `update()` / `delete()` は §3.10 を参照し、フィルタとして足された分だけ書いた
- 値の候補は**実装と実測した .twb から採った**。`add_reference_line()` が受ける
  `formula` は `average` / `median` / `minimum` / `maximum` の 4 つ、`scope` の既定は
  `per-table`。`filter_class` と `functions` は実物にあった値を例示に留めた

### F-2 【低】`docs/` の文書体系が不明瞭

7 文書あるが、役割と鮮度の関係が書かれていない。

| ファイル | 役割 | 最終更新 |
|---|---|---|
| `model_api_spec.md` | 正典 | 8/23 |
| `requirements.md` | 初期要件 | 7/9 |
| `metadata_api_scope.md` | 個別改修の範囲 | 7/10 |
| ~~`api_reference.md`~~ | **F-1 で `README.md` へ統合し削除（2026-09-07）** | — |
| `migration_status.md` | 自動生成の進捗（`/spec-conformance` が全文を作り直す） | 9/7 |
| `backlog.md` | 課題一覧（本ファイル） | 9/7 |
| `html_screen_spec.md` | 設定画面の仕様 | 9/7 |
| `roundtrip.md` | 設定画面を使った作り方（2 周方式） | 9/7 |

`requirements.md` と `metadata_api_scope.md` は正典に取り込み済みか、まだ有効かが不明。

> **次のアクション**: 分解不要。`docs/README.md` で索引を作り、役割終了分をアーカイブする。
> `docs/tasks/` は作成済み（`J_html_config.md` / `G2_sample_inventory.md`）。

---

## G. 整理と再パッケージ

C-1 / C-2 / D-2 を置き換える。既存のサンプルを直して残すのではなく、**削除して作り直す**。

### G-1 【完了】未使用ファイルの削除（`.twb` / `.py` / `.md`）

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

### G-2 【完了】サンプルスクリプトの削除

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

### G-3 【完了】展開用サンプルの作成

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

### G-4 【完了】`.gitignore` の整理

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

### H-1 【完了】ダッシュボードアクションが読み取り専用

`TwbDashboardAction` はプロパティ 9 個だけで、`update()` も `delete()` も無い。
`create_*` も存在しない。**アクションの取得はできるが、作成・変更・削除ができない。**

**根拠**: 接続型モデル 11 クラス中、`update()` / `delete()` の両方を欠くのは
`TwbDashboardAction` のみ。`grep 'def create_dashboard_action'` → 0 件。

**完了（2026-09-07）。フィルタと URL の 2 種を実装した。**
ハイライトとパラメータは要望から外れるため作っていない。

XML の形は、Tableau が保存した `.twb`（`outputs/example_dashboard.twb`）から実測した。

| 分かったこと | 内容 |
|---|---|
| 置き場所 | **`/workbook/actions` 直下**。ダッシュボード配下ではない |
| 名前 | `[Action<連番>_<32 桁の 16 進大文字>]` |
| 対象シート | **「除外するシート」で書かれる。** フィルタは `<param name="exclude" value="名前,...">`、URL は `<exclude-sheet>` の並び |
| フィルタの式 | `<link expression>` が `tsl:<ダッシュボード名>?<フィールド>~s0=<<フィールド>~na>`（左辺は URL エンコード） |
| 選択解除時 | `<activation auto-clear="true">`。フィルタにしか付かない |
| 自動生成 | `<actions>` 直下に、使うデータソースと列の宣言が置かれる。SDK でも一緒に書く |
| ワークシート側 | **何も増えない。** 逆参照は無い |

- クラス方式: `dashboard.create_action(kind=...)` と `TwbDashboardAction.update()` / `delete()`
- 実装: `twbpatch/action_writer.py`
- 読み取り側の不具合も直した。ターゲットが常に空になる（`<target>` 要素を探していたが
  実際は `<command>` の param）のと、URL アクションの種別が `None` になる（`<command>` が無い）

**未実測**: 実行方法は `on-select` しか実物を見ていない。`on-hover` / `on-menu` は
Tableau で一般に使われる値だが確認が要る。「すべてのフィールド」のフィルタアクションも
未実測だが、**利用者が使わない想定のため対応しない**（2026-09-07 決定）。

画面側も直した（2026-09-07）。アクション設定の種類をフィルターと URL の 2 つにし、
フィルターに「絞り込むフィールド」を足した。候補はエリアのデータソースのディメンション。

### H-2 【中】`create_datasource()` がない

`TwbWorkbook` に `create_worksheet` / `create_dashboard` / `create_parameter` はあるが、
**データソースを新規作成する API が無い**。既存ワークブックのデータソースを流用するしかない。

**根拠**: `grep 'def create_datasource'` → 0 件。

> **次のアクション**: 個別タスクに分解する。接続種別（BigQuery / Excel / CSV）ごとに
> 必要な XML が違う。`update(source=...)` の既存実装が土台になる。

### H-3 【低】一部モデルに CRUD の欠け

| モデル | 欠けているもの | 状態 |
|---|---|---|
| `TwbFolder` | `update()` | **完了 2026-09-07**（L-1）。`update(name=)` を追加 |
| `TwbPane` | `delete()` | 未。**L-4 で扱う**（H-13 の採否待ち） |

**根拠**: 接続型モデルの CRUD 有無を AST で走査した結果。

> **次のアクション**: 分解不要。残りは `TwbPane.delete()` だけ。
> H-13（ペインを削除できない）の採否が決まってから着手する。

### H-4 【完了】グループ・セット・ビン・階層が未対応

Tableau の主要なフィールド概念のうち、実装に登場しなかったもの。

| 概念 | 状態 |
|---|---|
| 階層（ドリルパス） | **完了 2026-09-07**（L-2）。`TwbDrillPath` |
| グループ | **完了 2026-09-07**（L-5）。`create_group()` |
| セット / ビン | **対象外（2026-09-07 決定）** |

計算フィールドとフォルダは前から扱えた。

> **次のアクション**: 個別タスクに分解する。概念ごとに独立。まず「取得だけ」を通してから
> 編集へ進むほうが安全。

### H-5 【完了】合計・小計が未対応

`total` / `subtotal` の出現は実装内 **0 箇所**（`validator.py` の要素順定義を除く）だった。

**根拠**: `docs/requirements.md:253` に「ソート、合計、小計は将来拡張とすること」と明記。
ソート（`add_sort()`）だけが実装済みで、合計・小計は未着手だった。

**決定（2026-09-06・完了）**: 総計と小計で置き場所を分ける。どちらも `TwbWorksheet`。

| | 公開形 | XML |
|---|---|---|
| 総計 | `update(grand_totals=...)` とプロパティ `grand_totals` | `<rows total onTop>` / `<cols total onLeft>` |
| 小計 | `set_subtotal_visibility(field=, visible=)` | `<table>/<subtotals>/<column>` |

リポジトリ内に総計・小計を含む実 XML が 1 件も無かったため、Tableau 公式スキーマ
（`twb_2026.2.0.xsd`）を一次情報にした。経緯と XML の形は `docs/tasks/H5_totals.md`。

合計の集計方法（`column-instance/@visual-totals`）は、XSD が値の語彙を絞っておらず
確定できないため範囲外とした。

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

**設定画面の前提ではない（2026-09-07 に確認）。** 画面のグラフ一覧は `draw_*` の実
シグネチャから自動生成しているので、実装にある種類しか画面に出ない。増やせば画面にも
自動で出る。一時期「ダッシュボード設定画面の着手条件」に挙げていたが誤りだった。

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

**次回リリースで対応する（2026-09-07 決定）。** 今回のリリースには入れない。

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

**先送りにした理由**: 規模が大きく、今回のリリースの締めくくり（F-1 README /
F-3 リファレンス）と並べられない。**ツリーの形をどこで定義するかが未決**でもある。
設定画面の YAML に節を足すのか、Python の API だけ先に出すのかで作りが変わる。

> **次回リリースでやること**
>
> 1. **ツリーの定義場所を決める。** 設定画面（YAML）か Python の API か。
>    画面に載せるなら `docs/html_screen_spec.md` の節を先に決める
> 2. 「入力の階層定義フォーマット」「ノード 1 個分のシート群」「ツリー配置ロジック」
>    の 3 つに分解する
> 3. ノードのシートは `draw_card` / `draw_bar` を流用する。配置は
>    `TwbDashboardContainer` の `direction` / `order` / `weight` で組む

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

### 範囲の見直し（2026-09-06）

起票時は「範囲 a（表示名とフォルダ割り当てのみ）」で始める前提だった。
その後、画面仕様として次の 4 つが要望として出た。

| # | 画面 | 内容 |
|---|---|---|
| 1 | 全体 | （内容未定） |
| 2 | データソース / リネーム・フォルダ | Excel のようなセル状の表。**コピペ可能** |
| 3 | データソース / 計算フィールド | Excel のようなセル状の表。**コピペ可能** |
| 4 | ダッシュボード | ヘッダー編集 + ボディ（縦段組 → 横配置 → エリア → グラフ／フィルター選択 → グラフパラメータ → アクション設定） |

2 と 3 は範囲 b、4 は範囲 c〜d に当たる。**着手できる状態が両者で違うため二段構えにした。**

| 段 | 画面 | 出力先の Python 側 | 着手 |
|---|---|---|---|
| 第 1 段 | データソース設定（2・3） | `apply_field_config()` が既にある | **今すぐ可** |
| 第 2 段 | ダッシュボード設定（4） | `build_report()`。**形が固まっていない** | 土台 3 件の後 |

画面が吐く設定ファイルの形は、それを受け取る Python 側の引数の形で決まる。
ダッシュボード側は受け手が 3 箇所とも未確定で、**先に画面を作ると設定ファイルの形が
後から変わり、画面ごと作り直しになる。**

### J-1 【完了】データソースの内容を HTML で出力する

読み取り専用。データソースとフィールド一覧（元の名前・表示名・型・役割・連続／不連続・
計算式・所属フォルダ・非表示）を一覧できる HTML を出す。

**これだけでも「調べるのが面倒」は半分解決する。** `export_json()` の結果を
HTML に整形するだけなので、実装は軽い。API 方式（仕様 §2.0）として
`TwbWorkbook.export_html(path)` を新設する。

**根拠**: `serialize_workbook()`（`twbpatch/serialization.py:110`）が
フィールドの名前・型・役割・計算式・フォルダ ID まで既に返している。

**完了（2026-09-06）**。`TwbWorkbook.export_html()` を新設した。
画面の仕様は `docs/html_screen_spec.md`。

### J-2 【完了】HTML 画面で設定し、設定ファイルを出力する

J-1 の HTML に編集機能を付ける。画面で設定した内容を YAML でダウンロードさせる。
**第 1 段の対象はデータソース設定（リネーム・フォルダ + 計算フィールド）。**

| 範囲 | 内容 | 扱い |
|---|---|---|
| a | フィールドの表示名・フォルダ割り当て | 第 1 段に含む |
| b | a + 計算フィールドの定義 | **第 1 段に含む**（J-3 が前提） |
| c | b + ワークシート構成 | 第 2 段（J-4） |
| d | c + ダッシュボードのレイアウト | 第 2 段（J-4） |

**外部ライブラリが使えないのがここの難所。** 依存は `lxml` と `PyYAML` のみで、
CDN もオフライン前提で使えない。**「Excel のようなセル状」の表は自前の JavaScript で書く。**
貼り付け時に TSV を複数セルへ分解する処理は、要望を満たすうえで最小構成でも必須。

**画面は完了（2026-09-06）**。範囲選択・TSV コピペ・undo / redo・行の追加削除まで自前で実装した。
出力は 1 ファイル（`twbpatch_config.yaml`）。

**受け手も完了（2026-09-07）**。`TwbWorkbook.apply_config()` が表示名・フォルダ・
計算フィールドを適用する。

### J-3 【完了】設定ファイル形式の拡張（受け手）

現在の形式は `データソース名 → フォルダ名 → {元のフィールド名: 表示名}` の入れ子辞書だけ。

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

**完了（2026-09-07）。** `TwbWorkbook.apply_config()` を API 方式で新設した。
実装は `twbpatch/config_apply.py`。

| 決めたこと | 結論 |
|---|---|
| D4 後方互換 | **保たない。別メソッドにした。** `apply_field_config()` は最上位がデータソース名、新形式は `design` / `datasources` / `dashboard`。形が違うので見分け処理を持たない |
| D6 受け手の数 | **1 本**（`apply_config()`）。節ごとに分けない |
| 同名の計算フィールド | **上書きする。** 2 周方式で同じ YAML を 2 度通すため、エラーで止めると往復が回らない |
| `role` と連続 / 不連続 | `dimension` は不連続、`measure` は連続。画面では指定しない |
| 受け手が無い節 | 名前を警告ログへ出して読み飛ばす。画面は常に全節を出すのでエラーにできない |

計算フィールドの上書きでデータ型を直せるように、`TwbField.update()` へ `datatype=` を
足した（計算フィールド以外は `UnsupportedFeatureError`）。

**残っている表現できないもの**: 表示順（記述順に依存）、非表示フラグ、書式。
どれも画面が出力していないので、必要になった時点で足す。

### J-4 【完了】HTML 画面でダッシュボードを設定する

**第 2 段。** 要望された画面構成は次のとおり。

```
ヘッダー
  ヘッダー編集
ボディ
  縦段組
    横配置
      エリア: グラフ選択 / フィルター選択
        グラフパラメータ選択
        アクション設定
```

**画面は完了（2026-09-06）。受け手は次の 3 件が揃うまで着手しない。**

画面を先に作ったのは、受け手が読む YAML の形が画面の出力で決まるため。
「出力する YAML の形は後から変わってよい」前提で作ってあり、Python 側で
依存しているものは無い。

| 未確定なもの | 課題 | 状態 | 画面のどこに効くか |
|---|---|---|---|
| `build_report()` の `struct` 形式 | K-1 | **完了 2026-09-07**。区分値 `kind` で制御する | 縦段組・横配置・エリア |
| ダッシュボードアクション | H-1 | **完了 2026-09-07**。フィルタと URL の 2 種 | アクション設定 |

グラフ種類の拡充（H-10）は前提ではない。画面のグラフ一覧は `draw_*` の実シグネチャから
自動生成しているので、実装にある種類しか画面に出ない。

ヘッダー編集だけは `build_report()` の `header_height` / `header_background_color` /
`header_font_color` が既にあるが、単独で切り出す価値が小さいので J-4 にまとめる。

画面でできること: ヘッダー編集、縦段組と横配置のドラッグ並べ替え、エリアごとの
グラフ / フィルター選択、`draw_*` の実シグネチャから自動生成したパラメータ入力、
アクション設定。既存ダッシュボードの読み込みはしない（新規作成専用）。

**受け手も完了（2026-09-07）。** `apply_config()` が `dashboard` セクションを読み、
`draw_*()` → `build_report()` → `create_action()` の順に組み立てる。
`@main_color` はデザインルールの色コードへ解決してから `draw_*()` へ渡す。

### J-5 【完了】デザインルールの設定をダッシュボードへ届ける

**当初は「ワークブック全体の書式 API」として起票していたが、範囲を切り直した
（2026-09-07）。** デザインルールの各項目が `.twb` のどこへ届くかを実測したところ、
ワークブック全体に書くものはフォントだけで、残りはダッシュボードを組むときの
引数だった。

| 項目 | 届け先 | 状態 |
|---|---|---|
| フォント | `set_default_font()` | 済（`apply_config()` から適用） |
| メインカラー / サブカラー①② / 文字色 | `draw_*` の色引数。画面では `@main_color` として `dashboard` の `params` に入る | クラス方式は揃っている。**流し込みはダッシュボード受け手（K-1 待ち）** |
| 余白 多め / 少なめ | `TwbDashboardZone.update(style={"padding": …})` と `build_report(content_style=…)` | クラス方式は揃っている。同上 |
| フィルターに「適用」ボタン | `zone[@type-v2='filter']` の `show-apply` 属性 | **完了（2026-09-07）** |

**穴はクラス方式に 1 箇所だけだった。** `show-apply` は読み取り専用
（`TwbFilterControl.show_apply`）で、書く手段が無かった。

- クラス方式: `container.add_filter(show_apply=…)` と `TwbDashboardZone.update(show_apply=…)`
- API 方式: `build_report(filter_apply_button=…)`

Tableau は付けるときだけ `show-apply="true"` を書き、付けないときは属性ごと書かない
（`workbook/RETAIL - POS` の .twb で実測）。`False` は属性を削除する。

> **残り**: 画面の `design.filter_apply_button` を実際に流し込むのは
> ダッシュボード受け手（J-4 の受け手、K-1 / H-10 / H-1 の後）。それまでは
> Python から直接指定する。

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

### K-1 【完了】コンテナ名の文字列で挙動が変わる

`struct` のキー（コンテナ名）に特定の日本語が含まれるかどうかで、動作が分岐していた。

| 判定 | 効果 |
|---|---|
| `"フィルタ" in container_name` | フィルタ用コンテナとして扱う。高さ既定 50、均等配分しない |
| `"スコア" in container_name` | 高さ既定 250 |
| 上記以外 | 高さ既定 300 |

**問題**

- コンテナ名は**画面に出る表示名**。それが制御フラグを兼ねていた
- 英語名（`"filter"`）では動かない
- 「売上フィルタ状況」のように、意図せず部分一致して挙動が変わる
- 表示名を変えたらレイアウトが変わる

**完了（2026-09-07）。区分値 `kind` で制御する形にした。省略はできない。**

```python
struct={
    "地域を選ぶ": {"kind": "filter",    "items": [("売上データ", "地域")]},
    "本体":     {"kind": "worksheet", "items": ["SheetA", "SheetB"]},
}
```

- 解釈: `_container_spec()`。`kind` は `worksheet` と `filter` の 2 つ
- **区分値は項目（エリア）ごとに持つ。** 1 つの段にグラフとフィルタを混ぜられる。
  設定画面がエリアごとに種別を選ばせているため、段ごとだと画面の並びを表現できなかった
- 高さ: 段の `height` → `container_sizes[名前]` → 既定 `_CONTAINER_HEIGHT = 300`。
  「フィルタ」の 50 と「スコア」の 250 は廃止
- 均等配分は「並べたワークシートが 2 つ以上あり、フィルタが無い」ときだけ

**中身から推測する案も、`kind` 省略時の既定を置く案も採らなかった。**
どちらも「なぜこの枠がフィルタ置き場になったか」が呼び出し側から読めない。
一度は「フィルタだけ `kind` 必須、ワークシートはリスト略記」で実装したが、
略記を許すとリスト内のタプルを見て誤りを検出することになり、中身を見る処理が
残ってしまうため、`kind` を必須にした。判定は `kind` の値 1 箇所だけになった。

### K-2 【中】ヘッダーの書式が固定

ヘッダーは必ず 1 つ付き、書式のほとんどが実装内に埋め込まれている（`:872` 付近）。

| 項目 | 現状 | 引数で変えられるか |
|---|---|---|
| 表示テキスト | 既定は `dashboard_name` | 可（`header_title=`、2026-09-07 に追加） |
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
| 段の高さ | 300（`_CONTAINER_HEIGHT`）。フィルタ行の 50 とスコア行の 250 は K-1 で廃止 |
| 本文の背景色 | `#f5f5f5`（`_DEFAULT_REPORT_CONTENT_STYLE`、`:27`） |
| ワークシートの背景色 | `#ffffff`（`_DEFAULT_REPORT_WORKSHEET_STYLE`） |

個々の段は `struct` の `height` か `container_sizes=` で変えられる（K-1 で整理した）。
**残る問題は既定値そのものを差し替えられないこと**と、色を引数で受けないこと。

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
合計・小計も生成後に `update(grand_totals=...)` / `set_subtotal_visibility()` で
設定できるようになった（H-5）が、`draw_*` の引数にはない。

> **次のアクション（保留解除 2026-09-06）**: H-5 が完了し、クラス方式が揃った。
> 仕様 §2.0 の「API 方式はクラス方式の上に建てる」に従い、`draw_*` の引数として
> 露出させるか判断する。

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
