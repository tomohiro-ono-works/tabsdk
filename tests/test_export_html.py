from __future__ import annotations

import json
import re

import pytest

from twbpatch import TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def _embedded_data(html: str) -> dict:
    match = re.search(
        r'<script type="application/json" id="wb-data">(.*?)</script>', html, re.S
    )
    assert match is not None
    return json.loads(match.group(1).replace("<\\/", "</"))


def test_export_html_writes_self_contained_file(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    target = workbook.export_html(tmp_path / "config.html")

    html = target.read_text(encoding="utf-8")
    assert html.startswith('<meta charset="utf-8">')
    assert "cdn" not in html.lower()
    assert "<link" not in html
    assert 'src="' not in html


def test_export_html_contains_three_tabs(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'data-tab="tab-design"' in html
    assert 'data-tab="tab-datasource"' in html
    assert 'data-tab="tab-dashboard"' in html
    assert "リネーム後名称" in html
    assert "計算フィールド" in html


def test_export_html_embeds_field_names(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    def field_names(payload: dict) -> set[str]:
        return {
            field["name"]
            for datasource in payload["datasources"]
            for field in datasource["fields"]
        }

    assert field_names(_embedded_data(html)) == field_names(workbook.export_json())


def test_export_html_design_tab_uses_pickers(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    # フォントは選択式
    assert '<select id="d-font">' in html
    assert '<option value="Meiryo UI" selected>' in html
    assert '<option value="Tableau Book">' in html
    # カラーコードは色味を選べる
    for name in ("d-main", "d-sub1", "d-sub2", "d-text"):
        assert f'<input type="color" id="{name}-pick">' in html


def test_export_html_has_single_yaml_download(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'id="yaml-download"' in html
    assert html.count('class="act"') == 2  # 行を追加 / 選択行を削除 のみ
    for removed in ("rename-download", "calc-download", "design-download"):
        assert removed not in html
    assert 'download("twbpatch_config.yaml"' in html
    # design と datasources を 1 つの YAML にまとめる
    assert '"\\ndatasources:\\n"' in html or "datasources:" in html


def test_export_html_header_is_folded_into_sticky_nav(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "<header>" not in html
    assert "nav { position: sticky" in html
    # タイトルと件数はダウンロードボタンの右隣に置く
    nav = html[html.index("<nav>"):html.index("</nav>")]
    assert nav.index('id="yaml-download"') < nav.index('class="meta"')
    assert "データソース 1 件" in nav


def test_export_html_datasource_panels_are_exclusive_accordions(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'class="panel acc open" id="acc-rename"' in html
    assert 'class="panel acc" id="acc-calc"' in html
    assert 'ACCORDIONS = ["acc-rename", "acc-calc"]' in html


def test_export_html_has_range_selection_and_row_delete(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    # 範囲選択・複数セルのコピー・貼り付け
    assert 'addEventListener("copy"' in html
    assert 'addEventListener("paste"' in html
    assert 'setData("text/plain"' in html
    assert 'addEventListener("mouseover"' in html
    # 計算フィールドの行削除
    assert 'id="calc-delete"' in html
    assert "selectedRowRange" in html
    # 元に戻す / やり直し
    assert "function undo()" in html
    assert "function redo()" in html
    assert 'key === "y"' in html


def test_export_html_keeps_japanese_and_escapes_markup(tmp_path) -> None:
    source = tmp_path / "escape.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上&amp;分析">
      <column name="[a]" caption="&lt;script&gt;売上" datatype="integer" role="measure" />
    </datasource>
  </datasources>
  <worksheets />
  <dashboards />
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    data = _embedded_data(html)
    names = [field["name"] for field in data["datasources"][0]["fields"]]
    assert "<script>売上" in names
    assert "売上&分析" == data["datasources"][0]["name"]
    # 生の </script> が埋め込みデータを閉じてしまわないこと
    assert html.count("</script>") == 2


def test_export_html_refuses_to_overwrite(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    target = tmp_path / "config.html"
    workbook.export_html(target)

    with pytest.raises(FileExistsError):
        workbook.export_html(target)

    workbook.export_html(target, overwrite=True)
