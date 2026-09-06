from __future__ import annotations

import json
from typing import Any

_STYLE = """
* { box-sizing: border-box; }
body { margin: 0; font: 13px/1.6 "Meiryo UI", "Hiragino Kaku Gothic ProN", sans-serif;
       color: #222; background: #f6f7f9; }
header { padding: 12px 20px; background: #2f3b52; color: #fff; }
header h1 { margin: 0; font-size: 16px; font-weight: 600; }
header p { margin: 4px 0 0; font-size: 12px; opacity: .75; }
nav { display: flex; gap: 4px; padding: 0 20px; background: #2f3b52; }
nav button { border: 0; padding: 8px 18px; font: inherit; cursor: pointer;
             background: #46536e; color: #dbe1ec; border-radius: 6px 6px 0 0; }
nav button.active { background: #f6f7f9; color: #222; font-weight: 600; }
main { padding: 20px; }
section { display: none; }
section.active { display: block; }
h2 { font-size: 14px; margin: 0 0 4px; }
.note { font-size: 12px; color: #666; margin: 0 0 14px; }
.todo { display: inline-block; padding: 1px 6px; border-radius: 3px;
        background: #ffe6b3; color: #7a5200; font-size: 11px; }
.panel { background: #fff; border: 1px solid #d8dde5; border-radius: 6px;
         padding: 16px; margin-bottom: 18px; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
input[type=text], input[type=search], select { font: inherit; padding: 4px 8px;
         border: 1px solid #c3cad6; border-radius: 4px; }
button.act { font: inherit; padding: 5px 12px; border: 1px solid #c3cad6;
             background: #fff; border-radius: 4px; cursor: pointer; }
button.act:hover { background: #eef1f6; }
table { border-collapse: collapse; width: 100%; font-size: 12px; background: #fff; }
th, td { border: 1px solid #d8dde5; padding: 3px 6px; text-align: left; vertical-align: top; }
th { background: #eef1f6; position: sticky; top: 0; font-weight: 600; white-space: nowrap; }
td.ro { background: #fafbfc; color: #555; }
td[contenteditable]:focus { outline: 2px solid #4a7dff; outline-offset: -2px; background: #fffdf2; }
td.invalid { background: #ffecec; }
td.sel, td.ro.sel { background: #dbe6ff; }
table.dragging { user-select: none; }
.scroll { max-height: 60vh; overflow: auto; border: 1px solid #d8dde5; border-radius: 4px; }
.grid { display: grid; grid-template-columns: 180px 1fr; gap: 8px 12px; align-items: center;
        max-width: 520px; }
.errors { color: #b00020; font-size: 12px; margin: 8px 0 0; white-space: pre-wrap; }
ul.tree { list-style: none; margin: 4px 0; padding-left: 18px; font-size: 12px; }
ul.tree > li { margin: 2px 0; }
.tag { font-size: 11px; color: #666; }
.empty { color: #888; font-size: 12px; }
"""

_SCRIPT = r"""
const DATA = JSON.parse(document.getElementById("wb-data").textContent);

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const key in (attrs || {})) {
    if (key === "text") node.textContent = attrs[key];
    else node.setAttribute(key, attrs[key]);
  }
  (children || []).forEach(child => node.appendChild(child));
  return node;
}

/* ---- タブ ---- */
document.querySelectorAll("nav button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll("section").forEach(s => s.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

/* ---- セル状の表: 範囲選択・コピー・貼り付け ---- */
let activeGrid = null;

function enableGrid(table, options) {
  options = options || {};
  const sel = { r1: -1, c1: -1, r2: -1, c2: -1 };
  let dragging = false;

  const rowsOf = () => Array.from(table.tBodies[0].rows);
  const posOf = cell => ({ r: rowsOf().indexOf(cell.parentElement), c: cell.cellIndex });
  const rect = () => ({
    top: Math.min(sel.r1, sel.r2), bottom: Math.max(sel.r1, sel.r2),
    left: Math.min(sel.c1, sel.c2), right: Math.max(sel.c1, sel.c2),
  });
  const hasRange = () => sel.r1 >= 0 && (sel.r1 !== sel.r2 || sel.c1 !== sel.c2);

  function paint() {
    const r = rect();
    const range = hasRange();
    rowsOf().forEach((row, ri) => {
      Array.from(row.cells).forEach((cell, ci) => {
        const on = range && sel.r1 >= 0
          && ri >= r.top && ri <= r.bottom && ci >= r.left && ci <= r.right;
        cell.classList.toggle("sel", on);
      });
    });
  }
  function anchorAt(cell) { const p = posOf(cell); sel.r1 = sel.r2 = p.r; sel.c1 = sel.c2 = p.c; paint(); }
  function extendTo(cell) { const p = posOf(cell); sel.r2 = p.r; sel.c2 = p.c; paint(); }
  function dirty() { table.dispatchEvent(new Event("griddirty")); }

  function ensureRows(count) {
    if (!options.newRow) return;
    const body = table.tBodies[0];
    while (body.rows.length < count) body.appendChild(options.newRow());
  }

  /* ---- 元に戻す / やり直し ---- */
  const HISTORY_LIMIT = 100;
  let history = [];
  let hIndex = -1;
  let idleTimer = null;

  function snapshot() {
    const clone = table.tBodies[0].cloneNode(true);
    clone.querySelectorAll("td").forEach(td => {
      td.classList.remove("sel", "invalid");
      if (!td.getAttribute("class")) td.removeAttribute("class");
    });
    return clone.innerHTML;
  }
  function resetHistory() {
    history = [snapshot()];
    hIndex = 0;
  }
  function commit() {
    const current = snapshot();
    if (hIndex >= 0 && history[hIndex] === current) return;
    history = history.slice(0, hIndex + 1);
    history.push(current);
    if (history.length > HISTORY_LIMIT) history.shift();
    hIndex = history.length - 1;
  }
  function restore(html) {
    const active = document.activeElement;
    if (active && table.contains(active)) active.blur();
    table.tBodies[0].innerHTML = html;
    sel.r1 = sel.c1 = sel.r2 = sel.c2 = -1;
    dirty();
  }
  function undo() {
    if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; commit(); }
    if (hIndex <= 0) return;
    hIndex -= 1;
    restore(history[hIndex]);
  }
  function redo() {
    if (hIndex < 0 || hIndex >= history.length - 1) return;
    hIndex += 1;
    restore(history[hIndex]);
  }
  function scheduleCommit() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { idleTimer = null; commit(); }, 500);
  }

  document.addEventListener("keydown", event => {
    if (activeGrid !== table) return;
    if (!(event.ctrlKey || event.metaKey)) return;
    const key = event.key.toLowerCase();
    if (key === "z" && !event.shiftKey) { event.preventDefault(); undo(); }
    else if (key === "y" || (key === "z" && event.shiftKey)) { event.preventDefault(); redo(); }
  });
  table.addEventListener("focusin", () => { activeGrid = table; });
  table.addEventListener("focusout", () => {
    if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
    commit();
  });

  table.addEventListener("mousedown", event => {
    const cell = event.target.closest("td");
    if (!cell) return;
    activeGrid = table;
    if (event.shiftKey && sel.r1 >= 0) {
      event.preventDefault();
      extendTo(cell);
      return;
    }
    anchorAt(cell);
    dragging = true;
    table.classList.add("dragging");
  });
  table.addEventListener("mouseover", event => {
    if (!dragging) return;
    const cell = event.target.closest("td");
    if (!cell) return;
    extendTo(cell);
    if (hasRange()) {
      const active = document.activeElement;
      if (active && table.contains(active) && active.isContentEditable) active.blur();
      const selection = window.getSelection();
      if (selection) selection.removeAllRanges();
    }
  });
  document.addEventListener("mouseup", () => {
    dragging = false;
    table.classList.remove("dragging");
  });

  table.addEventListener("keydown", event => {
    const cell = event.target.closest("td");
    if (!cell) return;
    if ((event.key === "Delete" || event.key === "Backspace") && hasRange()) {
      event.preventDefault();
      forEachSelected(c => { if (c.isContentEditable) c.textContent = ""; });
      dirty();
      commit();
      return;
    }
    let dr = 0, dc = 0;
    if (event.key === "ArrowDown" || event.key === "Enter") dr = 1;
    else if (event.key === "ArrowUp") dr = -1;
    else if (event.key === "ArrowLeft") dc = -1;
    else if (event.key === "ArrowRight") dc = 1;
    else if (event.key === "Tab") dc = event.shiftKey ? -1 : 1;
    else return;
    if ((event.key === "ArrowLeft" || event.key === "ArrowRight") && !event.shiftKey) return;
    if (event.shiftKey && event.key.startsWith("Arrow")) {
      event.preventDefault();
      const rows = rowsOf();
      const nr = Math.max(0, Math.min(rows.length - 1, sel.r2 + dr));
      const nc = Math.max(0, Math.min(rows[0].cells.length - 1, sel.c2 + dc));
      sel.r2 = nr; sel.c2 = nc; paint();
      return;
    }
    event.preventDefault();
    const rows = rowsOf();
    let ri = rows.indexOf(cell.parentElement), ci = cell.cellIndex;
    let next = null;
    for (let step = 0; step < 200 && !next; step++) {
      ri += dr; ci += dc;
      const row = rows[ri];
      if (!row) break;
      const candidate = row.cells[ci];
      if (!candidate) break;
      if (candidate.isContentEditable) next = candidate;
      else if (dc === 0) break;
    }
    if (next) { next.focus(); anchorAt(next); }
  });

  function forEachSelected(callback) {
    const r = rect();
    const rows = rowsOf();
    for (let ri = r.top; ri <= r.bottom; ri++) {
      const row = rows[ri];
      if (!row) continue;
      for (let ci = r.left; ci <= r.right; ci++) {
        const cell = row.cells[ci];
        if (cell) callback(cell, ri - r.top, ci - r.left);
      }
    }
  }

  document.addEventListener("copy", event => {
    if (activeGrid !== table || !hasRange()) return;
    const r = rect();
    const rows = rowsOf();
    const lines = [];
    for (let ri = r.top; ri <= r.bottom; ri++) {
      const row = rows[ri];
      if (!row) continue;
      const cells = [];
      for (let ci = r.left; ci <= r.right; ci++) {
        const cell = row.cells[ci];
        cells.push(cell ? cell.textContent.trim() : "");
      }
      lines.push(cells.join("\t"));
    }
    event.clipboardData.setData("text/plain", lines.join("\n"));
    event.preventDefault();
  });

  table.addEventListener("paste", event => {
    const cell = event.target.closest("td");
    if (!cell && sel.r1 < 0) return;
    const text = (event.clipboardData || window.clipboardData).getData("text/plain");
    if (!text) return;
    event.preventDefault();
    const grid = text.replace(/\r/g, "").replace(/\n+$/, "").split("\n").map(r => r.split("\t"));
    const start = cell ? posOf(cell) : { r: rect().top, c: rect().left };
    ensureRows(start.r + grid.length);
    const rows = rowsOf();
    grid.forEach((cols, r) => {
      const row = rows[start.r + r];
      if (!row) return;
      cols.forEach((value, c) => {
        const target = row.cells[start.c + c];
        if (target && target.isContentEditable) target.textContent = value.trim();
      });
    });
    sel.r1 = start.r; sel.c1 = start.c;
    sel.r2 = start.r + grid.length - 1;
    sel.c2 = start.c + Math.max(...grid.map(cols => cols.length)) - 1;
    paint();
    dirty();
    commit();
  });

  table.addEventListener("input", () => { dirty(); scheduleCommit(); });

  table.grid = {
    selectedRowRange: () => (sel.r1 < 0 ? null : { top: rect().top, bottom: rect().bottom }),
    clearSelection: () => { sel.r1 = sel.c1 = sel.r2 = sel.c2 = -1; paint(); },
    resetHistory: resetHistory,
    commit: commit,
  };
  resetHistory();
}

function download(name, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const a = el("a", { href: URL.createObjectURL(blob), download: name });
  document.body.appendChild(a); a.click(); a.remove();
}

function yamlKey(value) {
  return '"' + String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
}

/* ---- データソースタブ ---- */
const dsSelect = document.getElementById("ds-select");
DATA.datasources.forEach((ds, i) => {
  dsSelect.appendChild(el("option", { value: String(i), text: ds.name || ds.id }));
});

function folderNameOf(ds, field) {
  const folder = (ds.folders || []).find(f => f.id === field.folder_id);
  return folder ? folder.name : "";
}
function originalNameOf(field) {
  const id = field.id || "";
  return id.startsWith("[") && id.endsWith("]") ? id.slice(1, -1) : (id || field.name || "");
}

function renderRenameTable(ds) {
  const body = document.getElementById("rename-body");
  body.innerHTML = "";
  (ds.fields || []).filter(f => !f.is_calculated).forEach(field => {
    body.appendChild(el("tr", {}, [
      el("td", { class: "ro", text: originalNameOf(field) }),
      el("td", { contenteditable: "true", text: field.name || "" }),
      el("td", { contenteditable: "true", text: folderNameOf(ds, field) }),
      el("td", { class: "ro", text: field.datatype || "" }),
      el("td", { class: "ro", text: field.role || "" }),
      el("td", { class: "ro", text: field.hidden ? "非表示" : "" }),
    ]));
  });
}

function calcRow(name, formula, datatype, role, folder) {
  return el("tr", {}, [
    el("td", { contenteditable: "true", text: name }),
    el("td", { contenteditable: "true", text: formula }),
    el("td", { contenteditable: "true", text: datatype }),
    el("td", { contenteditable: "true", text: role }),
    el("td", { contenteditable: "true", text: folder }),
  ]);
}

function renderCalcTable(ds) {
  const body = document.getElementById("calc-body");
  body.innerHTML = "";
  (ds.fields || []).filter(f => f.is_calculated).forEach(field => {
    body.appendChild(calcRow(field.name || "", field.formula || "",
                             field.datatype || "", field.role || "", folderNameOf(ds, field)));
  });
  for (let i = 0; i < 3; i++) body.appendChild(calcRow("", "", "", "", ""));
}

function currentDatasource() { return DATA.datasources[Number(dsSelect.value) || 0]; }

function refreshDatasource() {
  const ds = currentDatasource();
  if (!ds) return;
  renderRenameTable(ds);
  renderCalcTable(ds);
  validateRename();
  document.querySelectorAll("table").forEach(table => {
    if (table.grid) table.grid.resetHistory();
  });
}
dsSelect.addEventListener("change", refreshDatasource);

document.getElementById("field-search").addEventListener("input", event => {
  const q = event.target.value.trim().toLowerCase();
  Array.from(document.getElementById("rename-body").rows).forEach(row => {
    const hit = !q || Array.from(row.cells).some(c => c.textContent.toLowerCase().includes(q));
    row.style.display = hit ? "" : "none";
  });
});

document.getElementById("calc-add").addEventListener("click", () => {
  const table = document.getElementById("calc-table");
  document.getElementById("calc-body").appendChild(calcRow("", "", "", "", ""));
  activeGrid = table;
  table.grid.commit();
});

document.getElementById("calc-delete").addEventListener("click", () => {
  const table = document.getElementById("calc-table");
  const range = table.grid.selectedRowRange();
  if (!range) { alert("削除する行を選んでください。"); return; }
  const rows = Array.from(table.tBodies[0].rows).slice(range.top, range.bottom + 1);
  if (!rows.length) return;
  const named = rows.filter(row => row.cells[0].textContent.trim()).length;
  if (named && !confirm(rows.length + " 行を削除します。よろしいですか。")) return;
  rows.forEach(row => row.remove());
  table.grid.clearSelection();
  activeGrid = table;
  table.grid.commit();
});

/* ---- 画面側バリデーション ---- */
function validateRename() {
  const rows = Array.from(document.getElementById("rename-body").rows);
  const errors = [];
  const assigned = new Set();
  rows.forEach(row => {
    const original = row.cells[0].textContent.trim();
    const display = row.cells[1].textContent.trim();
    const folder = row.cells[2].textContent.trim();
    row.cells[1].classList.toggle("invalid", !!folder && !display);
    row.cells[2].classList.remove("invalid");
    if (!folder) return;
    if (!display) errors.push("表示名が空: " + original);
    if (assigned.has(original)) {
      errors.push("同じフィールドが 2 回割り当てられている: " + original);
      row.cells[2].classList.add("invalid");
    }
    assigned.add(original);
  });
  document.getElementById("rename-errors").textContent = errors.join("\n");
  return errors.length === 0;
}
document.getElementById("rename-table").addEventListener("griddirty", validateRename);

/* ---- YAML 出力 ---- */
document.getElementById("rename-download").addEventListener("click", () => {
  if (!validateRename()) { alert("エラーを直してから出力してください。"); return; }
  const ds = currentDatasource();
  const folders = new Map();
  Array.from(document.getElementById("rename-body").rows).forEach(row => {
    const original = row.cells[0].textContent.trim();
    const display = row.cells[1].textContent.trim();
    const folder = row.cells[2].textContent.trim();
    if (!folder || !display) return;
    if (!folders.has(folder)) folders.set(folder, []);
    folders.get(folder).push([original, display]);
  });
  if (!folders.size) { alert("フォルダが 1 つも指定されていません。"); return; }
  let out = yamlKey(ds.name || ds.id) + ":\n";
  folders.forEach((pairs, folder) => {
    out += "  " + yamlKey(folder) + ":\n";
    pairs.forEach(pair => {
      out += "    " + yamlKey(pair[0]) + ": " + yamlKey(pair[1]) + "\n";
    });
  });
  download("fields.yaml", out);
});

document.getElementById("calc-download").addEventListener("click", () => {
  const rows = Array.from(document.getElementById("calc-body").rows)
    .map(row => Array.from(row.cells).map(c => c.textContent.trim()))
    .filter(cells => cells[0] && cells[1]);
  if (!rows.length) { alert("名前と式が入った行がありません。"); return; }
  let out = "# 案: Python 側の受け手は未実装（設定ファイル形式の拡張が必要）\n";
  out += yamlKey(currentDatasource().name) + ":\n  calculations:\n";
  rows.forEach(cells => {
    out += "    - name: " + yamlKey(cells[0]) + "\n";
    out += "      formula: " + yamlKey(cells[1]) + "\n";
    if (cells[2]) out += "      datatype: " + yamlKey(cells[2]) + "\n";
    if (cells[3]) out += "      role: " + yamlKey(cells[3]) + "\n";
    if (cells[4]) out += "      folder: " + yamlKey(cells[4]) + "\n";
  });
  download("calculations.yaml", out);
});

/* ---- デザインルールタブ ---- */
document.getElementById("design-download").addEventListener("click", () => {
  const value = id => document.getElementById(id).value.trim();
  let out = "# 案: Python 側の受け手は set_default_font() のみ（他は未実装）\n";
  out += "design:\n";
  out += "  font: " + yamlKey(value("d-font")) + "\n";
  out += "  main_color: " + yamlKey(value("d-main")) + "\n";
  out += "  sub_color_1: " + yamlKey(value("d-sub1")) + "\n";
  out += "  sub_color_2: " + yamlKey(value("d-sub2")) + "\n";
  out += "  text_color: " + yamlKey(value("d-text")) + "\n";
  out += "  filter_apply_button: " + (document.getElementById("d-apply").checked ? "true" : "false") + "\n";
  out += "  spacing: " + yamlKey(document.querySelector("input[name=d-space]:checked").value) + "\n";
  download("design.yaml", out);
});

/* ---- ダッシュボードタブ（読み取り専用） ---- */
function containerNode(container) {
  const label = (container.direction === "horz" ? "横配置" : "縦段組")
    + " " + (container.name || "(無名)");
  const children = [];
  (container.containers || []).forEach(c => children.push(containerNode(c)));
  (container.zones || []).forEach(z => children.push(el("li", {
    text: "エリア: " + (z.worksheet_id ? ("シート " + z.worksheet_id) : (z.name || "(空)"))
  })));
  return el("li", {}, [
    el("span", { text: label }),
    children.length ? el("ul", { class: "tree" }, children)
                    : el("span", { class: "tag", text: " (空)" }),
  ]);
}
const dashRoot = document.getElementById("dash-root");
if (!DATA.dashboards.length) {
  dashRoot.appendChild(el("p", { class: "empty", text: "ダッシュボードがありません。" }));
}
DATA.dashboards.forEach(dashboard => {
  const items = (dashboard.containers || []).map(containerNode);
  dashRoot.appendChild(el("div", { class: "panel" }, [
    el("h2", { text: dashboard.name || dashboard.id }),
    el("p", { class: "note",
      text: "サイズ: " + (dashboard.width || "?") + " x " + (dashboard.height || "?")
            + " / シート " + (dashboard.worksheets || []).length + " 件"
            + " / アクション " + (dashboard.actions || []).length + " 件" }),
    items.length ? el("ul", { class: "tree" }, items)
                 : el("p", { class: "empty", text: "コンテナがありません。" }),
  ]));
});

refreshDatasource();
enableGrid(document.getElementById("rename-table"));
enableGrid(document.getElementById("calc-table"), { newRow: () => calcRow("", "", "", "", "") });
"""

_BODY = """
<header>
  <h1>__TITLE__</h1>
  <p>twbpatch が出力した設定画面 / データソース __DS_COUNT__ 件・ワークシート __WS_COUNT__ 件・ダッシュボード __DB_COUNT__ 件</p>
</header>
<nav>
  <button data-tab="tab-design">全体（デザインルール）</button>
  <button data-tab="tab-datasource" class="active">データソース</button>
  <button data-tab="tab-dashboard">ダッシュボード</button>
</nav>
<main>

<section id="tab-design">
  <div class="panel">
    <h2>全体の書式設定 <span class="todo">受け手はフォントのみ実装済み</span></h2>
    <p class="note">ここで設定した内容を Python 側へ渡す API は未実装。今は YAML の案を出力するだけ。</p>
    <div class="grid">
      <label for="d-font">フォント</label>
      <input type="text" id="d-font" value="Meiryo UI">
      <label for="d-main">メインカラーコード</label>
      <input type="text" id="d-main" value="#2f3b52">
      <label for="d-sub1">サブカラー&#9312;</label>
      <input type="text" id="d-sub1" value="#4a7dff">
      <label for="d-sub2">サブカラー&#9313;</label>
      <input type="text" id="d-sub2" value="#c0c0c0">
      <label for="d-text">通常時の文字色</label>
      <input type="text" id="d-text" value="#333333">
      <label for="d-apply">フィルターに「適用」ボタン</label>
      <span><input type="checkbox" id="d-apply"> 入れる</span>
      <label>余白</label>
      <span>
        <label><input type="radio" name="d-space" value="wide" checked> 多め</label>
        <label><input type="radio" name="d-space" value="narrow"> 少なめ</label>
      </span>
    </div>
    <p><button class="act" id="design-download">design.yaml をダウンロード</button></p>
  </div>
</section>

<section id="tab-datasource" class="active">
  <div class="toolbar">
    <label for="ds-select">データソース</label>
    <select id="ds-select"></select>
    <input type="search" id="field-search" placeholder="フィールドを絞り込む">
  </div>

  <div class="panel">
    <h2>リネーム・フォルダ設定</h2>
    <p class="note">ドラッグまたは Shift+クリックで範囲選択。Ctrl+C でコピー、Ctrl+V で貼り付け、
      Delete で選択セルを消去。Ctrl+Z / Ctrl+Y で元に戻す・やり直し。
      フォルダ欄が空の行は出力に含まれない。</p>
    <div class="scroll">
      <table id="rename-table">
        <thead><tr>
          <th>元カラム</th><th>リネーム後名称</th><th>フォルダ</th>
          <th>データ型</th><th>役割</th><th>非表示</th>
        </tr></thead>
        <tbody id="rename-body"></tbody>
      </table>
    </div>
    <p class="errors" id="rename-errors"></p>
    <p><button class="act" id="rename-download">fields.yaml をダウンロード</button></p>
  </div>

  <div class="panel">
    <h2>計算フィールド <span class="todo">受け手は未実装</span></h2>
    <p class="note">範囲選択・コピー・貼り付けはリネームの表と同じ。
      Ctrl+Z / Ctrl+Y も同じ。
      行が足りないときは貼り付けで自動的に増える。名前と式が両方入った行だけ出力する。</p>
    <div class="scroll">
      <table id="calc-table">
        <thead><tr>
          <th>名前</th><th>式</th><th>データ型</th><th>役割</th><th>フォルダ</th>
        </tr></thead>
        <tbody id="calc-body"></tbody>
      </table>
    </div>
    <p>
      <button class="act" id="calc-add">行を追加</button>
      <button class="act" id="calc-delete">選択行を削除</button>
      <button class="act" id="calc-download">calculations.yaml をダウンロード</button>
    </p>
  </div>
</section>

<section id="tab-dashboard">
  <div class="panel">
    <h2>ダッシュボード <span class="todo">読み取り専用</span></h2>
    <p class="note">編集画面は未着手。コンテナ階層の形が確定してから作る。</p>
  </div>
  <div id="dash-root"></div>
</section>

</main>
"""

_TEMPLATE = """<meta charset="utf-8">
<title>__TITLE__</title>
<style>__STYLE__</style>
__BODY__
<script type="application/json" id="wb-data">__DATA__</script>
<script>__SCRIPT__</script>
"""


def _escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _embed_json(data: dict[str, Any]) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text.replace("</", "<\\/")


def render_workbook_html(data: dict[str, Any], *, title: str = "twbpatch 設定") -> str:
    body = (
        _BODY.replace("__TITLE__", _escape(title))
        .replace("__DS_COUNT__", str(len(data.get("datasources", []))))
        .replace("__WS_COUNT__", str(len(data.get("worksheets", []))))
        .replace("__DB_COUNT__", str(len(data.get("dashboards", []))))
    )
    return (
        _TEMPLATE.replace("__STYLE__", _STYLE)
        .replace("__BODY__", body)
        .replace("__SCRIPT__", _SCRIPT)
        .replace("__DATA__", _embed_json(data))
        .replace("__TITLE__", _escape(title))
    )
