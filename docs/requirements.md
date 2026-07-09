# tabsdk 要件メモ

## 目的

Tableau Workbook (`.twb` / `.twbx`) を Python SDK から参照・更新・作成できるようにする。
まずは既存 Workbook を安全に編集する更新 API を優先し、その後に定型ワークシート・ダッシュボード作成 API を拡張する。

## 前提

- 対象は Tableau Workbook XML の読み取り・編集。
- 既存 Workbook を壊さないことを優先する。
- caption は表示名、id は Tableau 内部IDとして扱う。
- 更新 API は原則として既存要素を対象にし、曖昧な指定はエラーにする。
- `.twbx` の保存時は既存パッケージ構造を維持する。

## 参照 API

### データソース

- データソース一覧を取得できること。
- `Parameters` はデータソース一覧から除外すること。
- データソースID、表示名、接続種別、フィールド一覧、フォルダ一覧を取得できること。

### パラメータ

- `Parameters` datasource は専用のパラメータ一覧として取得できること。
- パラメータID、表示名、データ型、現在値、表示値、許可値、domain type、hidden を取得できること。
- hidden な内部パラメータは既定では除外し、必要時のみ取得できること。

### フィールド

- フィールドID、表示名、role、datatype、計算フィールド判定を取得できること。
- 計算フィールドの場合、表示名に置換済みの formula を取得できること。
- SDK内部用に raw formula を保持できること。
- 計算式が参照しているフィールドを配列で取得できること。
- フィールドのフォルダ、書式設定を取得できること。

### ワークシート

- ワークシート一覧を取得できること。
- 行、列、フィルタ、ペインで使われているフィールドを取得できること。
- ペイン配下の encoding として、色、ラベル、ツールチップ、サイズ、形状、詳細、パス、角度を取得できること。
- フィルタの場合、設定値を取得できること。

### ダッシュボード

- ダッシュボード一覧を取得できること。
- ダッシュボードに紐づくワークシートを取得できること。
- 将来的に配置情報、サイズ、ゾーン構造を取得できること。

## 更新 API

### フィールド名変更

目的: 既存フィールドの表示名を変更する。
Tableau XML 上では、表示名がデフォルト名のままの場合 `caption` 属性が存在しないことがある。
そのため、この API は内部IDではなく `caption` 属性のみを追加・更新する。

想定 API:

```python
wb.rename_field(datasource, field, caption, by="auto")
wb.reset_field_caption(datasource, field, by="auto")
```

要件:

- `rename_field()` は `caption` 属性を追加・更新できること。
- `reset_field_caption()` は `caption` 属性を削除し、Tableauのデフォルト表示名へ戻せること。
- `caption` が元々存在しないフィールドでもリネーム対象にできること。
- field は caption / id のどちらでも指定できること。
- 対象が曖昧な場合はエラーにすること。
- 内部IDである `name` / `id` は変更しないこと。
- 同一データソース内に同じ caption がある場合はエラーにすること。
- `caption` が `None` または空文字の場合はエラーにすること。
- `Parameters` datasource は対象外とし、必要な場合はパラメータ専用APIで扱うこと。
- 更新後の `TwbColumn` を返すこと。

### フィールドのフォルダ指定

目的: 既存フィールドを指定フォルダへ移動する。
Tableau XML 上では、フォルダ所属はフィールド本体ではなく datasource 配下の `folders-common/folder` 情報として保持される。
そのため、この API はフィールドIDを維持したまま、フォルダ所属だけを追加・更新する。

想定 API:

```python
wb.move_field_to_folder(datasource, field, folder, by="auto", create_if_missing=True)
wb.remove_field_from_folder(datasource, field, by="auto")
```

要件:

- `move_field_to_folder()` は既存フィールドを指定フォルダに所属させられること。
- `remove_field_from_folder()` はフィールドのフォルダ所属を解除できること。
- field は caption / id のどちらでも指定できること。
- folder はフォルダ表示名として指定すること。
- フォルダが存在しない場合、`create_if_missing=True` なら作成すること。
- フォルダが存在せず `create_if_missing=False` の場合はエラーにすること。
- measure / dimension のフォルダ構造を考慮すること。
- 既に別フォルダに所属している場合は、新しいフォルダへ移動すること。
- 対象が曖昧な場合はエラーにすること。
- 内部IDである `name` / `id` は変更しないこと。
- `Parameters` datasource は対象外とし、必要な場合はパラメータ専用APIで扱うこと。
- 更新後の `TwbColumn` を返すこと。

### 計算フィールドの新規作成

目的: データソースに計算フィールドを追加する。

想定 API:

```python
wb.create_calculated_field(
    datasource,
    caption,
    formula,
    datatype="real",
    role="measure",
    folder=None,
)
```

要件:

- caption ベースの式を Tableau 内部IDベースへ変換して保存できること。
- `caption` は Tableau 上の表示名として扱うこと。
- `name` は Tableau 内部IDとしてSDKが自動生成し、ユーザー引数にはしないこと。
- 作成後は表示用 formula、raw_formula、referenced_columns を取得できること。
- 同captionが存在する場合はエラーにすること。
- 自動生成した `name` が既存IDと衝突する場合は別IDを再生成すること。
- 作成時にフォルダ指定できること。
- 更新後の `TwbColumn` を返すこと。

### パラメータ更新

目的: 既存パラメータの現在値を変更する。

想定 API:

```python
wb.update_parameter(parameter, value, by="auto")
```

要件:

- 現在値を更新できること。
- list 型の場合、許可値外の値は原則エラーにすること。
- alias がある場合、表示値との対応を解決できること。
- hidden パラメータ更新は明示指定時のみ許可すること。

### フィールド書式更新

目的: 既存フィールドの数値形式・表示形式を変更する。

想定 API:

```python
wb.update_field_format(datasource, field, attr, value, scope=None, worksheet=None, by="auto")
```

要件:

- `text-format` などの format 属性を更新・追加できること。
- worksheet 指定時は対象ワークシート内の書式を更新できること。
- worksheet 未指定時の適用範囲は要議論。
- 既存 format が複数ある場合の更新ルールを定義すること。

### フィルタ更新

目的: ワークシート上の既存フィルタ値を変更する。

想定 API:

```python
wb.update_filter_values(worksheet, field, values, by="auto")
```

要件:

- 単一値・複数値を更新できること。
- 複数値は groupfilter として保存できること。
- 範囲フィルタ、日付フィルタ、相対日付は別仕様として扱うこと。

## 作成 API

### ワークシート作成

目的: 定型パターンのワークシートを新規作成する。

想定 API:

```python
wb.create_worksheet(name, template_type, datasource, **options)
```

共通要件:

- ワークシート名の重複を検出すること。
- rows / columns / filters / marks / encodings を指定できること。
- 最小限のXMLを生成し、Tableauで開けることを優先すること。
- 生成後に `list_worksheets()` で取得できること。

### スコアカード

目的: KPI値を大きく表示するワークシートを作成する。

要件:

- 主要メジャーをラベルに配置できること。
- 任意で色、ツールチップ、フィルタを指定できること。
- 数値書式を指定できること。

### 時系列グラフ

目的: 日付軸とメジャーの推移グラフを作成する。

要件:

- 日付フィールドを列、メジャーを行に配置できること。
- mark type は line を基本とすること。
- 色分けディメンションを任意指定できること。
- 日付粒度の指定は要議論。

### ヒートマップ

目的: 2軸のディメンションと色メジャーによるヒートマップを作成する。

要件:

- 行ディメンション、列ディメンション、色メジャーを指定できること。
- ラベル表示の有無を指定できること。
- mark type は square を基本とすること。

### ポジショニングマップ

目的: X軸・Y軸メジャーによる散布図を作成する。

要件:

- X軸メジャー、Y軸メジャーを指定できること。
- 色、サイズ、ラベル、詳細を任意指定できること。
- mark type は circle を基本とすること。

### 帳票

目的: 明細表またはクロス集計のワークシートを作成する。

要件:

- 行ディメンション、列ディメンション、表示メジャーを指定できること。
- Measure Names / Measure Values の扱いを定義すること。
- ソート、合計、小計は将来拡張とすること。

## ダッシュボード作成 API

### サンプルボックス配置

目的: 作成済みワークシートをダッシュボード上に配置する。

想定 API:

```python
wb.create_dashboard(name, width=1200, height=800)
wb.add_dashboard_box(dashboard, worksheet, x, y, width, height)
```

要件:

- ダッシュボードを新規作成できること。
- ワークシートを指定座標・サイズで配置できること。
- 配置情報は固定座標を初期対象とすること。
- tiled / floating の扱いは要議論。
- サンプルとして複数ボックスを並べたダッシュボードを生成できること。

## 優先順位

1. フィールド名変更
2. フィールドのフォルダ指定
3. 計算フィールドの新規作成
4. パラメータ更新
5. フィールド書式更新
6. ワークシート作成の最小版
7. スコアカード / 時系列 / ヒートマップ / ポジショニングマップ / 帳票テンプレート
8. ダッシュボード作成とサンプルボックス配置

## 未決事項

- フィールド指定は caption 優先か id 優先か。
- worksheet 未指定の書式更新をどの範囲に適用するか。
- 作成ワークシートのXMLテンプレートをどこまでSDK内で持つか。
- Tableau Desktopで開ける最小XMLの検証方法。
- `.twbx` 保存時の上書き運用。
