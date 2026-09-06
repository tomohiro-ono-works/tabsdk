"""H-1: ダッシュボードアクションの作成・更新・削除。

XML の形は Tableau が保存した `.twb` から実測した（2026-09-07）。
`<action>` は `/workbook/actions` 直下に置かれ、対象シートは「除外するシート」で書かれる。
"""

from __future__ import annotations

from urllib.parse import unquote

import pytest

from twbpatch import TwbWorkbook


def _workbook(tmp_path):
    path = tmp_path / "actions.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Region]" caption="地域"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name="元シート">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
    <worksheet name="先シート">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
    <worksheet name="無関係シート">
      <table><view><datasource-dependencies datasource="ds1" /></view></table>
    </worksheet>
  </worksheets>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(path))
    dashboard = workbook.create_dashboard(name="ダッシュボード", width=1600, height=900)
    container = dashboard.create_container(direction="vertical")
    for worksheet in workbook.get_worksheets():
        container.add_worksheet(worksheet, show_title=False)
    return workbook, dashboard


def _action_el(workbook, action_id):
    return workbook.tree.getroot().xpath(
        "./actions/action[@name=$id]", id=action_id
    )[0]


def test_filter_action_matches_the_shape_tableau_writes(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)

    action = dashboard.create_action(
        kind="filter",
        name="地域で絞る",
        source="元シート",
        targets=["先シート"],
        field=("売上データ", "地域"),
    )

    element = _action_el(workbook, action.id)
    assert element.get("caption") == "地域で絞る"
    assert element.get("name").startswith("[Action1_")

    activation = element.find("activation")
    assert activation.get("type") == "on-select"
    assert activation.get("auto-clear") == "true"

    source = element.find("source")
    assert source.attrib == {
        "dashboard": "ダッシュボード",
        "type": "sheet",
        "worksheet": "元シート",
    }

    # 対象は「除外するシート」で書かれる。元シートと先シートは除外に入らない。
    params = {param.get("name"): param.get("value") for param in element.iter("param")}
    assert params["target"] == "ダッシュボード"
    assert params["exclude"] == "無関係シート"
    assert element.find("command").get("command") == "tsc:tsl-filter"

    link = element.find("link")
    assert unquote(link.get("expression")) == (
        "tsl:ダッシュボード?[ds1].[Region]~s0=<[ds1].[Region]~na>"
    )
    assert link.get("multi-select") == "true"


def test_filter_action_declares_the_field_it_uses(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    dashboard.create_action(
        kind="filter",
        name="地域で絞る",
        source="元シート",
        targets=["先シート"],
        field=("売上データ", "地域"),
    )

    actions = workbook.tree.getroot().find("actions")
    assert actions.find("datasources/datasource").get("name") == "ds1"
    column = actions.find("datasource-dependencies/column")
    assert column.get("name") == "[Region]"
    assert column.get("caption") == "地域"


def test_url_action_matches_the_shape_tableau_writes(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)

    action = dashboard.create_action(
        kind="url",
        name="検索を開く",
        source=["元シート"],
        url="https://example.com/",
    )

    element = _action_el(workbook, action.id)
    assert element.find("activation").attrib == {"type": "on-select"}
    assert element.find("command") is None

    source = element.find("source")
    assert source.attrib == {"dashboard": "ダッシュボード", "type": "sheet"}
    # 起点にしないシートを列挙する
    assert [item.get("name") for item in source.iter("exclude-sheet")] == [
        "先シート",
        "無関係シート",
    ]

    link = element.find("link")
    assert link.get("expression") == "https://example.com/"
    assert link.get("caption") == ""


def test_actions_are_numbered_in_sequence(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    first = dashboard.create_action(
        kind="url", name="1 つ目", source="元シート", url="https://example.com/1"
    )
    second = dashboard.create_action(
        kind="url", name="2 つ目", source="元シート", url="https://example.com/2"
    )

    assert first.id.startswith("[Action1_")
    assert second.id.startswith("[Action2_")
    assert first.id != second.id


def test_get_actions_reads_back_what_was_created(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    dashboard.create_action(
        kind="filter",
        name="地域で絞る",
        source="元シート",
        targets=["先シート"],
        field=("売上データ", "地域"),
    )
    dashboard.create_action(
        kind="url", name="検索を開く", source="元シート", url="https://example.com/"
    )

    actions = dashboard.get_actions()
    assert [action.name for action in actions] == ["地域で絞る", "検索を開く"]
    # URL アクションは <command> を持たないが種別を読める（読み取りの不具合を修正）
    assert [action.type for action in actions] == ["filter", "url"]

    filter_action = dashboard.get_actions(name="地域で絞る")[0]
    assert filter_action.source_worksheet_ids == ["元シート"]
    # ターゲットは <command> の param から読む（読み取りの不具合を修正）
    assert filter_action.target_worksheet_ids == ["元シート", "先シート"]


def test_update_changes_scalar_values(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    action = dashboard.create_action(
        kind="filter",
        name="地域で絞る",
        source="元シート",
        targets=["先シート"],
        field=("売上データ", "地域"),
    )

    action.update(name="地域フィルター", activation="on-hover", clear_selection="exclude")

    element = _action_el(workbook, action.id)
    assert element.get("caption") == "地域フィルター"
    assert element.find("activation").get("type") == "on-hover"
    assert element.find("activation").get("auto-clear") == "false"
    assert element.find("link").get("caption") == "地域フィルター"
    assert action.name == "地域フィルター"


def test_update_rejects_options_of_the_other_kind(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    url_action = dashboard.create_action(
        kind="url", name="検索を開く", source="元シート", url="https://example.com/"
    )

    with pytest.raises(ValueError, match="clear_selection is only available"):
        url_action.update(clear_selection="exclude")


def test_delete_removes_only_that_action(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    keep = dashboard.create_action(
        kind="url", name="残す", source="元シート", url="https://example.com/1"
    )
    drop = dashboard.create_action(
        kind="url", name="消す", source="元シート", url="https://example.com/2"
    )

    drop.delete()

    assert [action.name for action in dashboard.get_actions()] == ["残す"]
    assert keep.name == "残す"


def test_a_filter_action_needs_a_field(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)

    with pytest.raises(TypeError, match="field must be"):
        dashboard.create_action(
            kind="filter", name="地域で絞る", source="元シート", targets=["先シート"]
        )


def test_a_filter_action_needs_a_target(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)

    with pytest.raises(ValueError, match="needs at least one target"):
        dashboard.create_action(
            kind="filter",
            name="地域で絞る",
            source="元シート",
            field=("売上データ", "地域"),
        )


def test_a_url_action_needs_a_url(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)

    with pytest.raises(ValueError, match="needs a url"):
        dashboard.create_action(kind="url", name="検索を開く", source="元シート")


def test_worksheets_outside_the_dashboard_are_rejected(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    workbook.create_worksheet(name="別のシート")

    with pytest.raises(ValueError, match="not on this dashboard"):
        dashboard.create_action(
            kind="url", name="検索を開く", source="別のシート", url="https://example.com/"
        )


def test_an_unknown_kind_is_rejected(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)

    with pytest.raises(ValueError, match="kind must be one of"):
        dashboard.create_action(
            kind="highlight", name="光らせる", source="元シート", targets=["先シート"]
        )


def test_a_duplicate_name_is_rejected(tmp_path) -> None:
    workbook, dashboard = _workbook(tmp_path)
    dashboard.create_action(
        kind="url", name="検索を開く", source="元シート", url="https://example.com/"
    )

    with pytest.raises(ValueError, match="already exists"):
        dashboard.create_action(
            kind="url", name="検索を開く", source="元シート", url="https://example.com/2"
        )
