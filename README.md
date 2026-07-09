# twbpatch

既存の Tableau `.twb` / `.twbx` を読み込み、データソース・カラム・計算フィールド・フォルダを取得/編集して保存するための最小実装です。

```python
from twbpatch import TwbWorkbook

wb = TwbWorkbook.open("template.twb")
wb.create_calculated_field(
    datasource="売上データ",
    name="Profit Ratio",
    caption="粗利率",
    formula="SUM([粗利]) / SUM([売上])",
)
wb.save("output.twb", overwrite=True)
```
