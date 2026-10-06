"""A-6: 公開 `update_*()` の `update()` 統合と、取得側のプロパティ化。

根拠: docs/developer/model_api_spec.md §3.3 / §4.1、docs/api_rename_plan.md
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "style_group.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ" datatype="string" role="dimension" type="nominal" />
      <column name="[Sales]" caption="売上" datatype="real" role="measure" type="quantitative" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def test_worksheet_update_accepts_style_groups(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")
    worksheet.add_field(field=datasource.get_fields(name="カテゴリ")[0], shelf="rows")

    assert worksheet.update(
        name="一覧2",
        table_style={"header_bold": True, "header_color": "#555555"},
        title_style={"background_color": "#eeeeee"},
    ) is worksheet

    assert worksheet.id == "一覧2"
    assert worksheet.table_style["header_bold"] is True
    assert worksheet.table_style["header_color"] == "#555555"
    assert worksheet.title_style["background_color"] == "#eeeeee"


def test_worksheet_update_style_group_is_incremental(tmp_path) -> None:
    """グループを分けて渡しても、先に入れた値を消さない。"""
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")
    worksheet.add_field(field=datasource.get_fields(name="カテゴリ")[0], shelf="rows")

    worksheet.update(table_style={"header_background": "#f5f5f5", "row_band": False})
    worksheet.update(table_style={"header_bold": True})

    assert worksheet.table_style["header_background"] == "#f5f5f5"
    assert worksheet.table_style["row_band"] is False
    assert worksheet.table_style["header_bold"] is True


def test_renamed_methods_are_gone(tmp_path) -> None:
    """A-6: 公開 `update_*()` は廃止した（仕様 §3.3）。"""
    workbook = _workbook(tmp_path)
    worksheet = workbook.create_worksheet(name="一覧")
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")
    zone = container.add_worksheet(worksheet, fixed_size=200, show_title=False)

    for owner, removed in (
        (worksheet, "update_table_style"),
        (worksheet, "update_title_style"),
        (worksheet.get_panes()[0], "update_customized_label"),
        (container, "update_style"),
        (zone, "update_style"),
    ):
        assert not hasattr(owner, removed), f"{removed} still exists"


@pytest.mark.parametrize(
    "value, error, message",
    [
        (["header_bold"], TypeError, "table_style must be a dict"),
        ({1: True}, TypeError, "table_style keys must be strings"),
        ({"unknown": True}, ValueError, "unknown table_style key"),
    ],
)
def test_worksheet_update_rejects_bad_style_group(tmp_path, value, error, message) -> None:
    workbook = _workbook(tmp_path)
    worksheet = workbook.create_worksheet(name="一覧")
    with pytest.raises(error, match=message):
        worksheet.update(table_style=value)


def test_worksheet_update_rejects_bad_style_group_before_changing_xml(tmp_path) -> None:
    """§5.5 原子性: 検証に失敗したら XML も is_dirty も変えない。"""
    workbook = _workbook(tmp_path)
    workbook.create_worksheet(name="一覧")
    workbook.save(str(tmp_path / "saved.twb"), overwrite=True)
    worksheet = workbook.get_worksheets()[0]
    assert workbook.is_dirty is False

    with pytest.raises(ValueError, match="unknown table_style key"):
        worksheet.update(name="別名", table_style={"unknown": True})

    assert workbook.is_dirty is False
    assert worksheet.id == "一覧"


def test_container_and_zone_update_accept_style(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet = workbook.create_worksheet(name="一覧")
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)

    container = dashboard.create_container(direction="vertical", friendly_name="contents")
    assert container.update(
        friendly_name="contents2",
        style={"background_color": "#f5f5f5", "margin": 8},
    ) is container
    assert container.style == {"background_color": "#f5f5f5", "margin": "8"}

    zone = container.add_worksheet(worksheet, fixed_size=200, show_title=False)
    assert zone.update(style={"background_color": "#ffffff", "padding": 8}) is zone
    assert zone.style == {"background_color": "#ffffff", "padding": "8"}

    # キー集合が開いているグループなので、未知のキーは弾かない
    zone.update(style={"border_style": "none"})
    assert zone.style["border_style"] == "none"

    with pytest.raises(TypeError, match="style must be a dict"):
        zone.update(style="#ffffff")


def test_attribute_getters_are_properties(tmp_path) -> None:
    """§4.1: 引数を取らない属性の読み取りはプロパティで公開する。"""
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")
    pane = worksheet.get_panes()[0]
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=800, height=600)
    container = dashboard.create_container(direction="vertical")
    zone = container.add_worksheet(worksheet, fixed_size=200, show_title=False)

    for owner, name in (
        (datasource, "field_grouping"),
        (worksheet, "table_style"),
        (worksheet, "title_style"),
        (pane, "customized_label"),
        (pane, "mark_opacity"),
        (container, "style"),
        (zone, "style"),
    ):
        assert isinstance(getattr(type(owner), name), property), f"{name} is not a property"
        assert not hasattr(owner, f"get_{name}"), f"get_{name} still exists"

    # 引数を取る取得はプロパティにできないため get_/set_ の対を維持する（§4.1）
    assert callable(pane.get_categorical_colors)
    assert callable(pane.set_categorical_colors)


def test_pane_has_set_customized_label(tmp_path) -> None:
    """他フィールドを受け取る操作は update() へ統合せず動詞名にする。"""
    workbook = _workbook(tmp_path)
    pane = workbook.create_worksheet(name="カード").get_panes()[0]
    assert hasattr(pane, "set_customized_label")
    with pytest.raises(TypeError, match="main_metric must be TwbWorksheetField"):
        pane.set_customized_label(main_metric="売上", sub_metric=None, main_color="#602fff")


# --- A-9: 自分の値を変える set_* を update() へ統合 -------------------------


def test_worksheet_update_accepts_title(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet = workbook.create_worksheet(name="一覧")

    assert worksheet.update(title="売上の一覧") is worksheet
    assert worksheet.title == "売上の一覧"

    worksheet.update(title=None)
    assert worksheet.title is None

    with pytest.raises(TypeError, match="title must be a string or None"):
        worksheet.update(title=1)


def test_pane_update_accepts_every_mark_setting(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    datasource = workbook.get_datasources()[0]
    worksheet = workbook.create_worksheet(name="一覧")
    worksheet.add_field(field=datasource.get_fields(name="売上")[0], shelf="rows")
    pane = worksheet.get_panes()[0]

    assert pane.update(
        mark_type="bar",
        mark_color="#602fff",
        mark_size=4,
        mark_opacity=0.6,
        mark_scaling=False,
        label_style={"show": True, "cull": False},
    ) is pane

    assert pane.mark_type == "bar"
    assert pane.mark_opacity == pytest.approx(0.6, abs=0.01)


def test_pane_update_changes_only_given_arguments(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    worksheet = workbook.create_worksheet(name="一覧")
    pane = worksheet.get_panes()[0]

    pane.update(mark_type="bar", mark_opacity=0.5)
    pane.update(mark_color="#602fff")

    assert pane.mark_type == "bar"
    assert pane.mark_opacity == pytest.approx(0.5, abs=0.01)


@pytest.mark.parametrize(
    "value, error, message",
    [
        ("show", TypeError, "label_style must be a dict"),
        ({"unknown": True}, ValueError, "unknown label_style key"),
    ],
)
def test_pane_update_rejects_bad_label_style(tmp_path, value, error, message) -> None:
    workbook = _workbook(tmp_path)
    pane = workbook.create_worksheet(name="一覧").get_panes()[0]
    with pytest.raises(error, match=message):
        pane.update(label_style=value)


def test_scalar_setters_are_gone(tmp_path) -> None:
    """自分の値を変える操作は update() に統一した（§3.3）。"""
    workbook = _workbook(tmp_path)
    worksheet = workbook.create_worksheet(name="一覧")
    pane = worksheet.get_panes()[0]

    for owner, removed in (
        (worksheet, "set_title"),
        (pane, "set_mark_color"),
        (pane, "set_mark_size"),
        (pane, "set_mark_opacity"),
        (pane, "set_mark_sizing"),
        (pane, "set_label_style"),
    ):
        assert not hasattr(owner, removed), f"{removed} still exists"

    # 他モデルを引数に取るものは動詞名のまま（§3.3）
    assert callable(pane.set_customized_label)
    assert callable(pane.set_categorical_colors)
    assert callable(worksheet.set_axis_visibility)
