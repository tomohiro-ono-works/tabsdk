import pytest

from twbpatch import NotFoundError, TwbWorkbook


DATASOURCE_ID = "federated.00vlmup0b8v7m212i5x9f03fouo2"
DATASOURCE_NAME = "Orders++ (sample_-_superstore)"


def _superstore_workbook(tmp_path):
    """実ワークブックを模した最小構成。

    データソースの `@name` は Tableau が実際に付ける `federated.xxx` 形式にしてある。
    `draw_*` が組み立てる参照文字列がこの形式を前提にしているため。
    """
    path = tmp_path / "superstore.twb"
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="{DATASOURCE_ID}" caption="{DATASOURCE_NAME}">
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Sub-Category]" caption="サブカテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Order Date]" caption="注文日" datatype="date" role="dimension" type="ordinal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_draw_methods_with_a_datasource_accept_plain_field_names(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    sheet = workbook.draw_sheet(
        datasource,
        name="API_一覧",
        items=["カテゴリ", "サブカテゴリ"],
    )
    bar = workbook.draw_bar(
        datasource,
        name="API_棒",
        item="サブカテゴリ",
        metric="売上",
    )
    card = workbook.draw_card(
        datasource,
        name="API_カード",
        main_metric="売上",
        sub_metric="利益",
    )

    assert {field.shelf for field in sheet.get_fields()} == {"rows"}
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='API_一覧']/table/rows)"
    ) == (
        f"[{DATASOURCE_ID}].[none:Category:nk]"
        f" / [{DATASOURCE_ID}].[none:Sub-Category:nk]"
    )
    assert bar.get_panes()[0].mark_type == "bar"
    assert card.get_panes()[0].mark_type == "automatic"
    assert card.get_panes()[0].customized_label == {
        "main_metric": "売上",
        "sub_metric": "利益",
        "main_color": "#602fff",
        "value_color": "#333333",
    }
    assert [field.encoding for field in card.get_fields()] == ["label", "label"]
    assert not [message for message in workbook.validate() if message.severity == "error"]

    with pytest.raises(NotFoundError, match="field not found"):
        workbook.draw_bar(
            datasource,
            name="API_不正",
            item="存在しない項目",
            metric="売上",
        )
    assert workbook.get_worksheets(name="API_不正") == []


def test_draw_bar_without_an_item_draws_a_single_bar(tmp_path) -> None:
    """項目は任意。省くとディメンションを置かず、並べ替えもしない（2026-09-22）。"""
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    bar = workbook.draw_bar(datasource, name="API_棒_項目なし", metric="売上")

    element = bar._resolve_element()
    assert (element.findtext("./table/rows") or "") == ""
    assert (element.findtext("./table/cols") or "") == f"[{DATASOURCE_ID}].[sum:Sales:qk]"
    assert element.findall("./table/view/computed-sort") == []
    assert bar.get_panes()[0].mark_type == "bar"
    assert not [message for message in workbook.validate() if message.severity == "error"]

    # 画面は使わない引数を空文字で渡してくるので、空も「指定なし」として扱う
    workbook.draw_bar(datasource, name="API_棒_空文字", item="", metric="売上")
    assert (
        workbook.get_worksheets(name="API_棒_空文字")[0]._resolve_element().findtext(
            "./table/rows"
        )
        or ""
    ) == ""


def test_draw_bar_places_an_aggregated_calculation_as_agg(tmp_path) -> None:
    """式の中に集計関数があるメジャーは、合計ではなく集計（`usr:`）として置く
    （2026-09-22 修正）。

    棒グラフだけ `aggregation="sum"` に固定していたため、
    `SUM([売上]) / SUM([利益])` のような計算フィールドが二重に集計されていた。
    ほかのグラフは以前から `"auto"` で自動判定している。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="売上(昨年比)",
        formula="SUM([Sales]) / SUM([Profit])",
        datatype="real",
        role="measure",
    )
    ratio = datasource.get_fields(name="売上(昨年比)")[0]

    aggregated = workbook.draw_bar(
        datasource, name="API_昨年比", item="サブカテゴリ", metric="売上(昨年比)"
    )
    plain = workbook.draw_bar(
        datasource, name="API_売上", item="サブカテゴリ", metric="売上"
    )
    forced = workbook.draw_bar(
        datasource, name="API_合計固定", item="サブカテゴリ",
        metric="売上(昨年比)", aggregation="sum",
    )

    token = ratio.id.strip("[]")
    # 置いたピルも、並べ替えの基準も集計（usr:）にそろえる
    assert aggregated._resolve_element().findtext("./table/cols") == (
        f"[{DATASOURCE_ID}].[usr:{token}:qk]"
    )
    assert aggregated._resolve_element().xpath(
        "string(./table/view/computed-sort/@using)"
    ) == f"[{DATASOURCE_ID}].[usr:{token}:qk]"
    assert aggregated._resolve_element().xpath(
        "./table/view/datasource-dependencies/column-instance"
        f"[@name='[usr:{token}:qk]']/@derivation"
    ) == ["User"]
    # ふつうのメジャーは今までどおり合計
    assert plain._resolve_element().findtext("./table/cols") == (
        f"[{DATASOURCE_ID}].[sum:Sales:qk]"
    )
    # 明示的に渡した集計はそのまま使う
    assert forced._resolve_element().findtext("./table/cols") == (
        f"[{DATASOURCE_ID}].[sum:{token}:qk]"
    )
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_bar_sub_metric_builds_a_synchronized_bar_in_bar(tmp_path) -> None:
    """バーインバーは二重軸。軸を同期し、内側の棒を細くする（2026-09-22）。

    Tableau の書き方は実ワークブックで確認した。シェルフは `+` で連結し、
    2 本目の軸へ `fold="true"`、描画は軸ごとのペインが持つ。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    bar = workbook.draw_bar(
        datasource,
        name="API_バーインバー",
        item="サブカテゴリ",
        metric="売上",
        sub_metric="利益",
        bar_color="#2f3b52",
        sub_bar_color="#94a3b8",
    )

    element = bar._resolve_element()
    assert element.findtext("./table/cols") == (
        f"([{DATASOURCE_ID}].[sum:Sales:qk] + [{DATASOURCE_ID}].[sum:Profit:qk])"
    )
    folds = element.xpath(
        "./table/style/style-rule[@element='axis']/encoding[@fold='true']"
    )
    assert [(item.get("field"), item.get("scope"), item.get("synchronized"))
            for item in folds] == [
        (f"[{DATASOURCE_ID}].[sum:Profit:qk]", "cols", "true")
    ]
    panes = element.findall("./table/panes/pane")
    assert [pane.get("x-axis-name") for pane in panes] == [
        None,
        f"[{DATASOURCE_ID}].[sum:Sales:qk]",
        f"[{DATASOURCE_ID}].[sum:Profit:qk]",
    ]
    assert [pane.find("mark").get("class") for pane in panes] == ["Bar", "Bar", "Bar"]
    # マークの色と太さは軸ごとのペインが持つ。内側（サブ）の棒だけ細くする
    def mark_format(index: int, attr: str) -> list[str]:
        return panes[index].xpath(
            f"./style/style-rule[@element='mark']/format[@attr='{attr}']/@value"
        )

    assert mark_format(1, "mark-color") == ["#2f3b52"]
    assert mark_format(2, "mark-color") == ["#94a3b8"]
    assert mark_format(1, "size") == []
    assert mark_format(2, "size") == ["0.5"]
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_bar_line_metric_puts_a_line_on_the_second_axis(tmp_path) -> None:
    """折れ線は二重軸の 2 本目。単位が違うので軸は同期しない（2026-09-22）。"""
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    bar = workbook.draw_bar(
        datasource,
        name="API_折れ線付き",
        item="サブカテゴリ",
        metric="売上",
        line_metric="利益",
        line_color="#e03131",
    )

    element = bar._resolve_element()
    folds = element.xpath(
        "./table/style/style-rule[@element='axis']/encoding[@fold='true']"
    )
    # 同期しないときは属性を書かない（Tableau も書いていない）
    assert [item.get("synchronized") for item in folds] == [None]
    panes = element.findall("./table/panes/pane")
    assert [pane.find("mark").get("class") for pane in panes] == ["Bar", "Bar", "Line"]
    assert panes[2].xpath(
        "./style/style-rule[@element='mark']/format[@attr='mark-color']/@value"
    ) == ["#e03131"]
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_bar_with_three_metrics_uses_measure_values(tmp_path) -> None:
    """棒 2 本と折れ線を同時に出すときは、棒の軸をメジャーバリューにまとめる
    （2026-09-22）。Tableau の二重軸は 2 軸までなので、3 本目の置き場がない。

    メジャーバリューの棒は既定で積み上がるため、スタックを外して重ねる。
    `<breakdown value="off">` は公式スキーマ（`StackingMode-ST`）で確認した。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="達成率", formula="SUM([Sales]) / SUM([Profit])", datatype="real",
        role="measure",
    )

    bar = workbook.draw_bar(
        datasource,
        name="API_三つとも",
        item="サブカテゴリ",
        metric="売上",
        sub_metric="利益",
        line_metric="達成率",
        line_color="#e03131",
    )

    element = bar._resolve_element()
    names = f"[{DATASOURCE_ID}].[:Measure Names]"
    # 棒はメジャーバリューの 1 本のピル、折れ線が 2 本目の軸
    assert element.findtext("./table/cols").startswith(
        f"([{DATASOURCE_ID}].[Multiple Values] + "
    )
    members = element.xpath(
        "./table/view/filter[@column=$column]/groupfilter[@function='union']"
        "/groupfilter/@member",
        column=names,
    )
    # メジャーバリューの中身も、メジャーごとに集計を決める（2026-09-22）
    assert members == [
        f'"[{DATASOURCE_ID}].[sum:Sales:qk]"',
        f'"[{DATASOURCE_ID}].[sum:Profit:qk]"',
    ]
    assert element.xpath("./table/view/slices/column/text()") == [names]

    panes = element.findall("./table/panes/pane")
    assert [pane.find("mark").get("class") for pane in panes] == ["Bar", "Bar", "Line"]
    # スタックは棒の側だけ外す
    assert [pane.find("./view/breakdown").get("value") for pane in panes] == [
        "off", "off", "auto",
    ]
    # メジャーネームの色は、メジャーバリューの軸のペインにだけ載せる。
    # 折れ線の軸に載せると折れ線まで色で分かれてしまう
    assert [
        [color.get("column") for color in pane.findall("./encodings/color")]
        for pane in panes
    ] == [[], [names], []]
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_workbook_draw_methods_accept_datasource_field_tuples(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    datasource_name = DATASOURCE_NAME

    sheet = workbook.draw_sheet(
        name="API_タプル一覧",
        items=[
            (datasource_name, "カテゴリ"),
            (datasource_name, "サブカテゴリ"),
        ],
    )
    bar = workbook.draw_bar(
        name="API_タプル棒",
        item=(datasource_name, "サブカテゴリ"),
        metric=(datasource_name, "売上"),
    )
    card = workbook.draw_card(
        name="API_タプルカード",
        main_metric=(datasource_name, "売上"),
        sub_metric=(datasource_name, "利益"),
    )

    assert {field.shelf for field in sheet.get_fields()} == {"rows"}
    assert bar.get_panes()[0].mark_type == "bar"
    assert card.get_panes()[0].customized_label["main_metric"] == "売上"


def test_workbook_draw_bar_applies_bar_color(tmp_path) -> None:
    """`bar_color` を指定すると棒の色に反映される（2026-09-12 追加）。

    以前は draw_bar に色を指定する引数が無く、常に既定色で描画されていた。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    workbook.draw_bar(datasource, name="色指定なし", item="カテゴリ", metric="売上")
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='色指定なし']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-color']/@value"
    ) == []

    bar = workbook.draw_bar(
        datasource,
        name="色指定あり",
        item="カテゴリ",
        metric="売上",
        item_shelf="columns",
        bar_color="#602fff",
    )
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='色指定あり']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-color']/@value"
    ) == ["#602fff"]
    assert bar.get_panes()[0].mark_type == "bar"


def test_draw_card_aggregates_row_level_calculated_fields(tmp_path) -> None:
    """計算フィールドでも、式が集計関数を含まなければ通常どおり集計する
    （2026-09-12 追加）。

    以前は `field.is_calculated` だけを見て一律「集計済み扱い（derivation=User）」
    にしていたため、`IIF(...)` のような行レベルの式を持つ計算フィールドを指標に
    使うと、集計されずに明細がそのまま出てしまっていた。式が SUM/AVG/COUNT/COUNTD
    などの集計関数を含む場合だけ「集計済み」とみなし、含まない場合は通常のフィールドと
    同じ既定集計（SUM）を適用する。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="行レベル売上", formula="IIF(1=1, [Sales], 0)", datatype="real", role="measure"
    )
    datasource.create_calculated_field(
        name="集計済み利益", formula="SUM([Profit])", datatype="real", role="measure"
    )

    row_level = workbook.draw_card(datasource, name="行レベルカード", main_metric="行レベル売上")
    aggregated = workbook.draw_card(datasource, name="集計済みカード", main_metric="集計済み利益")

    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='行レベルカード']"
        "//column-instance/@derivation"
    ) == ["Sum"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='集計済みカード']"
        "//column-instance/@derivation"
    ) == ["User"]
    assert row_level.get_panes()[0].mark_type == "automatic"
    assert aggregated.get_panes()[0].mark_type == "automatic"


def test_workbook_draw_bar_resolves_fields_from_different_datasources(tmp_path) -> None:
    source = tmp_path / "multi-datasource.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="products" caption="商品データ">
      <column name="[Sub-Category]" caption="サブカテゴリ"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
    <datasource name="sales" caption="売上データ">
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))

    worksheet = workbook.draw_bar(
        name="データソース横断",
        item=("商品データ", "サブカテゴリ"),
        metric=("売上データ", "売上"),
    )

    assert worksheet.get_panes()[0].mark_type == "bar"
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='データソース横断']"
        "/table/view/datasources/datasource/@name"
    ) == ["products", "sales"]
    sort = workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='データソース横断']"
        "/table/view/computed-sort"
    )[0]
    assert sort.get("column").startswith("[products].")
    assert sort.get("using").startswith("[sales].")


def test_draw_card_title_bar_shows_background_without_text(tmp_path) -> None:
    """スコアカードのタイトルバーは帯（背景色）だけ表示し、文字は入れない
    （2026-09-12 変更）。

    以前はプレースホルダーとして "-" という文字を入れており、Tableau で
    実際に開くとタイトルバーにその文字が見えてしまっていた。
    """
    workbook = _superstore_workbook(tmp_path)
    card = workbook.draw_card(name="タイトル確認", main_metric="売上")

    assert card.title is None
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='タイトル確認']"
        "/layout-options/title/formatted-text/run)"
    ) == ""
    assert card.title_style["background_color"] == "#602fff"
    # 指標名の前に全角スペースを 1 つ入れて左端から離す（2026-09-21 追加）
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='タイトル確認']"
        "//customized-label/formatted-text/run[1])"
    ) == "　売上"


def test_draw_card_chooses_aggregation_per_metric() -> None:
    workbook = TwbWorkbook.open("tests/sample_minimal.twb")
    datasource = workbook.get_datasources()[0]
    calculated = datasource.create_calculated_field(
        name="集計済み売上",
        formula="SUM([売上])",
        datatype="real",
    )

    card = workbook.draw_card(
        name="API_自動集計カード",
        main_metric=calculated,
        sub_metric=(datasource.name, "売上"),
    )

    assert {field.name: field.aggregation for field in card.get_fields()} == {
        "売上": "sum",
        "集計済み売上": "agg",
    }


def test_draw_quadrant_builds_scatter_medians_and_four_colors(tmp_path) -> None:
    source = tmp_path / "quadrant.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="商品データ">
      <column name="[Sub-Category]" caption="サブカテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Profit]" caption="利益"
              datatype="real" role="measure" type="quantitative" />
      <column name="[Quantity]" caption="数量"
              datatype="integer" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))
    datasource = workbook.get_datasources()[0]
    profit_ratio = datasource.create_calculated_field(
        name="利益率",
        formula="SUM([利益]) / SUM([売上])",
        datatype="real",
    )
    product_count = datasource.create_calculated_field(
        name="商品数",
        formula="COUNTD([サブカテゴリ])",
        datatype="integer",
    )

    worksheet = workbook.draw_quadrant(
        name="商品ポジショニング",
        title="商品ポジショニングマップ",
        item=("商品データ", "サブカテゴリ"),
        x_metric=("商品データ", "売上"),
        y_metric=profit_ratio,
        size_metric=product_count,
        colors=("#111111", "#222222", "#333333", "#444444"),
    )

    assert worksheet.get_panes()[0].mark_type == "circle"
    assert worksheet.title == "商品ポジショニングマップ"
    assert {
        field.shelf: field.aggregation
        for field in worksheet.get_fields()
        if field.shelf and field.shelf != "filters"
    } == {
        "columns": "sum",
        "rows": "agg",
    }
    assert next(field for field in worksheet.get_fields() if field.encoding == "size").aggregation == "agg"
    assert worksheet.get_panes()[0].mark_opacity == pytest.approx(0.6, abs=0.01)
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-transparency']/@value)"
    ) == "206"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/mark-sizing/@mark-sizing-setting)"
    ) == "marks-scaling-off"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='size']/@value)"
    ) == "4"
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/view/datasource-dependencies/column-instance"
        "[@column=$field]/@derivation",
        field=profit_ratio.id,
    ) == ["User"]
    color = next(field for field in worksheet.get_fields() if field.encoding == "color")
    assert color.table_calculation == "field"
    assert worksheet.get_panes()[0].get_categorical_colors(color) == {
        "1": "#111111",
        "2": "#222222",
        "3": "#333333",
        "4": "#444444",
    }
    datasource_color_ref = f"[usr:{color.field_id.strip('[]')}:nk:2]"
    assert workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$datasource]"
        "/column-instance[@name=$reference]/@column",
        datasource=datasource.id,
        reference=datasource_color_ref,
    ) == [color.field_id]
    datasource_palette = workbook.tree.xpath(
        "/workbook/datasources/datasource[@name=$datasource]"
        "/style/style-rule[@element='mark']"
        "/encoding[@attr='color'][@field=$reference]/map",
        datasource=datasource.id,
        reference=datasource_color_ref,
    )
    assert {
        mapping.findtext("bucket", "").strip('"'): mapping.get("to")
        for mapping in datasource_palette
    } == {
        "1": "#111111",
        "2": "#222222",
        "3": "#333333",
        "4": "#444444",
    }
    assert [line.formula for line in worksheet.get_reference_lines()] == [
        "median",
        "median",
        "median",
    ]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@z-order"
    ) == ["1", "1", "2"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@probability"
    ) == ["95", "95", "95"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@scope"
    ) == ["per-table", "per-table", "per-pane"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@label-type"
    ) == ["value", "value", "automatic"]
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/panes/pane/reference-line/@enable-instant-analytics"
    ) == ["true", "true", "true"]
    quadrant = workbook.get_datasources()[0].get_fields(name="商品ポジショニング_四象限")[0]
    assert "WINDOW_MEDIAN(SUM([Sales]))" in (quadrant.raw_formula or "")
    assert "WINDOW_MEDIAN([Calculation_" in (quadrant.raw_formula or "")
    assert quadrant.hidden is False
    assert workbook.tree.xpath(
        "string(/workbook/datasources/datasource/column[@name=$field]/@hidden)",
        field=quadrant.id,
    ) == ""
    assert quadrant.role == "measure"
    assert workbook.tree.xpath(
        "string(/workbook/datasources/datasource/column[@name=$field]"
        "/calculation/table-calc/@ordering-type)",
        field=quadrant.id,
    ) == "Rows"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/view/datasource-dependencies/column[@name=$field]"
        "/calculation/table-calc/@ordering-type)",
        field=quadrant.id,
    ) == "Rows"
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='商品ポジショニング']"
        "/table/view/datasource-dependencies/column-instance[@column=$field]"
        "/table-calc/@ordering-field)",
        field=quadrant.id,
    ) == f"[{datasource.id}].{datasource.get_fields(name='サブカテゴリ')[0].id}"
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_sheet_aligns_numbers_right_and_text_left(tmp_path) -> None:
    """帳票は数字を右、文字を左に揃える（2026-09-22 指定）。

    Tableau は不連続のピルの揃えを `style-rule element="label"` に
    `field` 付きで書く（examples/サンプル.twb と実ダッシュボードで確認）。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    worksheet = workbook.draw_sheet(
        datasource, name="帳票_揃え", items=["カテゴリ", "注文日", "売上"]
    )

    # 表ヘッダー（フィールドラベル）は薄い灰色（2026-09-22 指定）
    assert worksheet.table_style["header_background"] == "#f0f0f0"
    aligns = worksheet._resolve_element().xpath(
        "./table/style/style-rule[@element='label']/format[@attr='text-align']"
    )
    assert [(item.get("field"), item.get("value")) for item in aligns] == [
        (f"[{DATASOURCE_ID}].[none:Category:nk]", "left"),
        (f"[{DATASOURCE_ID}].[none:Order Date:nk]", "left"),
        (f"[{DATASOURCE_ID}].[sum:Sales:ok]", "right"),
    ]
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_sheet_adds_bar_and_color_columns(tmp_path) -> None:
    """帳票へ棒と色帯の列を足す（2026-09-22 追加）。

    examples/サンプル.twb の作りに合わせた。軸は重ねず横に並べる（`fold` を
    書かない）ので、列は何本でも足せる。色帯は「常に 1」の軸（0〜1 に固定して
    隠す）へ、長さ `MIN(-1)` のガントバーを置き、色にメジャーを載せる。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    worksheet = workbook.draw_sheet(
        datasource,
        name="帳票_棒と色",
        items=["カテゴリ", "売上"],
        bar_metrics=["売上"],
        color_metrics=["利益"],
        bar_colors=["#2f3b52"],
        color_starts=["#f6f8fc"],
        color_ends=["#1d3557"],
    )

    element = worksheet._resolve_element()
    band = datasource.get_fields(name="帳票_棒と色_色帯1")[0]
    width = datasource.get_fields(name="帳票_棒と色_色帯幅1")[0]
    assert band.formula == "MIN(1)" and width.formula == "MIN(-1)"
    # 列は軸ごとに分かれる。重ねないので fold は書かない
    assert element.findtext("./table/cols") == (
        f"([{DATASOURCE_ID}].[sum:Sales:qk]"
        f" + [{DATASOURCE_ID}].[usr:{band.id.strip('[]')}:qk])"
    )
    assert element.xpath(
        "./table/style/style-rule[@element='axis']/encoding[@fold='true']"
    ) == []
    # 軸は両方とも隠し、色帯の軸だけ 0〜1 に固定する
    assert [
        (item.get("field"), item.get("value"))
        for item in element.xpath(
            "./table/style/style-rule[@element='axis']/format[@attr='display']"
        )
    ] == [
        (f"[{DATASOURCE_ID}].[sum:Sales:qk]", "false"),
        (f"[{DATASOURCE_ID}].[usr:{band.id.strip('[]')}:qk]", "false"),
    ]
    assert [
        (item.get("min"), item.get("max"), item.get("range-type"))
        for item in element.xpath(
            "./table/style/style-rule[@element='axis']/encoding[@range-type='fixed']"
        )
    ] == [("0", "1", "fixed")]
    # 土台 / 棒 / 色帯 の 3 ペイン
    panes = element.findall("./table/panes/pane")
    assert [pane.find("mark").get("class") for pane in panes] == [
        "Automatic", "Bar", "GanttBar",
    ]
    # 値はラベル（text）で出す。列へ置いただけでは数字が見えない（2026-09-22）
    assert [
        (child.tag, child.get("column")) for child in panes[2].findall("./encodings/*")
    ] == [
        ("color", f"[{DATASOURCE_ID}].[sum:Profit:qk]"),
        ("size", f"[{DATASOURCE_ID}].[usr:{width.id.strip('[]')}:qk]"),
        ("text", f"[{DATASOURCE_ID}].[sum:Profit:qk]"),
    ]
    assert [
        (child.tag, child.get("column")) for child in panes[1].findall("./encodings/*")
    ] == [("text", f"[{DATASOURCE_ID}].[sum:Sales:qk]")]
    for pane in panes[1:]:
        assert [
            (item.get("attr"), item.get("value"))
            for item in pane.xpath("./style/style-rule[@element='mark']/format")
            if item.get("attr").startswith("mark-labels")
        ] == [("mark-labels-show", "true"), ("mark-labels-cull", "true")]
        assert pane.xpath(
            "./style/style-rule[@element='cell']/format[@attr='text-align']/@value"
        ) == ["right"]
    # 色は独自の 2 色（薄い側 → 濃い側）の濃淡（2026-09-22 指定）
    encodings = element.xpath(
        "./table/style/style-rule[@element='mark']/encoding[@attr='color']"
    )
    assert [(item.get("field"), item.get("type")) for item in encodings] == [
        (f"[{DATASOURCE_ID}].[sum:Profit:qk]", "interpolated")
    ]
    palette_name = encodings[0].get("palette")
    assert palette_name.startswith("twbpatch-")
    palettes = workbook.tree.getroot().xpath(
        "/workbook/preferences/color-palette[@name=$name]", name=palette_name
    )
    assert [item.get("type") for item in palettes] == ["ordered-sequential"]
    assert [color.text for color in palettes[0]] == ["#f6f8fc", "#1d3557"]
    # 棒は 1 色
    assert panes[1].xpath(
        "./style/style-rule[@element='mark']/format[@attr='mark-color']/@value"
    ) == ["#2f3b52"]
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_quadrant_rebuilds_its_own_calculated_field(tmp_path) -> None:
    """`{シート名}_四象限` はそのシートの持ち物なので、同名があれば作り直す
    （2026-09-22。カードの予実比較と同じ扱いへ揃えた）。

    以前は `caption already exists` で止まり、設定 YAML の `calculations` 節で
    同じ名前を定義していても四象限を描けなかった。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="象限_四象限", formula='"古い式"', datatype="string"
    )

    workbook.draw_quadrant(
        datasource,
        name="象限",
        item="サブカテゴリ",
        x_metric="売上",
        y_metric="利益",
        size_metric="売上",
    )

    fields = [field for field in datasource.get_fields() if field.name == "象限_四象限"]
    assert len(fields) == 1
    assert "WINDOW_MEDIAN" in (fields[0].formula or "")
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_quadrant_and_card_stop_on_a_duplicate_sheet_name(tmp_path) -> None:
    """同名のシートが残っているときは、計算フィールドを触る前に止める（2026-09-22）。

    先に作り直そうとすると、そのシートが参照しているせいで消せず、
    `ResourceInUseError` という分かりにくいエラーになっていた。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    quadrant = dict(
        item="サブカテゴリ", x_metric="売上", y_metric="利益", size_metric="売上"
    )
    workbook.draw_quadrant(datasource, name="象限", **quadrant)
    workbook.draw_card(
        datasource, name="カード", main_metric="売上", mode="budget",
        budget_metric="利益",
    )

    with pytest.raises(ValueError, match="worksheet already exists: 象限"):
        workbook.draw_quadrant(datasource, name="象限", **quadrant)
    with pytest.raises(ValueError, match="worksheet already exists: カード"):
        workbook.draw_card(
            datasource, name="カード", main_metric="売上", mode="budget",
            budget_metric="利益",
        )
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_crosstab_uses_color_and_label_metrics(tmp_path) -> None:
    source = tmp_path / "crosstab.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Segment]" caption="顧客セグメント"
              datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))

    worksheet = workbook.draw_crosstab(
        name="カテゴリ_顧客セグメント",
        x_item=("売上データ", "カテゴリ"),
        y_item=("売上データ", "顧客セグメント"),
        color_metric=("売上データ", "売上"),
        label_metric=("売上データ", "売上"),
        min_color="#FF007F",
        mid_color="#FFFFFF",
        max_color="#4400FF",
        title="カテゴリ・顧客セグメント別売上",
    )

    assert worksheet.get_panes()[0].mark_type == "square"
    assert worksheet.title == "カテゴリ・顧客セグメント別売上"
    assert [(field.name, field.shelf) for field in worksheet.get_fields() if field.shelf] == [
        ("顧客セグメント", "rows"),
        ("カテゴリ", "columns"),
    ]
    assert {
        (field.encoding, field.name, field.aggregation)
        for field in worksheet.get_fields()
        if field.encoding
    } == {
        ("color", "売上", "sum"),
        ("label", "売上", "sum"),
    }
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='カテゴリ_顧客セグメント']"
        "/table/panes/pane/style/style-rule[@element='mark']"
        "/format[@attr='mark-labels-show']/@value)"
    ) == "true"
    palette = workbook.tree.xpath(
        "/workbook/preferences/color-palette[@type='ordered-diverging']"
    )[0]
    assert [color.text for color in palette.findall("./color")] == [
        "#ff007f",
        "#ffffff",
        "#4400ff",
    ]
    assert workbook.tree.xpath(
        "string(/workbook/worksheets/worksheet[@name='カテゴリ_顧客セグメント']"
        "/table/style/style-rule[@element='mark']"
        "/encoding[@attr='color']/@palette)"
    ) == palette.get("name")
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_card_treats_calculation_referencing_aggregated_calculation_as_aggregated(tmp_path) -> None:
    """集計済みの計算フィールドだけを参照する計算フィールドも、集計済みとして扱う（2026-09-20）。

    式に集計関数が無くても、参照先が集計済みなら SUM をかけると Tableau でエラーになる。
    行レベルの計算フィールド同士の式は従来どおり SUM をかける。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    for name, formula in [
        ("売上合計", "SUM([Sales])"),
        ("売上比", "[売上合計] / [売上合計]"),
        ("売上比の比", "[売上比] / 2"),
        ("行レベル", "[Sales] * 2"),
        ("行レベル比", "[行レベル] / 2"),
    ]:
        datasource.create_calculated_field(name=name, formula=formula, datatype="real", role="measure")

    def derivations(metric: str) -> list[str]:
        workbook.draw_card(datasource, name=f"カード|{metric}", main_metric=metric)
        return workbook.tree.xpath(
            f"/workbook/worksheets/worksheet[@name='カード|{metric}']//column-instance/@derivation"
        )

    assert derivations("売上合計") == ["User"]
    assert derivations("売上比") == ["User"]
    assert derivations("売上比の比") == ["User"]
    assert derivations("行レベル比") == ["Sum"]


def test_draw_card_budget_mode_makes_one_field_per_color(tmp_path) -> None:
    """予実比較モードは達成・未達を条件ごとの計算フィールドにする（2026-09-21 追加）。

    ラベルの文字色は run ごとに 1 色しか書けないため、条件で色を変えるには
    条件の数だけフィールドを作り、条件に合わない側を NULL にする。
    条件ごとに率（パーセント表示）と文言の 2 つを作り、同じ色で並べる。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="達成率", formula="SUM([Sales]) / SUM([Profit])",
        datatype="real", role="measure",
    )

    workbook.draw_card(
        datasource,
        name="予実カード",
        main_metric="売上",
        mode="budget",
        budget_metric="達成率",
        # 画面は数の入力欄も文字列で渡す
        budget_threshold="1",
        achieved_color="#2f9e44",
        missed_color="#e03131",
    )

    formulas = {
        field.name: field.formula
        for field in datasource.get_fields()
        if field.name.startswith("予実カード_")
    }
    assert formulas == {
        # 集計済みの計算フィールドなので、二重に集計しない
        "予実カード_達成": "IF [達成率] >= 1.0 THEN [達成率] END",
        "予実カード_達成判定": 'IF [達成率] >= 1.0 THEN "達成" END',
        "予実カード_未達": "IF [達成率] < 1.0 THEN [達成率] END",
        "予実カード_未達判定": 'IF [達成率] < 1.0 THEN "未達" END',
    }
    # 率はパーセント表示にする（Tableau の書き方は default-format="p0%"）
    assert workbook.tree.xpath(
        "/workbook/datasources/datasource"
        "/column[starts-with(@caption,'予実カード_')][@default-format]/@default-format"
    ) == ["p0%", "p0%"]
    runs = workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='予実カード']"
        "//customized-label//run/@fontcolor"
    )
    # 率は文字色②（既定 #666666）、文言は達成・未達それぞれの色（2026-09-22）
    assert runs[-4:] == ["#666666", "#2f9e44", "#666666", "#e03131"]
    # 率と文言は太さが違うので run を分ける（率は太字なし、文言は太字）
    bolds = workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='予実カード']"
        "//customized-label//run[@fontsize='12']/@bold"
    )
    assert bolds == ["true", "true", "true"]  # 見出しと、達成・未達の文言だけ
    texts = workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='予実カード']//customized-label//run/text()"
    )
    # 達成の率 / 達成の文言 / 区切りの空白 / 未達の率 / 未達の文言
    assert [text.count("<[") for text in texts[-5:]] == [1, 1, 0, 1, 1]
    # 集計済みの式は agg（usr:）で置く。none: にすると Tableau がシートを
    # エラーにする（2026-09-21 バグ修正）
    assert workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='予実カード']"
        "//column-instance[starts-with(@name,'[usr:')]/@derivation"
    ) == ["User", "User", "User", "User"]
    # 率は連続（:qk）、文言は文字列なので不連続（:nk）。文言を連続にしていた
    # ため Tableau がシートをエラーにしていた（2026-09-21 バグ修正）
    assert [
        instance.get("type")
        for instance in workbook.tree.xpath(
            "/workbook/worksheets/worksheet[@name='予実カード']"
            "//column-instance[starts-with(@name,'[usr:')]"
        )
    ] == ["quantitative", "nominal", "quantitative", "nominal"]
    assert not workbook.tree.xpath(
        "/workbook/worksheets/worksheet[@name='予実カード']"
        "//column-instance[starts-with(@name,'[none:Calculation')]"
    )


def test_draw_card_budget_mode_puts_the_fields_in_the_given_folder(tmp_path) -> None:
    """`folder=` を渡すと予実比較の 4 フィールドを同じフォルダへ入れる（無ければ作る）。"""
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    datasource.create_calculated_field(
        name="達成率", formula="SUM([Sales]) / SUM([Profit])",
        datatype="real", role="measure",
    )

    workbook.draw_card(
        datasource,
        name="予実カード",
        main_metric="売上",
        mode="budget",
        budget_metric="達成率",
        folder="41_KPIカード",
    )

    folders = {
        field.name: field.folder.name if field.folder else None
        for field in datasource.get_fields()
        if field.name.startswith("予実カード_")
    }
    assert folders == {
        "予実カード_達成": "41_KPIカード",
        "予実カード_達成判定": "41_KPIカード",
        "予実カード_未達": "41_KPIカード",
        "予実カード_未達判定": "41_KPIカード",
    }


def test_draw_card_budget_mode_rejects_a_sub_metric(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    with pytest.raises(ValueError, match="budget mode does not take sub_metric"):
        workbook.draw_card(
            datasource, name="予実カード", main_metric="売上", mode="budget",
            budget_metric="利益", sub_metric="利益",
        )
    # 使わない引数を空のまま渡す画面の出力は通る
    workbook.draw_card(
        datasource, name="予実カード", main_metric="売上", mode="budget",
        budget_metric="利益", sub_metric="",
    )
    assert workbook.get_worksheets(name="予実カード")


def test_draw_sheet_places_measures_as_discrete_aggregates(tmp_path) -> None:
    """帳票のメジャーは集計してからディメンションとして置く（2026-09-21 追加）。

    帳票は値を並べる表なので、連続の軸ではなく文字として出す。
    行の縞模様も既定で消す（Tableau は透明色を書いて消す）。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    worksheet = workbook.draw_sheet(datasource, name="帳票", items=["カテゴリ", "売上"])

    # 不連続で、集計は Sum。**数値は順序（:ok / ordinal）**（2026-09-22 修正）。
    # 名義（:nk）にすると Tableau が数値を文字として扱う
    assert worksheet._resolve_element().xpath("string(./table/rows)").endswith(
        f"[{DATASOURCE_ID}].[sum:Sales:ok]"
    )
    assert [
        (instance.get("column"), instance.get("derivation"), instance.get("type"))
        for instance in worksheet._resolve_element().xpath(
            ".//*[local-name()='column-instance']"
        )
    ] == [("[Category]", "None", "nominal"), ("[Sales]", "Sum", "ordinal")]
    # 縞模様は透明色で消す
    assert {
        (item.get("attr"), item.get("value"))
        for item in worksheet._resolve_element().xpath(
            ".//*[local-name()='format'][@attr='band-color']"
        )
    } == {("band-color", "#00000000")}


def test_draw_quadrant_filters_by_two_parameters_with_true_only(tmp_path) -> None:
    """外れ値で外形が崩れないよう、パラメータで制御する真偽値の計算フィールドを
    True だけ残す条件にする（2026-09-24）。中央比率の初期値は 0.95、閾値は 0。
    条件の `true`（引用符なし）は 2026-09-25 に Tableau で動作を確認した。
    """
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]

    workbook.draw_quadrant(
        datasource,
        name="象限",
        item="サブカテゴリ",
        x_metric="売上",
        y_metric="利益",
        size_metric="売上",
    )

    parameters = {item.name: item for item in workbook.get_parameters()}
    assert float(parameters["象限_中央比率"].value) == 0.95
    assert float(parameters["象限_売上閾値"].value) == 0.0

    threshold = datasource.get_fields(name="象限_売上閾値以上")[0]
    assert threshold.datatype == "boolean"
    assert "[Parameters].[象限_売上閾値]" in (threshold.formula or "")
    center = datasource.get_fields(name="象限_中央範囲")[0]
    # WINDOW_PERCENTILE の第 2 引数はリテラルしか受けない（パラメータを入れるとエラー、
    # 2026-09-25）ので、パラメータと比較できる RANK_PERCENTILE を使う
    assert "WINDOW_PERCENTILE" not in (center.formula or "")
    assert "RANK_PERCENTILE(SUM([売上])) >= (1 - [Parameters].[象限_中央比率]) / 2" in (
        center.formula or ""
    )

    worksheet = workbook.get_worksheets(name="象限")[0]
    filters = worksheet._resolve_element().xpath("./table/view/filter")
    assert {(item.get("column"), item.xpath("string(./groupfilter/@member)")) for item in filters} == {
        (f"[{datasource.id}].[usr:{threshold.id.strip('[]')}:nk]", "true"),
        (f"[{datasource.id}].[usr:{center.id.strip('[]')}:nk:2]", "true"),
    }
    assert not [message for message in workbook.validate() if message.severity == "error"]


def test_draw_quadrant_rebuilds_its_parameters(tmp_path) -> None:
    workbook = _superstore_workbook(tmp_path)
    datasource = workbook.get_datasources(name=DATASOURCE_NAME)[0]
    workbook.create_parameter(name="象限_中央比率", value=0.5, datatype="real")
    quadrant = dict(
        item="サブカテゴリ", x_metric="売上", y_metric="利益", size_metric="売上"
    )

    workbook.draw_quadrant(datasource, name="象限", **quadrant)

    parameters = [item for item in workbook.get_parameters() if item.name == "象限_中央比率"]
    assert len(parameters) == 1
    assert float(parameters[0].value) == 0.95
