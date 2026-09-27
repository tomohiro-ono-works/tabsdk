import pytest
from lxml import etree as ET

from twbpatch import TwbWorkbook

DATASOURCE_ID = "federated.00vlmup0b8v7m212i5x9f03fouo2"
DATASOURCE_NAME = "EC Orders"


def _waterfall_workbook(tmp_path):
    """ウォーターフォール用の最小構成。

    `連番` は①（データソースへの 1=1 クロスジョイン）で Tableau 側の手作業で足す想定の
    フィールド。ここではテストのため素の整数フィールドとして用意する。
    """
    path = tmp_path / "waterfall.twb"
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="{DATASOURCE_ID}" caption="{DATASOURCE_NAME}">
      <column name="[連番]" caption="連番" datatype="integer" role="dimension" type="ordinal" />
      <column name="[前月残]" caption="前月残" datatype="real" role="measure" type="quantitative" />
      <column name="[今月売上]" caption="今月売上" datatype="real" role="measure" type="quantitative" />
      <column name="[今月原価]" caption="今月原価" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_build_waterfall_metric_creates_the_four_fields(tmp_path) -> None:
    """②③の縦持ち変換: 連番の並び順に 1, 2, 3... を割り当てる。合計（終了）バーは作らない
    （2026-09-23、実測した手作業の例には無かったため外した）。

    値は正なら「増加」、負なら「減少」と動的に判定する。
    `size`（`-値`）はガントバー用（実測した手作業の例の符号反転に合わせる）。
    """
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上", "今月原価"],
    )

    assert metric.value.name == "残高_値"
    assert metric.label.name == "残高_項目名"
    assert metric.kind.name == "残高_種別"
    assert metric.size.name == "残高_サイズ"
    assert metric.value.role == "measure"
    assert metric.label.role == "dimension"
    assert metric.kind.role == "dimension"
    assert metric.size.role == "measure"

    assert metric.value.formula == (
        "CASE ATTR([連番])\n"
        "    WHEN 1 THEN SUM([前月残])\n"
        "    WHEN 2 THEN SUM([今月売上])\n"
        "    WHEN 3 THEN SUM([今月原価])\n"
        "END"
    )
    assert metric.label.formula == (
        "CASE [連番]\n"
        '    WHEN 1 THEN "前月残"\n'
        '    WHEN 2 THEN "今月売上"\n'
        '    WHEN 3 THEN "今月原価"\n'
        "END"
    )
    assert metric.kind.formula == (
        'IF [残高_値] >= 0 THEN "増加"\n'
        'ELSE "減少"\n'
        "END"
    )
    assert metric.size.formula == "-[残高_値]"
    assert metric.count == 3
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_metric_requires_metrics(tmp_path) -> None:
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    with pytest.raises(ValueError, match="metrics must be a non-empty list"):
        workbook.build_waterfall_metric(
            datasource,
            name="残高",
            index="連番",
            metrics=[],
        )


def test_build_waterfall_metric_puts_fields_in_the_given_folder(tmp_path) -> None:
    """`folder=` で指定した名前のフォルダへ 4 つとも入れる（無ければ作る）。"""
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上"],
        folder="40_WF",
    )

    assert metric.value.folder.name == "40_WF"
    assert metric.label.folder.name == "40_WF"
    assert metric.kind.folder.name == "40_WF"
    assert metric.size.folder.name == "40_WF"


def test_build_waterfall_chart_places_the_fields_and_marks(tmp_path) -> None:
    """④: ②③で作った WaterfallMetric を並べる。

    列は連番だけ（項目名は置かない、2026-09-23 に実機で確認して変更）、行は値（累計）、
    マークはガントチャート、色は種別、サイズはサイズ。
    """
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上", "今月原価"],
    )

    worksheet = workbook.build_waterfall_chart(
        datasource,
        name="ウォーターフォール",
        index="連番",
        metric=metric,
    )

    assert worksheet.get_panes()[0].mark_type == "gantt"
    shelves = {field.shelf for field in worksheet.get_fields()}
    assert "rows" in shelves and "columns" in shelves
    columns_fields = [field.name for field in worksheet.get_fields() if field.shelf == "columns"]
    assert columns_fields == ["連番"]  # 項目名は列に置かない。ラベルのマークだけで表示する

    # 累計（クイック表計算）は行に置いたピルの参照とその column-instance で確認する。
    # 計算対象は「特定のディメンション」で連番・項目名を明示する
    # （2026-09-23、実機で確認。列に置いていない項目名も対象にできる）。
    rows_text = workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='ウォーターフォール']/table/rows)"
    )
    assert rows_text.startswith(f"[{DATASOURCE_ID}].[cum:usr:")
    assert rows_text.endswith(":2]")
    table_calc = workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='ウォーターフォール']/table/view/"
        "datasource-dependencies/column-instance[starts-with(@name,'[cum:')]/table-calc"
    )[0]
    assert table_calc.get("type") == "CumTotal"
    assert table_calc.get("ordering-type") == "Field"
    orders = table_calc.findall("order")
    assert orders[0].get("field") == f"[{DATASOURCE_ID}].[none:連番:ok]"
    assert orders[1].get("field") == f"[{DATASOURCE_ID}].{metric.label.id}"

    pane = worksheet.get_panes()[0]
    encodings = {field.encoding: field.name for field in pane.get_fields()}
    assert encodings["color"] == "残高_種別"
    assert encodings["size"] == "残高_サイズ"
    assert encodings["label"] == "残高_項目名"

    # 連番は使った分（1..count）だけに絞る（2026-09-23、余った連番の NULL 列を隠す）
    filters = worksheet.get_filters()
    assert len(filters) == 1
    assert filters[0].name == "連番"
    assert sorted(filters[0].values, key=int) == ["1", "2", "3"]

    # 連番の数字ラベル（軸見出し）は隠す（2026-09-23、ユーザーの指摘。ラベルのマークで
    # 項目名を出すので、軸の数字を見せる意味が無い）。
    label_display = workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='ウォーターフォール']/table/style"
        "/style-rule[@element='label']/format[@attr='display']"
    )
    assert len(label_display) == 1
    assert label_display[0].get("value") == "false"
    assert label_display[0].get("field") == f"[{DATASOURCE_ID}].[none:連番:ok]"

    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_metric_with_connectors_uses_odd_positions(tmp_path) -> None:
    """`connectors=True`: 奇数番号に指標、偶数番号は値 0 の連結枠（2026-09-23）。

    値 0 の Gantt バーは長さが無いので薄い横線に見える。種別は 0 のときだけ固定で
    「連結」、それ以外は符号で「増加」/「減少」。
    """
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上", "今月原価"],
        connectors=True,
    )

    assert metric.count == 3
    assert metric.used_index == 5  # 1, 3, 5 が指標、2, 4 が連結枠

    assert metric.value.formula == (
        "CASE ATTR([連番])\n"
        "    WHEN 1 THEN SUM([前月残])\n"
        "    WHEN 3 THEN SUM([今月売上])\n"
        "    WHEN 5 THEN SUM([今月原価])\n"
        "    WHEN 2 THEN 0\n"
        "    WHEN 4 THEN 0\n"
        "END"
    )
    assert metric.label.formula == (
        "CASE [連番]\n"
        '    WHEN 1 THEN "前月残"\n'
        '    WHEN 3 THEN "今月売上"\n'
        '    WHEN 5 THEN "今月原価"\n'
        "END"
    )
    assert metric.kind.formula == (
        'IF [残高_値] = 0 THEN "連結"\n'
        'ELSEIF [残高_値] > 0 THEN "増加"\n'
        'ELSE "減少"\n'
        "END"
    )
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_chart_with_connectors_filters_all_positions_and_maps_the_color(
    tmp_path,
) -> None:
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上"],
        connectors=True,
    )

    worksheet = workbook.build_waterfall_chart(
        datasource,
        name="ウォーターフォール連結",
        index="連番",
        metric=metric,
        connector_color="#cccccc",
    )

    filters = worksheet.get_filters()
    assert len(filters) == 1
    # count=2 の連結枠は 1, 2, 3（1, 3 が指標、2 が連結枠）
    assert sorted(filters[0].values, key=int) == ["1", "2", "3"]

    style = worksheet._resolve_element().xpath(
        ".//*[local-name()='style-rule'][@element='mark']"
        "/*[local-name()='encoding'][@attr='color']/*[local-name()='map'][@to='#cccccc']"
        "/*[local-name()='bucket']"
    )
    assert [bucket.text for bucket in style] == ['"連結"']
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_metric_with_landing_adds_a_closing_bar(tmp_path) -> None:
    """`landing=True`: 選んだ指標すべての合計をマイナスで足し、累計を 0 まで戻す
    「着地」バーを最後に足す（2026-09-23、ユーザーの手作業の例に合わせた）。
    """
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上", "今月原価"],
        landing=True,
    )

    assert metric.count == 3
    assert metric.used_index == 4  # 1, 2, 3 が指標、4 が着地

    assert metric.value.formula == (
        "CASE ATTR([連番])\n"
        "    WHEN 1 THEN SUM([前月残])\n"
        "    WHEN 2 THEN SUM([今月売上])\n"
        "    WHEN 3 THEN SUM([今月原価])\n"
        "    WHEN 4 THEN -SUM([前月残])-SUM([今月売上])-SUM([今月原価])\n"
        "END"
    )
    assert metric.label.formula == (
        "CASE [連番]\n"
        '    WHEN 1 THEN "前月残"\n'
        '    WHEN 2 THEN "今月売上"\n'
        '    WHEN 3 THEN "今月原価"\n'
        '    WHEN 4 THEN "着地"\n'
        "END"
    )
    assert metric.kind.formula == (
        'IF ATTR([連番]) = 4 THEN "着地"\n'
        'ELSEIF [残高_値] >= 0 THEN "増加"\n'
        'ELSE "減少"\n'
        "END"
    )
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_metric_with_connectors_and_landing(tmp_path) -> None:
    """`connectors=True` と `landing=True` を両方使うと、着地の手前にも連結枠を挟む。"""
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上", "今月原価"],
        connectors=True,
        landing=True,
    )

    assert metric.used_index == 7  # 1,3,5 が指標、2,4,6 が連結枠、7 が着地

    assert metric.value.formula == (
        "CASE ATTR([連番])\n"
        "    WHEN 1 THEN SUM([前月残])\n"
        "    WHEN 3 THEN SUM([今月売上])\n"
        "    WHEN 5 THEN SUM([今月原価])\n"
        "    WHEN 2 THEN 0\n"
        "    WHEN 4 THEN 0\n"
        "    WHEN 6 THEN 0\n"
        "    WHEN 7 THEN -SUM([前月残])-SUM([今月売上])-SUM([今月原価])\n"
        "END"
    )
    assert metric.kind.formula == (
        'IF ATTR([連番]) = 7 THEN "着地"\n'
        'ELSEIF [残高_値] = 0 THEN "連結"\n'
        'ELSEIF [残高_値] > 0 THEN "増加"\n'
        'ELSE "減少"\n'
        "END"
    )
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_chart_with_landing_filters_and_maps_the_color(tmp_path) -> None:
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    metric = workbook.build_waterfall_metric(
        datasource,
        name="残高",
        index="連番",
        metrics=["前月残", "今月売上"],
        landing=True,
    )

    worksheet = workbook.build_waterfall_chart(
        datasource,
        name="ウォーターフォール着地",
        index="連番",
        metric=metric,
        landing_color="#4263eb",
    )

    filters = worksheet.get_filters()
    assert len(filters) == 1
    # count=2 の着地枠は 1, 2, 3（3 が着地）
    assert sorted(filters[0].values, key=int) == ["1", "2", "3"]

    style = worksheet._resolve_element().xpath(
        ".//*[local-name()='style-rule'][@element='mark']"
        "/*[local-name()='encoding'][@attr='color']/*[local-name()='map'][@to='#4263eb']"
        "/*[local-name()='bucket']"
    )
    assert [bucket.text for bucket in style] == ['"着地"']
    assert not [message for message in workbook.validate() if message.severity == "error"]


# ---------------------------------------------------------------------------
# build_waterfall(): 設定画面向けの一括版（①〜④を 1 回で実行）。
# ---------------------------------------------------------------------------

RELATION_ORDERS_OBJECT_ID = "Orders_E82A0D784F4E42B1A8CF60FF78680595"


def _relation_datasource_workbook(tmp_path):
    """`add_index_relation()` が前提にする federated + object-graph の最小構成。
    `tests/test_waterfall_relation.py` の fixture と同じ形。"""
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
              <column datatype="real" name="Profit" ordinal="2" />
            </columns>
          </relation>
        </relation>
      </connection>
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
      <extract count="-1" enabled="true" object-id="" units="records" user-specific="false">
        <connection class="hyper" dbname="C:/temp/extract.hyper" schema="Extract" tablename="Extract">
          <relation type="collection">
            <relation name="{RELATION_ORDERS_OBJECT_ID}" table="[Extract].[{RELATION_ORDERS_OBJECT_ID}]" type="table" />
          </relation>
          <cols>
            <map key="[Category]" value="[{RELATION_ORDERS_OBJECT_ID}].[Category]" />
            <map key="[Sales]" value="[{RELATION_ORDERS_OBJECT_ID}].[Sales]" />
            <map key="[Profit]" value="[{RELATION_ORDERS_OBJECT_ID}].[Profit]" />
          </cols>
        </connection>
      </extract>
      <object-graph>
        <objects>
          <object caption="Orders" id="{RELATION_ORDERS_OBJECT_ID}">
            <properties context="">
              <relation connection="excel-direct.1wk7x6i16gwroz19147dy1u57n1l" name="Orders" table="[Orders$]" type="table">
                <columns header="yes">
                  <column datatype="string" name="Category" ordinal="0" />
                  <column datatype="real" name="Sales" ordinal="1" />
                  <column datatype="real" name="Profit" ordinal="2" />
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


def test_build_waterfall_creates_the_shared_relation_metric_and_chart(tmp_path) -> None:
    """共有連番テーブルが無ければ ① を自動で行い、②③④まで 1 回で組み上げる。"""
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    worksheet = workbook.build_waterfall(
        datasource,
        name="残高",
        metrics=["売上", "利益"],
    )

    assert datasource.get_fields(name="連番")[0].role == "dimension"
    assert (tmp_path / "twbpatch_waterfall_index.txt").read_text(encoding="utf-8").splitlines()[
        1:
    ] == [str(index) for index in range(1, 22)]
    assert [field.name for field in datasource.get_fields() if field.name.startswith("残高_")] == [
        "残高_値",
        "残高_項目名",
        "残高_種別",
        "残高_サイズ",
    ]
    assert worksheet.get_panes()[0].mark_type == "gantt"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_reruns_cleanly_when_the_source_twb_is_reopened_without_saving(
    tmp_path,
) -> None:
    """`apply_config()` は毎回 source の .twb を開き直して別名で保存する運用があり得る
    （source 自体は変更しない、`scripts/03_apply_dashboard.py` の運用）。この場合、対象
    データソースには毎回「連番」がまだ無い状態になるが、.txt ファイルは前回の実行で
    既にディスクへ書かれて残っている。ファイルの中身は常に同じ（1..21）なので、
    別名へ逃げるのではなく上書きしてよい（2026-09-23、実機で確認したバグ修正。
    「既にあるなら追加しない」は連番フィールドの有無で判定するので、ファイルの重複だけを
    理由に別名にするのは筋が違うという指摘を受けた）。
    """
    workbook1 = _relation_datasource_workbook(tmp_path)
    datasource1 = workbook1.get_datasources(name=DATASOURCE_NAME)[0]
    workbook1.build_waterfall(datasource1, name="残高", metrics=["売上", "利益"])
    # workbook1 は保存しない。source の waterfall.twb 自体はまだ「連番」を持たない。

    workbook2 = TwbWorkbook.open(str(tmp_path / "waterfall.twb"))
    datasource2 = workbook2.get_datasources(name=DATASOURCE_NAME)[0]
    assert not datasource2.get_fields(name="連番")

    worksheet = workbook2.build_waterfall(datasource2, name="残高2", metrics=["売上", "利益"])

    assert datasource2.get_fields(name="連番")
    assert (tmp_path / "twbpatch_waterfall_index.txt").exists()
    assert not (tmp_path / "twbpatch_waterfall_index_2.txt").exists()
    assert worksheet.get_panes()[0].mark_type == "gantt"
    assert not [message for message in workbook2.validate() if message.severity == "error"]


def test_build_waterfall_skips_calculated_fields_when_choosing_join_to(tmp_path) -> None:
    """`metrics[0]` が計算フィールドでも ① の `join_to` に選ばない（2026-09-23、実機で
    確認したバグ修正）。計算フィールドは `<extract>` の cols マップに乗らないため、
    そのまま `join_to` に使うと `add_index_relation()` が `UnsupportedFeatureError` に
    なっていた。metrics の中の物理フィールドを探して使う。
    """
    workbook = _relation_datasource_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="利益率", formula="SUM([Profit])/SUM([Sales])", datatype="real", role="measure"
    )

    worksheet = workbook.build_waterfall(
        datasource,
        name="残高",
        metrics=["利益率", "売上"],
    )

    assert datasource.get_fields(name="連番")
    assert worksheet.get_panes()[0].mark_type == "gantt"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_reuses_an_existing_shared_index_field(tmp_path) -> None:
    """データソースに既に `連番` があれば ① をスキップし、そのまま使い回す。

    2 つ目のウォーターフォールを同じデータソースへ足すケースに相当する
    （2026-09-23、ユーザー承認の「共有テーブル方式」）。
    """
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    worksheet = workbook.build_waterfall(
        datasource,
        name="残高2",
        metrics=["前月残", "今月売上"],
    )

    # ① は走らない（federated 前提が無いこの datasource で例外にならないことがその証拠）。
    assert [field.name for field in datasource.get_fields() if field.name.startswith("残高2_")] == [
        "残高2_値",
        "残高2_項目名",
        "残高2_種別",
        "残高2_サイズ",
    ]
    columns_fields = [field.name for field in worksheet.get_fields() if field.shelf == "columns"]
    assert columns_fields == ["連番"]
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_build_waterfall_fixes_the_connector_color(tmp_path) -> None:
    """`connector_color` は画面に出さない固定値 `#cccccc`。"""
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    worksheet = workbook.build_waterfall(
        datasource,
        name="残高3",
        metrics=["前月残", "今月売上"],
        connectors=True,
    )

    style = worksheet._resolve_element().xpath(
        ".//*[local-name()='style-rule'][@element='mark']"
        "/*[local-name()='encoding'][@attr='color']/*[local-name()='map'][@to='#cccccc']"
        "/*[local-name()='bucket']"
    )
    assert [bucket.text for bucket in style] == ['"連結"']


def test_build_waterfall_rejects_metrics_too_long_for_the_shared_table(tmp_path) -> None:
    """共有連番テーブルの容量（21）を超える構成は、フィールドを作る前に止める。"""
    workbook = _waterfall_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    metrics = [f"m{i}" for i in range(11)]
    for metric_name in metrics:
        datasource._resolve_element().append(
            ET.fromstring(
                f'<column name="[{metric_name}]" datatype="real" role="measure" type="quantitative" />'
            )
        )

    with pytest.raises(ValueError, match="used_index"):
        workbook.build_waterfall(
            datasource,
            name="残高4",
            metrics=metrics,
            connectors=True,
            landing=True,
        )
    # 検証で止まるので、計算フィールドは 1 つも作られない。
    assert not [field for field in datasource.get_fields() if field.name.startswith("残高4_")]
