"""B-2: `TwbDashboard.update()` を直接検証する。

**テスト中に一度も実行されていなかった**唯一のメソッド（`docs/backlog.md` B-2）。
表示名は `<dashboard caption>`、表示・非表示は `/workbook/windows/window` の
`hidden` 属性に書かれる。
"""

from __future__ import annotations

import pytest

from twbpatch import TwbWorkbook, UnsupportedFeatureError


def _workbook(tmp_path):
    path = tmp_path / "dashboard.twb"
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Category]" caption="カテゴリ"
              datatype="string" role="dimension" type="nominal" />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
""",
        encoding="utf-8",
    )
    return TwbWorkbook.open(str(path))


def _dashboard_with_worksheet(workbook, name):
    """表示・非表示は window にしか書けず、window はシートが要る。"""
    worksheet = workbook.create_worksheet(name=f"{name}のシート")
    dashboard = workbook.create_dashboard(name=name, width=800, height=600)
    dashboard.create_container(direction="vertical").add_worksheet(
        worksheet, show_title=False
    )
    return dashboard


def _dashboard_el(workbook, dashboard_id):
    return workbook.tree.getroot().xpath(
        "./dashboards/dashboard[@name=$id]", id=dashboard_id
    )[0]


def _windows(workbook, dashboard_id):
    return workbook.tree.getroot().xpath(
        "./windows/window[@class='dashboard'][@name=$id]", id=dashboard_id
    )


def test_renaming_writes_the_caption_and_keeps_the_id(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)
    dashboard_id = dashboard.id

    assert dashboard.update(name="売上ダッシュボード") is dashboard

    assert dashboard.name == "売上ダッシュボード"
    # caption を変えても内部 ID は変わらない（仕様 §3.2）
    assert dashboard.id == dashboard_id
    assert _dashboard_el(workbook, dashboard_id).get("caption") == "売上ダッシュボード"
    assert workbook.is_dirty is True


def test_the_name_is_trimmed(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)

    dashboard.update(name="  概要  ")

    assert dashboard.name == "概要"


def test_passing_none_drops_the_caption(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)
    dashboard_id = dashboard.id

    dashboard.update(name=None)

    assert _dashboard_el(workbook, dashboard_id).get("caption") is None
    # caption が無くなると表示名は内部 ID へ落ちる
    assert dashboard.name == dashboard_id


def test_hiding_sets_hidden_on_the_window(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = _dashboard_with_worksheet(workbook, "売上")

    dashboard.update(visible=False)

    windows = _windows(workbook, dashboard.id)
    assert len(windows) == 1
    assert windows[0].get("hidden") == "true"
    assert dashboard.visible is False


def test_showing_it_again_updates_the_same_window(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = _dashboard_with_worksheet(workbook, "売上")

    dashboard.update(visible=False)
    dashboard.update(visible=True)

    windows = _windows(workbook, dashboard.id)
    assert len(windows) == 1
    assert windows[0].get("hidden") == "false"


def test_visible_true_on_an_empty_dashboard_adds_nothing(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)

    dashboard.update(visible=True)

    # 既定が表示なので、window を足す必要はない
    assert _windows(workbook, dashboard.id) == []


def test_an_empty_dashboard_cannot_be_hidden(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)

    # window は viewpoints / active / simple-id をシートから作る。
    # シートが無いと Tableau が読める形にならない
    with pytest.raises(UnsupportedFeatureError, match="at least one worksheet"):
        dashboard.update(visible=False)

    assert _windows(workbook, dashboard.id) == []


def test_hidden_survives_adding_another_worksheet(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = _dashboard_with_worksheet(workbook, "売上")
    dashboard.update(visible=False)

    added = workbook.create_worksheet(name="追加シート")
    dashboard.get_containers()[0].add_worksheet(added, show_title=False)

    # window はシートを足すたびに作り直される。hidden を落とさない
    assert _windows(workbook, dashboard.id)[0].get("hidden") == "true"
    assert dashboard.visible is False


def test_name_and_visible_can_be_set_together(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = _dashboard_with_worksheet(workbook, "売上")

    dashboard.update(name="概要", visible=False)

    assert dashboard.name == "概要"
    assert _windows(workbook, dashboard.id)[0].get("hidden") == "true"


def test_update_without_arguments_changes_nothing(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)
    workbook.save(str(tmp_path / "saved.twb"))

    before = workbook.is_dirty
    assert dashboard.update() is dashboard

    assert dashboard.name == "売上"
    assert workbook.is_dirty is before


def test_setting_the_same_name_is_a_no_op(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)
    workbook.save(str(tmp_path / "saved.twb"))

    before = workbook.is_dirty
    dashboard.update(name="売上")

    # 表示名が変わらないなら caption も書き足さない
    assert workbook.is_dirty is before
    assert _dashboard_el(workbook, dashboard.id).get("caption") is None


def test_a_duplicate_name_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    workbook.create_dashboard(name="売上", width=800, height=600)
    other = workbook.create_dashboard(name="利益", width=800, height=600)

    with pytest.raises(ValueError, match="dashboard name already exists"):
        other.update(name="売上")

    assert other.name == "利益"


def test_an_empty_name_is_rejected(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)

    with pytest.raises(ValueError, match="name must not be empty"):
        dashboard.update(name="   ")


def test_visible_must_be_bool(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = workbook.create_dashboard(name="売上", width=800, height=600)

    with pytest.raises(TypeError, match="visible must be bool"):
        dashboard.update(visible="false")


def test_the_rename_survives_a_round_trip(tmp_path) -> None:
    workbook = _workbook(tmp_path)
    dashboard = _dashboard_with_worksheet(workbook, "売上")
    dashboard.update(name="概要", visible=False)
    out = tmp_path / "out.twb"
    workbook.save(str(out))

    reopened = TwbWorkbook.open(str(out))
    assert [d.name for d in reopened.get_dashboards()] == ["概要"]
    assert reopened.get_dashboards()[0].visible is False
