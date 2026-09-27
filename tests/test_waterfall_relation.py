from pathlib import Path

import pytest
from lxml import etree as ET

from twbpatch import TwbWorkbook
from twbpatch.errors import UnsupportedFeatureError

DATASOURCE_ID = "federated.00vlmup0b8v7m212i5x9f03fouo2"
DATASOURCE_NAME = "EC Orders"
ORDERS_OBJECT_ID = "Orders_E82A0D784F4E42B1A8CF60FF78680595"


def _relation_datasource_workbook(tmp_path):
    """`examples/ウォーターフォール.twb` の EC Orders データソースを縮めた最小構成。

    federated の物理リレーション（collection）・抽出の cols マップ・object-graph の
    関連モデルを実測どおりの形にしておく。`add_index_relation()` はこの形を前提にする。
    """
    path = tmp_path / "waterfall.twb"
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="{DATASOURCE_ID}" caption="{DATASOURCE_NAME}">
      <connection class="federated">
        <named-connections>
          <named-connection name="excel-direct.1wk7x6i16gwroz19147dy1u57n1l" caption="sample_-_superstore">
            <connection class="excel-direct" filename="C:/sample.xlsx" />
          </named-connection>
        </named-connections>
        <relation type="collection">
          <relation connection="excel-direct.1wk7x6i16gwroz19147dy1u57n1l" name="Orders" table="[Orders$]" type="table">
            <columns header="yes">
              <column datatype="string" name="Category" ordinal="0" />
              <column datatype="real" name="Sales" ordinal="1" />
            </columns>
          </relation>
        </relation>
      </connection>
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <extract count="-1" enabled="true" object-id="" units="records" user-specific="false">
        <connection class="hyper" dbname="C:/temp/extract.hyper" schema="Extract" tablename="Extract">
          <relation type="collection">
            <relation name="{ORDERS_OBJECT_ID}" table="[Extract].[{ORDERS_OBJECT_ID}]" type="table" />
          </relation>
          <cols>
            <map key="[Category]" value="[{ORDERS_OBJECT_ID}].[Category]" />
            <map key="[Sales]" value="[{ORDERS_OBJECT_ID}].[Sales]" />
          </cols>
        </connection>
      </extract>
      <object-graph>
        <objects>
          <object caption="Orders" id="{ORDERS_OBJECT_ID}">
            <properties context="">
              <relation connection="excel-direct.1wk7x6i16gwroz19147dy1u57n1l" name="Orders" table="[Orders$]" type="table">
                <columns header="yes">
                  <column datatype="string" name="Category" ordinal="0" />
                  <column datatype="real" name="Sales" ordinal="1" />
                </columns>
              </relation>
            </properties>
          </object>
        </objects>
        <relationships />
      </object-graph>
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_add_index_relation_writes_the_text_file_and_wires_the_relation(tmp_path) -> None:
    """①: 1=1 のクロスジョインで連番テーブルを足す。<extract> には触れない。"""
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    txt_path = tmp_path / "waterfall_index.txt"

    field = workbook.add_index_relation(
        datasource,
        join_to="カテゴリ",
        path=str(txt_path),
        max_index=5,
    )

    assert field.name == "連番"
    assert field.role == "dimension"
    assert field.datatype == "integer"

    assert txt_path.read_text(encoding="utf-8") == "連番\n1\n2\n3\n4\n5\n"

    datasource_el = workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$id]", id=DATASOURCE_ID
    )[0]

    # 物理リレーション（federated の collection）に新しいテーブルが増えている
    # name はファイル名（edge.txt の実測どおり）、table は stem#txt
    physical = datasource_el.xpath("./connection/relation[@type='collection']/relation")
    assert [r.get("name") for r in physical] == ["Orders", "waterfall_index.txt"]
    assert physical[1].get("table") == "[waterfall_index#txt]"

    # named-connections に textscan が増えている
    named = datasource_el.xpath("./connection/named-connections/named-connection")
    assert len(named) == 2
    assert named[1][0].get("class") == "textscan"
    assert named[1][0].get("filename") == "waterfall_index.txt"

    # object-graph に新しいオブジェクトと 1=1 の relationship が増えている
    objects = datasource_el.xpath("./object-graph/objects/object")
    assert [o.get("caption") for o in objects] == ["Orders", "waterfall_index"]
    new_object_id = objects[1].get("id")
    assert new_object_id.startswith("waterfall_index_")

    relationships = datasource_el.xpath("./object-graph/relationships/relationship")
    assert len(relationships) == 1
    expression = relationships[0].find("expression")
    assert [e.get("op") for e in expression] == ["1", "1"]
    assert relationships[0].find("first-end-point").get("object-id") == ORDERS_OBJECT_ID
    assert relationships[0].find("second-end-point").get("object-id") == new_object_id

    # object-graph の `context="extract"` properties も必要（無いと Tableau の
    # リレーションシップ画面で未接続に見える、2026-09-23 に実機で確認）
    new_object = objects[1]
    extract_props = new_object.xpath("./properties[@context='extract']/relation")
    assert len(extract_props) == 1
    assert extract_props[0].get("name") == new_object_id
    assert extract_props[0].get("table") == f"[Extract].[{new_object_id}]"

    # 抽出には触れていない（テーブルは増えていない、フィクスチャの collection + 1 個のまま）
    extract = datasource_el.xpath("./extract")[0]
    assert len(extract.xpath(".//relation")) == 2
    assert len(extract.xpath(".//map")) == 2

    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_add_index_relation_rejects_an_existing_file_without_overwrite(tmp_path) -> None:
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    txt_path = tmp_path / "waterfall_index.txt"
    txt_path.write_text("何か別の内容\n", encoding="utf-8")

    with pytest.raises(ValueError, match="file already exists"):
        workbook.add_index_relation(datasource, join_to="カテゴリ", path=str(txt_path), max_index=5)

    assert txt_path.read_text(encoding="utf-8") == "何か別の内容\n"


def test_add_index_relation_overwrites_the_file_when_asked(tmp_path) -> None:
    """`overwrite=True`（2026-09-23 追加）: `build_waterfall()` が同じ元の .twb を
    開き直して apply_config() を繰り返すワークフローで使う。ファイルの中身は毎回
    同じなので、既存ファイルがあっても上書きしてよい。
    """
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    txt_path = tmp_path / "waterfall_index.txt"
    txt_path.write_text("古い内容\n", encoding="utf-8")

    field = workbook.add_index_relation(
        datasource, join_to="カテゴリ", path=str(txt_path), max_index=5, overwrite=True
    )

    assert field.name == "連番"
    assert txt_path.read_text(encoding="utf-8") == "連番\n1\n2\n3\n4\n5\n"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_add_index_relation_leaves_the_file_untouched_when_validation_fails_first(
    tmp_path,
) -> None:
    """引数の検証はファイルへ触れる前に終わらせる（原子性）。`overwrite=True` でも、
    検証で落ちれば既存ファイルの中身は変わらない。
    """
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    txt_path = tmp_path / "waterfall_index.txt"
    txt_path.write_text("古い内容\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid column name"):
        workbook.add_index_relation(
            datasource,
            join_to="カテゴリ",
            path=str(txt_path),
            column="[bad]",
            max_index=5,
            overwrite=True,
        )

    # column の検証はファイル書き込みより前に落ちるので、そもそも触られていない
    assert txt_path.read_text(encoding="utf-8") == "古い内容\n"


def test_add_index_relation_rejects_unrelated_datasource_shape(tmp_path) -> None:
    """federated + object-graph 以外の形は UnsupportedFeatureError。"""
    path = tmp_path / "plain.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="federated.plain" caption="Plain">
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))
    datasource = workbook.get_datasources(name="Plain")[0]

    with pytest.raises(UnsupportedFeatureError):
        workbook.add_index_relation(
            datasource,
            join_to="カテゴリ",
            path=str(tmp_path / "index.txt"),
        )
    assert not (tmp_path / "index.txt").exists()


def test_add_index_relation_rejects_existing_file(tmp_path) -> None:
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    txt_path = tmp_path / "existing.txt"
    txt_path.write_text("dummy", encoding="utf-8")

    with pytest.raises(ValueError, match="file already exists"):
        workbook.add_index_relation(datasource, join_to="カテゴリ", path=str(txt_path))


def test_add_index_relation_puts_the_field_in_the_given_folder(tmp_path) -> None:
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    field = workbook.add_index_relation(
        datasource,
        join_to="カテゴリ",
        path=str(tmp_path / "waterfall_index.txt"),
        folder="40_WF",
    )

    assert field.folder.name == "40_WF"
