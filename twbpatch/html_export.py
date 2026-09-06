from __future__ import annotations

import json
from typing import Any

_STYLE = """
* { box-sizing: border-box; }
body { margin: 0; font: 13px/1.6 "Meiryo UI", "Hiragino Kaku Gothic ProN", sans-serif;
       color: #222; background: #f6f7f9; }
nav { position: sticky; top: 0; z-index: 10; display: flex; gap: 3px; align-items: center;
      padding: 0 14px; background: #2f3b52; box-shadow: 0 1px 4px rgba(0,0,0,.25); }
nav button { border: 0; padding: 6px 14px; margin-top: 4px; font: inherit; cursor: pointer;
             background: #46536e; color: #dbe1ec; border-radius: 5px 5px 0 0; }
nav button.active { background: #f6f7f9; color: #222; font-weight: 600; }
nav button.dl { margin: 4px 0 4px 18px; border-radius: 4px; background: #4a7dff; color: #fff;
                font-weight: 600; }
nav button.dl:hover { background: #3a68e0; }
nav .meta { margin-left: 14px; color: #c7d0e0; font-size: 11px; line-height: 1.35;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
nav .meta b { color: #fff; font-weight: 600; margin-right: 8px; }
.color { display: flex; gap: 6px; align-items: center; }
.color input[type=color] { width: 34px; height: 28px; padding: 0; border: 1px solid #c3cad6;
                           border-radius: 4px; background: none; cursor: pointer; }
.color input[type=text] { width: 110px; font-family: monospace; }
main { padding: 20px; }
section { display: none; }
section.active { display: block; }
h2 { font-size: 14px; margin: 0 0 4px; }
.note { font-size: 12px; color: #666; margin: 0 0 14px; }
.todo { display: inline-block; padding: 1px 6px; border-radius: 3px;
        background: #ffe6b3; color: #7a5200; font-size: 11px; }
.panel { background: #fff; border: 1px solid #d8dde5; border-radius: 6px;
         padding: 16px; margin-bottom: 18px; }
.acc { padding: 0; }
.acc-head { margin: 0; padding: 10px 16px 10px 34px; cursor: pointer; position: relative;
            border-radius: 6px; user-select: none; }
.acc-head:hover { background: #eef1f6; }
.acc-head::before { content: "\25B6"; position: absolute; left: 14px; color: #7a869c;
                    font-size: 10px; transition: transform .12s; }
.acc.open > .acc-head::before { transform: rotate(90deg); }
.acc-body { display: none; padding: 0 16px 16px; }
.acc.open > .acc-body { display: block; }
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
document.querySelectorAll("nav button[data-tab]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button[data-tab]").forEach(b => b.classList.remove("active"));
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

/* データソースごとの編集内容。切り替えても保持する */
const EDITS = {};

function folderNameOf(ds, field) {
  const folder = (ds.folders || []).find(f => f.id === field.folder_id);
  return folder ? folder.name : "";
}
function originalNameOf(field) {
  const id = field.id || "";
  return id.startsWith("[") && id.endsWith("]") ? id.slice(1, -1) : (id || field.name || "");
}

function initialState(ds) {
  const rename = (ds.fields || []).filter(f => !f.is_calculated).map(field => ({
    original: originalNameOf(field),
    display: field.name || "",
    folder: folderNameOf(ds, field),
    datatype: field.datatype || "",
    role: field.role || "",
    hidden: field.hidden ? "非表示" : "",
  }));
  const calcs = (ds.fields || []).filter(f => f.is_calculated).map(field => ([
    field.name || "", field.formula || "", field.datatype || "",
    field.role || "", folderNameOf(ds, field),
  ]));
  for (let i = 0; i < 3; i++) calcs.push(["", "", "", "", ""]);
  return { rename: rename, calcs: calcs };
}

function stateAt(index) {
  if (!EDITS[index]) EDITS[index] = initialState(DATA.datasources[index]);
  return EDITS[index];
}
function currentIndex() { return Number(dsSelect.value) || 0; }
function currentDatasource() { return DATA.datasources[currentIndex()]; }

function calcRow(name, formula, datatype, role, folder) {
  return el("tr", {}, [
    el("td", { contenteditable: "true", text: name }),
    el("td", { contenteditable: "true", text: formula }),
    el("td", { contenteditable: "true", text: datatype }),
    el("td", { contenteditable: "true", text: role }),
    el("td", { contenteditable: "true", text: folder }),
  ]);
}

function renderTables(state) {
  const renameBody = document.getElementById("rename-body");
  renameBody.innerHTML = "";
  state.rename.forEach(row => {
    renameBody.appendChild(el("tr", {}, [
      el("td", { class: "ro", text: row.original }),
      el("td", { contenteditable: "true", text: row.display }),
      el("td", { contenteditable: "true", text: row.folder }),
      el("td", { class: "ro", text: row.datatype }),
      el("td", { class: "ro", text: row.role }),
      el("td", { class: "ro", text: row.hidden }),
    ]));
  });
  const calcBody = document.getElementById("calc-body");
  calcBody.innerHTML = "";
  state.calcs.forEach(cells => calcBody.appendChild(calcRow.apply(null, cells)));
}

/* 画面の内容を、いま表示しているデータソースの編集内容へ書き戻す */
function captureInto(index) {
  const state = stateAt(index);
  state.rename = Array.from(document.getElementById("rename-body").rows).map(row => ({
    original: row.cells[0].textContent.trim(),
    display: row.cells[1].textContent.trim(),
    folder: row.cells[2].textContent.trim(),
    datatype: row.cells[3].textContent.trim(),
    role: row.cells[4].textContent.trim(),
    hidden: row.cells[5].textContent.trim(),
  }));
  state.calcs = Array.from(document.getElementById("calc-body").rows)
    .map(row => Array.from(row.cells).map(cell => cell.textContent.trim()));
  return state;
}

let renderedIndex = null;
function captureCurrent() {
  return captureInto(renderedIndex === null ? currentIndex() : renderedIndex);
}

function refreshDatasource() {
  if (!DATA.datasources.length) return;
  if (renderedIndex !== null && renderedIndex !== currentIndex()) captureInto(renderedIndex);
  renderedIndex = currentIndex();
  renderTables(stateAt(renderedIndex));
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

/* ---- 折り畳み（片方を開くともう片方が閉じる） ---- */
const ACCORDIONS = ["acc-rename", "acc-calc"];
ACCORDIONS.forEach(id => {
  const panel = document.getElementById(id);
  panel.querySelector(".acc-head").addEventListener("click", () => {
    if (panel.classList.contains("open")) return;
    ACCORDIONS.forEach(other => {
      document.getElementById(other).classList.toggle("open", other === id);
    });
  });
});

/* ---- 画面側バリデーション ---- */
function validateState(state) {
  const errors = [];
  const assigned = new Set();
  state.rename.forEach(row => {
    if (!row.folder) return;
    if (!row.display) errors.push("表示名が空: " + row.original);
    if (assigned.has(row.original)) {
      errors.push("同じフィールドが 2 回割り当てられている: " + row.original);
    }
    assigned.add(row.original);
  });
  return errors;
}

function validateRename() {
  const seen = new Set();
  Array.from(document.getElementById("rename-body").rows).forEach(row => {
    const original = row.cells[0].textContent.trim();
    const display = row.cells[1].textContent.trim();
    const folder = row.cells[2].textContent.trim();
    row.cells[1].classList.toggle("invalid", !!folder && !display);
    row.cells[2].classList.toggle("invalid", !!folder && seen.has(original));
    if (folder) seen.add(original);
  });
  const errors = validateState(captureCurrent());
  document.getElementById("rename-errors").textContent = errors.join("\n");
  return errors.length === 0;
}
document.getElementById("rename-table").addEventListener("griddirty", validateRename);
document.getElementById("calc-table").addEventListener("griddirty", () => captureCurrent());

/* ---- デザインルールタブ ---- */
function bindColor(id) {
  const text = document.getElementById(id);
  const picker = document.getElementById(id + "-pick");
  picker.value = text.value;
  picker.addEventListener("input", () => { text.value = picker.value; });
  text.addEventListener("input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(text.value.trim())) picker.value = text.value.trim();
  });
}
["d-main", "d-sub1", "d-sub2", "d-text"].forEach(bindColor);

function designYaml() {
  const value = id => document.getElementById(id).value.trim();
  let out = "design:\n";
  out += "  font: " + yamlKey(value("d-font")) + "\n";
  out += "  main_color: " + yamlKey(value("d-main")) + "\n";
  out += "  sub_color_1: " + yamlKey(value("d-sub1")) + "\n";
  out += "  sub_color_2: " + yamlKey(value("d-sub2")) + "\n";
  out += "  text_color: " + yamlKey(value("d-text")) + "\n";
  out += "  filter_apply_button: "
       + (document.getElementById("d-apply").checked ? "true" : "false") + "\n";
  out += "  spacing: "
       + yamlKey(document.querySelector("input[name=d-space]:checked").value) + "\n";
  return out;
}

/* ---- YAML 出力（全タブ分を 1 ファイルに） ---- */
function buildYaml() {
  captureCurrent();
  let out = "# twbpatch 設定ファイル\n";
  out += "# 受け手の実装状況: datasources.*.folders のみ実装済み。\n";
  out += "# design と datasources.*.calculations は案（Python 側は未実装）。\n\n";
  out += designYaml();
  out += "\ndatasources:\n";
  let wrote = false;
  DATA.datasources.forEach((ds, index) => {
    const state = EDITS[index];
    if (!state) return;
    const folders = new Map();
    state.rename.forEach(row => {
      if (!row.folder || !row.display) return;
      if (!folders.has(row.folder)) folders.set(row.folder, []);
      folders.get(row.folder).push([row.original, row.display]);
    });
    const calcs = state.calcs.filter(cells => cells[0] && cells[1]);
    if (!folders.size && !calcs.length) return;
    wrote = true;
    out += "  " + yamlKey(ds.name || ds.id) + ":\n";
    if (folders.size) {
      out += "    folders:\n";
      folders.forEach((pairs, folder) => {
        out += "      " + yamlKey(folder) + ":\n";
        pairs.forEach(pair => {
          out += "        " + yamlKey(pair[0]) + ": " + yamlKey(pair[1]) + "\n";
        });
      });
    }
    if (calcs.length) {
      out += "    calculations:\n";
      calcs.forEach(cells => {
        out += "      - name: " + yamlKey(cells[0]) + "\n";
        out += "        formula: " + yamlKey(cells[1]) + "\n";
        if (cells[2]) out += "        datatype: " + yamlKey(cells[2]) + "\n";
        if (cells[3]) out += "        role: " + yamlKey(cells[3]) + "\n";
        if (cells[4]) out += "        folder: " + yamlKey(cells[4]) + "\n";
      });
    }
  });
  if (!wrote) out += "  {}\n";
  return out;
}

document.getElementById("yaml-download").addEventListener("click", () => {
  captureCurrent();
  const errors = [];
  DATA.datasources.forEach((ds, index) => {
    if (!EDITS[index]) return;
    validateState(EDITS[index]).forEach(message => {
      errors.push((ds.name || ds.id) + ": " + message);
    });
  });
  if (errors.length) {
    alert("エラーを直してから出力してください。\n\n" + errors.join("\n"));
    return;
  }
  download("twbpatch_config.yaml", buildYaml());
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
<nav>
  <button data-tab="tab-design">全体（デザインルール）</button>
  <button data-tab="tab-datasource" class="active">データソース</button>
  <button data-tab="tab-dashboard">ダッシュボード</button>
  <button class="dl" id="yaml-download">設定 YAML をダウンロード</button>
  <span class="meta"><b>__TITLE__</b>
    データソース __DS_COUNT__ 件・ワークシート __WS_COUNT__ 件・ダッシュボード __DB_COUNT__ 件</span>
</nav>
<main>

<section id="tab-design">
  <div class="panel">
    <h2>全体の書式設定 <span class="todo">受け手はフォントのみ実装済み</span></h2>
    <p class="note">ここで設定した内容を Python 側へ渡す API は未実装。今は YAML の案を出力するだけ。</p>
    <div class="grid">
      <label for="d-font">フォント</label>
      <select id="d-font">__FONT_OPTIONS__</select>
      <label for="d-main">メインカラーコード</label>
      <span class="color">
        <input type="color" id="d-main-pick"><input type="text" id="d-main" value="#2f3b52">
      </span>
      <label for="d-sub1">サブカラー&#9312;</label>
      <span class="color">
        <input type="color" id="d-sub1-pick"><input type="text" id="d-sub1" value="#4a7dff">
      </span>
      <label for="d-sub2">サブカラー&#9313;</label>
      <span class="color">
        <input type="color" id="d-sub2-pick"><input type="text" id="d-sub2" value="#c0c0c0">
      </span>
      <label for="d-text">通常時の文字色</label>
      <span class="color">
        <input type="color" id="d-text-pick"><input type="text" id="d-text" value="#333333">
      </span>
      <label for="d-apply">フィルターに「適用」ボタン</label>
      <span><input type="checkbox" id="d-apply"> 入れる</span>
      <label>余白</label>
      <span>
        <label><input type="radio" name="d-space" value="wide" checked> 多め</label>
        <label><input type="radio" name="d-space" value="narrow"> 少なめ</label>
      </span>
    </div>
  </div>
</section>

<section id="tab-datasource" class="active">
  <div class="toolbar">
    <label for="ds-select">データソース</label>
    <select id="ds-select"></select>
    <input type="search" id="field-search" placeholder="フィールドを絞り込む">
  </div>

  <div class="panel acc open" id="acc-rename">
    <h2 class="acc-head">リネーム・フォルダ設定</h2>
    <div class="acc-body">
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
    </div>
  </div>

  <div class="panel acc" id="acc-calc">
    <h2 class="acc-head">計算フィールド <span class="todo">受け手は未実装</span></h2>
    <div class="acc-body">
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
    </p>
    </div>
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


#: フォント候補。Tableau Desktop の既定フォントと、Windows / macOS の日本語標準フォント。
FONT_CHOICES = (
    "Meiryo UI",
    "メイリオ",
    "Yu Gothic UI",
    "游ゴシック",
    "游明朝",
    "BIZ UDPGothic",
    "BIZ UDPMincho",
    "MS PGothic",
    "MS Gothic",
    "MS PMincho",
    "Hiragino Kaku Gothic ProN",
    "Hiragino Mincho ProN",
    "Noto Sans JP",
    "Tableau Book",
    "Tableau Medium",
    "Tableau Regular",
    "Arial",
    "Segoe UI",
    "Helvetica Neue",
)


def _font_options(selected: str) -> str:
    return "".join(
        '<option value="{value}"{mark}>{label}</option>'.format(
            value=_escape(font),
            mark=" selected" if font == selected else "",
            label=_escape(font),
        )
        for font in FONT_CHOICES
    )


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


def render_workbook_html(
    data: dict[str, Any],
    *,
    title: str = "twbpatch 設定",
    font: str = "Meiryo UI",
) -> str:
    body = (
        _BODY.replace("__FONT_OPTIONS__", _font_options(font))
        .replace("__TITLE__", _escape(title))
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
