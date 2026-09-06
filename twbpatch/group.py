"""グループの XML を組み立てる。

構造は Tableau が保存した `.twb` から実測した（2026-09-07、
`workbook/hierarchy_group_sample.twb`）。

```xml
<column datatype="string" name="[カテゴリ (グループ)]" role="dimension" type="nominal">
  <calculation class="categorical-bin" column="[Category]" new-bin="true">
    <bin value="&quot;家具と事務用品&quot;">
      <value>"Furniture"</value>
      <value>"Office Supplies"</value>
    </bin>
  </calculation>
</column>
```

- `<group>` 要素ではない。**普通の `<column>` と同列**でデータソース直下に置かれる
- `caption` は付かない。**表示名がそのまま内部 ID**になる（角括弧付き）。
  階層など他の要素からも `[カテゴリ (グループ)]` の形で参照される
- `<bin>` は**まとめた 1 グループにつき 1 件**。まとめなかった値は書かれず、
  Tableau が暗黙に単独扱いする
- グループ名もメンバーも**ダブルクォート込みの文字列**として書く
- `default-name="true"` はグループ名を Tableau の自動生成に任せた印。
  こちらは名前を必ず受け取るので付けない
"""

from __future__ import annotations

from lxml import etree as ET

#: 既定のフィールド名に付く接尾辞。Tableau の日本語 UI と同じ。
NAME_SUFFIX = " (グループ)"

#: グループにできる元フィールドの型。実測がこれだけなので他は受け付けない。
SUPPORTED_DATATYPE = "string"


def default_field_name(source_name: str) -> str:
    """`カテゴリ` → `カテゴリ (グループ)`。"""
    return f"{source_name}{NAME_SUFFIX}"


def quote(value: str) -> str:
    """`Furniture` → `"Furniture"`。Tableau は文字列リテラルとして書く。"""
    return f'"{value}"'


def build_group_column(
    *,
    field_id: str,
    source_id: str,
    groups: dict[str, list[str]],
) -> ET._Element:
    """グループの `<column>` を作る。`groups` は グループ名 → メンバー値。"""
    column = ET.Element(
        "column",
        attrib={
            "datatype": SUPPORTED_DATATYPE,
            "name": field_id,
            "role": "dimension",
            "type": "nominal",
        },
    )
    calculation = ET.SubElement(
        column,
        "calculation",
        attrib={"class": "categorical-bin", "column": source_id, "new-bin": "true"},
    )
    for group_name, members in groups.items():
        bin_el = ET.SubElement(calculation, "bin", attrib={"value": quote(group_name)})
        for member in members:
            ET.SubElement(bin_el, "value").text = quote(member)
    return column
