from __future__ import annotations

import json
import re

import pytest

from twbpatch import TwbWorkbook


SAMPLE = "tests/sample_minimal.twb"


def _embedded_rules(html: str) -> list[dict]:
    match = re.search(r"const PROMPT_RULES = (\[.*?\]);", html, re.S)
    assert match is not None
    return json.loads(match.group(1).replace("<\\/", "</"))


def test_prompt_rules_are_embedded_in_filename_order(tmp_path) -> None:
    html = TwbWorkbook.open(SAMPLE).export_html(tmp_path / "config.html").read_text(encoding="utf-8")
    rules = _embedded_rules(html)

    assert [rule["name"] for rule in rules] == [
        "00-common-rules.md", "10-customer-data.md", "20-product-data.md"
    ]
    assert [rule["default_checked"] for rule in rules] == [True, False, False]
    assert "データソース構造" in rules[0]["text"]
    assert "入力項目：" in rules[1]["text"]


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

    original = "Keep __TITLE__ and __FIELD_PROMPT__ literal."
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
    assert 'promptRuleOptions.hidden = true;' in html
