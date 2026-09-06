from __future__ import annotations

import shutil

import pytest
from lxml import etree as ET

from twbpatch import DetachedModelError, NotFoundError, TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def test_get_fields_merges_connection_metadata_with_explicit_overrides(tmp_path) -> None:
    source = tmp_path / "metadata-fields.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <connection>
        <metadata-records>
          <metadata-record class="column">
            <remote-name>Category</remote-name><local-name>[Category]</local-name>
            <local-type>string</local-type><aggregation>Count</aggregation>
          </metadata-record>
          <metadata-record class="column">
            <remote-name>Sales</remote-name><local-name>[Sales]</local-name>
            <local-type>real</local-type><aggregation>Sum</aggregation>
          </metadata-record>
        </metadata-records>
      </connection>
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
      <column name="[Calc]" caption="計算" datatype="real" role="measure" type="quantitative">
        <calculation class="tableau" formula="[Sales]" />
      </column>
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )

    workbook = TwbWorkbook.open(str(source))
    datasource = workbook.get_datasources()[0]
    fields = datasource.get_fields()

    assert [(field.id, field.name) for field in fields] == [
        ("[Category]", "Category"),
        ("[Sales]", "売上"),
        ("[Calc]", "計算"),
    ]
    assert (fields[0].datatype, fields[0].role, fields[0].discrete) == (
        "string",
        "dimension",
        True,
    )
    assert [field.default_aggregation for field in fields] == ["count", "sum", None]
    assert workbook.is_dirty is False

    before = ET.tostring(workbook.tree)
    with pytest.raises(ValueError, match="name must not be empty"):
        fields[0].update(name=" ")
    assert workbook.is_dirty is False
    assert ET.tostring(workbook.tree) == before

    datasource.create_folder(name="商品")
    fields[0].update(name="カテゴリ")
    assert datasource.get_fields(name="カテゴリ")[0].id == "[Category]"
    assert workbook.tree.xpath(
        "string(/workbook/datasources/datasource/column[@name='[Category]']/@caption)"
    ) == "カテゴリ"
    child_names = [
        ET.QName(child).localname
        for child in workbook.tree.xpath("/workbook/datasources/datasource")[0]
    ]
    assert child_names.index("column") < child_names.index("folders-common")


def test_get_datasources_and_fields_use_list_filters() -> None:
    workbook = TwbWorkbook.open(SAMPLE)

    datasources = workbook.get_datasources()
    assert isinstance(datasources, list)
    assert [(item.id, item.name) for item in datasources] == [("ds1", "売上データ")]
    assert [item.id for item in workbook.get_datasources(id="ds1")] == ["ds1"]
    assert [item.id for item in workbook.get_datasources(name="売上データ")] == ["ds1"]
    assert workbook.get_datasources(id="missing") == []

    datasource = datasources[0]
    fields = datasource.get_fields()
    assert [(item.id, item.name) for item in fields] == [
        ("[Sales]", "売上"),
        ("[Profit]", "粗利"),
    ]
    assert datasource.get_fields(id="[Sales]")[0].name == "売上"
    assert datasource.get_fields(name="売上")[0].id == "[Sales]"

    with pytest.raises(ValueError, match="cannot be specified together"):
        workbook.get_datasources(id="ds1", name="売上データ")
    with pytest.raises(ValueError, match="cannot be specified together"):
        datasource.get_fields(id="[Sales]", name="売上")


def test_field_update_is_live_and_caption_falls_back_to_xml_id() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    field = workbook.get_datasources()[0].get_fields(id="[Sales]")[0]

    returned = field.update(name="純売上", hidden=True, discrete=True)
    assert returned is field
    assert field.name == "純売上"
    assert field.hidden is True
    assert field.discrete is True
    assert workbook.is_dirty is True

    field.update(name=None)
    assert field.id == "[Sales]"
    assert field.name == "Sales"


def test_formula_input_uses_names_and_xml_stores_ids_atomically() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]

    field = datasource.create_calculated_field(
        name="粗利率",
        formula="SUM([粗利]) / SUM([売上])",
    )
    assert field.name == "粗利率"
    assert field.raw_formula == "SUM([Profit]) / SUM([Sales])"
    assert field.formula == "SUM([粗利]) / SUM([売上])"
    assert field.referenced_fields == ["[Profit]", "[Sales]"]

    before = field.raw_formula
    with pytest.raises(NotFoundError, match="formula reference not found"):
        field.update(formula="SUM([存在しない項目])")
    assert field.raw_formula == before


def test_folder_is_connected_model_and_move_accepts_a_name() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]
    folder = datasource.create_folder(name="KPI")
    field = datasource.get_fields(id="[Sales]")[0]

    assert folder.id == "KPI"
    assert datasource.get_folders(name="KPI")[0].id == "KPI"
    assert field.move_to_folder(folder) is field
    assert field.folder is not None
    assert field.folder.id == "KPI"
    assert [item.id for item in folder.get_fields()] == ["[Sales]"]

    field.remove_from_folder()
    assert field.folder is None

    # フォルダ名でも渡せる。folder= を取る他のメソッドと揃えてある（2026-09-07）
    assert field.move_to_folder("KPI") is field
    assert field.folder is not None and field.folder.id == "KPI"

    with pytest.raises(NotFoundError, match="folder not found"):
        field.move_to_folder("無いフォルダ")

    with pytest.raises(TypeError, match="folder must be"):
        field.move_to_folder(1)  # type: ignore[arg-type]


def test_datasource_field_grouping_can_be_saved_as_folder_mode() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]

    assert datasource.field_grouping is None
    assert datasource.update(field_grouping="folder") is datasource
    assert datasource.field_grouping == "folder"
    assert datasource._resolve_element().xpath("string(./layout/@show-structure)") == "false"

    datasource.update(field_grouping="table")
    assert datasource.field_grouping == "table"
    assert datasource._resolve_element().xpath("string(./layout/@show-structure)") == "true"


def test_datasource_applies_yaml_field_config(tmp_path) -> None:
    config = tmp_path / "fields.yaml"
    config.write_text(
        """Measure:
  Sales: 純売上
  Profit: 利益
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]

    assert datasource.apply_field_config(config) is datasource
    assert datasource.field_grouping == "folder"
    folder = datasource.get_folders(name="Measure")[0]
    assert [field.name for field in folder.get_fields()] == ["純売上", "利益"]


def test_datasource_creates_calculated_fields_in_one_call() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]
    datasource.create_folder(name="Measure")

    fields = datasource.create_calculated_fields(
        {
            "利益率": ("SUM([粗利]) / SUM([売上])", "real", "%"),
            "売上件数": ("COUNT([売上])", "integer"),
        },
        folder="Measure",
    )

    assert [(field.name, field.datatype) for field in fields] == [
        ("利益率", "real"),
        ("売上件数", "integer"),
    ]
    assert datasource._resolve_element().xpath(
        'string(./column[@caption="利益率"]/@default-format)'
    ) == "p0%"
    assert datasource._resolve_element().xpath(
        'string(./column[@caption="売上件数"]/@default-format)'
    ) == ""
    assert [field.name for field in datasource.get_folders(name="Measure")[0].get_fields()] == [
        "利益率",
        "売上件数",
    ]


def test_create_yoy_calculated_fields_generates_seven_metric_fields() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]
    datasource.get_fields(id="[Profit]")[0].update(name="利益")
    datasource.get_fields(id="[Sales]")[0].update(name="当年昨年区分")
    datasource.create_folder(name="Measure")

    fields = datasource.create_yoy_calculated_fields(
        metric="利益",
        year_category="当年昨年区分",
        folder="Measure",
    )

    assert [field.name for field in fields] == [
        "利益|当年",
        "利益|昨年",
        "利益|昨年差",
        "利益|昨年差<0",
        "利益|昨年差>=0",
        "利益色|昨年差",
        "利益比|昨年比",
    ]
    assert [field.formula for field in fields] == [
        'IIF([当年昨年区分]="当年",[利益],null)',
        'IIF([当年昨年区分]="昨年",[利益],null)',
        "SUM([利益|当年])-SUM([利益|昨年])",
        "IIF([利益|昨年差]<0,SUM([利益|当年]),null)",
        "IIF(zn([利益|昨年差])>=0,SUM([利益|当年]),null)",
        "IIF(zn([利益|昨年差])>=0,SUM([利益|当年]),null)",
        "SUM([利益|当年])/SUM([利益|昨年])",
    ]
    assert datasource._resolve_element().xpath(
        'string(./column[@caption="利益比|昨年比"]/@default-format)'
    ) == "p0%"
    assert [field.name for field in datasource.get_folders(name="Measure")[0].get_fields()] == [
        field.name for field in fields
    ]


def test_create_yoy_calculated_fields_rolls_back_all_fields_on_name_conflict(tmp_path) -> None:
    source = tmp_path / "yoy-name-conflict.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Profit]" caption="利益" datatype="real" role="measure" type="quantitative" />
      <column name="[YearCategory]" caption="当年昨年区分" datatype="string" role="dimension" type="nominal" />
      <column name="[ExistingDifference]" caption="利益|昨年差" datatype="real" role="measure" type="quantitative">
        <calculation class="tableau" formula="[Profit]" />
      </column>
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))
    datasource = workbook.get_datasources()[0]
    existing_metric = datasource.get_fields(id="[Profit]")[0]
    before = ET.tostring(workbook.tree)
    before_revision = datasource._context.revision

    with pytest.raises(ValueError, match="caption already exists: 利益\\|昨年差"):
        datasource.create_yoy_calculated_fields(
            metric="利益",
            year_category="当年昨年区分",
        )

    assert ET.tostring(workbook.tree) == before
    assert workbook.is_dirty is False
    assert datasource._context.revision == before_revision

    existing_metric.update(name="営業利益")
    assert datasource.get_fields(id="[Profit]")[0].name == "営業利益"


def test_calculated_field_rejects_unknown_number_format() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]

    with pytest.raises(ValueError, match="number_format"):
        datasource.create_calculated_field(
            name="粗利率",
            formula="SUM([粗利]) / SUM([売上])",
            number_format="percent",
        )


def test_workbook_applies_datasource_first_yaml_field_config(tmp_path) -> None:
    config = tmp_path / "workbook-fields.yaml"
    config.write_text(
        """"売上データ":
  Measure:
    Sales: 純売上
    Profit: 利益
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(SAMPLE)

    assert workbook.apply_field_config(config) is workbook
    datasource = workbook.get_datasources(name="売上データ")[0]
    assert datasource.field_grouping == "folder"
    assert [field.name for field in datasource.get_folders(name="Measure")[0].get_fields()] == [
        "純売上",
        "利益",
    ]


def test_yaml_field_config_is_validated_before_creating_folders(tmp_path) -> None:
    config = tmp_path / "invalid-fields.yaml"
    config.write_text("Measure:\n  Missing: 不明\n", encoding="utf-8")
    workbook = TwbWorkbook.open(SAMPLE)
    datasource = workbook.get_datasources()[0]

    with pytest.raises(NotFoundError, match="field not found: Missing"):
        datasource.apply_field_config(config)
    assert datasource.get_folders() == []


def test_updates_stay_in_memory_until_save(tmp_path) -> None:
    source = tmp_path / "source.twb"
    output = tmp_path / "output.twb"
    shutil.copyfile(SAMPLE, source)
    original = source.read_text(encoding="utf-8")
    workbook = TwbWorkbook.open(str(source))

    workbook.get_datasources()[0].get_fields(id="[Sales]")[0].update(name="純売上")
    assert source.read_text(encoding="utf-8") == original
    assert workbook.is_dirty is True

    workbook.save(str(output), validate=False)
    assert "純売上" in output.read_text(encoding="utf-8")
    assert source.read_text(encoding="utf-8") == original
    assert workbook.is_dirty is False


def test_reload_discards_memory_changes_and_detaches_old_models(tmp_path) -> None:
    source = tmp_path / "source.twb"
    shutil.copyfile(SAMPLE, source)
    workbook = TwbWorkbook.open(str(source))
    old_field = workbook.get_datasources()[0].get_fields(id="[Sales]")[0]
    old_field.update(name="純売上")

    returned = workbook.reload()
    assert returned is workbook
    assert workbook.is_dirty is False
    with pytest.raises(DetachedModelError):
        _ = old_field.name
    assert workbook.get_datasources()[0].get_fields(id="[Sales]")[0].name == "売上"
