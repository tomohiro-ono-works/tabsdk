# G-2 サンプルスクリプトの知見洗い出し

- 作成日: 2026-09-05
- 目的: ルート直下のサンプル 20 本を削除する前に、各スクリプトが持つ「どの API を
  どう組み合わせるか」を記録する。**G-3（展開用サンプルの作成）の入力。**
- 根拠: 削除前の 20 本を実測（`grep` による API 呼び出しの抽出と本文の読み取り）

## 削除したファイル

| 種別 | ファイル |
|---|---|
| フィールド整理 | `yaml_field_config_sample.py` / `field_folder_assignment_sample.py` / `field_organization_test.py` |
| 計算フィールド | `calculated_fields_sample.py` / `calculated_fields_string_sample.py` |
| `draw_*` 単体 | `draw_card_sample.py` / `draw_yoy_sample.py` / `draw_crosstab_sample.py` / `draw_quadrant_sample.py` / `draw_sheet_style_sample.py` / `scorecards_sample.py` / `draw_api_build.py` |
| コンテナ手組み | `dashboard_build_sample.py` / `dashboard_build_sample_2cards.py` |
| `build_report()` | `dashboard_build_report_sample.py` / `draw_quadrant_dashboard_sample.py` / `yoy_dashboard_sample.py` / `colored_yoy_bar_dashboard_sample.py` |
| 総合 | `complete_dashboard_sample.py` / `ec_site_analysis_build.py` |
| 設定ファイル | `ec_site_fields.yaml` |

**20 本すべてに共通していた問題**: `SOURCE` / `OUTPUT` がリポジトリ外の実 Tableau
リポジトリの絶対パスを指し、全本が `save(..., validate=True, overwrite=True)` を呼んでいた（C-1）。

---

## 6 つのパターン

内容は重複が多く、実質 6 パターンに縮まる。

### 1. フィールド整理（英名 → 和名、フォルダ分類）

YAML 一括指定。

```python
workbook.apply_field_config(FIELD_CONFIG)   # Path
```

`ec_site_fields.yaml` の書式は **データソース名 → フォルダ名 → {英名: 和名}** の 3 階層。

```yaml
"Orders++ (sample_-_superstore)":
  Dim注文配送:
    Order ID: 注文ID
    Order Date: 注文日
  Measure:
    Sales: 売上
```

同じことを API で 1 件ずつ書く場合（`field_organization_test.py`）:

```python
datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
folder = datasource.create_folder(name=folder_name)
field.update(name=japanese_name)
```

### 2. 計算フィールドの作成

一括（辞書渡し）と単体の 2 通り。

```python
datasource.create_calculated_fields(CALCULATIONS, folder="Measure")  # {name: formula}
datasource.create_calculated_field(
    name="#", formula="index()", datatype="integer",
    role="measure", discrete=True,
)
datasource.create_calculated_field(name="粗利", formula="[利益]", datatype="real", folder=folder)
datasource.create_yoy_calculated_fields(metric="売上", year_category="当年昨年区分", folder=folder)
```

- `datatype` は `real` / `integer` / `string`
- `folder=` は文字列でもフォルダオブジェクトでも渡せた
- `discrete=True` + `index()` で「連番列 `#`」を作るのが帳票の定番

### 3. `draw_*` 7 種の引数パターン

`TwbWorkbook` のメソッド版とモジュール関数版が併存（**A-4 の対象**）。
メソッド版は `(datasource_name, field_name)` のタプル、関数版は
`draw_x(workbook, datasource, ...)` で第 2 引数にデータソースを渡し項目は文字列。

```python
workbook.draw_sheet(name=, title=, items=[(DS, "#"), (DS, "カテゴリ")])
workbook.draw_card(name=, main_metric=(DS, "売上"), sub_metric=(DS, "利益"))
workbook.draw_yoy(name=, item=(DS, "注文日"), metric=(DS, "売上"))
workbook.draw_bar(name=, item=(DS, "サブカテゴリ"), metric=(DS, "売上"))
workbook.draw_quadrant(
    name=, title=, item=, x_metric=, y_metric=, size_metric=,
    colors=("#4400FF", "#FF007F", "#00C888", "#CCD500"), opacity=0.6,
)
workbook.draw_crosstab(
    name=, title=, x_item=, y_item=, color_metric=, label_metric=,
    min_color="#FF007F", mid_color="#FFFFFF", max_color="#4400FF",
)
workbook.draw_colored_yoy_sheet(
    name=, items=[...], metrics=[...],
    negative_color=, positive_color=, ratio_color=,
    mark_type="bar", bar_color=None, axis_min=0, axis_max=1,
    show_axes=False, bar_opacity=0.0, index_partition_by=(DS, "カテゴリ"),
)
```

表スタイルの後付け（**A-6 で `update()` に統合される呼び出し**）:

```python
worksheet.update_table_style(
    header_background="#f5f5f5", header_bold=True, header_color="#555555",
    row_band=False, column_widths={"#": 36},
)
worksheet.set_title("カテゴリ・サブカテゴリ別 年前年差帳票")
```

### 4. コンテナの手組みレイアウト

`create_container()` を入れ子にして 1 段ずつ組む方式。`build_report()` を使わない低レベル操作。

```python
root = dashboard.create_container(direction="vertical", friendly_name="contents")
root.update_style(background_color="#f5f5f5", border_style="none", margin=8)

header = root.create_container(direction="horizontal", fixed_size=43, friendly_name="header")
header.add_image(fixed_size=52, style={"margin": 0, "border_style": "none"})
header.add_text("  < Sheet Name", bold=True, fixed_size=None, style={...})

score_area.add_spacer(fixed_size=6, style={"background_color": color, "margin": 4, "margin_right": 0})
card = score_area.add_worksheet(sheet, fixed_size=267, show_title=False)
card.update_style(background_color=, border_style=, margin=, margin_left=,
                  margin_right=, padding=)
```

- `direction` は `"vertical"` / `"horizontal"`
- `fixed_size` を省くと可変幅（残りを分け合う）
- スタイルは `update_style(...)` かコンストラクタの `style={...}` の 2 経路
  （**A-6 の改名対象**）
- `add_worksheet()` は**シート名の文字列ではなく `TwbWorksheet` オブジェクト**を受け取る。
  文字列を渡すと `TypeError: worksheet must be TwbWorksheet`
  （`connected_dashboard.py:514`）。サンプル再現時に踏んだ

### 5. `build_report()` による帳票レイアウト

`struct` の値の形で配置が決まる。

```python
dashboard = workbook.create_dashboard(name=DASHBOARD, width=1169, height=1654)
dashboard.build_report(
    dashboard_name=DASHBOARD,
    struct={
        "フィルタコンテナ": [(DS, "カテゴリ")],        # フィルタは (ds, field) のタプル
        "スコア・時系列コンテナ": [[card, trend], ...],  # ネストで横並びの行
        "分析グラフコンテナ": ["シート名", "シート名"],   # 平坦なら横並び
        "帳票コンテナ": ["帳票"],
    },
    container_sizes={"スコア・時系列コンテナ": 206},
    content_style={"background_color": "#e6e6e6", "margin": 0, "padding": 16, "padding_top": 4},
    header_height=44, header_background_color="#333333", header_font_color="#ffffff",
)
workbook.set_filter((DS, "カテゴリ"))   # build_report のフィルタコンテナの前提
workbook.set_default_font()             # 既定 "Meiryo UI"
```

**キー名（コンテナ名）の文字列で挙動が変わる。** 「フィルタコンテナ」という表示名が
制御フラグを兼ねている。**これが K-1 の対象そのもの。**

### 6. ペインの直接操作（`draw_*` に無いグラフを作る）

`draw_*` が 7 種しかない（H-10）ため、円グラフは低レベル API で作っていた。

```python
pie = workbook.create_worksheet(name="カテゴリ別売上_円")
pie.get_panes()[0].update(mark_type="pie")
pie.get_panes()[0].add_field(field, encoding="color", discrete=True)
pie.get_panes()[0].add_field(field, encoding="label", discrete=True)
pie.get_panes()[0].add_field(field, encoding="angle", aggregation="sum", discrete=False)

bar = draw_bar(...)
bar.get_panes()[0].add_field(fields["カテゴリ"], encoding="color", discrete=True)  # draw_* の結果に色を足す
```

`encoding` は `color` / `label` / `angle` / `size` など。`draw_*` の戻り値に
後からフィールドを足せる点が重要。

---

## 引き継ぎ事項

| 宛先 | 内容 |
|---|---|
| **G-3** | 上の 6 パターンを 1 本に統合したサンプルを `examples/` に作る。入力はリポジトリ同梱、出力は `outputs/` |
| **A-4** | `draw_*` の 2 系統（メソッド版・関数版）はサンプル内でも混在していた。どちらを正とするか要決定 |
| **A-6** | `update_table_style()` / `update_style()` はサンプルの主要な呼び出し。改名後はサンプルも追随が要る |
| **K-1** | `build_report()` の `struct` キーが表示名と制御フラグを兼ねている実例 |
| **H-10** | 円グラフはペイン直接操作でしか作れなかった。`draw_pie` の需要の根拠 |
