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
/* YAML のダウンロードはタブごと（2026-09-14）。タブの右上に置く */
.tab-actions { display: flex; justify-content: flex-end; align-items: center; gap: 10px;
               margin-bottom: 12px; }
.tab-actions .tag { font-size: 11px; color: #6b7688; }
button.dl { font: inherit; padding: 5px 14px; border: 0; border-radius: 4px; cursor: pointer;
            background: #4a7dff; color: #fff; font-weight: 600; }
button.dl:hover { background: #3a68e0; }
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
table { border-collapse: collapse; width: 100%; font-size: 12px; background: #fff;
        table-layout: fixed; }
th, td { border: 1px solid #d8dde5; padding: 3px 6px; text-align: left; vertical-align: top;
         word-break: break-word; }
th { background: #eef1f6; position: sticky; top: 0; font-weight: 600; white-space: nowrap;
     overflow: hidden; text-overflow: ellipsis; }
table.col-resize-hover, table.col-resizing { cursor: col-resize; }
table.col-resizing { user-select: none; }
/* 中身が空のセルでも行の高さを保つ。セルを常時 contenteditable にしていた頃は
   ブラウザが空でもキャレット1行分の高さを確保していたが、1クリック＝選択に
   変えて通常の要素になったため、空行がパディングだけの高さに潰れた
   （計算フィールド表の空行、2026-09-13 修正）。表のセルの height は最小値として
   効くので、中身が増えれば行は伸びる。 */
td { height: 23px; }
td.ro { background: #fafbfc; color: #555; }
td[data-edit] { white-space: pre-wrap; }
td:focus { outline: none; }
td.invalid { background: #ffecec; }
td.sel, td.ro.sel { background: #dbe6ff; }
/* 選んだセル（1クリック目）と、編集中のセル（2クリック目）を見分ける */
td.active { outline: 2px solid #4a7dff; outline-offset: -2px; }
td[contenteditable] { background: #fffdf2; cursor: text; }
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
.color2 { display: flex; gap: 4px; align-items: center; }
.color2 select { max-width: 118px; font-size: 12px; padding: 3px 6px; }
.color2 input[type=color] { width: 30px; height: 26px; padding: 0; border: 1px solid #c3cad6;
                            border-radius: 4px; background: none; cursor: pointer; }
.color2 input[type=color]:disabled { cursor: default; opacity: .65; }
.colors4 { display: flex; gap: 10px; flex-wrap: wrap; }
.colors4-item { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.colors4-item span.colors4-label { font-size: 10px; color: #6b7688; }
.grip { cursor: grab; color: #8b96a8; font-size: 14px; line-height: 1; padding: 0 2px;
        user-select: none; }
.grip:active { cursor: grabbing; }
.dragging-src { opacity: .4; }
.area.drop-left { box-shadow: inset 3px 0 0 #4a7dff; }
.area.drop-right { box-shadow: inset -3px 0 0 #4a7dff; }
.areas.drop-into { outline: 2px dashed #4a7dff; outline-offset: -4px; }
.row-card.drop-top { box-shadow: inset 0 3px 0 #4a7dff; }
.row-card.drop-bottom { box-shadow: inset 0 -3px 0 #4a7dff; }
.folder-popup { position: absolute; z-index: 20; background: #fff; border: 1px solid #c3cad6;
                border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,.15); max-height: 200px;
                overflow-y: auto; min-width: 140px; }
.folder-popup-item { padding: 5px 10px; font-size: 12px; cursor: pointer; white-space: nowrap; }
.folder-popup-item:hover { background: #eef1f6; }
.fields-check-btn { font-size: 12px; padding: 4px 8px; border: 1px solid #c3cad6; border-radius: 4px;
                     background: #fff; cursor: pointer; min-width: 90px; text-align: left; }
.fields-check-btn:hover { background: #eef1f6; }
.name-gen { display: flex; gap: 4px; align-items: center; }
.name-gen input { flex: 1; }
.modal-overlay { position: fixed; inset: 0; background: rgba(20,26,38,.4); z-index: 100;
                 display: flex; align-items: center; justify-content: center; }
.modal-box { background: #fff; border-radius: 8px; width: 640px; max-width: 92vw; max-height: 82vh;
             display: flex; flex-direction: column; box-shadow: 0 12px 32px rgba(0,0,0,.25); }
.modal-head { display: flex; align-items: center; justify-content: space-between;
              padding: 10px 14px; border-bottom: 1px solid #e3e7ee; }
.modal-head strong { font-size: 13px; }
.modal-body { display: flex; gap: 12px; padding: 12px 14px; overflow: hidden; flex: 1; }
.modal-col { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.modal-col h3 { margin: 0 0 6px; font-size: 11px; color: #6b7688; font-weight: normal; }
.modal-list { flex: 1; overflow-y: auto; border: 1px solid #e3e7ee; border-radius: 4px;
              padding: 4px; min-height: 260px; }
.modal-group-label { padding: 6px 8px 2px; font-size: 10px; color: #8b96a8; }
.modal-item { display: flex; align-items: center; gap: 6px; padding: 5px 8px; font-size: 12px;
              border-radius: 4px; cursor: grab; user-select: none; }
.modal-item:hover { background: #eef1f6; }
.modal-item span:nth-child(2) { flex: 1; }
.modal-item.dragging-src { opacity: .4; }
.modal-item.drop-top { box-shadow: inset 0 2px 0 #4a7dff; }
.modal-item.drop-bottom { box-shadow: inset 0 -2px 0 #4a7dff; }
.modal-foot { padding: 10px 14px; border-top: 1px solid #e3e7ee; text-align: right; }
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

/* ---- 表の列幅をドラッグで変える ---- */
/* table-layout: fixed にし、<colgroup> の <col> 幅をドラッグで直接書き換える。
   <thead> はデータの再描画（renderTables）では作り直さないので、ページ読み込み時に
   一度つければ持続する（2026-09-13 追加）。

   境界 i を動かすときは col[i] と col[i+1] の幅の合計を変えず、2列の間だけで
   やり取りする。動かした列だけを % から px へ変えると、他の列は % のまま残り、
   table-layout: fixed が「列幅の合計を表の幅に一致させる」ために動かしていない
   列まで再配分してしまう（左隣の列が勝手に縮む不具合の原因だった）。
   最小幅（MIN_WIDTH）は動かす側・動かされる側の両方に効くので、右へ広げすぎて
   隣の列を潰すこともできない。

   つまみは th の中の小さな要素ではなく、表全体への mousedown/mousemove で
   「クリック位置が列境界の x 座標に近いか」を判定する方式にする（2026-09-13
   修正）。th の高さだけが当たり判定だと、見た目の縦線（表の全行にまたがる）の
   ごく一部でしかつかめず判定がシビアだったため、縦線の全長（tbody の行も含む）
   を対象にする。判定は capture フェーズで行い、`enableGrid()` の mousedown
   （`event.target.closest("td")` でセル選択を始める、bubble フェーズ）より必ず
   先に実行されるようにする。境界にヒットしたら stopImmediatePropagation() で
   後続のセル選択を起こさせない。 */
const COLUMN_RESIZE_MIN_WIDTH = 40;
const COLUMN_RESIZE_HIT_ZONE = 10; // 境界から左右何pxまでを判定対象にするか

function enableColumnResize(table) {
  const cols = Array.from(table.querySelectorAll("colgroup col"));
  const headers = Array.from(table.querySelectorAll("thead th"));

  // すべての列幅を実測 px へ固定する（% のままの列を残さない）。ドラッグ開始の
  // たびに呼び直す（2026-09-13 修正）。ページ読み込み時に1回だけ呼ぶと、表が
  // アコーディオンの中で折りたたまれている（display: none）場合に全列の幅が
  // 0px のまま固定されてしまう。計算フィールド表は既定で折りたたまれているため
  // ここで実際に踏んだ ―― 0px で固定された列は、他の列を動かした瞬間に
  // 「指定した合計が表の幅に足りない分」の帳尻合わせで一気に広がって見えた。
  function freezeAllColumnWidths() {
    headers.forEach((th, index) => {
      if (cols[index]) cols[index].style.width = th.getBoundingClientRect().width + "px";
    });
  }

  // 最後の列は残り幅を埋めるので境界の対象にしない（headers.length - 1 個の境界）
  function boundaryAt(clientX) {
    for (let index = 0; index < headers.length - 1; index++) {
      const distance = Math.abs(clientX - headers[index].getBoundingClientRect().right);
      if (distance <= COLUMN_RESIZE_HIT_ZONE) return index;
    }
    return -1;
  }

  let dragIndex = -1;
  let startX = 0;
  let startWidth = 0;
  let pairWidth = 0;

  function onMove(event) {
    const rawWidth = startWidth + (event.clientX - startX);
    const width = Math.max(
      COLUMN_RESIZE_MIN_WIDTH,
      Math.min(pairWidth - COLUMN_RESIZE_MIN_WIDTH, rawWidth)
    );
    cols[dragIndex].style.width = width + "px";
    cols[dragIndex + 1].style.width = (pairWidth - width) + "px";
  }
  function onUp() {
    dragIndex = -1;
    table.classList.remove("col-resizing");
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
  }

  table.addEventListener("mousedown", event => {
    const index = boundaryAt(event.clientX);
    if (index < 0) return;
    // preventDefault() はしない。contenteditable セルの端はこの判定域に入りやすく、
    // preventDefault() するとセルへフォーカスするブラウザの既定動作まで止まり、
    // フォーカスで開くはずのデータ型・役割・フォルダの候補ポップアップが開かなく
    // なる実害があった（2026-09-13）。ドラッグ中の文字選択は table.col-resizing の
    // user-select: none で防いでいるので、preventDefault() は無くても支障ない。
    event.stopImmediatePropagation();
    freezeAllColumnWidths();
    dragIndex = index;
    startX = event.clientX;
    // <col> は非表示要素で getBoundingClientRect() が使えないため、対応する
    // <th> の実測幅を使う（列の位置は th と 1 対 1 で対応する）。
    startWidth = headers[index].getBoundingClientRect().width;
    pairWidth = startWidth + headers[index + 1].getBoundingClientRect().width;
    table.classList.add("col-resizing");
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, true);

  table.addEventListener("mousemove", event => {
    if (dragIndex >= 0) return;
    table.classList.toggle("col-resize-hover", boundaryAt(event.clientX) >= 0);
  });
  table.addEventListener("mouseleave", () => {
    if (dragIndex < 0) table.classList.remove("col-resize-hover");
  });
}

/* ---- セル状の表: 範囲選択・コピー・貼り付け ---- */
let activeGrid = null;

function enableGrid(table, options) {
  options = options || {};
  const sel = { r1: -1, c1: -1, r2: -1, c2: -1 };
  let dragging = false;
  /* 編集中のセル。null なら「選んでいるだけ」（2026-09-13 追加）。
     セルは既定で contenteditable を持たないので、`isContentEditable` は
     「いま編集中か」を意味する。「編集できるセルか」は isEditable() を使う。 */
  let editing = null;
  const isEditable = cell => !!cell && cell.dataset.edit === "1";

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
        cell.classList.toggle("active", sel.r1 >= 0 && ri === sel.r1 && ci === sel.c1);
      });
    });
  }
  function anchorAt(cell) { const p = posOf(cell); sel.r1 = sel.r2 = p.r; sel.c1 = sel.c2 = p.c; paint(); }
  function extendTo(cell) { const p = posOf(cell); sel.r2 = p.r; sel.c2 = p.c; paint(); }
  function dirty() { table.dispatchEvent(new Event("griddirty")); }

  /* ---- セルの選択と編集（Excel と同じ 1クリック＝選択 / 2クリック＝編集） ---- */
  function caretTo(cell, clientX, clientY) {
    const selection = window.getSelection();
    if (!selection) return;
    let range = null;
    if (clientX !== undefined && document.caretRangeFromPoint) {
      range = document.caretRangeFromPoint(clientX, clientY);
      if (range && !cell.contains(range.startContainer)) range = null;
    }
    if (!range) {
      range = document.createRange();
      range.selectNodeContents(cell);
      range.collapse(false); // 末尾
    }
    selection.removeAllRanges();
    selection.addRange(range);
  }
  function beginEdit(cell, clientX, clientY) {
    if (!isEditable(cell) || editing === cell) return;
    endEdit();
    editing = cell;
    cell.setAttribute("contenteditable", "true");
    cell.focus();
    caretTo(cell, clientX, clientY);
  }
  function endEdit() {
    if (!editing) return;
    const cell = editing;
    editing = null;
    cell.removeAttribute("contenteditable");
  }
  function isAnchor(cell) {
    if (sel.r1 < 0 || hasRange()) return false;
    const p = posOf(cell);
    return p.r === sel.r1 && p.c === sel.c1;
  }

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
      td.classList.remove("sel", "invalid", "active");
      // 編集中に付く contenteditable は履歴に残さない（残すと undo 後に
      // 編集中でないセルが編集可能なまま復元される）
      td.removeAttribute("contenteditable");
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
    editing = null; // これから作り直す要素なので属性を外す必要はない
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
  table.addEventListener("focusout", event => {
    if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
    // 表の外へ出たときだけ編集を終える。表の中の移動（次のセルへ）は
    // それぞれの処理が endEdit() を呼ぶ。
    if (editing && !table.contains(event.relatedTarget)) endEdit();
    commit();
  });

  table.addEventListener("mousedown", event => {
    const cell = event.target.closest("td");
    if (!cell) return;
    activeGrid = table;
    // 編集中のセルの中は、そのままキャレットの移動・範囲選択をさせる
    if (editing === cell) return;
    if (event.shiftKey && sel.r1 >= 0) {
      event.preventDefault();
      endEdit();
      extendTo(cell);
      return;
    }
    // 2クリック目（すでに選んでいるセルをもう一度）で編集に入る
    const second = isAnchor(cell) && isEditable(cell);
    event.preventDefault(); // 1クリック目でキャレットを入れない
    endEdit();
    anchorAt(cell);
    if (second) {
      beginEdit(cell, event.clientX, event.clientY);
      return;
    }
    cell.focus();
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
      endEdit();
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
    // 選んでいるだけのとき（編集中でない）は Excel と同じ挙動にする
    if (!editing) {
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        forEachSelected(c => { if (isEditable(c)) c.textContent = ""; });
        dirty();
        commit();
        return;
      }
      if (event.key === "F2" && isEditable(cell)) {
        event.preventDefault();
        beginEdit(cell);
        return;
      }
      // 文字キーを押したら、その文字で置き換えて編集に入る
      if (isEditable(cell) && event.key.length === 1
          && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        beginEdit(cell);
        cell.textContent = event.key;
        caretTo(cell);
        cell.dispatchEvent(new Event("input", { bubbles: true }));
        return;
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      endEdit();
      cell.focus();
      commit();
      return;
    }
    /* セル内改行。この表で複数行になるのは主に式なので、編集中の Enter は
       改行にする（2026-09-13 変更。当初は Excel に合わせて Alt+Enter だけを
       改行にしていたが、式を書くには Enter のほうが打ちやすいため入れ替えた）。
       Alt+Enter は Excel の指の記憶に合わせた別名として残す。確定は Ctrl+Enter。
       挿入するのは <br> ではなく素の "\n"（white-space: pre-wrap と組み合わせる）。
       textContent は <br> を無視して前後を連結してしまい、読み取り側
       （captureInto() など）で改行が消えるため。 */
    const insertsLineBreak = event.key === "Enter"
      && (event.altKey || (editing && !event.ctrlKey && !event.metaKey));
    if (insertsLineBreak && isEditable(cell)) {
      event.preventDefault();
      if (!editing) beginEdit(cell); // 選んでいるだけなら編集に入ってから改行する
      const selection = window.getSelection();
      if (selection && selection.rangeCount) {
        const range = selection.getRangeAt(0);
        range.deleteContents();
        const lineBreak = document.createTextNode("\n");
        range.insertNode(lineBreak);
        range.setStartAfter(lineBreak);
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
      }
      cell.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    /* 編集中はセルの外へ出さない（2026-09-13 修正）。矢印キーはすべてセル内の
       キャレット移動（上下は複数行の式の1つ上/下の行）。Ctrl+Enter で編集を
       終えてセルの選択へ戻り、そこから矢印でセルを移動する。Tab は Excel と
       同じく確定して隣のセルへ動く。 */
    if (editing && event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      endEdit();
      cell.focus();
      commit();
      return;
    }
    if (editing && event.key.startsWith("Arrow")) return;
    let dr = 0, dc = 0;
    if (event.key === "ArrowDown" || event.key === "Enter") dr = 1;
    else if (event.key === "ArrowUp") dr = -1;
    else if (event.key === "ArrowLeft") dc = -1;
    else if (event.key === "ArrowRight") dc = 1;
    else if (event.key === "Tab") dc = event.shiftKey ? -1 : 1;
    else return;
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
      if (isEditable(candidate)) next = candidate;
      else if (dc === 0) break;
    }
    if (next) { endEdit(); next.focus(); anchorAt(next); }
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
    // 編集中はセル内の文字選択をそのままコピーさせる。選んでいるだけなら
    // 1セルでも範囲と同じ扱いでコピーする（2026-09-13、選択モード導入に合わせ
    // hasRange() から「選択があるか」へ緩めた。以前は 1 セルだけだとキャレットが
    // 入っていたのでブラウザ既定のコピーが効いていた）
    if (activeGrid !== table || editing || sel.r1 < 0) return;
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
    // 編集中はキャレット位置へ差し込む。ブラウザ既定の貼り付けに任せると
    // <div> や <br> が入り、textContent で読む側が壊れるため自前で入れる。
    if (editing) {
      const selection = window.getSelection();
      if (selection && selection.rangeCount) {
        const range = selection.getRangeAt(0);
        range.deleteContents();
        const node = document.createTextNode(text.replace(/\r/g, ""));
        range.insertNode(node);
        range.setStartAfter(node);
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
      }
      editing.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    const grid = text.replace(/\r/g, "").replace(/\n+$/, "").split("\n").map(r => r.split("\t"));
    const start = cell ? posOf(cell) : { r: rect().top, c: rect().left };
    ensureRows(start.r + grid.length);
    const rows = rowsOf();
    grid.forEach((cols, r) => {
      const row = rows[start.r + r];
      if (!row) return;
      cols.forEach((value, c) => {
        const target = row.cells[start.c + c];
        if (target && isEditable(target)) target.textContent = value.trim();
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

const NO_FOLDER = "フォルダ未指定";
function isNoFolder(folder) { return !folder || folder === NO_FOLDER; }

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
    folder: folderNameOf(ds, field) || NO_FOLDER,
    datatype: field.datatype || "",
    role: field.role || "",
  }));
  const calcs = (ds.fields || []).filter(f => f.is_calculated).map(field => ([
    field.name || "", field.formula || "", folderNameOf(ds, field) || NO_FOLDER,
    field.datatype || "", field.role || "",
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

/* セルは既定では contenteditable にしない（2026-09-13 変更）。Excel と同じく
   1クリック目はセルの選択、2クリック目でテキスト編集に入る（`beginEdit()` が
   そのときだけ contenteditable を付ける）ため、「編集できるセルか」は
   data-edit 属性で持つ。tabindex を付けるのは、編集していなくてもセルへ
   フォーカスを当てて矢印キーの移動とコピーを効かせるため。 */
function editableCell(text) {
  return el("td", { "data-edit": "1", tabindex: "-1", text: text });
}
function readonlyCell(text) {
  return el("td", { class: "ro", tabindex: "-1", text: text });
}

/* 計算フィールド表の列順: 名前 / 式 / フォルダ / データ型 / 役割 */
const CALC_DATATYPE_CHOICES = ["string", "integer", "real", "boolean", "date", "datetime"];
const CALC_ROLE_CHOICES = ["measure", "dimension"];

function calcRow(name, formula, folder, datatype, role) {
  const folderCell = editableCell(folder);
  const datatypeCell = editableCell(datatype);
  const roleCell = editableCell(role);
  folderCell.addEventListener("focus", () => openChoicePopup(folderCell, folderCandidates()));
  datatypeCell.addEventListener("focus", () => openChoicePopup(datatypeCell, CALC_DATATYPE_CHOICES));
  roleCell.addEventListener("focus", () => openChoicePopup(roleCell, CALC_ROLE_CHOICES));
  return el("tr", {}, [
    editableCell(name),
    editableCell(formula),
    folderCell,
    datatypeCell,
    roleCell,
  ]);
}

/* セル状の表の候補ポップアップ。フォルダ・データ型・役割で共用する。
   フォルダは自由入力のまま検証しない。データ型・役割は候補外なら赤くする
   （validateCalc()）が、入力そのものは自由テキストのまま制限しない。 */
let choicePopup = null;
function closeFolderPopup() {
  if (choicePopup) { choicePopup.remove(); choicePopup = null; }
}
function folderCandidates() {
  const set = new Set([NO_FOLDER]);
  Array.from(document.getElementById("rename-body").rows).forEach(row => {
    const value = row.cells[2].textContent.trim();
    if (value) set.add(value);
  });
  return Array.from(set);
}
function openChoicePopup(cell, candidates) {
  closeFolderPopup();
  const popup = el("div", { class: "folder-popup" },
    candidates.map(name => {
      const item = el("div", { class: "folder-popup-item", text: name });
      item.addEventListener("mousedown", event => {
        event.preventDefault();
        cell.textContent = name;
        cell.dispatchEvent(new Event("input", { bubbles: true }));
        closeFolderPopup();
      });
      return item;
    })
  );
  const rect = cell.getBoundingClientRect();
  popup.style.left = (rect.left + window.scrollX) + "px";
  popup.style.top = (rect.bottom + window.scrollY) + "px";
  document.body.appendChild(popup);
  choicePopup = popup;
}
/* capture フェーズで閉じる（2026-09-13 修正）。セルの選択は mousedown の中で
   自前に cell.focus() を呼ぶようになり、その focus で開いた候補ポップアップを、
   同じクリックの続きで流れてくるこの「外側クリックで閉じる」処理が即座に
   閉じてしまっていた。capture なら開く前に走るので、前のポップアップだけを
   閉じて新しいものは残る。 */
document.addEventListener("mousedown", event => {
  if (choicePopup && !choicePopup.contains(event.target)) closeFolderPopup();
}, true);

/* items（draw_sheet の並び順）や metrics（前年差の帳票の行順）など、複数選択のフィールドは
   並び順がそのままシート上の配置順になる。<select multiple> や、順序を持てない
   チェックボックス一覧では並べ替えができないという指摘（2026-09-13）を受けて、
   左＝候補・右＝選択済み（この順で配置）のモーダルをドラッグ＆ドロップで
   操作する形にする。右リスト内のドラッグは既存の段・エリアの並べ替えと同じ
   「ドロップ位置が上半分か下半分かで前後を決める」やり方に揃える。 */
/* ドロップ先のインデックスと、目印を付ける対象・上下どちらかを1回で決める。
   見つかった要素の上半分なら「その手前に挿入（before）」、無ければ末尾。 */
function modalDropTarget(container, clientY) {
  const items = Array.from(container.querySelectorAll(".modal-item"));
  for (let i = 0; i < items.length; i++) {
    const rect = items[i].getBoundingClientRect();
    if (clientY < rect.top + rect.height / 2) return { index: i, markItem: items[i], before: true };
  }
  const last = items[items.length - 1] || null;
  return { index: items.length, markItem: last, before: false };
}
function clearModalDropMarks() {
  document.querySelectorAll(".modal-item.drop-top,.modal-item.drop-bottom")
    .forEach(node => node.classList.remove("drop-top", "drop-bottom"));
}

function openFieldOrderModal(area, spec, selected, onChange) {
  let dragFrom = null; // { list: "left" | "right", name: string }

  const overlay = el("div", { class: "modal-overlay" });
  overlay.addEventListener("mousedown", event => {
    if (event.target === overlay) overlay.remove();
  });

  const leftList = el("div", { class: "modal-list" });
  const rightList = el("div", { class: "modal-list" });

  function makeItem(name, listName) {
    const item = el("div", { class: "modal-item", draggable: "true" }, [
      el("span", { class: "grip", text: "⠿" }),
      el("span", { text: name }),
    ]);
    if (listName === "right") {
      const remove = el("button", { class: "mini danger", text: "×", title: "外す" });
      remove.addEventListener("click", () => {
        selected.splice(selected.indexOf(name), 1);
        onChange();
        renderLists();
      });
      item.appendChild(remove);
    } else {
      item.addEventListener("dblclick", () => {
        selected.push(name);
        onChange();
        renderLists();
      });
    }
    item.addEventListener("dragstart", event => {
      dragFrom = { list: listName, name: name };
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", name);
      item.classList.add("dragging-src");
    });
    item.addEventListener("dragend", () => {
      dragFrom = null;
      item.classList.remove("dragging-src");
      clearModalDropMarks();
    });
    return item;
  }

  function renderLists() {
    leftList.innerHTML = "";
    rightList.innerHTML = "";
    groupedFields(area.datasource, spec.role).forEach(group => {
      const remaining = group.fields.filter(field => !selected.includes(field.name || ""));
      if (!remaining.length) return;
      leftList.appendChild(el("div", { class: "modal-group-label", text: group.folderName }));
      remaining.forEach(field => leftList.appendChild(makeItem(field.name || "", "left")));
    });
    selected.forEach(name => rightList.appendChild(makeItem(name, "right")));
  }

  rightList.addEventListener("dragover", event => {
    if (!dragFrom) return;
    event.preventDefault();
    clearModalDropMarks();
    const { markItem, before } = modalDropTarget(rightList, event.clientY);
    if (markItem) markItem.classList.add(before ? "drop-top" : "drop-bottom");
  });
  rightList.addEventListener("drop", event => {
    if (!dragFrom) return;
    event.preventDefault();
    const { index } = modalDropTarget(rightList, event.clientY);
    if (dragFrom.list === "right") {
      const from = selected.indexOf(dragFrom.name);
      if (from < 0) return;
      selected.splice(from, 1);
      selected.splice(from < index ? index - 1 : index, 0, dragFrom.name);
    } else if (!selected.includes(dragFrom.name)) {
      selected.splice(index, 0, dragFrom.name);
    }
    onChange();
    renderLists();
  });
  leftList.addEventListener("dragover", event => {
    if (dragFrom && dragFrom.list === "right") event.preventDefault();
  });
  leftList.addEventListener("drop", event => {
    if (!dragFrom || dragFrom.list !== "right") return;
    event.preventDefault();
    const index = selected.indexOf(dragFrom.name);
    if (index >= 0) selected.splice(index, 1);
    onChange();
    renderLists();
  });

  renderLists();

  const closeBtn = el("button", { class: "mini", text: "×", title: "閉じる" });
  closeBtn.addEventListener("click", () => overlay.remove());
  const footClose = el("button", { class: "act", text: "閉じる" });
  footClose.addEventListener("click", () => overlay.remove());

  const box = el("div", { class: "modal-box" }, [
    el("div", { class: "modal-head" }, [
      el("strong", { text: (spec.label || spec.name) + "の並び替え" }),
      closeBtn,
    ]),
    el("div", { class: "modal-body" }, [
      el("div", { class: "modal-col" }, [el("h3", { text: "候補（ダブルクリックまたはドラッグで追加）" }), leftList]),
      el("div", { class: "modal-col" }, [el("h3", { text: "選択済み（この順でシートに配置）" }), rightList]),
    ]),
    el("div", { class: "modal-foot" }, [footClose]),
  ]);
  overlay.appendChild(box);
  document.body.appendChild(overlay);
}

function fieldsCheckControl(area, spec, value) {
  const selected = Array.isArray(value) ? value.slice() : [];
  const button = el("button", { type: "button", class: "fields-check-btn" });
  function refreshLabel() {
    button.textContent = selected.length ? selected.length + "件選択" : "（選ぶ）";
  }
  refreshLabel();
  button.addEventListener("click", () => {
    area.params[spec.name] = selected;
    openFieldOrderModal(area, spec, selected, refreshLabel);
  });
  return button;
}

function renderTables(state) {
  const renameBody = document.getElementById("rename-body");
  renameBody.innerHTML = "";
  state.rename.forEach(row => {
    const folderCell = editableCell(row.folder);
    folderCell.addEventListener("focus", () => openChoicePopup(folderCell, folderCandidates()));
    renameBody.appendChild(el("tr", {}, [
      readonlyCell(row.original),
      editableCell(row.display),
      folderCell,
      readonlyCell(row.datatype),
      readonlyCell(row.role),
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
  document.getElementById("calc-body").appendChild(calcRow("", "", NO_FOLDER, "", ""));
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
    if (isNoFolder(row.folder)) return;
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
    const hasFolder = !isNoFolder(folder);
    row.cells[1].classList.toggle("invalid", hasFolder && !display);
    row.cells[2].classList.toggle("invalid", hasFolder && seen.has(original));
    if (hasFolder) seen.add(original);
  });
  const errors = validateState(captureCurrent());
  document.getElementById("rename-errors").textContent = errors.join("\n");
  return errors.length === 0;
}
document.getElementById("rename-table").addEventListener("griddirty", validateRename);

/* 計算フィールド: フォルダは自由入力のまま検証しない。データ型・役割は
   テキスト入力を許すが、候補にない文字列は赤くしてエラー欄に出す。 */
function validateCalc() {
  const errors = [];
  Array.from(document.getElementById("calc-body").rows).forEach(row => {
    const name = row.cells[0].textContent.trim();
    const formula = row.cells[1].textContent.trim();
    if (!name && !formula) return;
    const datatype = row.cells[3].textContent.trim();
    const role = row.cells[4].textContent.trim();
    const datatypeInvalid = !!datatype && !CALC_DATATYPE_CHOICES.includes(datatype);
    const roleInvalid = !!role && !CALC_ROLE_CHOICES.includes(role);
    row.cells[3].classList.toggle("invalid", datatypeInvalid);
    row.cells[4].classList.toggle("invalid", roleInvalid);
    if (datatypeInvalid) errors.push((name || formula) + ": データ型が不正です (" + datatype + ")");
    if (roleInvalid) errors.push((name || formula) + ": 役割が不正です (" + role + ")");
  });
  document.getElementById("calc-errors").textContent = errors.join("\n");
  return errors;
}
document.getElementById("calc-table").addEventListener("griddirty", () => {
  captureCurrent();
  validateCalc();
});

/* ダウンロード前は表示中のデータソースだけでなく全データソース分を検証する
   （EDITS を見る。rename の validateState() と対になる） */
function validateCalcState(state) {
  const errors = [];
  state.calcs.forEach(cells => {
    const name = cells[0], formula = cells[1];
    if (!name && !formula) return;
    const datatype = cells[3], role = cells[4];
    if (datatype && !CALC_DATATYPE_CHOICES.includes(datatype)) {
      errors.push((name || formula) + ": データ型が不正です (" + datatype + ")");
    }
    if (role && !CALC_ROLE_CHOICES.includes(role)) {
      errors.push((name || formula) + ": 役割が不正です (" + role + ")");
    }
  });
  return errors;
}

/* ---- デザインルールタブ ---- */
function bindColor(id) {
  const text = document.getElementById(id);
  const picker = document.getElementById(id + "-pick");
  picker.value = text.value;
  picker.addEventListener("input", () => { text.value = picker.value; });
  text.addEventListener("input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(text.value.trim())) picker.value = text.value.trim();
    if (typeof renderRows === "function") renderRows();
    if (typeof renderKpiTree === "function") renderKpiTree();
  });
  picker.addEventListener("input", () => {
    if (typeof renderRows === "function") renderRows();
    if (typeof renderKpiTree === "function") renderKpiTree();
  });
}
["d-main", "d-sub1", "d-sub2", "d-text", "d-heat-min", "d-heat-mid", "d-heat-max"]
  .forEach(bindColor);

function designYaml() {
  const value = id => document.getElementById(id).value.trim();
  let out = "design:\n";
  out += "  font: " + yamlKey(value("d-font")) + "\n";
  out += "  main_color: " + yamlKey(value("d-main")) + "\n";
  out += "  sub_color_1: " + yamlKey(value("d-sub1")) + "\n";
  out += "  sub_color_2: " + yamlKey(value("d-sub2")) + "\n";
  out += "  text_color: " + yamlKey(value("d-text")) + "\n";
  out += "  min_color: " + yamlKey(value("d-heat-min")) + "\n";
  out += "  mid_color: " + yamlKey(value("d-heat-mid")) + "\n";
  out += "  max_color: " + yamlKey(value("d-heat-max")) + "\n";
  out += "  filter_apply_button: "
       + (document.getElementById("d-apply").checked ? "true" : "false") + "\n";
  out += "  spacing: "
       + yamlKey(document.querySelector("input[name=d-space]:checked").value) + "\n";
  return out;
}

/* ---- YAML 出力（タブごとに、そのタブで使う節だけを出す、2026-09-14） ----
   以前は全タブを 1 ファイルに束ねていたが、ダッシュボードタブを使わなくても
   dashboard: 節（段 0）が出て、適用すると空のダッシュボードが増えていた。
   データソースの節は 2 回適用しても上書きになるので、各タブのファイルに入れてよい。 */
function yamlHeader(sections) {
  let out = "# twbpatch 設定ファイル（" + sections.join(" / ") + "）\n";
  out += "# 受け手: wb.apply_config() がこのファイルを読んで .twb へ反映する。\n";
  out += "# 集計方法は画面で指定しない。役割とデータ型から自動で決める。\n\n";
  return out;
}

function datasourcesYaml() {
  captureCurrent();
  let out = "datasources:\n";
  let wrote = false;
  DATA.datasources.forEach((ds, index) => {
    const state = EDITS[index];
    if (!state) return;
    const folders = new Map();
    const renames = [];
    state.rename.forEach(row => {
      if (!row.display) return;
      if (isNoFolder(row.folder)) {
        renames.push([row.original, row.display]);
        return;
      }
      if (!folders.has(row.folder)) folders.set(row.folder, []);
      folders.get(row.folder).push([row.original, row.display]);
    });
    const calcs = state.calcs.filter(cells => cells[0] && cells[1]);
    if (!folders.size && !renames.length && !calcs.length) return;
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
    if (renames.length) {
      out += "    renames:\n";
      renames.forEach(pair => {
        out += "      " + yamlKey(pair[0]) + ": " + yamlKey(pair[1]) + "\n";
      });
    }
    if (calcs.length) {
      out += "    calculations:\n";
      calcs.forEach(cells => {
        out += "      - name: " + yamlKey(cells[0]) + "\n";
        out += "        formula: " + yamlKey(cells[1]) + "\n";
        if (cells[3]) out += "        datatype: " + yamlKey(cells[3]) + "\n";
        if (cells[4]) out += "        role: " + yamlKey(cells[4]) + "\n";
        if (cells[2] && !isNoFolder(cells[2])) {
          out += "        folder: " + yamlKey(cells[2]) + "\n";
        }
      });
    }
  });
  if (!wrote) out += "  {}\n";
  return out;
}

function datasourceErrors() {
  captureCurrent();
  const errors = [];
  DATA.datasources.forEach((ds, index) => {
    if (!EDITS[index]) return;
    validateState(EDITS[index]).forEach(message => {
      errors.push((ds.name || ds.id) + ": " + message);
    });
    validateCalcState(EDITS[index]).forEach(message => {
      errors.push((ds.name || ds.id) + ": " + message);
    });
  });
  return errors;
}

function downloadYaml(fileName, errors, build) {
  if (errors.length) {
    alert("エラーを直してから出力してください。\n\n" + errors.join("\n"));
    return;
  }
  download(fileName, build());
}

document.getElementById("yaml-download-datasources").addEventListener("click", () => {
  downloadYaml("twbpatch_datasources.yaml", datasourceErrors(),
               () => yamlHeader(["datasources"]) + datasourcesYaml());
});

/* ---- ダッシュボードタブ（新規作成） ---- */
const DRAW_SPECS = JSON.parse(document.getElementById("draw-specs").textContent);
const CHART_TYPES = Object.keys(DRAW_SPECS);

const DASH = { rows: [] };
let rowSeq = 0;

/* draw_crosstab の min/mid/max_color は3つ揃えるかゼロかしか許されない
   （draw.py が ValueError にする）。毎回3つ手入力させるのは非現実的なので、
   グラフ種類を選んだ時点でデザインルールの既定3色を参照させておく。
   個別の色を使いたい場合はグラフ側でいつでも「個別に指定」へ切り替えられる。 */
function defaultParamsFor(chart) {
  if (chart === "draw_crosstab") {
    return { min_color: "@min_color", mid_color: "@mid_color", max_color: "@max_color" };
  }
  return {};
}

function newArea() {
  const chart = CHART_TYPES[0] || "";
  return {
    id: ++rowSeq,
    kind: "worksheet",
    width: "600",
    sheet: "",
    chart: chart,
    datasource: 0,
    params: defaultParamsFor(chart),
    filterField: "",
    action: { enabled: false, type: "filter", target: "", field: "" },
  };
}
function newRow() {
  return { id: ++rowSeq, name: "", height: "300", collapsed: false, areas: [newArea()] };
}
function cloneArea(area) {
  return Object.assign({}, area, {
    id: ++rowSeq,
    params: Object.assign({}, area.params),
    action: Object.assign({}, area.action),
  });
}

/* シート名の自動生成: グラフ種類ごとに使うフィールドを決め、{短縮ラベル}|{フィールド} で組む。
   複数選択の項目は limit で使う件数を絞る。 */
const SHEET_NAME_PATTERNS = {
  draw_card: { label: "スコア", fields: [{ name: "main_metric" }] },
  draw_bar: { label: "棒", fields: [{ name: "item" }, { name: "metric" }] },
  draw_quadrant: { label: "象限", fields: [{ name: "x_metric" }, { name: "y_metric" }] },
  draw_crosstab: { label: "クロス", fields: [{ name: "x_item" }, { name: "y_item" }] },
  draw_sheet: { label: "帳票", fields: [{ name: "items", limit: 2 }] },
};
function fieldPartsOf(area, spec) {
  const value = area.params[spec.name];
  if (Array.isArray(value)) {
    return (spec.limit ? value.slice(0, spec.limit) : value).filter(Boolean);
  }
  return value ? [value] : [];
}
function generateSheetName(area) {
  const pattern = SHEET_NAME_PATTERNS[area.chart];
  if (!pattern) return "";
  const parts = pattern.fields
    .map(spec => fieldPartsOf(area, spec))
    .filter(values => values.length)
    .map(values => values.join(","));
  if (!parts.length) return "";
  return uniqueName(pattern.label + "|" + parts.join("×"), usedSheetNames(area));
}

/* 名前が重複したら「 (2)」「 (3)」…を付ける（2026-09-14）。受け手（apply_config）では付けない。
   受け手で付けると、同じ YAML を誤って 2 回適用しても止まらずに黙って増え、
   アクションの対象シート（名前で指定）もずれるため。 */
function uniqueName(base, used) {
  if (!used.has(base)) return base;
  // 「売上 (2)」を複製したら「売上 (2) (2)」ではなく「売上 (3)」にする
  const stem = base.replace(/ \(\d+\)$/, "");
  let n = 2;
  while (used.has(stem + " (" + n + ")")) n += 1;
  return stem + " (" + n + ")";
}

/* シート名の重複を見る相手: ダッシュボードタブ・KPI ツリータブ・.twb に既にあるシート。
   `except` は名前を付けようとしている項目自身。KPI ツリーのシート名は
   html_kpi_tree.py の kpiTreeSheetNames() から取る。 */
function dashboardSheetNames(except) {
  const names = [];
  DASH.rows.forEach(row => row.areas.forEach(area => {
    if (area !== except && area.kind === "worksheet" && area.sheet) names.push(area.sheet);
  }));
  return names;
}
function usedSheetNames(except) {
  const used = new Set((DATA.worksheets || []).map(ws => ws.name));
  dashboardSheetNames(except).forEach(name => used.add(name));
  kpiTreeSheetNames(except).forEach(name => used.add(name));
  return used;
}

/* 手で入力したシート名の重複を、ダウンロード前の検証で出す。
   `names` はそのタブのシート名（[名前, 表示用の場所] の組）、`others` は別タブのシート名。 */
function duplicateSheetErrors(names, others, otherLabel) {
  const errors = [];
  const existing = new Set((DATA.worksheets || []).map(ws => ws.name));
  const other = new Set(others);
  const seen = new Set();
  names.forEach(([name, label]) => {
    if (!name) return;
    if (seen.has(name)) errors.push(label + ": シート名「" + name + "」がこのタブの中で重複");
    else if (existing.has(name)) errors.push(label + ": シート名「" + name + "」は .twb に既にある");
    else if (other.has(name)) errors.push(label + ": シート名「" + name + "」が" + otherLabel + "と重複");
    seen.add(name);
  });
  return errors;
}

/* ダッシュボード名の重複。別タブの名前は、そのタブを使っているときだけ渡す */
function duplicateDashboardErrors(name, label, otherName, otherLabel) {
  if (!name) return [label + ": ダッシュボード名が空"];
  if ((DATA.dashboards || []).some(db => db.name === name)) {
    return [label + ": ダッシュボード名「" + name + "」は .twb に既にある"];
  }
  if (otherName && otherName === name) {
    return [label + ": ダッシュボード名「" + name + "」が" + otherLabel + "と重複"];
  }
  return [];
}

function dsOptions(selected) {
  return DATA.datasources.map((ds, i) =>
    el("option", Object.assign({ value: String(i), text: ds.name || ds.id },
                               Number(selected) === i ? { selected: "selected" } : {}))
  );
}
/* フィールドをフォルダごとにまとめる（フォルダ未指定は最後）。
   単一選択プルダウンの optgroup と、複数選択チェックリストの両方から使う。 */
function groupedFields(dsIndex, role) {
  const ds = DATA.datasources[Number(dsIndex) || 0];
  const groups = new Map();
  ((ds && ds.fields) || []).forEach(field => {
    if (field.hidden) return;
    if (role && field.role !== role) return;
    const folderName = folderNameOf(ds, field) || NO_FOLDER;
    if (!groups.has(folderName)) groups.set(folderName, []);
    groups.get(folderName).push(field);
  });
  const folderNames = Array.from(groups.keys()).sort((a, b) => {
    if (a === NO_FOLDER) return 1;
    if (b === NO_FOLDER) return -1;
    return a.localeCompare(b, "ja");
  });
  return folderNames.map(folderName => ({ folderName, fields: groups.get(folderName) }));
}

/* フィールドの候補はフォルダごとに optgroup でまとめる（プルダウンは1つのまま、
   フォルダを見てからフィールドを選ぶ体験にする。フォルダ未指定は最後に出す） */
function fieldOptions(dsIndex, selected, role) {
  const options = [el("option", { value: "", text: "（選ぶ）" })];
  groupedFields(dsIndex, role).forEach(group => {
    options.push(el("optgroup", { label: group.folderName },
      group.fields.map(field => {
        const name = field.name || "";
        return el("option", Object.assign({ value: name, text: name },
                                          name === selected ? { selected: "selected" } : {}));
      })
    ));
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
  { key: "min_color", label: "ヒートマップ：最小値の色", input: "d-heat-min" },
  { key: "mid_color", label: "ヒートマップ：中間の色", input: "d-heat-mid" },
  { key: "max_color", label: "ヒートマップ：最大値の色", input: "d-heat-max" },
];
function designValue(key) {
  const token = DESIGN_TOKENS.find(item => item.key === key);
  return token ? document.getElementById(token.input).value.trim() : "";
}

/* 色は「デザインルールを参照」と「個別に指定」を選べる。参照は @キー で保存する。
   保存先は呼び出し側が onChange で決める（単色は1か所、colors は配列の1要素）。 */
function colorControl(value, onChange) {
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
      onChange("@" + source.value);
    } else {
      picker.disabled = false;
      onChange(picker.value);
    }
  }
  source.addEventListener("change", apply);
  picker.addEventListener("input", () => {
    if (!source.value) onChange(picker.value);
  });
  picker.disabled = !!token;
  return el("span", { class: "color2" }, [source, picker]);
}

//: draw_quadrant の colors 既定値。4色そろわない場合の初期値にも使う。
const DEFAULT_QUADRANT_COLORS = ["#4400FF", "#FF007F", "#00C888", "#CCD500"];

/* draw_quadrant の colors は配列インデックス順に象限が固定されている
   （draw.py の quadrant_formula: x/y とも中央値以上なら "1"、以降時計回りと
   逆に "2"→左上, "3"→左下, "4"→右下）。ラベルなしでは4色のうちどれが
   どの象限かわからないため、ここで対応を明示する。 */
const QUADRANT_COLOR_LABELS = ["右上", "左上", "左下", "右下"];

/* colors（4色必要な配列パラメータ）は color を4つ並べる。配列の各要素を
   個別に「デザインルール参照」か「個別指定」か選べる点は単色と同じ。 */
function colorsControl(area, spec, value) {
  const current = Array.isArray(value) && value.length === 4
    ? value.slice() : DEFAULT_QUADRANT_COLORS.slice();
  const pickers = current.map((c, index) => {
    const picker = colorControl(c, v => {
      const next = Array.isArray(area.params[spec.name]) && area.params[spec.name].length === 4
        ? area.params[spec.name].slice() : DEFAULT_QUADRANT_COLORS.slice();
      next[index] = v;
      area.params[spec.name] = next;
    });
    return el("span", { class: "colors4-item" }, [
      el("span", { class: "colors4-label", text: QUADRANT_COLOR_LABELS[index] }),
      picker,
    ]);
  });
  return el("span", { class: "colors4" }, pickers);
}

function paramControl(area, spec) {
  const value = area.params[spec.name] === undefined ? "" : area.params[spec.name];
  let control;
  if (spec.kind === "bool") {
    control = el("input", Object.assign({ type: "checkbox" }, value ? { checked: "checked" } : {}));
    control.addEventListener("change", () => { area.params[spec.name] = control.checked; });
  } else if (spec.kind === "fields") {
    control = fieldsCheckControl(area, spec, value);
  } else if (spec.kind === "field") {
    control = el("select", {}, fieldOptions(area.datasource, value, spec.role));
    control.addEventListener("change", () => { area.params[spec.name] = control.value; });
  } else if (spec.kind === "color") {
    control = colorControl(value, v => { area.params[spec.name] = v; });
  } else if (spec.kind === "colors") {
    control = colorsControl(area, spec, value);
  } else if (spec.kind === "select") {
    control = el("select", {}, [el("option", { value: "", text: "（既定値）" })].concat(
      spec.choices.map(choice =>
        el("option", Object.assign({ value: choice[0], text: choice[1] },
                                   choice[0] === value ? { selected: "selected" } : {})))));
    control.addEventListener("change", () => { area.params[spec.name] = control.value; });
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
    /* 値は build_report() の区分値に合わせる。表示は「グラフ」のまま */
    el("option", Object.assign({ value: "worksheet", text: "グラフ" },
                               area.kind === "worksheet" ? { selected: "selected" } : {})),
    el("option", Object.assign({ value: "filter", text: "フィルター" },
                               area.kind === "filter" ? { selected: "selected" } : {})),
  ]);
  kind.addEventListener("change", () => { area.kind = kind.value; renderRows(); });

  const width = el("input", { type: "number", step: "10", min: "0", value: area.width });
  width.addEventListener("input", () => { area.width = width.value.trim(); });

  const duplicate = el("button", { class: "mini", text: "⧉", title: "エリアを複製" });
  duplicate.addEventListener("click", () => {
    const copy = cloneArea(area);
    row.areas.splice(row.areas.indexOf(area) + 1, 0, copy);
    if (copy.sheet) copy.sheet = uniqueName(copy.sheet, usedSheetNames(copy));
    renderRows();
  });

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
    el("span", { class: "spacer" }), duplicate, remove,
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
    const genName = el("button", { class: "mini", text: "✎",
      title: "グラフ種類と選んだ項目からシート名を生成" });
    genName.addEventListener("click", () => {
      const generated = generateSheetName(area);
      if (generated) { area.sheet = generated; sheet.value = generated; }
    });
    const sheetWrap = el("span", { class: "name-gen" }, [sheet, genName]);

    const chart = el("select", {}, CHART_TYPES.map(type =>
      el("option", Object.assign({ value: type, text: DRAW_SPECS[type].label, title: type },
                                 type === area.chart ? { selected: "selected" } : {}))));
    chart.addEventListener("change", () => {
      area.chart = chart.value;
      area.params = defaultParamsFor(chart.value);
      renderRows();
    });

    const head = el("div", { class: "fields" }, [
      labeled("シート名", sheetWrap),
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
    /* 種類はフィルターと URL の 2 つ。ハイライトは受け手が無いので出さない */
    const ACTION_LABELS = { filter: "フィルター", url: "URL を開く" };
    if (!ACTION_LABELS[area.action.type]) area.action.type = "filter";
    const type = el("select", {}, Object.keys(ACTION_LABELS).map(value =>
      el("option", Object.assign({ value: value, text: ACTION_LABELS[value] },
                                 value === area.action.type ? { selected: "selected" } : {}))));
    type.addEventListener("change", () => {
      area.action.type = type.value;
      renderRows();
    });
    actionBox.appendChild(labeled("種類", type));

    if (area.action.type === "filter") {
      const target = el("input", { type: "text", value: area.action.target,
                                   placeholder: "対象シート名" });
      target.addEventListener("input", () => { area.action.target = target.value.trim(); });
      actionBox.appendChild(labeled("対象シート", target));

      /* フィルターアクションは絞り込むフィールドが要る。「すべてのフィールド」は扱わない */
      const field = el("select", {},
                       fieldOptions(area.datasource, area.action.field, "dimension"));
      field.addEventListener("change", () => { area.action.field = field.value; });
      actionBox.appendChild(labeled("絞り込むフィールド", field));
    } else {
      const url = el("input", { type: "text", value: area.action.target,
                                placeholder: "https://" });
      url.addEventListener("input", () => { area.action.target = url.value.trim(); });
      actionBox.appendChild(labeled("URL", url));
    }
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

/* ダッシュボードタブの必須入力チェック。データソースタブと違い、これまで
   何も検証しないまま YAML を出せてしまい、必須パラメータが空のエリアが
   そのまま apply_config() の TypeError になっていた（2026-09-08 バグ修正）。 */
function validateDashboard() {
  const errors = [];
  if (!DASH.rows.length) return ["ダッシュボード: 段がありません"];
  errors.push.apply(errors, duplicateDashboardErrors(
    document.getElementById("db-name").value.trim(), "ダッシュボード",
    kpiTreeDashboardName(), "KPI ツリータブ"));
  const sheets = [];
  DASH.rows.forEach((row, rowIndex) => row.areas.forEach((area, areaIndex) => {
    if (area.kind !== "worksheet") return;
    sheets.push([area.sheet, (row.name || ("段" + (rowIndex + 1))) + " / エリア" + (areaIndex + 1)]);
  }));
  errors.push.apply(errors, duplicateSheetErrors(sheets, kpiTreeSheetNames(null), "KPI ツリータブ"));
  DASH.rows.forEach((row, rowIndex) => {
    const rowLabel = row.name || ("段" + (rowIndex + 1));
    row.areas.forEach((area, areaIndex) => {
      const label = rowLabel + " / エリア" + (areaIndex + 1);
      if (area.kind === "filter") {
        if (!area.filterField) errors.push(label + ": フィールドが未選択");
        return;
      }
      if (!area.sheet) errors.push(label + ": シート名が空");
      const specs = (DRAW_SPECS[area.chart] || {}).params || [];
      specs.filter(spec => spec.required).forEach(spec => {
        const value = area.params[spec.name];
        const empty = spec.kind === "fields" ? !(value && value.length) : !value;
        if (empty) errors.push(label + ": " + (spec.label || spec.name) + " が未選択");
      });
      // draw_crosstab の min/mid/max_color は3つ揃えるか、全く指定しないかの
      // どちらか（draw.py 側のバリデーションと同じ制約）。2026-09-12 追加
      if (area.chart === "draw_crosstab") {
        const trio = ["min_color", "mid_color", "max_color"];
        const filled = trio.filter(name => area.params[name]).length;
        if (filled > 0 && filled < trio.length) {
          errors.push(label + ": 最小値・中間・最大値の色は3つ揃えるか、全く指定しないでください");
        }
      }
    });
  });
  return errors;
}

/* グラフの引数を `params:` として書く。`pad` は `params:` の行の字下げ。
   KPI ツリーのノードも同じ形で書く（html_kpi_tree.py）。 */
function paramsYaml(chart, source, pad) {
  // value_color と title_background_color は画面に出さず main_color を
  // そのまま複製する（draw_card 固有、2026-09-12, 2026-09-13）
  const params = Object.assign({}, source);
  if (chart === "draw_card" && params.main_color) {
    params.value_color = params.main_color;
    params.title_background_color = params.main_color;
  }
  const names = Object.keys(params).filter(key => {
    const v = params[key];
    return v !== "" && v !== undefined && !(Array.isArray(v) && !v.length);
  });
  if (!names.length) return "";
  let out = pad + "params:\n";
  names.forEach(key => {
    const v = params[key];
    if (Array.isArray(v)) {
      out += pad + "  " + key + ":\n";
      v.forEach(item => { out += pad + "    - " + yamlKey(item) + "\n"; });
    } else if (typeof v === "boolean") {
      out += pad + "  " + key + ": " + (v ? "true" : "false") + "\n";
    } else {
      out += pad + "  " + key + ": " + yamlKey(v) + "\n";
    }
  });
  return out;
}

document.getElementById("yaml-download-dashboard").addEventListener("click", () => {
  const errors = datasourceErrors();
  errors.push.apply(errors, validateDashboard());
  downloadYaml("twbpatch_dashboard.yaml", errors, () =>
    yamlHeader(["design", "datasources", "dashboard"])
    + designYaml() + "\n" + datasourcesYaml() + "\n" + dashboardYaml());
});

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
        out += paramsYaml(area.chart, area.params, "          ");
      }
      if (area.action.enabled) {
        out += "          action:\n";
        out += "            type: " + yamlKey(area.action.type) + "\n";
        if (area.action.type === "url") {
          out += "            url: " + yamlKey(area.action.target) + "\n";
        } else {
          out += "            target: " + yamlKey(area.action.target) + "\n";
          out += "            field: " + yamlKey(area.action.field) + "\n";
        }
      }
    });
  });
  return out;
}

refreshDatasource();
enableGrid(document.getElementById("rename-table"));
enableGrid(document.getElementById("calc-table"), { newRow: () => calcRow("", "", NO_FOLDER, "", "") });
enableColumnResize(document.getElementById("rename-table"));
enableColumnResize(document.getElementById("calc-table"));
"""

_BODY = """
<nav>
  <button data-tab="tab-design">全体（デザインルール）</button>
  <button data-tab="tab-datasource" class="active">データソース</button>
  <button data-tab="tab-dashboard">ダッシュボード</button>
  __KPI_TREE_NAV__
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
      <label for="d-heat-min">ヒートマップ：最小値の色</label>
      <span class="color">
        <input type="color" id="d-heat-min-pick"><input type="text" id="d-heat-min" value="#2166ac">
      </span>
      <label for="d-heat-mid">ヒートマップ：中間の色</label>
      <span class="color">
        <input type="color" id="d-heat-mid-pick"><input type="text" id="d-heat-mid" value="#f7f7f7">
      </span>
      <label for="d-heat-max">ヒートマップ：最大値の色</label>
      <span class="color">
        <input type="color" id="d-heat-max-pick"><input type="text" id="d-heat-max" value="#b2182b">
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
  <div class="tab-actions">
    <span class="tag">出力: データソース</span>
    <button class="dl" id="yaml-download-datasources">設定 YAML をダウンロード</button>
  </div>
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
        <colgroup>
          <col style="width: 20%"><col style="width: 25%"><col style="width: 22%">
          <col style="width: 16%"><col style="width: 17%">
        </colgroup>
        <thead><tr>
          <th>元カラム</th><th>リネーム後名称</th><th>フォルダ</th>
          <th>データ型</th><th>役割</th>
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
      行が足りないときは貼り付けで自動的に増える。名前と式が両方入った行だけ出力する。
      フォルダ・データ型・役割はフォーカスすると候補をクリックで選べる（自由入力も可）。
      データ型・役割は候補にない文字列を入れると赤くなる。</p>
    <div class="scroll">
      <table id="calc-table">
        <colgroup>
          <col style="width: 16%"><col style="width: 40%"><col style="width: 18%">
          <col style="width: 13%"><col style="width: 13%">
        </colgroup>
        <thead><tr>
          <th>名前</th><th>式</th><th>フォルダ</th><th>データ型</th><th>役割</th>
        </tr></thead>
        <tbody id="calc-body"></tbody>
      </table>
    </div>
    <p class="errors" id="calc-errors"></p>
    <p>
      <button class="act" id="calc-add">行を追加</button>
      <button class="act" id="calc-delete">選択行を削除</button>
    </p>
    </div>
  </div>
</section>

<section id="tab-dashboard">
  <div class="tab-actions">
    <span class="tag">出力: デザインルール ＋ データソース ＋ ダッシュボード</span>
    <button class="dl" id="yaml-download-dashboard">設定 YAML をダウンロード</button>
  </div>
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

__KPI_TREE_SECTION__

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
#: `value_color` / `title_background_color` / `vertical_alignment` は draw_card 固有。
#: 前2つは画面では main_color をそのまま複製する（2026-09-12, 2026-09-13）。
#: 文字色・タイトル背景色を指標の色と別々に選ばせても、個別に変える需要が薄く
#: 混乱のもとだった。`vertical_alignment` は「縦は常に中央でよい」との指摘
#: （2026-09-13）を受け、画面からは選ばせず API 既定の "center" のまま渡す。
_DRAW_SKIP = {"self", "datasource", "name", "value_color", "title_background_color", "vertical_alignment"}


def _is_skipped(name: str) -> bool:
    return name in _DRAW_SKIP or name == "aggregation" or name.endswith("_aggregation")

#: グラフ種類の表示名。仕様 §6.14 の説明に合わせる。
#: **この並び順がそのまま画面の選択肢の順になる**（2026-09-21。よく使う順）。
_CHART_LABELS = {
    "draw_card": "KPIカード",
    "draw_bar": "棒グラフ",
    "draw_sheet": "帳票",
    "draw_crosstab": "クロス集計（ヒートマップ）",
    "draw_quadrant": "散布図（四象限）",
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

#: 値が固定の選択肢しか受け付けない引数。(値, 表示ラベル) の一覧。
#: API 側のバリデーション（`_shelves()` など）と一致させる。
_PARAM_CHOICES: dict[str, list[tuple[str, str]]] = {
    "item_shelf": [("rows", "横棒（行）"), ("columns", "縦棒（列）")],
    "mark_type": [("bar", "棒"), ("text", "テキスト")],
}


def _param_kind(name: str, annotation: str) -> str:
    if "list[FieldInput]" in annotation:
        return "fields"
    if "FieldInput" in annotation:
        return "field"
    if name in _PARAM_CHOICES:
        return "select"
    if name == "colors":
        # draw_quadrant の colors は4色必要。"color" in name の判定に食われて
        # 単一色ピッカーになっていたバグ（2026-09-12 修正）
        return "colors"
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
    # 画面の選択肢は _CHART_LABELS の並び順。表示名の無いものは後ろに名前順で足す。
    names = [name for name in _CHART_LABELS if hasattr(TwbWorkbook, name)]
    names += [
        name
        for name in sorted(dir(TwbWorkbook))
        if name.startswith("draw_") and name not in _CHART_LABELS
    ]
    for method_name in names:
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
                    "choices": _PARAM_CHOICES.get(parameter.name),
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
    from .html_kpi_tree import KPI_TREE_NAV, KPI_TREE_SCRIPT, KPI_TREE_SECTION, KPI_TREE_STYLE

    body = (
        _BODY.replace("__FONT_OPTIONS__", _font_options(font))
        .replace("__KPI_TREE_NAV__", KPI_TREE_NAV)
        .replace("__KPI_TREE_SECTION__", KPI_TREE_SECTION)
        .replace("__TITLE__", _escape(title))
        .replace("__DS_COUNT__", str(len(data.get("datasources", []))))
        .replace("__WS_COUNT__", str(len(data.get("worksheets", []))))
        .replace("__DB_COUNT__", str(len(data.get("dashboards", []))))
    )
    return (
        _TEMPLATE.replace("__STYLE__", _STYLE + KPI_TREE_STYLE)
        .replace("__BODY__", body)
        .replace("__SCRIPT__", _SCRIPT + KPI_TREE_SCRIPT)
        .replace("__DATA__", _embed_json(data))
        .replace("__DRAW_SPECS__", _embed_json(_draw_specs()))
        .replace("__TITLE__", _escape(title))
    )
