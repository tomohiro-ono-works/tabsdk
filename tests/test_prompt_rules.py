from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from twbpatch import TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def test_prompt_rule_files_live_under_template_directory() -> None:
    import twbpatch.html_export as html_export

    template_dir = Path(html_export.__file__).resolve().parent.parent / "template"
    assert html_export._PROMPT_RULES_DIR == template_dir / "prompt_rules"
    assert html_export._CALC_PROMPT_RULES_DIR == template_dir / "calc_prompt_rules"
    assert (template_dir / "prompt_rules" / "00-common-rules.md").is_file()
    assert (template_dir / "calc_prompt_rules" / "00-calculation-rules.md").is_file()


def _embedded_rules(html: str) -> list[dict]:
    match = re.search(r"const PROMPT_RULES = (\[.*?\]);", html, re.S)
    assert match is not None
    return json.loads(match.group(1).replace("<\\/", "</"))


def _embedded_calc_rules(html: str) -> list[dict]:
    match = re.search(r"const CALC_PROMPT_RULES = (\[.*?\]);", html, re.S)
    assert match is not None
    return json.loads(match.group(1).replace("<\\/", "</"))


def test_prompt_rules_are_embedded_in_filename_order(tmp_path) -> None:
    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")
    rules = _embedded_rules(html)

    names = [rule["name"] for rule in rules]
    assert names == sorted(names)
    assert {"00-common-rules.md", "10-customer-data.md", "20-product-data.md"} <= set(names)
    assert [rule["name"] for rule in rules if rule["default_checked"]] == ["00-common-rules.md"]
    by_name = {rule["name"]: rule["text"] for rule in rules}
    assert "データソース構造" in by_name["00-common-rules.md"]
    assert "入力項目：" in by_name["10-customer-data.md"]


def test_field_guidance_is_in_common_md_without_repeating_base_prompt(tmp_path) -> None:
    import twbpatch.html_export as html_export

    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")
    common = next(rule["text"] for rule in _embedded_rules(html) if rule["name"] == "00-common-rules.md")
    base = html_export._FIELD_PROMPT

    for heading in ("# リネーム後名称の決め方", "# フォルダの決め方", "# 階層の決め方"):
        assert heading not in base
        assert heading in common
    assert "出力の例:" not in base
    assert "入力と同じ行数・同じ並びで、4 列だけ" in base
    assert "ディメンションとメジャーは別のフォルダ" in common
    assert "複数の分類ファイル" in common


def test_calculation_examples_are_only_in_md_while_output_contract_stays_in_base(tmp_path) -> None:
    import twbpatch.html_export as html_export

    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")
    base = html_export._CALC_PROMPT
    calc_rules = next(rule["text"] for rule in _embedded_calc_rules(html) if rule["name"] == "00-calculation-rules.md")

    assert "IIF(" not in base
    assert "SUM(" not in base
    assert "5 列を半角の縦棒 2 つ（||）" in base
    assert "データ型は string / integer / real / boolean / date / datetime" in base
    assert "IIF([当年・昨年区分]" in calc_rules
    assert "集計してから割る式" in calc_rules


def test_prompt_rules_scan_only_direct_md_files(tmp_path) -> None:
    from twbpatch.html_export import _load_prompt_rules

    (tmp_path / "b.md").write_text("商品", encoding="utf-8")
    (tmp_path / "a.md").write_text("顧客", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("ignored", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inside.md").write_text("ignored", encoding="utf-8")

    assert _load_prompt_rules(tmp_path) == [
        {"name": "a.md", "text": "顧客", "default_checked": False},
        {"name": "b.md", "text": "商品", "default_checked": False},
    ]


def test_prompt_rules_read_error_names_file(tmp_path) -> None:
    from twbpatch.html_export import _load_prompt_rules

    (tmp_path / "broken.md").write_bytes(b"\xff")
    with pytest.raises(ValueError, match="broken.md"):
        _load_prompt_rules(tmp_path)


def test_prompt_rules_empty_folder_is_allowed(tmp_path) -> None:
    from twbpatch.html_export import _load_prompt_rules

    assert _load_prompt_rules(tmp_path) == []


def test_prompt_rules_escape_script_terminator(tmp_path, monkeypatch) -> None:
    import twbpatch.html_export as html_export

    (tmp_path / "danger.md").write_text("</script><script>alert(1)</script>", encoding="utf-8")
    monkeypatch.setattr(html_export, "_PROMPT_RULES_DIR", tmp_path)
    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert _embedded_rules(html)[0]["text"] == "</script><script>alert(1)</script>"
    assert "</script><script>alert(1)" not in html


def test_prompt_rules_preserve_template_tokens(tmp_path, monkeypatch) -> None:
    import twbpatch.html_export as html_export

    original = "Keep __TITLE__, __FIELD_PROMPT__, and __CALC_PROMPT_RULES__ literal."
    (tmp_path / "tokens__TITLE__.md").write_text(original, encoding="utf-8")
    monkeypatch.setattr(html_export, "_PROMPT_RULES_DIR", tmp_path)
    html = TwbWorkbook.open(SAMPLE).export_html(
        tmp_path / "config.html", title="Different title"
    ).read_text(encoding="utf-8")

    assert _embedded_rules(html)[0] == {
        "name": "tokens__TITLE__.md",
        "text": original,
        "default_checked": False,
    }


def test_prompt_rules_checkbox_ui_is_available_for_field_prompt(tmp_path) -> None:
    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'id="prompt-rule-options"' in html
    assert 'id="prompt-rule-checkboxes"' in html
    assert "function renderPromptRuleCheckboxes()" in html
    assert "function syncPromptRules()" in html
    assert "<!-- twbpatch:reference-rules:start -->" in html
    assert "<!-- twbpatch:reference-rules:end -->" in html
    assert 'promptRuleOptions.hidden = PROMPT_RULES.length === 0;' in html


def test_calc_prompt_has_its_own_checkbox_group(tmp_path) -> None:
    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'id="calc-prompt-rule-checkboxes"' in html
    assert 'calcPromptRuleCheckboxes.hidden = false;' in html
    assert 'promptRuleOptions.hidden = CALC_PROMPT_RULES.length === 0;' in html
    assert 'openPrompt(calcPromptText() + promptRuleSection(),' in html


def test_calc_prompt_uses_separate_default_checked_md(tmp_path) -> None:
    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    field_names = {rule["name"] for rule in _embedded_rules(html)}
    calc_rules = _embedded_calc_rules(html)
    calc_names = {rule["name"] for rule in calc_rules}
    assert "00-common-rules.md" in field_names
    assert "00-calculation-rules.md" not in field_names
    assert "00-calculation-rules.md" in calc_names
    assert "00-common-rules.md" not in calc_names
    assert [rule["name"] for rule in calc_rules if rule["default_checked"]] == ["00-calculation-rules.md"]
    calculation_rule = next(rule for rule in calc_rules if rule["name"] == "00-calculation-rules.md")
    assert "# 文字列で絞り込む式（IIF）" in calculation_rule["text"]
    assert "# 集計してから割る式" in calculation_rule["text"]


def test_calc_prompt_rule_text_is_loaded_from_its_own_folder(tmp_path, monkeypatch) -> None:
    import twbpatch.html_export as html_export

    content = "Use __TITLE__ and __PROMPT_RULES__ literally. </script>"
    (tmp_path / "custom.md").write_text(content, encoding="utf-8")
    monkeypatch.setattr(html_export, "_CALC_PROMPT_RULES_DIR", tmp_path)
    html = TwbWorkbook.open(SAMPLE).export_html(
        tmp_path / "config.html", title="Different title"
    ).read_text(encoding="utf-8")

    assert _embedded_calc_rules(html) == [{
        "name": "custom.md", "text": content, "default_checked": False,
    }]
    assert "</script>" not in html.split("const CALC_PROMPT_RULES = ", 1)[1].split(";", 1)[0]
