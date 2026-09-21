from __future__ import annotations

import logging

import pytest
import yaml

from twbpatch import TwbWorkbook
from twbpatch.errors import NotFoundError, UnsupportedFeatureError


SAMPLE = "tests/sample_minimal.twb"


def _config(**overrides) -> dict:
    config = {
        "design": {"font": "Meiryo UI"},
        "datasources": {
            "売上データ": {
                "folders": {"指標": {"売上": "売上金額"}},
                "calculations": [
                    {
                        "name": "利益率",
                        "formula": "SUM([粗利]) / SUM([売上金額])",
                        "datatype": "real",
                        "role": "measure",
                        "folder": "指標",
                    }
                ],
            }
        },
    }
    config.update(overrides)
    return config


def _calc_config(**calc) -> dict:
    """計算フィールドだけの設定。

    `folders` は「元カラム名 → 表示名」なので、適用済みの .twb へ同じものを
    もう一度渡すと元カラム名が見つからない。2 周方式では画面が焼き直し後の
    .twb から YAML を作り直すため、これは起きない。
    """
    entry = {"name": "利益率", "formula": "SUM([粗利]) / SUM([売上])"}
    entry.update(calc)
    return {"datasources": {"売上データ": {"calculations": [entry]}}}


def test_apply_config_applies_folders_and_calculations() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(_config())

    datasource = workbook.get_datasources(name="売上データ")[0]
    assert [folder.name for folder in datasource.get_folders()] == ["指標"]
    assert datasource.get_fields(name="売上金額")

    field = datasource.get_fields(name="利益率")[0]
    assert field.is_calculated
    assert field.role == "measure"
    assert field.folder is not None and field.folder.name == "指標"
    # 式は表示名ではなく id で保存される（仕様 §3.4）
    assert "[Profit]" in (field.raw_formula or "")
    assert "[粗利]" not in (field.raw_formula or "")


def test_apply_config_accepts_yaml_path(tmp_path) -> None:
    path = tmp_path / "twbpatch_config.yaml"
    path.write_text(
        yaml.safe_dump(_config(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(path)

    assert workbook.get_datasources(name="売上データ")[0].get_fields(name="利益率")


def test_apply_config_applies_font() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config({"design": {"font": "Tableau Book"}})

    styles = workbook.tree.getroot().xpath("./style")
    assert "Tableau Book" in styles[0].xpath("string(.//format/@value)")


def test_apply_config_is_idempotent() -> None:
    """2 周方式では同じ YAML を 2 度通す。2 度目に止まらないこと。"""
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(_calc_config())
    workbook.apply_config(_calc_config())

    datasource = workbook.get_datasources(name="売上データ")[0]
    assert len(datasource.get_fields(name="利益率")) == 1


def test_apply_config_overwrites_existing_calculation() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(_calc_config())
    workbook.apply_config(
        _calc_config(formula="SUM([粗利])", datatype="integer", role="dimension")
    )

    field = workbook.get_datasources(name="売上データ")[0].get_fields(name="利益率")[0]
    assert field.raw_formula == "SUM([Profit])"
    assert field.datatype == "integer"
    assert field.role == "dimension"
    assert field.discrete is True


def test_apply_config_creates_referenced_calculations_first() -> None:
    """参照先の計算フィールドが YAML の後ろにあっても作れる（2026-09-14）。

    画面の計算フィールドの表は行を途中に挿入できず、参照先を後から足すと末尾に入る。
    以前は上から順に作っていたため `formula reference not found` で止まっていた。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(
        {
            "datasources": {
                "売上データ": {
                    "calculations": [
                        {"name": "利益率(差)", "formula": "[利益率] - [目標利益率]"},
                        {"name": "区分", "formula": '"A"', "datatype": "string", "role": "dimension"},
                        {"name": "利益率", "formula": "SUM([粗利]) / SUM([売上])"},
                        {"name": "目標利益率", "formula": "[利益率] * 0 + 0.3"},
                    ]
                }
            }
        }
    )

    datasource = workbook.get_datasources(name="売上データ")[0]
    assert datasource.get_fields(name="利益率(差)")[0].formula == "[利益率] - [目標利益率]"
    # 参照し合っていないものは YAML の並び順のまま、参照先は参照する側より先
    calculated = [field.name for field in datasource.get_fields() if field.is_calculated]
    assert calculated == ["区分", "利益率", "目標利益率", "利益率(差)"]


def test_apply_config_rejects_circular_calculations_before_creating_any() -> None:
    workbook = TwbWorkbook.open(SAMPLE)

    with pytest.raises(ValueError, match="cycle: A, B"):
        workbook.apply_config(
            {
                "datasources": {
                    "売上データ": {
                        "calculations": [
                            {"name": "合計", "formula": "SUM([売上])"},
                            {"name": "A", "formula": "[B] + 1"},
                            {"name": "B", "formula": "[A] + 1"},
                        ]
                    }
                }
            }
        )

    datasource = workbook.get_datasources(name="売上データ")[0]
    assert [field.name for field in datasource.get_fields() if field.is_calculated] == []


def test_apply_config_makes_dimension_discrete_and_measure_continuous() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(
        {
            "datasources": {
                "売上データ": {
                    "calculations": [
                        {"name": "区分", "formula": '"A"', "datatype": "string", "role": "dimension"},
                        {"name": "合計", "formula": "SUM([売上])", "role": "measure"},
                    ]
                }
            }
        }
    )

    datasource = workbook.get_datasources(name="売上データ")[0]
    assert datasource.get_fields(name="区分")[0].discrete is True
    assert datasource.get_fields(name="合計")[0].discrete is False


def test_apply_config_refuses_to_overwrite_a_source_field() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    with pytest.raises(ValueError, match="not a calculated field"):
        workbook.apply_config(
            {
                "datasources": {
                    "売上データ": {
                        "calculations": [{"name": "売上", "formula": "1"}]
                    }
                }
            }
        )


def test_apply_config_applies_renames_without_creating_a_folder() -> None:
    """`renames` はフォルダに入れず表示名だけ変更する（2026-09-08 追加）。

    `folders` は最上位がフォルダ名の3階層固定でフォルダなしを表現できないため、
    「リネームしたいがフォルダには入れたくない」場合の入口として別セクションにした。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(
        {"datasources": {"売上データ": {"renames": {"売上": "売上金額"}}}}
    )

    datasource = workbook.get_datasources(name="売上データ")[0]
    assert datasource.get_folders() == []
    field = datasource.get_fields(name="売上金額")[0]
    assert field.id == "[Sales]"
    assert field.folder is None


def test_apply_config_renames_and_folders_together() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    workbook.apply_config(
        {
            "datasources": {
                "売上データ": {
                    "folders": {"指標": {"粗利": "利益"}},
                    "renames": {"売上": "売上金額"},
                }
            }
        }
    )

    datasource = workbook.get_datasources(name="売上データ")[0]
    assert [folder.name for folder in datasource.get_folders()] == ["指標"]
    assert datasource.get_fields(name="利益")[0].folder.name == "指標"
    assert datasource.get_fields(name="売上金額")[0].folder is None


def test_apply_config_rejects_unknown_datasource() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    with pytest.raises(NotFoundError):
        workbook.apply_config({"datasources": {"存在しない": {"folders": {}}}})


def test_apply_config_does_not_touch_xml_when_a_datasource_is_missing() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    with pytest.raises(NotFoundError):
        workbook.apply_config(
            {
                "datasources": {
                    "売上データ": {"folders": {"指標": {"売上": "売上金額"}}},
                    "存在しない": {"folders": {}},
                }
            }
        )
    assert workbook.get_datasources(name="売上データ")[0].get_folders() == []


def test_apply_config_skips_sections_without_a_receiver(caplog) -> None:
    """`design` の色と余白は `dashboard` を通してしか届かない。単独では読み飛ばす。"""
    workbook = TwbWorkbook.open(SAMPLE)
    with caplog.at_level(logging.WARNING, logger="twbpatch.config_apply"):
        workbook.apply_config(
            {"design": {"font": "Meiryo UI", "main_color": "#2f3b52", "spacing": "wide"}}
        )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "design.main_color" in messages
    assert "design.spacing" in messages


def test_apply_config_rejects_a_non_mapping() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    with pytest.raises(ValueError, match="config must be a mapping"):
        workbook.apply_config(["design"])


def test_apply_config_rejects_a_bad_role() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    with pytest.raises(ValueError, match="role"):
        workbook.apply_config(
            {
                "datasources": {
                    "売上データ": {
                        "calculations": [
                            {"name": "利益率", "formula": "1", "role": "metric"}
                        ]
                    }
                }
            }
        )


def test_apply_config_does_not_write_the_file(tmp_path) -> None:
    source = tmp_path / "sample.twb"
    source.write_bytes(open(SAMPLE, "rb").read())
    before = source.read_bytes()

    workbook = TwbWorkbook.open(str(source))
    workbook.apply_config(_config())

    assert workbook.is_dirty
    assert source.read_bytes() == before


def test_field_update_rejects_datatype_on_a_source_field() -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    field = workbook.get_datasources(name="売上データ")[0].get_fields(name="売上")[0]
    with pytest.raises(UnsupportedFeatureError, match="calculated fields"):
        field.update(datatype="integer")


def test_design_border_color_draws_borders_around_the_zones(tmp_path) -> None:
    """デザインルールの枠線の色を入れると、ゾーンに枠線が付く（2026-09-21）。

    色が空なら今までどおり枠線なし。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    config = {
        "design": {"main_color": "#2f3b52", "border_color": "#334455"},
        "dashboard": {
            "name": "売上ダッシュボード",
            "rows": [
                {
                    "name": "段",
                    "areas": [
                        {
                            "kind": "worksheet",
                            "datasource": "売上データ",
                            "sheet": "カード",
                            "chart": "draw_card",
                            "params": {"main_metric": "売上"},
                        }
                    ],
                }
            ],
        },
    }

    workbook.apply_config(config)

    assert workbook.tree.xpath(
        "//zone[@name='カード']/zone-style/format[@attr='border-color']/@value"
    ) == ["#334455"]
    assert workbook.tree.xpath(
        "//zone[@name='カード']/zone-style/format[@attr='border-style']/@value"
    ) == ["solid"]
