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
.acc-head::before { content: "\\25B6"; position: absolute; left: 14px; color: #7a869c;
                    font-size: 10px; transition: transform .12s; }
.acc.open > .acc-head::before { transform: rotate(90deg); }
.acc-body { display: none; padding: 0 16px 16px; }
.acc.open > .acc-body { display: block; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
input[type=text], input[type=search], input[type=number], select { font: inherit;
         padding: 4px 8px; border: 1px solid #c3cad6; border-radius: 4px; }
input[type=number] { width: 96px; }
label.f input[type=number] { width: 88px; font-size: 12px; padding: 3px 6px; }
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
.tag { font-size: 11px; color: #666; }
.empty { color: #888; font-size: 12px; }
button.mini { border: 1px solid #c3cad6; background: #fff; border-radius: 4px; cursor: pointer;
              width: 26px; height: 26px; padding: 0; font-size: 12px; line-height: 1; }
button.mini:hover { background: #eef1f6; }
button.mini.danger { color: #b00020; border-color: #e6b8bf; }
.spacer { flex: 1; }
.row-card { border: 1px solid #c9d2e0; border-radius: 6px; margin-bottom: 12px; background: #fbfcfe; }
.row-card.collapsed > .areas { display: none; }
.row-card.collapsed > .row-head { border-radius: 6px; }
.row-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
            padding: 8px 12px; background: #eef1f6; border-radius: 6px 6px 0 0; }
.row-no { font-weight: 600; font-size: 12px; color: #46536e; white-space: nowrap; }
.areas { display: flex; gap: 10px; padding: 12px; overflow-x: auto; align-items: flex-start; }
.area { flex: 0 0 360px; width: 360px; border: 1px solid #d8dde5; border-radius: 6px;
        background: #fff; padding: 10px; }
.area-head { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.fields { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
.params { display: flex; gap: 10px; flex-wrap: wrap; border-top: 1px dashed #d8dde5;
          padding-top: 8px; margin-bottom: 6px; }
details.more > summary { cursor: pointer; font-size: 11px; color: #46536e; padding: 4px 0;
                        user-select: none; }
details.more > summary:hover { color: #2f3b52; }
details.more > .params { border-top: 0; }
label.f { display: flex; flex-direction: column; gap: 2px; font-size: 11px; color: #555; }
label.f input[type=text], label.f select { font-size: 12px; padding: 3px 6px; max-width: 190px; }
label.f select[multiple] { min-height: 56px; }
.color2 { display: flex; gap: 4px; align-items: center; }
.color2 select { max-width: 118px; font-size: 12px; padding: 3px 6px; }
.color2 input[type=color] { width: 30px; height: 26px; padding: 0; border: 1px solid #c3cad6;
                            border-radius: 4px; background: none; cursor: pointer; }
.color2 input[type=color]:disabled { cursor: default; opacity: .65; }
.grip { cursor: grab; color: #8b96a8; font-size: 14px; line-height: 1; padding: 0 2px;
        user-select: none; }
.grip:active { cursor: grabbing; }
.dragging-src { opacity: .4; }
.area.drop-left { box-shadow: inset 3px 0 0 #4a7dff; }
.area.drop-right { box-shadow: inset -3px 0 0 #4a7dff; }
.areas.drop-into { outline: 2px dashed #4a7dff; outline-offset: -4px; }
.row-card.drop-top { box-shadow: inset 0 3px 0 #4a7dff; }
.row-card.drop-bottom { box-shadow: inset 0 -3px 0 #4a7dff; }
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

/* ---- 折り畳み。データソースの 2 表だけ排他にする ---- */
const EXCLUSIVE = ["acc-rename", "acc-calc"];
document.querySelectorAll(".acc").forEach(panel => {
  panel.querySelector(".acc-head").addEventListener("click", () => {
    const close = panel.classList.contains("open");
    if (EXCLUSIVE.indexOf(panel.id) < 0) {
      panel.classList.toggle("open", !close);
      return;
    }
    EXCLUSIVE.forEach(other => {
      document.getElementById(other).classList.toggle("open", !close && other === panel.id);
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
    if (typeof renderRows === "function") renderRows();
  });
  picker.addEventListener("input", () => {
    if (typeof renderRows === "function") renderRows();
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
  out += "# design / calculations / dashboard は案（Python 側は未実装）。\n";
  out += "# 集計方法は画面で指定しない。役割とデータ型から自動で決める。\n\n";
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
  out += "\n" + dashboardYaml();
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

/* ---- ダッシュボードタブ（新規作成） ---- */
const DRAW_SPECS = JSON.parse(document.getElementById("draw-specs").textContent);
const CHART_TYPES = Object.keys(DRAW_SPECS);

const DASH = { rows: [] };
let rowSeq = 0;

function newArea() {
  return {
    id: ++rowSeq,
    kind: "chart",
    width: "600",
    sheet: "",
    chart: CHART_TYPES[0] || "",
    datasource: 0,
    params: {},
    filterField: "",
    action: { enabled: false, type: "filter", target: "" },
  };
}
function newRow() {
  return { id: ++rowSeq, name: "", height: "300", collapsed: false, areas: [newArea()] };
}

function dsOptions(selected) {
  return DATA.datasources.map((ds, i) =>
    el("option", Object.assign({ value: String(i), text: ds.name || ds.id },
                               Number(selected) === i ? { selected: "selected" } : {}))
  );
}
function fieldOptions(dsIndex, selected, role) {
  const ds = DATA.datasources[Number(dsIndex) || 0];
  const options = [el("option", { value: "", text: "（選ぶ）" })];
  ((ds && ds.fields) || []).forEach(field => {
    if (field.hidden) return;
    if (role && field.role !== role) return;
    const name = field.name || "";
    options.push(el("option", Object.assign({ value: name, text: name },
                                            name === selected ? { selected: "selected" } : {})));
  });
  return options;
}

function labeled(text, control) {
  return el("label", { class: "f" }, [el("span", { text: text }), control]);
}

const DESIGN_TOKENS = [
  { key: "main_color", label: "メインカラー", input: "d-main" },
  { key: "sub_color_1", label: "サブカラー①", input: "d-sub1" },
  { key: "sub_color_2", label: "サブカラー②", input: "d-sub2" },
  { key: "text_color", label: "通常時の文字色", input: "d-text" },
];
function designValue(key) {
  const token = DESIGN_TOKENS.find(item => item.key === key);
  return token ? document.getElementById(token.input).value.trim() : "";
}

/* 色は「デザインルールを参照」と「個別に指定」を選べる。参照は @キー で保存する */
function colorControl(area, spec, value) {
  const token = (typeof value === "string" && value.charAt(0) === "@") ? value.slice(1) : "";
  const picker = el("input", { type: "color",
    value: token ? (designValue(token) || "#4a7dff") : (value || "#4a7dff") });
  const source = el("select", {}, [el("option", { value: "", text: "個別に指定" })].concat(
    DESIGN_TOKENS.map(item => el("option",
      Object.assign({ value: item.key, text: item.label },
                    item.key === token ? { selected: "selected" } : {})))));
  function apply() {
    if (source.value) {
      picker.disabled = true;
      picker.value = designValue(source.value) || picker.value;
      area.params[spec.name] = "@" + source.value;
    } else {
      picker.disabled = false;
      area.params[spec.name] = picker.value;
    }
  }
  source.addEventListener("change", apply);
  picker.addEventListener("input", () => {
    if (!source.value) area.params[spec.name] = picker.value;
  });
  picker.disabled = !!token;
  return el("span", { class: "color2" }, [source, picker]);
}

function paramControl(area, spec) {
  const value = area.params[spec.name] === undefined ? "" : area.params[spec.name];
  let control;
  if (spec.kind === "bool") {
    control = el("input", Object.assign({ type: "checkbox" }, value ? { checked: "checked" } : {}));
    control.addEventListener("change", () => { area.params[spec.name] = control.checked; });
  } else if (spec.kind === "field" || spec.kind === "fields") {
    control = el("select", {}, fieldOptions(area.datasource, value, spec.role));
    if (spec.kind === "fields") control.setAttribute("multiple", "multiple");
    control.addEventListener("change", () => {
      area.params[spec.name] = spec.kind === "fields"
        ? Array.from(control.selectedOptions).map(o => o.value).filter(Boolean)
        : control.value;
    });
  } else if (spec.kind === "color") {
    control = colorControl(area, spec, value);
  } else {
    control = el("input", { type: "text", value: value });
    control.addEventListener("input", () => { area.params[spec.name] = control.value.trim(); });
  }
  const label = (spec.label || spec.name) + (spec.required ? " *" : "");
  const field = labeled(label, control);
  field.setAttribute("title", spec.name);
  return field;
}

let DRAG = null;
const DROP_MARKS = ["drop-left", "drop-right", "drop-top", "drop-bottom", "drop-into"];

function clearDropMarks() {
  document.querySelectorAll("." + DROP_MARKS.join(",."))
    .forEach(node => node.classList.remove.apply(node.classList, DROP_MARKS));
}

/* 掴む所を押したときだけ draggable にする。入力欄の文字選択を壊さないため */
function attachGrip(grip, card, payload) {
  grip.addEventListener("mousedown", () => card.setAttribute("draggable", "true"));
  grip.addEventListener("mouseup", () => card.removeAttribute("draggable"));
  card.addEventListener("dragstart", event => {
    DRAG = payload();
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", DRAG.kind);
    card.classList.add("dragging-src");
    event.stopPropagation();
  });
  card.addEventListener("dragend", () => {
    DRAG = null;
    card.removeAttribute("draggable");
    card.classList.remove("dragging-src");
    clearDropMarks();
  });
}

function moveAreaTo(targetRow, targetIndex) {
  if (!DRAG || DRAG.kind !== "area") return;
  const from = DRAG.row.areas.indexOf(DRAG.area);
  if (from < 0) return;
  DRAG.row.areas.splice(from, 1);
  if (DRAG.row === targetRow && from < targetIndex) targetIndex -= 1;
  targetRow.areas.splice(targetIndex, 0, DRAG.area);
  renderRows();
}

function moveRowTo(targetIndex) {
  if (!DRAG || DRAG.kind !== "row") return;
  const from = DASH.rows.indexOf(DRAG.row);
  if (from < 0) return;
  DASH.rows.splice(from, 1);
  if (from < targetIndex) targetIndex -= 1;
  DASH.rows.splice(targetIndex, 0, DRAG.row);
  renderRows();
}

function renderArea(row, area) {
  const card = el("div", { class: "area" });

  const kind = el("select", {}, [
    el("option", Object.assign({ value: "chart", text: "グラフ" },
                               area.kind === "chart" ? { selected: "selected" } : {})),
    el("option", Object.assign({ value: "filter", text: "フィルター" },
                               area.kind === "filter" ? { selected: "selected" } : {})),
  ]);
  kind.addEventListener("change", () => { area.kind = kind.value; renderRows(); });

  const width = el("input", { type: "number", step: "10", min: "0", value: area.width });
  width.addEventListener("input", () => { area.width = width.value.trim(); });

  const remove = el("button", { class: "mini danger", text: "×", title: "エリアを削除" });
  remove.addEventListener("click", () => {
    row.areas = row.areas.filter(a => a !== area);
    renderRows();
  });

  const grip = el("span", { class: "grip", text: "⠿", title: "ドラッグして移動" });
  attachGrip(grip, card, () => ({ kind: "area", row: row, area: area }));

  card.addEventListener("dragover", event => {
    if (!DRAG || DRAG.kind !== "area" || DRAG.area === area) return;
    event.preventDefault();
    event.stopPropagation();
    const box = card.getBoundingClientRect();
    const after = event.clientX > box.left + box.width / 2;
    clearDropMarks();
    card.classList.add(after ? "drop-right" : "drop-left");
  });
  card.addEventListener("drop", event => {
    if (!DRAG || DRAG.kind !== "area") return;
    event.preventDefault();
    event.stopPropagation();
    const box = card.getBoundingClientRect();
    const after = event.clientX > box.left + box.width / 2;
    clearDropMarks();
    moveAreaTo(row, row.areas.indexOf(area) + (after ? 1 : 0));
  });

  card.appendChild(el("div", { class: "area-head" }, [
    grip, kind, labeled("幅 (px)", width),
    el("span", { class: "spacer" }), remove,
  ]));

  const dsSelectEl = el("select", {}, dsOptions(area.datasource));
  dsSelectEl.addEventListener("change", () => {
    area.datasource = Number(dsSelectEl.value);
    area.params = {};
    area.filterField = "";
    renderRows();
  });

  if (area.kind === "filter") {
    const field = el("select", {}, fieldOptions(area.datasource, area.filterField));
    field.addEventListener("change", () => { area.filterField = field.value; });
    card.appendChild(el("div", { class: "fields" }, [
      labeled("データソース", dsSelectEl),
      labeled("フィールド", field),
    ]));
  } else {
    const sheet = el("input", { type: "text", value: area.sheet, placeholder: "シート名" });
    sheet.addEventListener("input", () => { area.sheet = sheet.value.trim(); });

    const chart = el("select", {}, CHART_TYPES.map(type =>
      el("option", Object.assign({ value: type, text: DRAW_SPECS[type].label, title: type },
                                 type === area.chart ? { selected: "selected" } : {}))));
    chart.addEventListener("change", () => { area.chart = chart.value; area.params = {}; renderRows(); });

    const head = el("div", { class: "fields" }, [
      labeled("シート名", sheet),
      labeled("グラフ種類", chart),
      labeled("データソース", dsSelectEl),
    ]);
    card.appendChild(head);

    const specs = (DRAW_SPECS[area.chart] || {}).params || [];
    const required = specs.filter(spec => spec.required);
    const optional = specs.filter(spec => !spec.required);
    if (required.length) {
      card.appendChild(el("div", { class: "params" },
        required.map(spec => paramControl(area, spec))));
    }
    if (optional.length) {
      const more = el("details", { class: "more" }, [
        el("summary", { text: "詳細設定（" + optional.length + "）" }),
        el("div", { class: "params" }, optional.map(spec => paramControl(area, spec))),
      ]);
      if (area.moreOpen) more.setAttribute("open", "open");
      more.addEventListener("toggle", () => { area.moreOpen = more.open; });
      card.appendChild(more);
    }
  }

  /* アクション設定 */
  const enabled = el("input", Object.assign({ type: "checkbox" },
                                            area.action.enabled ? { checked: "checked" } : {}));
  enabled.addEventListener("change", () => { area.action.enabled = enabled.checked; renderRows(); });
  const actionBox = el("div", { class: "fields" }, [
    labeled("アクション", enabled),
  ]);
  if (area.action.enabled) {
    const ACTION_LABELS = { filter: "フィルター", highlight: "ハイライト", url: "URL を開く" };
    const type = el("select", {}, Object.keys(ACTION_LABELS).map(value =>
      el("option", Object.assign({ value: value, text: ACTION_LABELS[value] },
                                 value === area.action.type ? { selected: "selected" } : {}))));
    type.addEventListener("change", () => { area.action.type = type.value; });
    const target = el("input", { type: "text", value: area.action.target,
                                 placeholder: "対象シート名 / URL" });
    target.addEventListener("input", () => { area.action.target = target.value.trim(); });
    actionBox.appendChild(labeled("種類", type));
    actionBox.appendChild(labeled("対象", target));
  }
  card.appendChild(actionBox);
  return card;
}

function moveRow(row, delta) {
  const index = DASH.rows.indexOf(row);
  const next = index + delta;
  if (next < 0 || next >= DASH.rows.length) return;
  DASH.rows.splice(index, 1);
  DASH.rows.splice(next, 0, row);
  renderRows();
}

function renderRow(row, index) {
  const name = el("input", { type: "text", value: row.name, placeholder: "段の名前" });
  name.addEventListener("input", () => { row.name = name.value.trim(); });
  const height = el("input", { type: "number", step: "10", min: "0", value: row.height });
  height.addEventListener("input", () => { row.height = height.value.trim(); });

  const up = el("button", { class: "mini", text: "↑", title: "上へ" });
  const down = el("button", { class: "mini", text: "↓", title: "下へ" });
  const remove = el("button", { class: "mini danger", text: "×", title: "段を削除" });
  const addArea = el("button", { class: "act", text: "エリアを追加" });
  up.addEventListener("click", () => moveRow(row, -1));
  down.addEventListener("click", () => moveRow(row, 1));
  remove.addEventListener("click", () => {
    if (row.areas.some(a => a.sheet || a.filterField)
        && !confirm("この段を削除します。よろしいですか。")) return;
    DASH.rows = DASH.rows.filter(r => r !== row);
    renderRows();
  });
  addArea.addEventListener("click", () => { row.areas.push(newArea()); renderRows(); });

  const card = el("div", { class: row.collapsed ? "row-card collapsed" : "row-card" });
  const grip = el("span", { class: "grip", text: "⠿", title: "ドラッグして段を移動" });
  attachGrip(grip, card, () => ({ kind: "row", row: row }));
  card.addEventListener("dragover", event => {
    if (!DRAG || DRAG.kind !== "row" || DRAG.row === row) return;
    event.preventDefault();
    const box = card.getBoundingClientRect();
    const below = event.clientY > box.top + box.height / 2;
    clearDropMarks();
    card.classList.add(below ? "drop-bottom" : "drop-top");
  });
  card.addEventListener("drop", event => {
    if (!DRAG || DRAG.kind !== "row") return;
    event.preventDefault();
    const box = card.getBoundingClientRect();
    const below = event.clientY > box.top + box.height / 2;
    clearDropMarks();
    moveRowTo(DASH.rows.indexOf(row) + (below ? 1 : 0));
  });
  const toggle = el("button", { class: "mini", title: "この段を畳む / 開く",
                                text: row.collapsed ? "▶" : "▼" });
  const summary = el("span", { class: "tag", text: "エリア " + row.areas.length + " 件" });
  toggle.addEventListener("click", () => {
    row.collapsed = !row.collapsed;
    card.classList.toggle("collapsed", row.collapsed);
    toggle.textContent = row.collapsed ? "▶" : "▼";
  });

  card.appendChild(el("div", { class: "row-head" }, [
    grip, toggle,
    el("span", { class: "row-no", text: (index + 1) + "段目" }),
    labeled("名前", name), labeled("高さ (px)", height), summary, addArea,
    el("span", { class: "spacer" }), up, down, remove,
  ]));

  const areas = el("div", { class: "areas" }, row.areas.map(area => renderArea(row, area)));
  areas.addEventListener("dragover", event => {
    if (!DRAG || DRAG.kind !== "area") return;
    event.preventDefault();
    clearDropMarks();
    areas.classList.add("drop-into");
  });
  areas.addEventListener("drop", event => {
    if (!DRAG || DRAG.kind !== "area") return;
    event.preventDefault();
    clearDropMarks();
    moveAreaTo(row, row.areas.length);
  });
  card.appendChild(areas);
  return card;
}

function renderRows() {
  const root = document.getElementById("rows-root");
  root.innerHTML = "";
  if (!DASH.rows.length) {
    root.appendChild(el("p", { class: "empty", text: "段がありません。「段を追加」から始める。" }));
    return;
  }
  DASH.rows.forEach((row, index) => root.appendChild(renderRow(row, index)));
}

document.getElementById("row-add").addEventListener("click", () => {
  DASH.rows.push(newRow());
  renderRows();
});
["h-bg", "h-fg"].forEach(bindColor);
renderRows();

function dashboardYaml() {
  const value = id => document.getElementById(id).value.trim();
  let out = "dashboard:\n";
  out += "  name: " + yamlKey(value("db-name")) + "\n";
  out += "  width: " + yamlKey(value("db-width")) + "\n";
  out += "  height: " + yamlKey(value("db-height")) + "\n";
  out += "  header:\n";
  out += "    title: " + yamlKey(value("h-title")) + "\n";
  out += "    height: " + yamlKey(value("h-height")) + "\n";
  out += "    background_color: " + yamlKey(value("h-bg")) + "\n";
  out += "    font_color: " + yamlKey(value("h-fg")) + "\n";
  out += "  rows:\n";
  if (!DASH.rows.length) { out += "    []\n"; return out; }
  DASH.rows.forEach(row => {
    out += "    - name: " + yamlKey(row.name) + "\n";
    if (row.height) out += "      height: " + yamlKey(row.height) + "\n";
    out += "      areas:\n";
    row.areas.forEach(area => {
      const ds = DATA.datasources[area.datasource];
      out += "        - kind: " + yamlKey(area.kind) + "\n";
      out += "          datasource: " + yamlKey(ds ? (ds.name || ds.id) : "") + "\n";
      if (area.width) out += "          width: " + yamlKey(area.width) + "\n";
      if (area.kind === "filter") {
        out += "          field: " + yamlKey(area.filterField) + "\n";
      } else {
        out += "          sheet: " + yamlKey(area.sheet) + "\n";
        out += "          chart: " + yamlKey(area.chart) + "\n";
        const names = Object.keys(area.params).filter(key => {
          const v = area.params[key];
          return v !== "" && v !== undefined && !(Array.isArray(v) && !v.length);
        });
        if (names.length) {
          out += "          params:\n";
          names.forEach(key => {
            const v = area.params[key];
            if (Array.isArray(v)) {
              out += "            " + key + ":\n";
              v.forEach(item => { out += "              - " + yamlKey(item) + "\n"; });
            } else if (typeof v === "boolean") {
              out += "            " + key + ": " + (v ? "true" : "false") + "\n";
            } else {
              out += "            " + key + ": " + yamlKey(v) + "\n";
            }
          });
        }
      }
      if (area.action.enabled) {
        out += "          action:\n";
        out += "            type: " + yamlKey(area.action.type) + "\n";
        out += "            target: " + yamlKey(area.action.target) + "\n";
      }
    });
  });
  return out;
}

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
  <div class="panel acc open" id="acc-dashboard">
    <h2 class="acc-head">ダッシュボード <span class="todo">受け手は未実装</span></h2>
    <div class="acc-body">
    <p class="note">新しく組むダッシュボードの構成を作る。既存ダッシュボードの読み込み編集はしない。</p>
    <div class="grid">
      <label for="db-name">ダッシュボード名</label>
      <input type="text" id="db-name" value="ダッシュボード">
      <label for="db-width">幅 (px)</label>
      <input type="number" step="10" min="0" id="db-width" value="1600">
      <label for="db-height">高さ (px)</label>
      <input type="number" step="10" min="0" id="db-height" value="900">
    </div>
    </div>
  </div>

  <div class="panel acc open" id="acc-header">
    <h2 class="acc-head">ヘッダー</h2>
    <div class="acc-body">
      <div class="grid">
        <label for="h-title">タイトル</label>
        <input type="text" id="h-title" value="">
        <label for="h-height">高さ (px)</label>
        <input type="text" id="h-height" value="43">
        <label for="h-bg">背景色</label>
        <span class="color">
          <input type="color" id="h-bg-pick"><input type="text" id="h-bg" value="#c0c0c0">
        </span>
        <label for="h-fg">文字色</label>
        <span class="color">
          <input type="color" id="h-fg-pick"><input type="text" id="h-fg" value="#333333">
        </span>
      </div>
    </div>
  </div>

  <div class="panel acc open" id="acc-body">
    <h2 class="acc-head">ボディ（縦段組）</h2>
    <div class="acc-body">
      <p class="note">上から順に段が並ぶ。段の中のエリアは左から右へ横に並ぶ。
        エリアはグラフかフィルターのどちらか。</p>
      <div id="rows-root"></div>
      <p><button class="act" id="row-add">段を追加</button></p>
    </div>
  </div>

</section>

</main>
"""

_TEMPLATE = """<meta charset="utf-8">
<title>__TITLE__</title>
<style>__STYLE__</style>
__BODY__
<script type="application/json" id="wb-data">__DATA__</script>
<script type="application/json" id="draw-specs">__DRAW_SPECS__</script>
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


#: グラフの引数のうち、画面に出さないもの。
#: 集計方法（`*aggregation`）は出さない。フィールドの役割とデータ型が分かっていれば
#: `draw.py` の `_auto_metric_aggregation()` が決められるため、人が選ぶ必要がない。
_DRAW_SKIP = {"self", "datasource", "name"}


def _is_skipped(name: str) -> bool:
    return name in _DRAW_SKIP or name == "aggregation" or name.endswith("_aggregation")

#: グラフ種類の表示名。仕様 §6.14 の説明に合わせる。
_CHART_LABELS = {
    "draw_sheet": "土台シート",
    "draw_bar": "棒グラフ",
    "draw_yoy": "前年比の時系列",
    "draw_card": "KPI カード",
    "draw_quadrant": "散布図の四象限",
    "draw_crosstab": "ヒートマップ付きクロス集計",
    "draw_colored_yoy_sheet": "前年差を色分けした帳票",
}

#: フィールドを取る引数が、ディメンションとメジャーのどちらを求めるか。
#: 載っていない引数は絞り込まず全フィールドを出す。
_PARAM_ROLES = {
    "item": "dimension",
    "items": "dimension",
    "x_item": "dimension",
    "y_item": "dimension",
    "index_partition_by": "dimension",
    "metric": "measure",
    "metrics": "measure",
    "main_metric": "measure",
    "sub_metric": "measure",
    "x_metric": "measure",
    "y_metric": "measure",
    "size_metric": "measure",
    "color_metric": "measure",
    "label_metric": "measure",
}

#: グラフの引数の表示名。載っていない引数は英語名のまま出す。
_PARAM_LABELS = {
    "item": "項目",
    "items": "項目",
    "metric": "メジャー",
    "metrics": "メジャー",
    "item_shelf": "項目を置くシェルフ",
    "aggregation": "集計方法",
    "descending": "降順にする",
    "visible": "シートを表示する",
    "title": "タイトル",
    "main_metric": "主メジャー",
    "sub_metric": "副メジャー",
    "main_aggregation": "主メジャーの集計",
    "sub_aggregation": "副メジャーの集計",
    "main_color": "主な色",
    "value_color": "数値の色",
    "title_background_color": "タイトルの背景色",
    "vertical_alignment": "縦の揃え",
    "negative_color": "減少の色",
    "positive_color": "増加の色",
    "ratio_color": "比率の色",
    "mark_type": "マークの種類",
    "bar_color": "棒の色",
    "bar_opacity": "棒の不透明度",
    "axis_min": "軸の最小値",
    "axis_max": "軸の最大値",
    "show_axes": "軸を表示する",
    "index_partition_by": "順位の区切り",
    "date_level": "日付の単位",
    "color": "色",
    "x_item": "横の項目",
    "y_item": "縦の項目",
    "x_metric": "横軸のメジャー",
    "y_metric": "縦軸のメジャー",
    "size_metric": "サイズのメジャー",
    "x_aggregation": "横軸の集計",
    "y_aggregation": "縦軸の集計",
    "size_aggregation": "サイズの集計",
    "color_metric": "色のメジャー",
    "label_metric": "ラベルのメジャー",
    "color_aggregation": "色の集計",
    "label_aggregation": "ラベルの集計",
    "min_color": "最小値の色",
    "mid_color": "中間の色",
    "max_color": "最大値の色",
    "colors": "四象限の色",
    "opacity": "不透明度",
}


def _param_kind(name: str, annotation: str) -> str:
    if "list[FieldInput]" in annotation:
        return "fields"
    if "FieldInput" in annotation:
        return "field"
    if "color" in name:
        return "color"
    if "bool" in annotation:
        return "bool"
    if "float" in annotation or "int" in annotation:
        return "number"
    return "text"


def _draw_specs() -> dict[str, dict[str, Any]]:
    """`TwbWorkbook.draw_*()` の引数を実物から読み、画面の入力欄の定義にする。"""
    import inspect

    from .workbook import TwbWorkbook

    specs: dict[str, dict[str, Any]] = {}
    for method_name in sorted(dir(TwbWorkbook)):
        if not method_name.startswith("draw_"):
            continue
        signature = inspect.signature(getattr(TwbWorkbook, method_name))
        params = []
        for parameter in signature.parameters.values():
            if _is_skipped(parameter.name):
                continue
            annotation = str(parameter.annotation)
            params.append(
                {
                    "name": parameter.name,
                    "label": _PARAM_LABELS.get(parameter.name, parameter.name),
                    "kind": _param_kind(parameter.name, annotation),
                    "role": _PARAM_ROLES.get(parameter.name),
                    "required": parameter.default is inspect.Parameter.empty,
                }
            )
        specs[method_name] = {
            "label": _CHART_LABELS.get(method_name, method_name),
            "params": params,
        }
    return specs


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
        .replace("__DRAW_SPECS__", _embed_json(_draw_specs()))
        .replace("__TITLE__", _escape(title))
    )
