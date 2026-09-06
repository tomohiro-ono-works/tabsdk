"""階層（ドリルパス）を含むワークブックを壊さない。

階層はフォルダへ `<folder-item type="drillpath" name="階層名">` として入る。
`name` は drill-path の表示名（角括弧なし）なので、列名と照合すると必ず外れる。

Tableau が保存した `.twb`（`workbook/hierarchy_group_sample.twb`）で実測した構造。

```xml
<drill-paths>
  <drill-path name="カテゴリ">
    <field>[Category]</field>
    <field>[Sub-Category]</field>
  </drill-path>
</drill-paths>
```
"""

from __future__ import annotations

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "drill.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sub-Category]" caption="サブカテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <drill-paths>
        <drill-path name="商品階層">
          <field>[Category]</field>
          <field>[Sub-Category]</field>
        </drill-path>
      </drill-paths>
      <folders-common>
        <folder name="Dim商品">
          <folder-item name="商品階層" type="drillpath" />
        </folder>
        <folder name="Measure">
          <folder-item name="[Sales]" type="field" />
        </folder>
      </folders-common>
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_a_drill_path_folder_item_is_not_reported_as_missing(tmp_path) -> None:
    workbook = _workbook(tmp_path)

    codes = [message.code for message in workbook.validate()]

    assert "folder_item_missing" not in codes


def test_a_missing_drill_path_is_still_reported(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    element = workbook.tree.getroot().xpath(".//folder-item[@type='drillpath']")[0]
    element.set("name", "無い階層")

    messages = [m for m in workbook.validate() if m.code == "folder_item_missing"]

    assert len(messages) == 1
    assert "drill path" in messages[0].message


def test_a_drill_path_item_is_not_a_field_reference(tmp_path) -> None:
    """階層の folder-item をフィールド参照と取り違えないこと。

    `folder-item` は `type` で意味が変わる。`field` は列を指すが `drillpath` は
    階層名を指す。名前だけで照合すると、階層名と一致する id を持つフィールドが
    削除できなくなる。
    """
    from twbpatch.references import field_references

    workbook = _workbook(tmp_path)
    element = workbook.tree.getroot().xpath(".//folder-item[@type='drillpath']")[0]
    # 階層名をフィールドの内部 ID と同じにする（誤ヒットを起こしうる状況）
    element.set("name", "[Sales]")

    locations = [
        reference.location
        for reference in field_references(workbook.tree, "ds1", "[Sales]")
    ]

    # Measure フォルダの folder-item だけが参照。drillpath の方は数えない
    assert len(locations) == 1
    assert "folder[2]" in locations[0]


def test_a_workbook_with_a_drill_path_saves(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    target = tmp_path / "out.twb"

    workbook.save(str(target), validate=True, overwrite=True)

    saved = target.read_text(encoding="utf-8")
    assert "drill-path" in saved
    assert 'type="drillpath"' in saved
