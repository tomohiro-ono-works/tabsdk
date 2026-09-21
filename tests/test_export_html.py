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


def test_export_html_contains_four_tabs(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'data-tab="tab-design"' in html
    assert 'data-tab="tab-datasource"' in html
    assert 'data-tab="tab-dashboard"' in html
    assert 'data-tab="tab-kpi-tree"' in html
    assert '<section id="tab-kpi-tree">' in html
    assert "リネーム後名称" in html
    assert "計算フィールド" in html


def test_export_html_rename_table_has_no_hidden_column(tmp_path) -> None:
    """リネーム・フォルダ設定の表に「非表示」列は出さない（2026-09-13 削除）。

    読み取り専用の情報列で、リネーム・フォルダ設定の判断に使わないため外した。
    非表示フィールド自体は引き続き一覧に含まれる（列を消しただけで除外はしない）。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    rename_table = html[html.index('<table id="rename-table">'):html.index("</table>")]
    assert "非表示" not in rename_table
    assert rename_table.count("<th>") == 5
    assert "hidden:" not in html
    assert "row.cells[5]" not in html


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
    # サブカラー③・文字色①②・枠線の色は 2026-09-21 追加
    for name in (
        "d-main", "d-sub1", "d-sub2", "d-sub3", "d-text1", "d-text2", "d-border",
        "d-heat-min", "d-heat-mid", "d-heat-max",
    ):
        assert f'<input type="color" id="{name}-pick">' in html


def test_export_html_downloads_yaml_per_tab(tmp_path) -> None:
    """YAML のダウンロードはタブごと（2026-09-14）。そのタブで使う節だけを出す。

    以前はナビ右端の 1 つで全タブを束ねていたため、ダッシュボードタブを使わなくても
    dashboard: 節（段 0）が出て、適用すると空のダッシュボードが増えていた。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    nav = html[html.index("<nav>"):html.index("</nav>")]
    assert 'class="dl"' not in nav
    assert 'id="yaml-download"' not in html
    for removed in ("rename-download", "calc-download", "design-download"):
        assert removed not in html
    assert html.count('class="act"') == 3  # 行を追加 / 選択行を削除 / 段を追加

    def section(section_id: str) -> str:
        start = html.index(f'<section id="{section_id}"')
        return html[start:html.index("</section>", start)]

    assert 'id="yaml-download-datasources"' in section("tab-datasource")
    assert 'id="yaml-download-dashboard"' in section("tab-dashboard")
    assert 'id="yaml-download-kpi-tree"' in section("tab-kpi-tree")
    assert 'class="dl"' not in section("tab-design")

    assert 'downloadYaml("twbpatch_datasources.yaml", datasourceErrors(),' in html
    assert 'yamlHeader(["datasources"]) + datasourcesYaml()' in html
    assert 'downloadYaml("twbpatch_dashboard.yaml", errors, () =>' in html
    assert 'yamlHeader(["design", "datasources", "dashboard"])' in html
    assert 'downloadYaml("twbpatch_kpi_tree.yaml", errors, () =>' in html
    assert 'yamlHeader(["design", "datasources", "kpi_tree"])' in html
    # 段が 0 のダッシュボードは出さない
    assert 'if (!DASH.rows.length) return ["ダッシュボード: 段がありません"];' in html


def test_export_html_header_is_folded_into_sticky_nav(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "<header>" not in html
    assert "nav { position: sticky" in html
    # タイトルと件数はタブの右隣に置く
    nav = html[html.index("<nav>"):html.index("</nav>")]
    assert nav.index('data-tab="tab-kpi-tree"') < nav.index('class="meta"')
    assert "データソース 1 件" in nav


def test_export_html_datasource_panels_are_exclusive_accordions(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'class="panel acc open" id="acc-rename"' in html
    assert 'class="panel acc" id="acc-calc"' in html
    assert 'EXCLUSIVE = ["acc-rename", "acc-calc"]' in html
    # 三角アイコンの \25B6 が Python の 8 進エスケープに食われないこと
    assert r'content: "\25B6"' in html
    assert not [c for c in html if ord(c) < 32 and c not in "\n\t\r"]


def test_export_html_table_columns_are_resizable(tmp_path) -> None:
    """リネーム表・計算フィールド表の列幅は利用者がドラッグで変更できる
    （2026-09-13 追加、隣接列間だけで幅をやり取りする方式と、判定を表全体への
    座標判定に変える方式に同日中でさらに修正）。`table-layout: fixed` にし、
    `<colgroup>` の `<col>` 幅を書き換える。`<thead>` はデータの再描画では
    作り直さないため、一度つければ持続する。

    境界 i のドラッグは col[i] と col[i+1] の幅の合計を変えずに2列間だけで
    やり取りする。動かした列だけを % から px に変えると、他の列は % のまま残り、
    table-layout: fixed が「列幅の合計を表の幅に一致させる」ために動かしていない
    列（特に左隣）まで再配分してしまう実害があったため。

    判定は th 内の小さなつまみ要素ではなく、表全体への mousedown で
    「クリック位置が列境界の x 座標に近いか」を見る方式にした。th の高さだけが
    当たり判定だと、見た目の縦線（表の全行にまたがる）のごく一部でしかつかめず
    シビアだったため。`enableGrid()` のセル選択（`event.target.closest("td")`、
    bubble フェーズ）より確実に先に判定できるよう capture フェーズで登録する。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "table-layout: fixed" in html
    assert "function enableColumnResize(table)" in html
    assert 'enableColumnResize(document.getElementById("rename-table"));' in html
    assert 'enableColumnResize(document.getElementById("calc-table"));' in html
    # <colgroup> の列数はヘッダーの列数と一致する
    rename_table = html[html.index('<table id="rename-table">'):html.index("</table>")]
    assert rename_table.count("<col ") == 5
    calc_start = html.index('<table id="calc-table">')
    calc_table = html[calc_start:html.index("</table>", calc_start)]
    assert calc_table.count("<col ") == 5
    # sticky ヘッダーを壊さないよう、JS 側で position を上書きしない
    assert 'th.style.position' not in html
    # 隣接列とだけ幅をやり取りする（他の列の % を残さない）
    assert "function freezeAllColumnWidths()" in html
    assert "cols[dragIndex + 1].style.width = (pairWidth - width) + " in html
    # 表全体への座標判定（th 内のつまみ要素ではない）で、セル選択より先に発火する
    assert "function boundaryAt(clientX)" in html
    assert 'table.addEventListener("mousedown", event => {' in html
    assert "event.stopImmediatePropagation();" in html
    assert '}, true);' in html
    assert "col-resize-handle" not in html


def test_export_html_column_resize_refreezes_widths_on_every_drag(tmp_path) -> None:
    """列幅を実測 px へ固定する処理は、ドラッグを始めるたびに呼び直す
    （2026-09-13 修正）。

    計算フィールド表（`#calc-table`）はアコーディオンが既定で折りたたまれている
    （`.acc-body { display: none; }`）。ページ読み込み時の1回だけ固定していると、
    非表示の間は `getBoundingClientRect()` が 0 を返すため全列が幅0pxで固定
    されてしまい、後で列を1つ動かした瞬間に「指定した合計が表の幅に足りない分」
    の帳尻合わせで他の列が一気に広がって壊れる実害があった。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'class="panel acc" id="acc-calc"' in html  # 既定で折りたたまれている
    assert "function freezeAllColumnWidths()" in html
    mousedown_start = html.index('table.addEventListener("mousedown", event => {')
    mousedown_block = html[mousedown_start:html.index("}, true);", mousedown_start)]
    assert "freezeAllColumnWidths();" in mousedown_block


def test_export_html_column_resize_does_not_block_cell_focus(tmp_path) -> None:
    """列幅ドラッグの判定は境界付近のセルへのフォーカスを妨げない（2026-09-13）。

    データ型・役割・フォルダの候補ポップアップは `focus` イベントで開くが、
    `enableColumnResize()` の mousedown で `preventDefault()` していたため、
    セルの端（列の境界に近い判定域）をクリックするとフォーカス自体が起きず
    ポップアップが開かない実害があった。列が狭いほど大部分が判定域に入るため、
    データ型・役割の列（幅の13%）ではほぼ常に再現した。
    ドラッグ中の文字選択は `table.col-resizing` の `user-select: none` で防ぐため、
    `preventDefault()` は不要だった。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    resize_start = html.index("function enableColumnResize(table)")
    resize_end = html.index("\n}\n", html.index('table.addEventListener("mousedown"', resize_start))
    resize_block = html[resize_start:resize_end]
    assert "event.preventDefault()" not in resize_block
    assert "table.col-resizing { user-select: none; }" in html


def test_export_html_enter_inserts_a_line_break_while_editing(tmp_path) -> None:
    """編集中の Enter はセル内改行、確定は Ctrl+Enter（2026-09-13 変更）。

    当初は Excel に合わせて Alt+Enter だけを改行にしていたが、この表で複数行に
    なるのは主に式なので、書きやすさを採って入れ替えた。Alt+Enter は Excel の
    指の記憶に合わせた別名として残す。選んでいるだけのとき（編集中でない）の
    Enter は従来どおり1つ下のセルへ移動する。

    挿入するのは `<br>` ではなく素の `"\\n"` テキストノードにする。`textContent` は
    `<br>` を無視して前後を連結してしまうため、`<br>` だと `captureInto()` などの
    読み取り側で改行が消える（式の複数行が1行に潰れる）。`white-space: pre-wrap`
    を `td[data-edit]` に指定し、素の改行を画面上でも折り返して見せる。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "td[data-edit] { white-space: pre-wrap; }" in html
    assert (
        'const insertsLineBreak = event.key === "Enter"\n'
        '      && (event.altKey || (editing && !event.ctrlKey && !event.metaKey));' in html
    )
    assert "if (insertsLineBreak && isEditable(cell)) {" in html
    assert 'const lineBreak = document.createTextNode("\\n");' in html
    assert "range.insertNode(lineBreak);" in html
    assert 'cell.dispatchEvent(new Event("input", { bubbles: true }));' in html


def test_export_html_cells_select_first_then_edit_on_second_click(tmp_path) -> None:
    """Excel と同じく、1クリック目でセルを選び、2クリック目でテキスト編集に入る
    （2026-09-13 追加）。

    以前はセルが常に `contenteditable` で、1クリックで即キャレットが入っていた。
    セルは既定では編集不可にし（`data-edit` 属性で「編集できるセル」を表す）、
    選択中も矢印移動・コピーが効くよう `tabindex` でフォーカスできるようにする。
    2クリック目（＝すでに選んでいるセルをもう一度押す）で `beginEdit()` が
    `contenteditable` を付ける。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    # 生成するセルは data-edit / tabindex を持ち、contenteditable は持たない
    assert 'el("td", { "data-edit": "1", tabindex: "-1", text: text })' in html
    assert 'el("td", { class: "ro", tabindex: "-1", text: text })' in html
    assert 'contenteditable: "true"' not in html
    # 編集の出入り口
    assert "function beginEdit(cell, clientX, clientY)" in html
    assert 'cell.setAttribute("contenteditable", "true");' in html
    assert "function endEdit()" in html
    assert 'cell.removeAttribute("contenteditable");' in html
    # 2クリック目の判定と、1クリック目でキャレットを入れない preventDefault
    assert "const second = isAnchor(cell) && isEditable(cell);" in html
    assert "beginEdit(cell, event.clientX, event.clientY);" in html
    # 選んでいるセルは枠線で示す
    assert "td.active { outline: 2px solid #4a7dff; outline-offset: -2px; }" in html
    assert 'cell.classList.toggle("active"' in html


def test_export_html_selected_cell_keyboard_matches_excel(tmp_path) -> None:
    """選択中のキー操作を Excel に合わせる（2026-09-13 追加）。

    F2 で編集開始、文字キーで置き換えて編集開始、Escape で編集を抜ける、
    Delete は選択セルを消す、左右キーは編集中だけキャレット移動で、
    選んでいるだけのときは隣のセルへ移動する。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'if (event.key === "F2" && isEditable(cell))' in html
    assert "event.key.length === 1" in html
    assert 'cell.textContent = event.key;' in html
    assert '} else if (event.key === "Escape") {' in html
    assert 'forEachSelected(c => { if (isEditable(c)) c.textContent = ""; });' in html
    # 編集中はセルの外へ出さない。矢印はセル内のキャレット移動、Ctrl+Enter で選択へ戻る
    assert (
        'if (editing && event.key === "Enter" && (event.ctrlKey || event.metaKey)) {' in html
    )
    assert 'if (editing && event.key.startsWith("Arrow")) return;' in html
    # 編集中はセル内の文字選択をそのままコピー、選択中は1セルでもコピーできる
    assert "if (activeGrid !== table || editing || sel.r1 < 0) return;" in html
    # 編集中の貼り付けはキャレット位置へ素のテキストで差し込む
    assert "if (editing) {" in html
    assert "const node = document.createTextNode(text.replace(/\\r/g, \"\"));" in html


def test_export_html_empty_cells_keep_the_row_height(tmp_path) -> None:
    """中身が空のセルでも行の高さを保つ（2026-09-13 修正）。

    セルを常時 `contenteditable` にしていた頃は、ブラウザが空セルにも
    キャレット1行分の高さを確保していた。1クリック＝選択に変えてセルが通常の
    要素になったため、中身が空の行がパディングだけの高さ（実測 7px）に潰れた。
    計算フィールド表は初期表示で空行を3行足すので、そこで顕著に出た。
    表のセルの `height` は最小値として効くので、中身が増えれば行は伸びる。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "td { height: 23px; }" in html


def test_export_html_choice_popup_closes_in_capture_phase(tmp_path) -> None:
    """候補ポップアップの「外側クリックで閉じる」は capture フェーズで行う
    （2026-09-13 修正）。

    セル選択が mousedown の中で自前に `cell.focus()` を呼ぶようになり、その
    focus で開いた候補ポップアップを、同じクリックの続きで流れてくる
    「外側クリックで閉じる」処理が即座に閉じてしまっていた（フォルダ・データ型・
    役割の候補が1クリックでは出ない）。capture なら開く前に走るので、前の
    ポップアップだけを閉じて新しいものは残る。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    close_start = html.index("if (choicePopup && !choicePopup.contains(event.target)) closeFolderPopup();")
    assert html[close_start:close_start + 120].find("}, true);") > 0


def test_export_html_dashboard_tab_is_an_editor(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    # ヘッダー編集とボディ（縦段組 → 横配置 → エリア）
    assert 'id="acc-dashboard"' in html
    assert 'id="acc-header"' in html
    assert 'id="acc-body"' in html
    # エリアは 360px 固定で、段の中を横スクロールする
    assert ".area { flex: 0 0 360px; width: 360px;" in html
    assert ".areas { display: flex; gap: 10px; padding: 12px; overflow-x: auto;" in html
    # px の入力は 10 刻み。既定は段の高さ 300 / エリアの幅 600
    assert '<input type="number" step="10" min="0" id="db-width" value="1600">' in html
    # 段の高さだけは 60 刻み（2026-09-21 に 10 から変更）
    assert 'type: "number", step: "60", min: "0", value: row.height' in html
    assert 'height: "300"' in html
    assert 'width: "600"' in html
    # 段とエリアはドラッグで動かす。左右ボタンは持たない
    assert "function attachGrip(" in html
    assert 'kind: "area"' in html and 'kind: "row"' in html
    assert 'text: "←"' not in html and 'text: "→"' not in html
    # 色はデザインルールを参照できる
    assert "function colorControl(" in html
    assert '{ key: "main_color", label: "メインカラー", input: "d-main" }' in html
    # 段ごとにも畳める
    assert ".row-card.collapsed > .areas { display: none; }" in html
    assert 'row.collapsed = !row.collapsed' in html
    assert 'id="rows-root"' in html
    assert 'id="row-add"' in html
    assert "エリアを追加" in html
    # 既存ダッシュボードの読み取り表示は持たない
    assert "dash-root" not in html
    # dashboard: セクションが YAML に出る
    assert 'let out = "dashboard:\\n"' in html
    assert "function dashboardYaml()" in html


def test_export_html_dashboard_areas_can_be_duplicated(tmp_path) -> None:
    """エリアはドラッグでの移動に加え、複製ボタンでコピーできる（2026-09-08 追加）。"""
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "function cloneArea(area)" in html
    assert 'title: "エリアを複製"' in html
    assert "row.areas.splice(row.areas.indexOf(area) + 1, 0, copy)" in html


def test_export_html_dashboard_can_generate_sheet_names(tmp_path) -> None:
    """シート名欄の右隣に、グラフ種類と選んだ項目から名前を作るボタンを持つ
    （2026-09-08 追加）。前年比の時系列・前年差帳票はメイン指標①のみを使う。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "function generateSheetName(area)" in html
    assert 'title: "グラフ種類と選んだ項目からシート名を生成"' in html
    assert 'draw_card: { label: "スコア", fields: [{ name: "main_metric" }] }' in html


def test_export_html_dashboard_validates_required_params_before_download(tmp_path) -> None:
    """必須パラメータが空のエリアのまま YAML をダウンロードさせない（2026-09-08 追加）。

    これまでダウンロード前の検証はデータソースタブの `validateState()` だけで、
    ダッシュボードタブは何も検証していなかった。グラフ種類だけ選んでパラメータを
    埋め忘れたエリアがそのまま YAML に出て、`apply_config()` の `TypeError`
    （missing required keyword-only argument）になっていた。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "function validateDashboard()" in html
    assert "errors.push.apply(errors, validateDashboard())" in html
    assert 'errors.push(label + ": シート名が空")' in html
    assert 'errors.push(label + ": フィールドが未選択")' in html
    assert "specs.filter(spec => spec.required).forEach(spec => {" in html


def test_export_html_fixed_choice_params_are_dropdowns(tmp_path) -> None:
    """値が固定の選択肢しかない引数はプルダウンにする（2026-09-12 追加）。

    以前は item_shelf（rows/columns の2択）が自由テキスト入力で、正しい値が
    分からないまま英単語を手で打ち込む必要があった。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    match = re.search(r'id="draw-specs">(.*?)</script>', html, re.S)
    assert match is not None
    specs = json.loads(match.group(1).replace("<\\/", "</"))

    item_shelf = next(p for p in specs["draw_bar"]["params"] if p["name"] == "item_shelf")
    assert item_shelf["kind"] == "select"
    assert item_shelf["choices"] == [["rows", "横棒（行）"], ["columns", "縦棒（列）"]]

    assert 'spec.kind === "select"' in html
    # bar_color は draw_bar に新規追加した色引数
    bar_color = next(p for p in specs["draw_bar"]["params"] if p["name"] == "bar_color")
    assert bar_color["kind"] == "color"


def test_export_html_draw_card_hides_value_color_and_mirrors_main_color(tmp_path) -> None:
    """スコアカードの `value_color` / `title_background_color` は画面に出さず、
    YAML出力時に `main_color` をそのまま複製する（2026-09-12, 2026-09-13）。
    `vertical_alignment` も「縦は常に中央でよい」との指摘を受けて画面から外し、
    API 既定の "center" のまま渡す（2026-09-13）。Python 側の `draw_card()` は
    3つとも引数を持ったまま変更しない。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    match = re.search(r'id="draw-specs">(.*?)</script>', html, re.S)
    assert match is not None
    specs = json.loads(match.group(1).replace("<\\/", "</"))
    names = [p["name"] for p in specs["draw_card"]["params"]]
    assert "value_color" not in names
    assert "title_background_color" not in names
    assert "vertical_alignment" not in names
    assert "main_color" in names

    assert (
        'if (chart === "draw_card" && params.main_color) {' in html
    )
    assert "params.value_color = params.main_color;" in html
    assert "params.title_background_color = params.main_color;" in html


def test_export_html_draw_quadrant_colors_is_four_pickers(tmp_path) -> None:
    """`draw_quadrant.colors`（4色必要）は単一色ピッカーにしない（2026-09-12 修正）。

    以前は引数名に "color" を含むという理由だけで単一色ピッカー扱いになり、
    4色を指定する手段が画面に無かった（実質使えないバグ）。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    match = re.search(r'id="draw-specs">(.*?)</script>', html, re.S)
    assert match is not None
    specs = json.loads(match.group(1).replace("<\\/", "</"))
    colors = next(p for p in specs["draw_quadrant"]["params"] if p["name"] == "colors")
    assert colors["kind"] == "colors"

    assert "function colorsControl(area, spec, value)" in html
    assert 'spec.kind === "colors"' in html
    assert (
        'const DEFAULT_QUADRANT_COLORS = '
        '["#4400FF", "#FF007F", "#00C888", "#CCD500"];' in html
    )


def test_export_html_draw_quadrant_colors_are_labeled_by_quadrant(tmp_path) -> None:
    """4色ピッカーのどれがどの象限かをラベルで示す（2026-09-12 追加）。

    draw.py の quadrant_formula は colors[0]〜[3] を「x/y とも中央値以上」→
    「x が中央値未満・y は以上」→「両方未満」→「x は以上・y は未満」の順、
    つまり右上・左上・左下・右下の順に固定して割り当てる。ラベルが無いと
    画面上でどのピッカーがどの象限かわからず、意図した配色にならない。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert (
        'const QUADRANT_COLOR_LABELS = ["右上", "左上", "左下", "右下"];' in html
    )
    assert 'class: "colors4-label", text: QUADRANT_COLOR_LABELS[index]' in html


def test_export_html_validates_crosstab_color_trio(tmp_path) -> None:
    """`draw_crosstab` の min/mid/max_color は3つ揃えるか全く指定しないかの
    どちらか（2026-09-12 追加）。以前は検証しておらず、2色だけ指定した状態で
    保存でき、`apply_config()` の `ValueError` で初めて気づく状態だった。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'if (area.chart === "draw_crosstab") {' in html
    assert 'const trio = ["min_color", "mid_color", "max_color"];' in html
    assert "最小値・中間・最大値の色は3つ揃えるか" in html


def test_export_html_crosstab_defaults_to_design_heatmap_colors(tmp_path) -> None:
    """`draw_crosstab` を選ぶと min/mid/max_color がデザインルールの既定3色を
    自動参照する（2026-09-12 追加）。3つ揃えるかゼロかしか許されないのに、
    グラフを置くたびに3色を手入力させるのは非現実的だったため、デザインルール
    タブに既定のヒートマップ3色を用意し、グラフ側は初期状態でそれを参照する。
    個別の色にしたい場合はグラフ側で「個別に指定」に切り替えられる。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert (
        'function defaultParamsFor(chart) {\n'
        '  if (chart === "draw_crosstab") {\n'
        '    return { min_color: "@min_color", mid_color: "@mid_color",'
        ' max_color: "@max_color" };\n'
        '  }\n'
        '  return {};\n'
        '}' in html
    )
    assert 'area.params = defaultParamsFor(chart.value);' in html
    # デザインルールタブの既定3色（ヒートマップ用）とその参照キー（色は 2026-09-21 変更）
    assert '<input type="color" id="d-heat-min-pick"><input type="text" id="d-heat-min" value="#ce70f0">' in html
    assert '<input type="color" id="d-heat-mid-pick"><input type="text" id="d-heat-mid" value="#ffffff">' in html
    assert '<input type="color" id="d-heat-max-pick"><input type="text" id="d-heat-max" value="#2366e1">' in html
    assert '{ key: "min_color", label: "ヒートマップ：最小値の色", input: "d-heat-min" }' in html
    assert '{ key: "mid_color", label: "ヒートマップ：中間の色", input: "d-heat-mid" }' in html
    assert '{ key: "max_color", label: "ヒートマップ：最大値の色", input: "d-heat-max" }' in html
    assert 'out += "  min_color: " + yamlKey(value("d-heat-min")) + "\\n";' in html
    assert 'out += "  mid_color: " + yamlKey(value("d-heat-mid")) + "\\n";' in html
    assert 'out += "  max_color: " + yamlKey(value("d-heat-max")) + "\\n";' in html


def test_export_html_action_settings_match_the_receiver(tmp_path) -> None:
    """アクション設定が `dashboard.create_action()` に渡せる形か（H-1、2026-09-07）。"""
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    # 種類はフィルターと URL の 2 つ。ハイライトは受け手が無いので出さない
    assert 'const ACTION_LABELS = { filter: "フィルター", url: "URL を開く" };' in html
    assert "highlight" not in html
    # フィルターアクションは絞り込むフィールドが要る（「すべてのフィールド」は扱わない）
    assert "絞り込むフィールド" in html
    assert 'fieldOptions(area.datasource, area.action.field, "dimension")' in html
    # 種別ごとに出す項目が変わる
    assert "対象シート" in html
    assert 'labeled("URL", url)' in html
    # YAML も種別ごとに変わる
    assert 'out += "            url: " + yamlKey(area.action.target)' in html
    assert 'out += "            field: " + yamlKey(area.action.field)' in html


def test_export_html_draw_specs_come_from_real_signatures(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    match = re.search(r'id="draw-specs">(.*?)</script>', html, re.S)
    assert match is not None
    specs = json.loads(match.group(1).replace("<\\/", "</"))

    assert set(specs) == {
        name for name in dir(TwbWorkbook) if name.startswith("draw_")
    }
    names = {param["name"]: param for param in specs["draw_bar"]["params"]}
    assert names["item"]["kind"] == "field" and names["item"]["required"]
    assert names["descending"]["kind"] == "bool"
    assert "datasource" not in names and "name" not in names
    assert specs["draw_sheet"]["params"][0]["kind"] == "fields"  # list[FieldInput]

    # 画面には日本語を出し、英語名は title 属性で辿れるようにする
    assert specs["draw_bar"]["label"] == "棒グラフ"
    assert names["item"]["label"] == "項目"
    assert names["descending"]["label"] == "降順にする"

    # 項目はディメンション、メジャーはメジャーだけを候補にする
    assert names["item"]["role"] == "dimension"
    assert names["metric"]["role"] == "measure"
    assert names["descending"]["role"] is None
    crosstab = {p["name"]: p for p in specs["draw_crosstab"]["params"]}
    assert crosstab["x_item"]["role"] == "dimension"
    assert crosstab["color_metric"]["role"] == "measure"
    assert 'if (role && field.role !== role) return;' in html
    assert "if (field.hidden) return;" in html

    # 集計方法は画面に出さない。役割とデータ型から自動で決まるため
    assert [
        (chart, param["name"])
        for chart, spec in specs.items()
        for param in spec["params"]
        if "aggregation" in param["name"]
    ] == []
    # 必須だけ前面に出し、残りは詳細設定に畳む
    assert 'el("summary", { text: "詳細設定（"' in html
    assert "specs.filter(spec => spec.required)" in html

    # フィールドを取る引数はすべて役割が決まっていること
    assert [
        (chart, param["name"])
        for chart, spec in specs.items()
        for param in spec["params"]
        if param["kind"] in ("field", "fields") and not param["role"]
    ] == []

    # 訳し漏れがあれば英語名がそのまま画面に出るので、漏れが無いことを固定する
    untranslated = [
        (chart, param["name"])
        for chart, spec in specs.items()
        for param in spec["params"]
        if param["label"] == param["name"]
    ]
    assert untranslated == []
    assert [chart for chart, spec in specs.items() if spec["label"] == chart] == []


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


def test_export_html_folder_defaults_to_unspecified_with_a_picker(tmp_path) -> None:
    """フォルダ未指定でもリネームが `renames` として出力される（2026-09-08 追加）。

    以前はフォルダ欄が空だとリネームが `folders` に一切出力されず消えていた。
    フォルダ欄はセル型の表のまま（コピー・貼り付けを壊さない）で、フォーカス時に
    候補一覧をポップアップ表示する。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'const NO_FOLDER = "フォルダ未指定";' in html
    assert "folder: folderNameOf(ds, field) || NO_FOLDER," in html
    assert "function isNoFolder(folder)" in html
    assert "function openChoicePopup(cell, candidates)" in html
    assert '.addEventListener("focus", () => openChoicePopup(folderCell, folderCandidates()))' in html
    assert "renames.push([row.original, row.display])" in html
    assert 'out += "    renames:\\n"' in html
    # 計算フィールドのフォルダ列も同じ「フォルダ未指定」ピッカーを使うが、
    # 出力時は isNoFolder() で判定してフォルダ未指定なら folder キーを出さない
    # （そうしないと「フォルダ未指定」という名前の実フォルダが作られてしまう）
    assert (
        'field.name || "", field.formula || "", folderNameOf(ds, field) || NO_FOLDER,'
        in html
    )
    assert "if (cells[2] && !isNoFolder(cells[2])) {" in html


def test_export_html_calc_table_column_order_and_validation(tmp_path) -> None:
    """計算フィールド表の列順は 名前/式/フォルダ/データ型/役割（2026-09-12 変更）。

    フォルダは自由入力のまま検証しない。データ型・役割はフォーカス時の候補
    ポップアップに加え、自由入力も許すが、候補にない文字列は赤くしてエラー
    欄に出す。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert (
        "<th>名前</th><th>式</th><th>フォルダ</th><th>データ型</th><th>役割</th>"
        in html
    )
    assert "function calcRow(name, formula, folder, datatype, role)" in html
    assert (
        'const CALC_DATATYPE_CHOICES = '
        '["string", "integer", "real", "boolean", "date", "datetime"];'
        in html
    )
    assert 'const CALC_ROLE_CHOICES = ["measure", "dimension"];' in html
    assert (
        'datatypeCell.addEventListener("focus", '
        "() => openChoicePopup(datatypeCell, CALC_DATATYPE_CHOICES));" in html
    )
    assert (
        'roleCell.addEventListener("focus", '
        "() => openChoicePopup(roleCell, CALC_ROLE_CHOICES));" in html
    )
    assert "function validateCalc()" in html
    assert "function validateCalcState(state)" in html
    assert 'id="calc-errors"' in html
    assert "validateCalcState(EDITS[index]).forEach(message => {" in html


def test_export_html_field_dropdown_groups_by_folder(tmp_path) -> None:
    """ダッシュボードタブのフィールド選択は 1 つの select のまま、フォルダごとに
    optgroup でまとめる（2026-09-12 追加）。フォルダ未指定は最後に出す。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert 'options.push(el("optgroup", { label: group.folderName },' in html
    assert (
        'const folderName = folderNameOf(ds, field) || NO_FOLDER;' in html
    )
    assert "if (a === NO_FOLDER) return 1;" in html
    assert "if (b === NO_FOLDER) return -1;" in html


def test_export_html_multi_field_params_use_ordered_drag_drop_modal(tmp_path) -> None:
    """複数選択のフィールド引数（`items` 等）は `<select multiple>` でも
    チェックボックス一覧でもなく、左＝候補・右＝選択済みのモーダルで
    ドラッグ＆ドロップで並び順を指定できるようにする（2026-09-13）。

    `items`（土台シートの並び順）や `metrics`（帳票の行順）は選んだ「順序」が
    そのままシート上の配置順になる。Ctrl+クリック必須の select multiple は
    使いにくく、その代替のチェックボックス一覧も並び順を指定できなかった
    （候補の五十音順のままにしかならない）ため、順序を指定できる形にした。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "function openFieldOrderModal(area, spec, selected, onChange)" in html
    assert "function fieldsCheckControl(area, spec, value)" in html
    assert 'control = fieldsCheckControl(area, spec, value);' in html
    # 左（候補）→右（選択済み、この順で配置）の2カラム
    assert "候補（ダブルクリックまたはドラッグで追加）" in html
    assert "選択済み（この順でシートに配置）" in html
    # 右リスト内の並べ替えは段・エリアと同じ「上半分/下半分」判定を使う
    assert "function modalDropTarget(container, clientY)" in html
    assert 'setAttribute("multiple"' not in html
    assert "selectedOptions" not in html
    assert "openFieldCheckPopup" not in html


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
    assert html.count("</script>") == 3


def test_export_html_refuses_to_overwrite(tmp_path) -> None:
    workbook = TwbWorkbook.open(SAMPLE)
    target = tmp_path / "config.html"
    workbook.export_html(target)

    with pytest.raises(FileExistsError):
        workbook.export_html(target)

    workbook.export_html(target, overwrite=True)


def test_export_html_lists_chart_types_in_the_configured_order(tmp_path) -> None:
    """グラフ種類の選択肢は、よく使う順に固定する（2026-09-21）。

    以前はメソッド名の名前順（draw_bar → draw_card → …）で、意味のない並びだった。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    specs = json.loads(
        re.search(r'id="draw-specs">(.*?)</script>', html, re.S).group(1)
    )
    assert [spec["label"] for spec in specs.values()] == [
        "KPIカード",
        "棒グラフ",
        "帳票",
        "クロス集計（ヒートマップ）",
        "散布図（四象限）",
    ]


def test_export_html_dropdowns_can_be_filtered_by_typing(tmp_path) -> None:
    """プルダウンは文字入力で絞り込める（2026-09-21）。

    候補が多いフィールドの選択で、目で探すしかなかった。`<select>` を隠して
    `<input list>` + `<datalist>` を前に出し、呼び出し側は今までどおり
    `select.value` と change イベントで扱う。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "function searchable(select)" in html
    assert 'el("span", { class: "combo-wrap" }, [input, list, select])' in html
    assert ".combo-wrap select { display: none; }" in html
    # グラフ種類・データソース・フィールド・エリアの区分・アクションのどれも包む
    for call in (
        'searchable(chart)',
        'searchable(dsSelectEl)',
        'searchable(role)',
        'searchable(kind)',
        'searchable(type)',
        'searchable(source)',
    ):
        assert call in html


def test_export_html_marks_empty_or_duplicated_sheet_names(tmp_path) -> None:
    """シート名が空・重複なら入力欄を薄い赤にする（2026-09-21）。

    これまで重複はダウンロード前の検証でしか分からず、入力中は気づけなかった。
    """
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "function markSheetName(input, area)" in html
    assert "const bad = !name || usedSheetNames(area).has(name);" in html
    assert "input.bad { background: #ffe0e0; border-color: #e09090; }" in html


def test_export_html_filter_picks_the_role_before_the_field(tmp_path) -> None:
    """フィルターはディメンション / メジャーを選んでからフィールドを選ぶ（2026-09-21）。"""
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert '["dimension", "ディメンション"], ["measure", "メジャー"], ["", "すべて"],' in html
    assert "function filterRoleOf(area)" in html
    assert 'fieldOptions(area.datasource, area.filterField, filterRoleOf(area) || undefined)' in html


def test_export_html_hides_the_datasource_object_fields(tmp_path) -> None:
    """データソースそのものを表す擬似フィールドは画面に出さない（2026-09-21）。

    改名もフォルダ分類もできないのに、リネーム・フォルダ設定の表に並んでいた。
    """
    source = tmp_path / "object-field.twb"
    source.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<workbook>
  <datasources>
    <datasource name="ds1" caption="売上データ">
      <column name="[Sales]" caption="売上"
              datatype="real" role="measure" type="quantitative" />
      <column name="[__tableau_internal_object_id__].[Orders_ABC]" caption="Orders"
              datatype="table" role="measure" type="quantitative" />
    </datasource>
  </datasources>
</workbook>
""",
        encoding="utf-8",
    )
    workbook = TwbWorkbook.open(str(source))

    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert "__tableau_internal_object_id__" not in html
    assert "売上" in html
    # export_json() は .twb のままを返す（画面だけの絞り込み）
    assert any(
        field["id"].startswith("[__tableau_internal_object_id__]")
        for field in workbook.export_json()["datasources"][0]["fields"]
    )


def test_export_html_kpi_card_labels_use_the_main_and_sub_wording(tmp_path) -> None:
    """KPI カードの用語は メイン / サブ に揃える（2026-09-21）。"""
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert '"label": "メインメジャー"' in html
    assert '"label": "サブメジャー"' in html
    assert '"label": "メインカラー"' in html
    assert "主メジャー" not in html and "副メジャー" not in html


def test_export_html_design_tab_starts_with_the_house_palette(tmp_path) -> None:
    """デザインルールの既定色（2026-09-21 に決めた配色）。"""
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    for input_id, color in [
        ("d-main", "#2366e1"),
        ("d-sub1", "#ce70f0"),
        ("d-sub2", "#ccd500"),
        ("d-sub3", "#4a9ca5"),
        ("d-text1", "#202020"),
        ("d-text2", "#4e4e4e"),
        ("d-heat-min", "#ce70f0"),
        ("d-heat-mid", "#ffffff"),
        ("d-heat-max", "#2366e1"),
    ]:
        assert f'<input type="text" id="{input_id}" value="{color}">' in html


def test_export_html_design_tab_defaults_to_narrow_spacing(tmp_path) -> None:
    """余白は「広い / 狭い」で、既定は狭い（2026-09-21）。"""
    workbook = TwbWorkbook.open(SAMPLE)
    html = workbook.export_html(tmp_path / "config.html").read_text(encoding="utf-8")

    assert '<input type="radio" name="d-space" value="wide"> 広い' in html
    assert '<input type="radio" name="d-space" value="narrow" checked> 狭い' in html
