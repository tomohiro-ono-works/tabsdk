from twbpatch import TwbWorkbook


def _write_forward_metadata_workbook(tmp_path):
    twb = tmp_path / "forward_metadata.twb"
    twb.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="Source">
      <connection class="federated">
        <relation type="join" join="inner">
          <clause type="join">
            <expression op="=">
              <expression op="[Orders].[Order ID]" />
              <expression op="[Returns].[Order ID]" />
            </expression>
          </clause>
          <relation connection="excel.1" name="Orders" table="[Orders$]" type="table" />
          <relation connection="excel.1" name="Custom Orders" type="text">
            SELECT * FROM Orders
          </relation>
        </relation>
      </connection>
      <column name="[Sales]" caption="Sales Amount" role="measure" />
      <column name="[Region]" caption="Sales Region" role="dimension" />
      <object-graph>
        <objects>
          <object id="Orders" caption="Orders">
            <properties><relation name="Orders" table="[Orders$]" type="table" /></properties>
          </object>
          <object id="Returns" caption="Returns">
            <properties><relation name="Returns" table="[Returns$]" type="table" /></properties>
          </object>
        </objects>
        <relationships>
          <relationship id="orders_returns">
            <expression op="=">
              <expression op="[Orders].[Order ID]" />
              <expression op="[Returns].[Order ID]" />
            </expression>
            <first-end-point object-id="Orders" />
            <second-end-point object-id="Returns" />
          </relationship>
        </relationships>
      </object-graph>
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="Sheet1" caption="Sales Sheet">
      <table>
        <view>
          <datasource-dependencies datasource="ds1" />
          <filter column="[ds1].[none:Region:nk]">
            <groupfilter function="member" member="&quot;East&quot;" />
          </filter>
          <rows>[ds1].[sum:Sales:qk]</rows>
          <cols>[ds1].[none:Region:nk]</cols>
          <pages>[ds1].[none:Region:nk]</pages>
          <sort column="[ds1].[sum:Sales:qk]" direction="DESC" />
        </view>
        <panes>
          <pane id="1">
            <mark class="Bar" />
            <encodings>
              <color column="[ds1].[none:Region:nk]" />
              <tooltip column="[ds1].[sum:Sales:qk]" />
            </encodings>
          </pane>
        </panes>
      </table>
    </worksheet>
  </worksheets>
</workbook>
""",
        encoding="utf-8",
    )
    return twb


def test_list_worksheet_fields_returns_shelves_marks_filters_and_identity(tmp_path):
    wb = TwbWorkbook.open(str(_write_forward_metadata_workbook(tmp_path)))

    fields = wb.list_worksheet_fields("Sales Sheet")

    placements = {(field.category, field.type, field.caption) for field in fields}
    assert ("軸", "y軸", "Sales Amount") in placements
    assert ("軸", "x軸", "Sales Region") in placements
    assert ("フィルタ", "フィルタ", "Sales Region") in placements
    assert ("ページ", "ページ", "Sales Region") in placements
    assert ("ペイン", "色", "Sales Region") in placements
    assert ("ペイン", "ツールチップ", "Sales Amount") in placements
    assert ("ソート", "ソート", "Sales Amount") in placements

    color = next(field for field in fields if field.type == "色")
    assert color.worksheet_id == "Sheet1"
    assert color.datasource == "Source"
    assert color.datasource_id == "ds1"
    assert color.field_id == "[Region]"
    assert color.pane_id == "1"
    assert color.mark_type == "Bar"
    assert color.attrs == {"column": "[ds1].[none:Region:nk]"}

    filter_field = next(field for field in fields if field.type == "フィルタ")
    assert filter_field.values == "East"
    assert wb.get_worksheet("Sales Sheet").fields == fields


def test_list_relations_returns_nested_physical_structure(tmp_path):
    wb = TwbWorkbook.open(str(_write_forward_metadata_workbook(tmp_path)))

    relations = wb.list_relations("Source")

    assert len(relations) == 1
    root = relations[0]
    assert root.datasource == "Source"
    assert root.datasource_id == "ds1"
    assert root.type == "join"
    assert root.join == "inner"
    assert root.scope == "connection"
    assert root.clauses[0]["tag"] == "clause"
    assert root.clauses[0]["children"][0]["attrs"] == {"op": "="}
    assert [(child.type, child.name, child.table) for child in root.children] == [
        ("table", "Orders", "[Orders$]"),
        ("text", "Custom Orders", None),
    ]
    assert root.children[1].custom_sql == "SELECT * FROM Orders"
    assert wb.get_datasource("Source").relations == relations


def test_list_relationships_returns_logical_endpoints_and_expression(tmp_path):
    wb = TwbWorkbook.open(str(_write_forward_metadata_workbook(tmp_path)))

    relationships = wb.list_relationships("Source")

    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship.id == "orders_returns"
    assert relationship.left_object == "Orders"
    assert relationship.left_object_id == "Orders"
    assert relationship.right_object == "Returns"
    assert relationship.right_object_id == "Returns"
    assert relationship.expression["attrs"] == {"op": "="}
    assert wb.get_datasource("Source").relationships == relationships

    exported = wb.export_json()["datasources"][0]
    assert exported["relations"][0]["type"] == "join"
    assert exported["relationships"][0]["id"] == "orders_returns"


def test_list_relations_falls_back_to_object_graph(tmp_path):
    twb = tmp_path / "object_graph_only.twb"
    twb.write_text(
        """<workbook>
  <datasources>
    <datasource name="ds1" caption="Source">
      <object-graph>
        <objects>
          <object id="Orders" caption="Orders Logical">
            <properties>
              <relation connection="db.1" name="Orders" table="[public].[orders]" type="table" />
            </properties>
          </object>
        </objects>
      </object-graph>
    </datasource>
  </datasources>
</workbook>""",
        encoding="utf-8",
    )

    relation = TwbWorkbook.open(str(twb)).list_relations("Source")[0]

    assert relation.scope == "object-graph"
    assert relation.logical_table == "Orders Logical"
    assert relation.logical_table_id == "Orders"
    assert relation.table == "[public].[orders]"
