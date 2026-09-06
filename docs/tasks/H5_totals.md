# H-5 合計・小計の XML と公開 API

- 作成日: 2026-09-06
- 目的: 総計・小計を Tableau XML のどこに書くかを確定し、公開 API の形を決める。
- 根拠: Tableau 公式スキーマ <https://github.com/tableau/tableau-document-schemas>
  の `schemas/2026_2/twb_2026.2.0.xsd`（`Workbook-VisualSpecification-G`）。

## リポジトリ内に参照実装が無いことの確認

`twb-xml-probe` で `workbook/*.twbx` / `examples/sample_ec.twb` / `outputs/*.twb` /
`tests/sample_minimal.twb` を全数走査した結果、**総計・小計を有効化した XML は 1 件も無い**。

- `total` / `grand` / `subtotal` / `summary` を含む要素名・属性名は 0 件。
- 唯一の該当は `table/style/style-rule/format[@data-class="total"]`（78 件）だが、
  これは総計セルの**書式**であって有効化ではない。37 ワークシート中 35 個に付いており、
  総計の有無に関わらず Tableau が既定で書き出す。
- したがって **`data-class="total"` の有無から総計の有無は判定できない。**

構造は公式 XSD を一次情報として採用した。

## XML の形（XSD 実測）

**総計は新しい要素ではなく、既存シェルフ要素の属性。**

```xml
<table>
  <rows total="true" onTop="false">...</rows>   <!-- 合計行。onTop=true で上部 -->
  <cols total="true" onLeft="false">...</cols>  <!-- 合計列。onLeft=true で左側 -->
</table>
```

`onTop` は `<rows>` にしか、`onLeft` は `<cols>` にしか定義が無い。
行シェルフの総計は「行」として現れるので上下、列シェルフの総計は「列」として
現れるので左右、という対応になっている。

**小計は `<table>` 直下の独立要素。**

```xml
<table>
  <subtotals>
    <column>[ds1].[none:Region:nk]</column>
  </subtotals>
</table>
```

- 位置は `join-lod-exclude-overrides` の直後、`table-calculations` の直前。
  `validator.py` の `_TABLE_ORDER` の並びと一致していた。
- `<column>` は `maxOccurs="unbounded"`、`minOccurs` 既定 1。
  **空の `<subtotals>` はスキーマ違反になるため、最後の 1 件を外すときは要素ごと削除する。**
- `<column>` の値は `QualifiedName-ST`。`pages` や `join-lod-*` と同じ配置参照の形。

**合計の集計方法**は `column-instance/@visual-totals`（`xs:string`）。
XSD が型を `AggType-ST` に絞っていないため取りうる値を確定できず、今回は範囲外とした。

## 公開 API

§3.3 の区分に従って総計と小計で置き場所を分けた。どちらも `TwbWorksheet`。

```python
worksheet.update(grand_totals={"row": "bottom", "column": "right"})
worksheet.grand_totals   # {"row": "bottom", "column": "right"}

placed = worksheet.add_field(field="地域", shelf="rows")
worksheet.set_subtotal_visibility(field=placed, visible=True)
```

| | 理由 |
|---|---|
| 総計 → `update()` のグループ引数 | ワークシート自身のスカラー設定。他モデルを引数に取らない |
| 小計 → `set_subtotal_visibility()` | 対象を `TwbWorksheetField` で受ける。§3.3 で `update()` へ統合しない側 |

`grand_totals` のキーを `rows` / `columns` にしなかった理由は、**Tableau UI の
「行の総計」が XML では `<cols>` 側にあたる**ため。`add_field(shelf="rows")` の
語と逆転して取り違える。キーを「合計行 / 合計列」の意味にすると
`row` は必ず `<rows>`、上下の位置しか取らないので取り違えようがない。

値を `bool` と位置の 2 キーに分けず、位置そのものか `None` にしたのも同じ理由。
`{"row": True, "row_position": "bottom"}` は 2 つの値の整合を呼び出し側が持つことになる。

## 積み残し

- 合計の集計方法（`visual-totals`）。実 Tableau で値の語彙を採取してから。
- K-7（帳票系 `draw_*` に合計・小計・ソートを渡す）は H-5 に依存していた。着手可能になった。
