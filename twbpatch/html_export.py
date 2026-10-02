from __future__ import annotations

import json
import re
from pathlib import Path
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
/* AI 用プロンプトのダイアログ（2026-09-21） */
dialog#prompt-dialog { width: min(900px, 90vw); border: 1px solid #c3cad6; border-radius: 6px; }
dialog#prompt-dialog h3 { margin: 0 0 8px; font-size: 14px; }
#prompt-text { width: 100%; height: 50vh; font: 12px/1.5 Consolas, monospace;
               padding: 8px; border: 1px solid #c3cad6; border-radius: 4px; }
#prompt-rule-options { margin: 0 0 10px; }
#prompt-rule-checkboxes, #calc-prompt-rule-checkboxes {
  display: flex; flex-wrap: wrap; gap: 8px; margin-top: 5px; }
#prompt-rule-checkboxes[hidden], #calc-prompt-rule-checkboxes[hidden] { display: none; }
#prompt-rule-checkboxes label, #calc-prompt-rule-checkboxes label {
  display: inline-flex; align-items: center; gap: 6px; max-width: 100%;
  box-sizing: border-box; padding: 6px 10px; border: 1px solid #c3cad6;
  border-radius: 8px; background: #fff; cursor: pointer; overflow-wrap: anywhere; }
#prompt-rule-checkboxes label:has(input:checked),
#calc-prompt-rule-checkboxes label:has(input:checked) {
  border-color: #4a7dff; background: #eef4ff; }
#prompt-rule-checkboxes label:focus-within,
#calc-prompt-rule-checkboxes label:focus-within { outline: 2px solid #4a7dff; outline-offset: 2px; }
/* 行のドラッグ＆ドロップ（2026-09-21） */
td.grip-cell { text-align: center; padding: 0; cursor: grab; }
tr.picked > td { background: #e8f0ff; }
td.grip-cell .grip { display: block; padding: 3px 0; }
tr.dragging-src { opacity: .4; }
tr.drop-row > td { border-top: 2px solid #4a7dff; }
/* 検索つきプルダウン（2026-09-21）。押すと下に検索欄 → 候補一覧が開く */
.combo-wrap { position: relative; display: inline-block; }
.combo-wrap select { display: none; }
.combo-box { font: inherit; text-align: left; width: 100%; min-width: 140px;
             padding: 4px 20px 4px 6px; border: 1px solid #c3cad6; border-radius: 4px;
             background: #fff; cursor: pointer; }
.combo-box::after { content: "▾"; position: absolute; right: 6px; color: #6b7280; }
/* 開いている間は <body> 直下へ移し、画面に対して固定で置く。位置は開くときに
   計算する（2026-09-21）。重なり順はモーダル（100）の下、それ以外の上 */
.combo-menu { position: fixed; z-index: 90; padding: 4px; background: #fff;
              border: 1px solid #c3cad6; border-radius: 4px;
              box-shadow: 0 4px 12px rgba(0, 0, 0, .16); }
.combo-group { padding: 4px 6px 2px; font-size: 10px; font-weight: 600; color: #6b7280;
               border-top: 1px solid #edf0f5; }
.combo-list > .combo-group:first-child { border-top: 0; }
.combo-group ~ .combo-item { padding-left: 14px; }
input.combo { box-sizing: border-box; width: 100%; font: inherit; font-size: 11px;
              padding: 3px 5px; border: 1px solid #c3cad6; border-radius: 3px; }
/* overscroll-behavior: 一覧の端まで送ったとき、ページ側へスクロールを送らない
   （送るとページが動いて一覧が閉じてしまう。2026-09-21） */
.combo-list { max-height: 220px; overflow-y: auto; overscroll-behavior: contain;
              margin-top: 4px; }
.combo-item { padding: 3px 6px; white-space: nowrap; cursor: pointer; }
.combo-item:hover { background: #eef3ff; }
.combo-item.on { background: #dbe6ff; }
.combo-empty { padding: 3px 6px; color: #888; }
/* 空・重複など、そのままでは適用できない入力（2026-09-21） */
input.bad { background: #ffe0e0; border-color: #e09090; }
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
label.f textarea { font-size: 12px; padding: 3px 6px; width: 260px; font-family: inherit; }
.color2 { display: flex; gap: 4px; align-items: center; }
.info-control { border-top: 1px dashed #d8dde5; padding-top: 8px; margin-bottom: 6px; }
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
/* 帳票の表示方法（2026-09-22）。選択済みの行の「×」の手前に置く小さなボタン。
   数値のときは控えめ、棒・色付けを選んでいるときは色を付けて分かるようにする */
.modal-item .display-pick { min-width: 44px; color: #6b7688; }
.modal-item .display-pick.on { border-color: #4a7dff; color: #2f5fd0; font-weight: bold; }
/* 表示方法の左に出す色。棒は 1 つ、色付けは 2 つ並ぶ */
.modal-item .display-colors { display: flex; gap: 3px; }
.modal-item .display-color { width: 22px; height: 20px; padding: 0; border: 1px solid #c8cfda;
                             border-radius: 3px; background: none; cursor: pointer; }
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

/* ---- 検索つきプルダウン（2026-09-21） ----
   はじめは <select> を隠して <input list> + <datalist> の一体型にしたが、
   選択中の値が入力欄に残るため Chrome の datalist がその値を含む候補しか出さず、
   一覧を見られなくなった（フィールドは候補 25 件でも 1 件しか出ない）。
   素の <select> の上に検索欄を常に置く形も、使わない欄まで場所を取って邪魔だった。
   そこで、閉じているときは選択中の値だけを出し、押すと下に「検索欄 → 候補一覧」が開く
   作りにする。値は隠した <select> が持つので、呼び出し側は今までどおり
   select.value と change イベントで扱える。
   候補が COMBO_SEARCH_MIN 以下のもの（グラフ/フィルターの区分、グラフ種類など）は
   探す必要が無いので、素の <select> のまま返す。 */
const COMBO_SEARCH_MIN = 6;
/* 開いている間は <body> の直下へ預ける（2026-09-21）。エリアの箱は横スクロール用に
   overflow-x: auto で、これは縦もスクロールする設定になるため、中に置いたままだと
   候補一覧が枠で切れ、段に縦スクロールバーまで生える。閉じたら元の場所へ戻す。 */
function closeCombo(menu) {
  menu.hidden = true;
  if (menu.comboHome && menu.parentNode !== menu.comboHome) menu.comboHome.appendChild(menu);
}
function closeCombos() {
  document.querySelectorAll(".combo-menu").forEach(closeCombo);
}
document.addEventListener("mousedown", event => {
  const node = event.target;
  if (!node.closest) return;
  if (!node.closest(".combo-wrap") && !node.closest(".combo-menu")) closeCombos();
});
/* 画面に対して固定で出しているので、下の何かが動いたら閉じる。ただし一覧の中の
   スクロールでは閉じない（2026-09-21。候補を送ろうとすると消えていた）。 */
window.addEventListener("scroll", event => {
  const node = event.target;
  if (node && node.closest && node.closest(".combo-menu")) return;
  closeCombos();
}, true);
window.addEventListener("resize", closeCombos);
/* 開く位置。箱の真下に出し、下に入らなければ上へ返す。どちらにも入らない
   ときは画面の中へ寄せる（2026-09-21）。 */
function placeMenu(box, menu) {
  const rect = box.getBoundingClientRect();
  menu.style.minWidth = rect.width + "px";
  menu.style.left = "0px";
  menu.style.top = "0px";
  const size = menu.getBoundingClientRect();
  function clamp(value, max) { return Math.min(Math.max(4, value), Math.max(4, max)); }
  let top = rect.bottom + 2;
  if (top + size.height > window.innerHeight - 4) top = rect.top - size.height - 2;
  menu.style.left = clamp(rect.left, window.innerWidth - size.width - 4) + "px";
  menu.style.top = clamp(top, window.innerHeight - size.height - 4) + "px";
}
function searchable(select) {
  if (select.dataset.combo || select.disabled) return select;
  select.dataset.combo = "1";
  if (select.options.length <= COMBO_SEARCH_MIN) return select;
  const box = el("button", { type: "button", class: "combo-box" });
  const search = el("input", { type: "search", class: "combo", placeholder: "検索" });
  const list = el("div", { class: "combo-list" });
  const menu = el("div", { class: "combo-menu", hidden: "hidden" }, [search, list]);

  function paint() {
    const option = select.options[select.selectedIndex];
    const text = option ? option.textContent : "";
    box.textContent = text || "（選択）";
  }
  function addItem(option, text) {
    if (text && option.textContent.toLowerCase().indexOf(text) < 0) return 0;
    const item = el("div", { class: "combo-item", text: option.textContent || "（選択）" });
    if (option.value === select.value) item.classList.add("on");
    // click だと検索欄から外れた時点で閉じてしまうので mousedown で拾う
    item.addEventListener("mousedown", event => {
      event.preventDefault();
      closeCombo(menu);
      if (select.value !== option.value) {
        select.value = option.value;
        paint();
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    list.appendChild(item);
    return 1;
  }
  /* フォルダ（optgroup）の見出しも出す。素のプルダウンと同じく、フォルダを見てから
     フィールドを選べるようにするため（2026-09-21。一覧を自前で描いたとき落ちていた）。
     絞り込みで中身が 1 つも残らないフォルダは見出しごと出さない。 */
  function renderList() {
    const text = search.value.trim().toLowerCase();
    list.textContent = "";
    let shown = 0;
    Array.prototype.forEach.call(select.children, node => {
      if (node.tagName !== "OPTGROUP") {
        shown += addItem(node, text);
        return;
      }
      const head = el("div", { class: "combo-group", text: node.label });
      list.appendChild(head);
      let count = 0;
      Array.prototype.forEach.call(node.children, option => { count += addItem(option, text); });
      if (count) shown += count;
      else list.removeChild(head);
    });
    if (!shown) {
      list.textContent = "";
      list.appendChild(el("div", { class: "combo-empty", text: "該当なし" }));
    }
  }
  const wrap = el("span", { class: "combo-wrap" }, [select, box, menu]);
  menu.comboHome = wrap;
  box.addEventListener("click", () => {
    if (!menu.hidden) { closeCombo(menu); return; }
    closeCombos();
    search.value = "";
    renderList();
    document.body.appendChild(menu);
    menu.hidden = false;
    placeMenu(box, menu);
    search.focus();
  });
  search.addEventListener("input", renderList);
  search.addEventListener("keydown", event => { if (event.key === "Escape") closeCombo(menu); });
  paint();
  return wrap;
}

/* ---- リネーム・フォルダ設定を AI に考えてもらうプロンプト（2026-09-21） ----
   選んだ行（無ければ全行）の 元カラム / データ型 / 役割 をタブ区切りにして、
   プロンプトへ差し込む。返ってくる 3 列はそのまま表へ貼り戻せる。 */
const FIELD_PROMPT = __FIELD_PROMPT__;
const CALC_PROMPT = __CALC_PROMPT__;
const PROMPT_RULES = __PROMPT_RULES__;
const CALC_PROMPT_RULES = __CALC_PROMPT_RULES__;

/* プロンプトに入れる行。掴み手の列を Ctrl+クリックで拾った行があればそれ、
   無ければ範囲選択した行、それも無ければ（絞り込みで残っている）全行（2026-09-21）。
   表の範囲選択は長方形なので、離れた行はこの Ctrl+クリックで選ぶ。 */
const PICKED_FIELDS = new Set();

/* AI の結果（元カラム||リネーム後名称||フォルダ||階層）は、貼り付け位置ではなく
   1 列目の元カラム名で行を合わせる。飛び飛びに選んだ行でもそのまま貼れる
   （2026-09-21）。1 列目が表に無い名前なら、今までどおり位置で貼る。 */
function pasteByOriginalName(grid, startColumn) {
  const lines = grid.filter(cols => cols.some(value => value.trim()));
  if (lines.length < 1 || lines.some(cols => cols.length < 2)) return false;
  const rows = Array.from(document.getElementById("rename-body").rows);
  const byName = new Map(rows.map(row => [row.cells[1].textContent.trim(), row]));
  if (!lines.every(cols => byName.has(cols[0].trim()))) return false;
  // 2 列目以降は、選んでいたセルの列から順に入れる。フォルダの列を選んで
  // 「元カラム||フォルダ」の 2 列だけ貼れば、フォルダだけを書き換えられる。
  const first = Math.min(Math.max(startColumn, 2), 4);
  lines.forEach(cols => {
    const row = byName.get(cols[0].trim());
    cols.slice(1).forEach((value, i) => {
      const target = row.cells[first + i];
      if (target && target.dataset.edit === "1") target.textContent = value.trim();
    });
  });
  return true;
}

let PICK_ANCHOR = -1;

function pickedRowName(tr) { return tr.cells[1].textContent.trim(); }

function markPicked(tr, on) {
  const name = pickedRowName(tr);
  if (on) PICKED_FIELDS.add(name);
  else PICKED_FIELDS.delete(name);
  tr.classList.toggle("picked", on);
}

/* 行のどこでも Ctrl+クリックで拾う / 外す。Shift+クリックは、直前に拾った行から
   そこまでをまとめて拾う（2026-09-21）。表のセル選択より先に処理して止める。
   拾った行が 1 つも無いときの Shift+クリックは、今までどおりセルの範囲選択。 */
function pickFieldRows(event) {
  const cell = event.target.closest("td");
  if (!cell || !cell.parentElement || cell.parentElement.parentElement.id !== "rename-body") return;
  const tr = cell.parentElement;
  const rows = Array.from(tr.parentElement.rows);
  const index = rows.indexOf(tr);
  if (event.ctrlKey || event.metaKey) {
    markPicked(tr, !PICKED_FIELDS.has(pickedRowName(tr)));
    PICK_ANCHOR = index;
  } else if (event.shiftKey && PICKED_FIELDS.size && PICK_ANCHOR >= 0) {
    const from = Math.min(PICK_ANCHOR, index);
    const to = Math.max(PICK_ANCHOR, index);
    for (let i = from; i <= to; i++) markPicked(rows[i], true);
    PICK_ANCHOR = index;
  } else {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
}
document.getElementById("rename-table").addEventListener("mousedown", pickFieldRows, true);

function selectedFieldRows() {
  const rows = Array.from(document.getElementById("rename-body").rows)
    .filter(row => row.style.display !== "none");
  const picked = rows.filter(row => PICKED_FIELDS.has(row.cells[1].textContent.trim()));
  if (picked.length) return picked;
  const selected = rows.filter(row =>
    Array.from(row.cells).some(cell => cell.classList.contains("sel")
                                    || cell.classList.contains("active")));
  return selected.length ? selected : rows;
}

function fieldPromptText() {
  // 入力も出力と同じ二重縦棒で区切る。タブはチャットへ貼ると潰れて、
  // 「商品 ID」のように値へ空白が入る名前と区別できなくなる（2026-09-21）。
  const lines = selectedFieldRows().map(row => [
    row.cells[1].textContent.trim(),
    row.cells[5].textContent.trim(),
    row.cells[6].textContent.trim(),
  ].join("||"));
  return FIELD_PROMPT.replace("__ROWS__", lines.join("\n"));
}

/* 計算フィールドのプロンプト。式の中で使える名前（リネーム後の名前と、
   いま表に入っている計算フィールド）を一覧にして渡す（2026-09-21）。 */
function calcPromptText() {
  const fields = selectedFieldRows().map(row => [
    row.cells[2].textContent.trim() || row.cells[1].textContent.trim(),
    row.cells[5].textContent.trim(),
    row.cells[6].textContent.trim(),
  ].join("||"));
  Array.from(document.getElementById("calc-body").rows).forEach(row => {
    const name = row.cells[0].textContent.trim();
    if (!name) return;
    fields.push([name, row.cells[3].textContent.trim(),
                 row.cells[4].textContent.trim()].join("||"));
  });
  return CALC_PROMPT.replace("__FIELDS__", fields.join("\n"));
}

const promptDialog = document.getElementById("prompt-dialog");
const promptRuleOptions = document.getElementById("prompt-rule-options");
const promptRuleCheckboxes = document.getElementById("prompt-rule-checkboxes");
const calcPromptRuleCheckboxes = document.getElementById("calc-prompt-rule-checkboxes");
const PROMPT_RULE_START = "\n\n<!-- twbpatch:reference-rules:start -->\n";
const PROMPT_RULE_END = "<!-- twbpatch:reference-rules:end -->\n";
let promptRulesManaged = false;
let activePromptKind = "field";

function selectedPromptRules() {
  const group = activePromptKind === "calc" ? calcPromptRuleCheckboxes : promptRuleCheckboxes;
  const rules = activePromptKind === "calc" ? CALC_PROMPT_RULES : PROMPT_RULES;
  return Array.from(group.querySelectorAll("input[type=checkbox]"))
    .filter(box => box.checked)
    .map(box => rules[Number(box.dataset.ruleIndex)]);
}

function promptRuleSection() {
  const selected = selectedPromptRules();
  if (!selected.length) return "";
  const content = selected.map(rule => "## " + rule.name + "\n" + rule.text).join("\n");
  return PROMPT_RULE_START + "# 参照ルール\n\n" + content + "\n" + PROMPT_RULE_END;
}

function syncPromptRules() {
  if (promptRuleOptions.hidden) return;
  const area = document.getElementById("prompt-text");
  const replacement = promptRuleSection();
  const start = area.value.indexOf(PROMPT_RULE_START);
  const end = area.value.indexOf(PROMPT_RULE_END);
  if (promptRulesManaged) {
    if (start < 0 || end < start || start !== area.value.lastIndexOf(PROMPT_RULE_START)
        || end !== area.value.lastIndexOf(PROMPT_RULE_END)) {
      document.getElementById("prompt-copied").textContent =
        "参照ルールの境界が変更されています。プロンプトを作り直してください。";
      return;
    }
    area.value = area.value.slice(0, start) + replacement
      + area.value.slice(end + PROMPT_RULE_END.length);
  } else {
    if (start >= 0 || end >= 0) {
      document.getElementById("prompt-copied").textContent =
        "参照ルールの境界が変更されています。プロンプトを作り直してください。";
      return;
    }
    area.value += replacement;
  }
  promptRulesManaged = Boolean(replacement);
  document.getElementById("prompt-copied").textContent = "";
}

function renderPromptRuleCheckboxes() {
  [[PROMPT_RULES, promptRuleCheckboxes], [CALC_PROMPT_RULES, calcPromptRuleCheckboxes]]
    .forEach(([rules, group]) => {
      rules.forEach((rule, index) => {
        const label = document.createElement("label");
        const box = document.createElement("input");
        box.type = "checkbox";
        box.checked = rule.default_checked;
        box.dataset.ruleIndex = String(index);
        box.addEventListener("change", syncPromptRules);
        label.appendChild(box);
        label.appendChild(document.createTextNode(rule.name));
        group.appendChild(label);
      });
    });
}
renderPromptRuleCheckboxes();

function openPrompt(text, note) {
  document.getElementById("prompt-text").value = text;
  document.getElementById("prompt-copied").textContent = note;
  promptDialog.showModal();
}
document.getElementById("prompt-open").addEventListener("click",
  () => {
    activePromptKind = "field";
    promptRuleCheckboxes.hidden = false;
    calcPromptRuleCheckboxes.hidden = true;
    promptRuleOptions.hidden = PROMPT_RULES.length === 0;
    promptRulesManaged = selectedPromptRules().length > 0;
    openPrompt(fieldPromptText() + promptRuleSection(), selectedFieldRows().length + " 行");
  });
document.getElementById("calc-prompt-open").addEventListener("click",
  () => {
    activePromptKind = "calc";
    promptRuleCheckboxes.hidden = true;
    calcPromptRuleCheckboxes.hidden = false;
    promptRuleOptions.hidden = CALC_PROMPT_RULES.length === 0;
    promptRulesManaged = selectedPromptRules().length > 0;
    openPrompt(calcPromptText() + promptRuleSection(),
      "「# 作りたい指標」を書いてからコピーする");
  });
document.getElementById("prompt-close").addEventListener("click", () => promptDialog.close());
document.getElementById("prompt-clear").addEventListener("click", () => {
  PICKED_FIELDS.clear();
  PICK_ANCHOR = -1;
  Array.from(document.getElementById("rename-body").rows)
    .forEach(row => row.classList.remove("picked"));
});
document.getElementById("prompt-copy").addEventListener("click", () => {
  const area = document.getElementById("prompt-text");
  const done = () => { document.getElementById("prompt-copied").textContent = "コピーしました"; };
  // file:// で開くと navigator.clipboard が使えないことがあるので、選択してのコピーへ落とす
  area.select();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(area.value).then(done, () => {
      if (document.execCommand("copy")) done();
    });
    return;
  }
  if (document.execCommand("copy")) done();
});

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

/* 貼り付けの区切り（2026-09-21）。タブがあればタブ（Excel・スプレッドシート）。
   無ければ二重縦棒（||）、それも無ければ縦棒（|）。生成 AI の返事はタブが落ちて
   届くことが多く、値に空白が入る「商品 ID」のような名前があるので空白では区切れない。
   二重縦棒にしているのは、値の中の縦棒（「売上|当年」など）とぶつからないため。
   Markdown の表で返ってきたときのために、行頭行末の | と区切り行（---）は落とす。 */
function parsePastedGrid(text) {
  const lines = text.replace(/\r/g, "").replace(/\n+$/, "").split("\n");
  if (text.indexOf("\t") >= 0) return lines.map(line => line.split("\t"));
  const mark = text.indexOf("||") >= 0 ? "||" : "|";
  if (text.indexOf(mark) < 0) return lines.map(line => [line]);
  return lines
    .filter(line => !/^\s*\|?\s*:?-{2,}/.test(line))
    .map(line => {
      // Markdown の表（行頭行末も | ）のときだけ、その 2 本を落とす。
      // 末尾の区切りは残す。3 列目が空の行を 2 列と読み違えないため。
      const body = (mark === "|" && /^\s*\|.*\|\s*$/.test(line))
        ? line.replace(/^\s*\|/, "").replace(/\|\s*$/, "")
        : line;
      return body.split(mark).map(value => value.trim());
    });
}

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
    /* 表の外にあるものからのコピーは、ブラウザ既定に任せる（2026-09-21）。
       表のセルを選んだまま別のタブへ移ると activeGrid と選択が残るため、
       ダッシュボードのシート名などテキストボックスのコピーを横取りしていた。 */
    const active = document.activeElement;
    if (active && active !== document.body && !table.contains(active)) return;
    const picked = window.getSelection && window.getSelection();
    if (picked && !picked.isCollapsed && picked.rangeCount) {
      const node = picked.getRangeAt(0).commonAncestorContainer;
      const element = node.nodeType === 1 ? node : node.parentNode;
      if (element && !table.contains(element)) return;
    }
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
    const grid = parsePastedGrid(text);
    const start = cell ? posOf(cell) : { r: rect().top, c: rect().left };
    // 1 列目が既にある行の名前なら、どの行かは名前で決める。列は貼り付け先から
    if (options.pasteByName && options.pasteByName(grid, start.c)) {
      dirty();
      commit();
      return;
    }
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

/* 階層（ドリルパス）は .twb では folder-item を持たないので、行の「フォルダ」には
   階層が置かれているフォルダを入れる。行の並びがそのまま階層の順になるよう、
   同じ階層のフィールドを先頭の行の位置へ集める（2026-09-21）。 */
function hierarchyOf(ds, field) {
  return (ds.drill_paths || []).find(path => (path.field_ids || []).indexOf(field.id) >= 0);
}

function orderByHierarchy(ds, rows) {
  (ds.drill_paths || []).forEach(path => {
    const members = (path.field_ids || [])
      .map(id => rows.find(row => row.fieldId === id))
      .filter(Boolean);
    if (members.length < 2) return;
    const at = rows.indexOf(members[0]);
    members.forEach(row => rows.splice(rows.indexOf(row), 1));
    rows.splice(rows.indexOf(members[0]) >= 0 ? rows.indexOf(members[0]) : at, 0, ...members);
  });
  return rows;
}

function initialState(ds) {
  const rename = orderByHierarchy(ds, (ds.fields || []).filter(f => !f.is_calculated).map(field => {
    const path = hierarchyOf(ds, field);
    return {
      fieldId: field.id,
      original: originalNameOf(field),
      display: field.name || "",
      folder: (path ? path.folder_name : folderNameOf(ds, field)) || NO_FOLDER,
      hierarchy: path ? path.name : "",
      datatype: field.datatype || "",
      role: field.role || "",
    };
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
    const value = row.cells[3].textContent.trim();
    if (value) set.add(value);
  });
  return Array.from(set);
}
/* 階層名の候補。今この表に入っている名前を集める（2026-09-21） */
function hierarchyCandidates() {
  const set = new Set([""]);
  Array.from(document.getElementById("rename-body").rows).forEach(row => {
    const value = row.cells[4].textContent.trim();
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

/* 帳票の表示方法（2026-09-22）。並び替えの一覧は表にしない（表にすると順番を
   ドラッグで変えられなくなる）。選択済みの行の「×」の手前に、メジャーだけ
   小さなボタンを置き、押すたびに 数値 → 棒 → 色付け と変える。
   受け手は draw_sheet の bar_metrics / color_metrics として読む。 */
const SHEET_DISPLAYS = [["value", "数値"], ["bar", "棒"], ["color", "色付け"]];
/* 表示方法ボタンの左に出す色。棒は 1 色、色付けは 2 色（薄い側 → 濃い側）。
   数値には色を出さない（2026-09-22 指定）。 */
const SHEET_BAR_COLOR = "#4a7dff";
const SHEET_COLOR_RANGE = ["#e8eef7", "#2f3b52"];
function hasSheetDisplay(area, spec) {
  return area.chart === "draw_sheet" && spec.name === "items";
}
function measureNames(dsIndex) {
  const ds = DATA.datasources[Number(dsIndex) || 0];
  return ((ds && ds.fields) || [])
    .filter(field => !field.hidden && field.role === "measure")
    .map(field => field.name || "");
}

function openFieldOrderModal(area, spec, selected, onChange) {
  let dragFrom = null; // { list: "left" | "right", name: string }

  const withDisplay = hasSheetDisplay(area, spec);
  const measures = withDisplay ? measureNames(area.datasource) : [];
  const displays = {};
  const barColors = {};
  const colorRanges = {};
  if (withDisplay) {
    (area.params.bar_metrics || []).forEach((name, index) => {
      displays[name] = "bar";
      barColors[name] = (area.params.bar_colors || [])[index] || SHEET_BAR_COLOR;
    });
    (area.params.color_metrics || []).forEach((name, index) => {
      displays[name] = "color";
      colorRanges[name] = [
        (area.params.color_starts || [])[index] || SHEET_COLOR_RANGE[0],
        (area.params.color_ends || [])[index] || SHEET_COLOR_RANGE[1],
      ];
    });
  }
  /* 選んだ順のまま書き出す。選択から外れたフィールドはここで落ちる。
     色もメジャーと同じ並びで書き出す（2026-09-22） */
  function applyDisplays() {
    if (!withDisplay) return;
    const bars = selected.filter(name => displays[name] === "bar");
    const colors = selected.filter(name => displays[name] === "color");
    area.params.bar_metrics = bars;
    area.params.color_metrics = colors;
    area.params.bar_colors = bars.map(name => barColors[name] || SHEET_BAR_COLOR);
    area.params.color_starts = colors.map(
      name => (colorRanges[name] || SHEET_COLOR_RANGE)[0]);
    area.params.color_ends = colors.map(
      name => (colorRanges[name] || SHEET_COLOR_RANGE)[1]);
  }

  const overlay = el("div", { class: "modal-overlay" });
  function closeModal() {
    applyDisplays();
    overlay.remove();
  }
  overlay.addEventListener("mousedown", event => {
    if (event.target === overlay) closeModal();
  });

  const leftList = el("div", { class: "modal-list" });
  const rightList = el("div", { class: "modal-list" });

  /* 表示方法のボタンと、その左に出す色。棒は 1 色、色付けは 2 色 */
  function displayControls(name) {
    const order = SHEET_DISPLAYS.map(pair => pair[0]);
    const swatches = el("span", { class: "display-colors" });
    const button = el("button", { class: "mini display-pick", draggable: "false" });
    function swatch(value, hint, onPick) {
      const input = el("input", { type: "color", class: "display-color",
                                  value: value, title: hint });
      input.addEventListener("input", () => { onPick(input.value); applyDisplays(); });
      return input;
    }
    function refresh() {
      const kind = displays[name] || "value";
      button.textContent = SHEET_DISPLAYS.filter(pair => pair[0] === kind)[0][1];
      button.title = "表示方法（押すと 数値 → 棒 → 色付け と変わります）";
      button.classList.toggle("on", kind !== "value");
      swatches.innerHTML = "";
      if (kind === "bar") {
        const value = barColors[name] || SHEET_BAR_COLOR;
        barColors[name] = value;
        swatches.appendChild(
          swatch(value, "棒の色", picked => { barColors[name] = picked; }));
      } else if (kind === "color") {
        const range = (colorRanges[name] || SHEET_COLOR_RANGE).slice();
        colorRanges[name] = range;
        ["薄い側の色", "濃い側の色"].forEach((hint, index) => {
          swatches.appendChild(
            swatch(range[index], hint, picked => { range[index] = picked; }));
        });
      }
    }
    button.addEventListener("click", () => {
      displays[name] = order[(order.indexOf(displays[name] || "value") + 1) % order.length];
      refresh();
      applyDisplays();
    });
    refresh();
    return [swatches, button];
  }

  function makeItem(name, listName) {
    const item = el("div", { class: "modal-item", draggable: "true" }, [
      el("span", { class: "grip", text: "⠿" }),
      el("span", { text: name }),
    ]);
    if (listName === "right") {
      if (withDisplay && measures.indexOf(name) >= 0) {
        displayControls(name).forEach(node => item.appendChild(node));
      }
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
    // 外したり並べ替えたりした結果を、その場で表示方法へ反映する（2026-09-22）
    applyDisplays();
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
  closeBtn.addEventListener("click", closeModal);
  const footClose = el("button", { class: "act", text: "閉じる" });
  footClose.addEventListener("click", closeModal);

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
  applyDisplays();

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

/* 表の行をドラッグで並べ替える（2026-09-21）。階層の順は行の並びで決まるので、
   ここで動かした順がそのままドリルの順になる。掴み手（⠿）を押している間だけ
   draggable にして、セルの選択と喧嘩しないようにする。

   掴むのは行オブジェクトではなく <tr> の位置。行オブジェクトは `captureCurrent()` が
   呼ばれるたびに作り直されるので、持っていても元の配列から見つからなくなる。 */
let ROW_DRAG = null;
function attachRowDrag(tr, gripCell, state) {
  const bodyRows = () => Array.from(tr.parentElement.rows);
  gripCell.addEventListener("mousedown", event => {
    tr.setAttribute("draggable", "true");
    event.stopPropagation();
  });
  gripCell.addEventListener("mouseup", () => tr.removeAttribute("draggable"));
  tr.addEventListener("dragstart", event => {
    ROW_DRAG = tr;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", "field-row");
    tr.classList.add("dragging-src");
  });
  tr.addEventListener("dragend", () => {
    ROW_DRAG = null;
    tr.removeAttribute("draggable");
    tr.classList.remove("dragging-src");
    bodyRows().forEach(other => other.classList.remove("drop-row"));
  });
  tr.addEventListener("dragover", event => {
    if (!ROW_DRAG || ROW_DRAG === tr) return;
    event.preventDefault();
    tr.classList.add("drop-row");
  });
  tr.addEventListener("dragleave", () => tr.classList.remove("drop-row"));
  tr.addEventListener("drop", event => {
    if (!ROW_DRAG || ROW_DRAG === tr) return;
    event.preventDefault();
    tr.classList.remove("drop-row");
    const rows = bodyRows();
    moveFieldRow(state, rows.indexOf(ROW_DRAG), rows.indexOf(tr));
  });
}

/* `from` 番目の行を `to` 番目の位置へ。上へ動かすときは落とした行の前、
   下へ動かすときは後ろに入る。 */
function moveFieldRow(state, from, to) {
  if (from < 0 || to < 0 || from === to) return;
  const rows = captureCurrent().rename;   // 画面の並びに合わせてから動かす
  const moved = rows.splice(from, 1)[0];
  rows.splice(to, 0, moved);
  renderTables(state);
  validateRename();
}

function renderTables(state) {
  const renameBody = document.getElementById("rename-body");
  renameBody.innerHTML = "";
  state.rename.forEach(row => {
    const folderCell = editableCell(row.folder);
    folderCell.addEventListener("focus", () => openChoicePopup(folderCell, folderCandidates()));
    const hierarchyCell = editableCell(row.hierarchy || "");
    hierarchyCell.addEventListener("focus",
      () => openChoicePopup(hierarchyCell, hierarchyCandidates()));
    const gripCell = el("td", { class: "ro grip-cell", tabindex: "-1" },
      [el("span", { class: "grip", text: "⠿", title: "ドラッグして並べ替え" })]);
    const tr = el("tr", {}, [
      gripCell,
      readonlyCell(row.original),
      editableCell(row.display),
      folderCell,
      hierarchyCell,
      readonlyCell(row.datatype),
      readonlyCell(row.role),
    ]);
    attachRowDrag(tr, gripCell, state);
    if (PICKED_FIELDS.has(row.original)) tr.classList.add("picked");
    renameBody.appendChild(tr);
  });
  const calcBody = document.getElementById("calc-body");
  calcBody.innerHTML = "";
  state.calcs.forEach(cells => calcBody.appendChild(calcRow.apply(null, cells)));
}

/* 画面の内容を、いま表示しているデータソースの編集内容へ書き戻す */
function captureInto(index) {
  const state = stateAt(index);
  state.rename = Array.from(document.getElementById("rename-body").rows).map((row, index) => ({
    fieldId: (state.rename[index] || {}).fieldId,
    // 先頭はドラッグの掴み手の列（2026-09-21）
    original: row.cells[1].textContent.trim(),
    display: row.cells[2].textContent.trim(),
    folder: row.cells[3].textContent.trim(),
    hierarchy: row.cells[4].textContent.trim(),
    datatype: row.cells[5].textContent.trim(),
    role: row.cells[6].textContent.trim(),
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
  validateCalc();
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
  errors.push.apply(errors, validateHierarchies(state));
  return errors;
}

/* 階層は 2 つ以上のフィールドが要る。フォルダは階層の中でそろえる（2026-09-21） */
function validateHierarchies(state) {
  const errors = [];
  hierarchiesOf(state).forEach((entry, name) => {
    if (entry.fields.length < 2) {
      errors.push("階層「" + name + "」はフィールドが 2 つ以上要る");
    }
    const folders = new Set(state.rename
      .filter(row => (row.hierarchy || "").trim() === name && row.display)
      .map(row => row.folder));
    if (folders.size > 1) {
      errors.push("階層「" + name + "」のフォルダがそろっていない: "
        + Array.from(folders).join(" / "));
    }
    if (state.rename.some(row => row.display === name)) {
      errors.push("階層「" + name + "」と同じ名前のフィールドがある");
    }
  });
  return errors;
}

function validateRename() {
  const seen = new Set();
  Array.from(document.getElementById("rename-body").rows).forEach(row => {
    const original = row.cells[1].textContent.trim();
    const display = row.cells[2].textContent.trim();
    const folder = row.cells[3].textContent.trim();
    const hasFolder = !isNoFolder(folder);
    row.cells[2].classList.toggle("invalid", hasFolder && !display);
    row.cells[3].classList.toggle("invalid", hasFolder && seen.has(original));
    if (hasFolder) seen.add(original);
  });
  const errors = validateState(captureCurrent());
  document.getElementById("rename-errors").textContent = errors.join("\n");
  // リネームすると式から参照できる名前が変わる（2026-09-21）
  if (document.getElementById("calc-body").rows.length) validateCalc();
  return errors.length === 0;
}
document.getElementById("rename-table").addEventListener("griddirty", validateRename);

/* 式の中で使える名前（2026-09-21）。リネーム後の名前（空なら元の名前）と、
   この表で定義する計算フィールドの名前。受け手も適用後の名前で解決するため、
   リネーム前の名前は使えない。絞り込みで隠れている行も対象に含める。 */
function knownFieldNames() {
  const names = new Set();
  Array.from(document.getElementById("rename-body").rows).forEach(row => {
    const name = row.cells[2].textContent.trim() || row.cells[1].textContent.trim();
    if (name) names.add(name);
  });
  Array.from(document.getElementById("calc-body").rows).forEach(row => {
    const name = row.cells[0].textContent.trim();
    if (name) names.add(name);
  });
  return names;
}
/* 式の [フィールド名] のうち、存在しないものを返す。文字列の中の [ ] までは
   見分けられないが、実在しない名前を早く気づける方を採る。 */
function missingReferences(formula, names) {
  const missing = [];
  (formula.match(/\[[^\[\]]+\]/g) || []).forEach(token => {
    const name = token.slice(1, -1).trim();
    if (name && !names.has(name) && missing.indexOf(name) < 0) missing.push(name);
  });
  return missing;
}

/* 計算フィールド: フォルダは自由入力のまま検証しない。データ型・役割は
   テキスト入力を許すが、候補にない文字列は赤くしてエラー欄に出す。
   式は [フィールド名] の参照先が無ければ赤くする（2026-09-21 追加）。 */
function validateCalc() {
  const errors = [];
  const names = knownFieldNames();
  Array.from(document.getElementById("calc-body").rows).forEach(row => {
    const name = row.cells[0].textContent.trim();
    const formula = row.cells[1].textContent.trim();
    if (!name && !formula) return;
    const datatype = row.cells[3].textContent.trim();
    const role = row.cells[4].textContent.trim();
    const datatypeInvalid = !!datatype && !CALC_DATATYPE_CHOICES.includes(datatype);
    const roleInvalid = !!role && !CALC_ROLE_CHOICES.includes(role);
    const missing = missingReferences(formula, names);
    row.cells[1].classList.toggle("invalid", missing.length > 0);
    row.cells[3].classList.toggle("invalid", datatypeInvalid);
    row.cells[4].classList.toggle("invalid", roleInvalid);
    if (missing.length) {
      errors.push((name || formula) + ": 無いフィールドを参照しています ("
                  + missing.map(item => "[" + item + "]").join(", ") + ")");
    }
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
  const names = new Set();
  state.rename.forEach(row => {
    const name = row.display || row.original;
    if (name) names.add(name);
  });
  state.calcs.forEach(cells => { if (cells[0]) names.add(cells[0]); });
  state.calcs.forEach(cells => {
    const name = cells[0], formula = cells[1];
    if (!name && !formula) return;
    const missing = missingReferences(formula || "", names);
    if (missing.length) {
      errors.push((name || formula) + ": 無いフィールドを参照しています ("
                  + missing.map(item => "[" + item + "]").join(", ") + ")");
    }
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
["d-main", "d-sub1", "d-sub2", "d-sub3", "d-accent", "d-text1", "d-text2", "d-bg",
 "d-border", "d-heat-min", "d-heat-mid", "d-heat-max"]
  .forEach(bindColor);

function designYaml() {
  const value = id => document.getElementById(id).value.trim();
  let out = "design:\n";
  out += "  font: " + yamlKey(value("d-font")) + "\n";
  out += "  main_color: " + yamlKey(value("d-main")) + "\n";
  out += "  sub_color_1: " + yamlKey(value("d-sub1")) + "\n";
  out += "  sub_color_2: " + yamlKey(value("d-sub2")) + "\n";
  out += "  sub_color_3: " + yamlKey(value("d-sub3")) + "\n";
  // 追加アクセントは入れたときだけ出す（プリセットによっては無い）
  if (value("d-accent")) out += "  accent_color: " + yamlKey(value("d-accent")) + "\n";
  out += "  text_color_1: " + yamlKey(value("d-text1")) + "\n";
  out += "  text_color_2: " + yamlKey(value("d-text2")) + "\n";
  // 台紙（ダッシュボードの地）の色（2026-09-21 追加）
  out += "  background_color: " + yamlKey(value("d-bg")) + "\n";
  // 枠線は色を入れたときだけ引く。空なら枠線なし
  if (value("d-border")) out += "  border_color: " + yamlKey(value("d-border")) + "\n";
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

/* 階層は「階層」列から組み立てる。並びは表の行順、フォルダは最初の行のフォルダ（2026-09-21） */
function hierarchiesOf(state) {
  const hierarchies = new Map();
  state.rename.forEach(row => {
    const name = (row.hierarchy || "").trim();
    if (!name || !row.display) return;
    if (!hierarchies.has(name)) hierarchies.set(name, { folder: row.folder, fields: [] });
    hierarchies.get(name).fields.push(row.display);
  });
  return hierarchies;
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
    const hierarchies = hierarchiesOf(state);
    if (!folders.size && !renames.length && !calcs.length && !hierarchies.size) return;
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
    if (hierarchies.size) {
      out += "    hierarchies:\n";
      hierarchies.forEach((entry, name) => {
        out += "      " + yamlKey(name) + ":\n";
        if (!isNoFolder(entry.folder)) out += "        folder: " + yamlKey(entry.folder) + "\n";
        out += "        fields:\n";
        entry.fields.forEach(field => { out += "          - " + yamlKey(field) + "\n"; });
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
// selectable: false のもの（draw_info。インフォメーションを追加のチェックボックス
// 経由でのみ使う）は「グラフ種類」プルダウンには出さない（2026-09-23）。
const CHART_TYPES = Object.keys(DRAW_SPECS).filter(name => DRAW_SPECS[name].selectable !== false);

/* 設定 YAML を読み込んで作った画面なら、その中身が入っている（2026-09-21）。
   .twb にはデザインルール・ダッシュボードの組み立て・KPI ツリーが残らないため、
   画面を作り直すときは YAML から戻す。 */
const CONFIG = JSON.parse(document.getElementById("config-data").textContent);

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
    filterRole: "dimension",
    action: { enabled: false, type: "filter", target: "", field: "" },
  };
}
function newRow() {
  // distribute: 段の幅を均等に割るか（2026-09-21）。均等割りの段では Tableau が
  // エリアごとの幅を見ないので、幅を効かせたい段はここを外す。
  // 名前は Tableau のレイアウトツリーに出るコンテナ名。空のままだと読みづらいので
  // 追加した順に既定を入れる（2026-09-21。並べ替えても付け直さない）。
  return { id: ++rowSeq, name: nextRowName(), height: "300", collapsed: false,
           distribute: true, areas: [newArea()] };
}
function nextRowName() {
  const used = new Set((typeof DASH === "undefined" ? [] : DASH.rows).map(row => row.name));
  for (let index = 1; ; index += 1) {
    const name = index + "段目";
    if (!used.has(name)) return name;
  }
}
function distributeOf(row) {
  return row.distribute === undefined ? true : !!row.distribute;
}
function cloneArea(area) {
  return Object.assign({}, area, {
    id: ++rowSeq,
    params: Object.assign({}, area.params),
    action: Object.assign({}, area.action),
    info: area.info ? Object.assign({}, area.info) : undefined,
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
  build_waterfall: { label: "滝", fields: [{ name: "metrics", limit: 2 }] },
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
/* フィルターのフィールドの種類。未設定はディメンション（2026-09-21） */
function filterRoleOf(area) {
  return area.filterRole === undefined ? "dimension" : area.filterRole;
}

function dashboardSheetNames(except) {
  const names = [];
  DASH.rows.forEach(row => row.areas.forEach(area => {
    if (area !== except && area.kind === "worksheet" && area.sheet) names.push(area.sheet);
  }));
  return names;
}
/* .twb に既にあるシート名。ただし**読み込んだ設定 YAML が作るシートは除く**
   （2026-09-21）。YAML を当ててから画面を作り直すと（bat の 2 番）、その YAML が
   作ったシートが .twb に居るため、戻した段のシート名が軒並み重複扱いになっていた。
   もう一度同じ YAML を適用するときは作り直されるので、重複ではない。 */
function existingSheetNames() {
  const mine = configSheetNames();
  return new Set((DATA.worksheets || []).map(ws => ws.name).filter(name => !mine.has(name)));
}
let CONFIG_SHEET_NAMES = null;
function configSheetNames() {
  if (CONFIG_SHEET_NAMES) return CONFIG_SHEET_NAMES;
  CONFIG_SHEET_NAMES = new Set();
  ((CONFIG.dashboard || {}).rows || []).forEach(row => {
    (row.areas || []).forEach(area => {
      if (area && area.sheet) CONFIG_SHEET_NAMES.add(area.sheet);
    });
  });
  const walk = node => {
    if (!node) return;
    if (node.sheet) CONFIG_SHEET_NAMES.add(node.sheet);
    (node.children || []).forEach(walk);
  };
  walk((CONFIG.kpi_tree || {}).root);
  return CONFIG_SHEET_NAMES;
}
function usedSheetNames(except) {
  const used = existingSheetNames();
  dashboardSheetNames(except).forEach(name => used.add(name));
  kpiTreeSheetNames(except).forEach(name => used.add(name));
  return used;
}

/* シート名が空・重複なら入力欄を薄い赤にする（2026-09-21）。
   ダウンロード前の検証と同じ条件を、入力中にその場で見せる。 */
function markSheetName(input, area) {
  const name = (input.value || "").trim();
  const bad = !name || usedSheetNames(area).has(name);
  input.classList.toggle("bad", bad);
  return !bad;
}

/* 手で入力したシート名の重複を、ダウンロード前の検証で出す。
   `names` はそのタブのシート名（[名前, 表示用の場所] の組）、`others` は別タブのシート名。 */
function duplicateSheetErrors(names, others, otherLabel) {
  const errors = [];
  const existing = existingSheetNames();
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
  // 読み込んだ設定 YAML が作るダッシュボードは、シート名と同じ理由で除く
  const mine = new Set([(CONFIG.dashboard || {}).name, (CONFIG.kpi_tree || {}).name]
    .filter(Boolean));
  if (!mine.has(name) && (DATA.dashboards || []).some(db => db.name === name)) {
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
/* optional を渡すと、空の選択肢を「（指定なし）」にする（2026-09-22）。
   棒グラフの項目のように、選ばないことが正しい指定になる引数のため。 */
function fieldOptions(dsIndex, selected, role, optional) {
  const options = [el("option", { value: "", text: optional ? "（指定なし）" : "（選ぶ）" })];
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
  { key: "sub_color_3", label: "サブカラー③", input: "d-sub3" },
  { key: "accent_color", label: "追加アクセント", input: "d-accent" },
  { key: "text_color_1", label: "文字色①", input: "d-text1" },
  { key: "text_color_2", label: "文字色②", input: "d-text2" },
  { key: "background_color", label: "背景色", input: "d-bg" },
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
  return el("span", { class: "color2" }, [searchable(source), picker]);
}

/* ---- インフォメーションアイコン（2026-09-23） ----
   グラフのエリア／KPI ツリーのノードに「インフォメーションを追加」チェックボックスを
   出す。チェックすると draw_info() の入力（本文・アイコン・見出し・色）が現れる。
   受け手（config_apply.py の _apply_info()）が build_report() の後、対象シートの
   ゾーンの右上へ浮動で重ねる。draw_info の choices/既定値は DRAW_SPECS からそのまま
   読むので、アイコンの種類や既定色を画面側で二重に持たない。 */
function infoParamSpec(name) {
  return ((DRAW_SPECS["draw_info"] || {}).params || []).find(p => p.name === name);
}
function infoControl(holder) {
  if (!holder.info) {
    const iconSpec = infoParamSpec("icon");
    const headingSpec = infoParamSpec("heading");
    holder.info = {
      enabled: false, text: "",
      icon: (iconSpec && iconSpec.default) || "info",
      heading: (headingSpec && headingSpec.default) || "説明",
      color: "",
    };
  }
  const info = holder.info;
  const checkbox = el("input", Object.assign({ type: "checkbox" },
    info.enabled ? { checked: "checked" } : {}));
  const body = el("div", { class: "params" });
  function renderBody() {
    body.innerHTML = "";
    body.hidden = !info.enabled;
    if (!info.enabled) return;
    const text = el("textarea", { rows: "3" }, []);
    text.value = info.text || "";
    text.addEventListener("input", () => { info.text = text.value; });
    const choices = (infoParamSpec("icon") || {}).choices || [];
    const icon = el("select", {}, choices.map(choice =>
      el("option", Object.assign({ value: choice[0], text: choice[1] },
                                 choice[0] === info.icon ? { selected: "selected" } : {}))));
    icon.addEventListener("change", () => { info.icon = icon.value; });
    const heading = el("input", { type: "text", value: info.heading });
    heading.addEventListener("input", () => { info.heading = heading.value.trim(); });
    const colorSpec = infoParamSpec("color");
    if (!info.color) info.color = (colorSpec && colorSpec.default) || "#e15759";
    const color = colorControl(info.color, v => { info.color = v; });
    body.appendChild(labeled("本文 *", text));
    body.appendChild(el("div", { class: "fields" }, [
      labeled("アイコン", searchable(icon)),
      labeled("見出し", heading),
      labeled("色", color),
    ]));
  }
  checkbox.addEventListener("change", () => { info.enabled = checkbox.checked; renderBody(); });
  renderBody();
  return el("div", { class: "info-control" }, [labeled("インフォメーションを追加", checkbox), body]);
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

/* ---- KPI カードのモード（2026-09-21） ----
   モードで使う引数が変わる。選んでいないモードの入力欄は出さず、YAML にも書かない
   （両方書くと受け手が「予実比較モードは sub_metric を取らない」で止まる）。
   モードと、そのモードの主役になる引数は、詳細設定に畳まず前に出す。 */
const CARD_MODE_PARAMS = {
  sub_metric: ["sub_metric"],
  /* budget_value_color は画面に出さない（paramsYaml が文字色②を当てる、2026-09-22）が、
     サブ指標モードのときに書き残さないよう、ここへも並べておく。 */
  budget: ["budget_metric", "budget_threshold", "achieved_color", "missed_color",
           "budget_value_color"],
};
function cardModeOf(params) {
  return (params || {}).mode || "sub_metric";
}
function hiddenParamNames(chart, params) {
  if (chart !== "draw_card") return [];
  const mode = cardModeOf(params);
  const names = [];
  Object.keys(CARD_MODE_PARAMS).forEach(key => {
    if (key !== mode) names.push.apply(names, CARD_MODE_PARAMS[key]);
  });
  return names;
}
/* chart を省くと area.chart を使う。KPI ツリーのノードは draw_card 固定で
   chart を持たないため、呼び出し側から渡す。 */
function visibleParams(area, chart) {
  const kind = chart || area.chart;
  const specs = (DRAW_SPECS[kind] || {}).params || [];
  const hidden = hiddenParamNames(kind, area.params);
  return specs.filter(spec => hidden.indexOf(spec.name) < 0);
}
function frontParams(area, chart) {
  const kind = chart || area.chart;
  /* 棒グラフの項目は任意（[指定なし]で棒 1 本）になったが、主役の指定なので
     詳細設定に畳まず前に出す（2026-09-22）。 */
  if (kind === "draw_bar") return ["item"];
  if (kind !== "draw_card") return [];
  return ["mode"].concat(cardModeOf(area.params) === "budget" ? ["budget_metric"] : []);
}
function renderAll() {
  if (typeof renderRows === "function") renderRows();
  if (typeof renderKpiTree === "function") renderKpiTree();
}

function paramControl(area, spec) {
  let value = area.params[spec.name] === undefined ? "" : area.params[spec.name];
  if (spec.kind === "color" && value === "" && spec.default) {
    /* 画面の色ピッカーは触らなければ汎用フォールバック色（#4a7dff）を映すだけで、
       area.params には何も書かれない。YAML にキー自体が出ず、受け手（build_waterfall
       などの draw_*()）は自分の既定色を使うため、画面に見えている色と実際に使われる
       色が食い違って見えるバグになっていた（2026-09-23、実機で確認）。ここで API 側の
       既定値を area.params にも書き込み、画面の表示と YAML の出力を一致させる。 */
    value = spec.default;
    area.params[spec.name] = value;
  }
  let control;
  if (spec.kind === "bool") {
    control = el("input", Object.assign({ type: "checkbox" }, value ? { checked: "checked" } : {}));
    control.addEventListener("change", () => { area.params[spec.name] = control.checked; });
  } else if (spec.kind === "fields") {
    control = fieldsCheckControl(area, spec, value);
  } else if (spec.kind === "field") {
    control = el("select", {},
                 fieldOptions(area.datasource, value, spec.role, !spec.required));
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
    control.addEventListener("change", () => {
      area.params[spec.name] = control.value;
      // モードを変えると出す入力欄が変わる（2026-09-21）
      if (spec.name === "mode") renderAll();
    });
  } else if (spec.kind === "textarea") {
    /* <textarea> は value 属性ではなく DOM プロパティで初期値を入れる
       （2026-09-23、インフォメーションの本文向け。複数行になりうる）。 */
    control = el("textarea", { rows: "4" }, []);
    control.value = value;
    control.addEventListener("input", () => { area.params[spec.name] = control.value; });
  } else {
    control = el("input", { type: "text", value: value });
    control.addEventListener("input", () => { area.params[spec.name] = control.value.trim(); });
  }
  const label = (spec.label || spec.name) + (spec.required ? " *" : "");
  const field = labeled(label, control.tagName === "SELECT" ? searchable(control) : control);
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

  // 均等割りの段では幅を書いても効かないので、入力させない（2026-09-21）
  const evenly = distributeOf(row);
  const width = el("input", Object.assign(
    { type: "number", step: "10", min: "0", value: area.width },
    evenly ? { disabled: "disabled", title: "段が「幅を均等割り」のときは使わない" } : {}));
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
    grip, searchable(kind), labeled("幅 (px)", width),
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
    /* フィールドの前に種類（ディメンション / メジャー）を選ばせ、候補を絞る（2026-09-21）。
       フィルターに使うのはたいていディメンションなので、既定はディメンション。 */
    const role = el("select", {}, [
      ["dimension", "ディメンション"], ["measure", "メジャー"], ["", "すべて"],
    ].map(choice => el("option",
      Object.assign({ value: choice[0], text: choice[1] },
                    choice[0] === filterRoleOf(area) ? { selected: "selected" } : {}))));
    const field = el("select", {},
      fieldOptions(area.datasource, area.filterField, filterRoleOf(area) || undefined));
    role.addEventListener("change", () => {
      area.filterRole = role.value;
      area.filterField = "";
      renderRows();
    });
    field.addEventListener("change", () => { area.filterField = field.value; });
    card.appendChild(el("div", { class: "fields" }, [
      labeled("データソース", searchable(dsSelectEl)),
      labeled("種類", searchable(role)),
      labeled("フィールド", searchable(field)),
    ]));
  } else {
    const sheet = el("input", { type: "text", value: area.sheet, placeholder: "シート名" });
    sheet.addEventListener("input", () => {
      area.sheet = sheet.value.trim();
      markSheetName(sheet, area);
    });
    markSheetName(sheet, area);
    const genName = el("button", { class: "mini", text: "✎",
      title: "グラフ種類と選んだ項目からシート名を生成" });
    genName.addEventListener("click", () => {
      const generated = generateSheetName(area);
      if (generated) { area.sheet = generated; sheet.value = generated; markSheetName(sheet, area); }
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
      labeled("グラフ種類", searchable(chart)),
      labeled("データソース", searchable(dsSelectEl)),
    ]);
    card.appendChild(head);

    const specs = visibleParams(area);
    const front = frontParams(area);
    const required = specs.filter(spec => spec.required || front.indexOf(spec.name) >= 0);
    const optional = specs.filter(spec => !spec.required && front.indexOf(spec.name) < 0);
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
    // インフォメーション自体には出さない（自分に自分を重ねることになるため）
    if (area.chart !== "draw_info") {
      card.appendChild(infoControl(area));
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
    actionBox.appendChild(labeled("種類", searchable(type)));

    if (area.action.type === "filter") {
      const target = el("input", { type: "text", value: area.action.target,
                                   placeholder: "対象シート名" });
      target.addEventListener("input", () => { area.action.target = target.value.trim(); });
      actionBox.appendChild(labeled("対象シート", target));

      /* フィルターアクションは絞り込むフィールドが要る。「すべてのフィールド」は扱わない */
      const field = el("select", {},
                       fieldOptions(area.datasource, area.action.field, "dimension"));
      field.addEventListener("change", () => { area.action.field = field.value; });
      actionBox.appendChild(labeled("絞り込むフィールド", searchable(field)));
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
  /* 段の高さは 60 刻み（2026-09-21）。カード 150 の倍数まわりで揃えやすくする */
  const height = el("input", { type: "number", step: "60", min: "0", value: row.height });
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

  /* 幅の割り方は段ごとに選ぶ（2026-09-21）。入れると Tableau の「均等に配布」に
     なり、エリアの幅 (px) は効かない。外すとエリアごとの幅がそのまま通る。 */
  const evenly = el("input", Object.assign({ type: "checkbox" },
                                           distributeOf(row) ? { checked: "checked" } : {}));
  evenly.addEventListener("change", () => { row.distribute = evenly.checked; renderRows(); });

  card.appendChild(el("div", { class: "row-head" }, [
    grip, toggle,
    el("span", { class: "row-no", text: (index + 1) + "段目" }),
    labeled("名前", name), labeled("高さ (px)", height),
    labeled("幅を均等割り", evenly), summary, addArea,
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
  closeCombos();  // 開いたままの候補一覧が <body> に取り残されないように（2026-09-21）
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
/* ---- 設定 YAML から画面を戻す（2026-09-21） ----
   デザインルール・ダッシュボード・KPI ツリーは .twb に残らないので、
   YAML を読み込んで作った画面ではここで入力欄へ戻す。 */
function restoreDesign(design) {
  if (!design) return;
  const setValue = (id, value) => {
    const node = document.getElementById(id);
    if (node && value !== undefined && value !== null && value !== "") node.value = value;
  };
  if (design.font) setValue("d-font", design.font);
  DESIGN_TOKENS.forEach(token => { setValue(token.input, design[token.key]); });
  setValue("d-border", design.border_color);
  document.getElementById("d-apply").checked = !!design.filter_apply_button;
  const spacing = document.querySelector(
    'input[name=d-space][value="' + (design.spacing || "narrow") + '"]');
  if (spacing) spacing.checked = true;
  // 色見本（input[type=color]）へも反映する
  document.querySelectorAll("#tab-design input[type=text]").forEach(text => {
    const picker = document.getElementById(text.id + "-pick");
    if (picker && /^#[0-9a-fA-F]{6}$/.test(text.value.trim())) picker.value = text.value.trim();
  });
}
/* プリセットを選ぶと、デザインルールの全項目をその値に置き換える（2026-09-25）。
   反映後も項目ごとに変えられる。restoreDesign() と違い、空の値も反映する
   （追加アクセントや枠線が無いプリセットで、前の値を残さないため）。 */
const DESIGN_PRESETS = JSON.parse(document.getElementById("design-presets").textContent);
function applyDesignPreset(name) {
  const preset = DESIGN_PRESETS[name];
  if (!preset) return;
  const setColor = (id, value) => {
    const node = document.getElementById(id);
    node.value = value || "";
    const picker = document.getElementById(id + "-pick");
    if (picker && /^#[0-9a-fA-F]{6}$/.test(node.value)) picker.value = node.value;
  };
  document.getElementById("d-font").value = preset.font;
  DESIGN_TOKENS.forEach(token => setColor(token.input, preset[token.key]));
  setColor("d-border", preset.border_color);
  document.getElementById("d-apply").checked = !!preset.filter_apply_button;
  const spacing = document.querySelector('input[name=d-space][value="' + preset.spacing + '"]');
  if (spacing) spacing.checked = true;
  if (typeof renderRows === "function") renderRows();
  if (typeof renderKpiTree === "function") renderKpiTree();
}
document.getElementById("d-preset").addEventListener("change", event => {
  applyDesignPreset(event.target.value);
});
//: データソース名 → 画面の添字
function datasourceIndexOf(name) {
  const index = DATA.datasources.findIndex(ds => (ds.name || ds.id) === name);
  return index < 0 ? 0 : index;
}
function restoreArea(source) {
  const area = newArea();
  area.kind = source.kind === "filter" ? "filter" : "worksheet";
  area.datasource = datasourceIndexOf(source.datasource);
  area.width = source.width === undefined || source.width === null ? "" : String(source.width);
  if (area.kind === "filter") {
    area.filterField = source.field || "";
    const field = ((DATA.datasources[area.datasource] || {}).fields || [])
      .find(item => item.name === area.filterField);
    area.filterRole = field ? (field.role || "dimension") : "dimension";
  } else {
    area.sheet = source.sheet || "";
    area.chart = source.chart || area.chart;
    area.params = Object.assign({}, source.params || {});
  }
  const action = source.action;
  if (action) {
    area.action = {
      enabled: true,
      type: action.type || "filter",
      target: action.type === "url" ? (action.url || "") : (action.target || ""),
      field: action.field || "",
    };
  }
  return area;
}
function restoreDashboard(dashboard) {
  if (!dashboard) return;
  const setValue = (id, value) => {
    const node = document.getElementById(id);
    if (node && value !== undefined && value !== null && value !== "") node.value = value;
  };
  setValue("db-name", dashboard.name);
  setValue("db-width", dashboard.width);
  setValue("db-height", dashboard.height);
  const header = dashboard.header || {};
  setValue("h-title", header.title);
  setValue("h-height", header.height);
  if (header.background_color) HEADER.background = header.background_color;
  if (header.font_color) HEADER.font = header.font_color;
  (dashboard.rows || []).forEach(source => {
    const row = newRow();
    if (source.name) row.name = source.name;
    if (source.height !== undefined && source.height !== null) row.height = String(source.height);
    row.distribute = source.distribute_evenly !== false;
    row.areas = (source.areas || []).map(restoreArea);
    if (!row.areas.length) row.areas = [newArea()];
    DASH.rows.push(row);
  });
}

/* ヘッダーの色はデザインルールを参照する（2026-09-21）。既定は背景＝メインカラー、
   文字＝背景色。濃いメインカラーの上でも読めるようにしてある。文字色①②など
   ほかの色や、個別の色コードもここから選べる。 */
const HEADER = { background: "@main_color", font: "@background_color" };
restoreDesign(CONFIG.design);
restoreDashboard(CONFIG.dashboard);
document.getElementById("h-bg-mount").appendChild(
  colorControl(HEADER.background, value => { HEADER.background = value; }));
document.getElementById("h-fg-mount").appendChild(
  colorControl(HEADER.font, value => { HEADER.font = value; }));
/* 最初の renderRows() は KPI ツリーのスクリプトの末尾で呼ぶ（2026-09-21）。
   段の描画はシート名の重複チェックで KPI ツリーの状態（const KT）を見るため、
   ここで呼ぶと「Cannot access 'KT' before initialization」になる。 */

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
      // インフォメーションを追加していて本文が空だと受け手（draw_info）が止まる
      if (area.info && area.info.enabled && !(area.info.text || "").trim()) {
        errors.push(label + ": インフォメーションの本文が空");
      }
    });
  });
  return errors;
}

/* エリア（または KPI ツリーのノード）の `info:` を書く。チェックが入っていて
   本文があるときだけ出す（2026-09-23）。`pad` は `sheet:` などと同じ字下げ。 */
function infoYaml(holder, pad) {
  const info = holder.info;
  if (!info || !info.enabled || !(info.text || "").trim()) return "";
  let out = pad + "info:\n";
  out += pad + "  text: " + yamlKey(info.text.trim()) + "\n";
  if (info.icon) out += pad + "  icon: " + yamlKey(info.icon) + "\n";
  if (info.heading) out += pad + "  heading: " + yamlKey(info.heading) + "\n";
  if (info.color) out += pad + "  color: " + yamlKey(info.color) + "\n";
  return out;
}

/* グラフの引数を `params:` として書く。`pad` は `params:` の行の字下げ。
   KPI ツリーのノードも同じ形で書く（html_kpi_tree.py）。 */
function paramsYaml(chart, source, pad) {
  /* value_color / budget_value_color / title_background_color は画面に出さず、
     デザインルールから当てる（draw_card 固有、2026-09-12, 2026-09-13）。
     タイトルの背景は主要色。メイン指標の数値は文字色①、
     予実比較の率は文字色②（2026-09-22 指定）。 */
  const params = Object.assign({}, source);
  if (chart === "draw_card" && params.main_color) {
    params.value_color = "@text_color_1";
    params.budget_value_color = "@text_color_2";
    params.title_background_color = params.main_color;
  }
  // 選んでいないモードの引数は書かない（2026-09-21）
  hiddenParamNames(chart, params).forEach(name => { delete params[name]; });
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
  // 色はデザインルールの参照（@キー）のまま出す。解決は受け手側（2026-09-21）
  out += "    background_color: " + yamlKey(HEADER.background) + "\n";
  out += "    font_color: " + yamlKey(HEADER.font) + "\n";
  out += "  rows:\n";
  if (!DASH.rows.length) { out += "    []\n"; return out; }
  DASH.rows.forEach(row => {
    out += "    - name: " + yamlKey(row.name) + "\n";
    if (row.height) out += "      height: " + yamlKey(row.height) + "\n";
    // 幅の割り方（2026-09-21）。真偽値なので yamlKey に通さない
    out += "      distribute_evenly: " + (distributeOf(row) ? "true" : "false") + "\n";
    out += "      areas:\n";
    row.areas.forEach(area => {
      const ds = DATA.datasources[area.datasource];
      out += "        - kind: " + yamlKey(area.kind) + "\n";
      out += "          datasource: " + yamlKey(ds ? (ds.name || ds.id) : "") + "\n";
      // 均等割りの段では幅が効かないので書かない
      if (area.width && !distributeOf(row)) {
        out += "          width: " + yamlKey(area.width) + "\n";
      }
      if (area.kind === "filter") {
        out += "          field: " + yamlKey(area.filterField) + "\n";
      } else {
        out += "          sheet: " + yamlKey(area.sheet) + "\n";
        out += "          chart: " + yamlKey(area.chart) + "\n";
        out += paramsYaml(area.chart, area.params, "          ");
        out += infoYaml(area, "          ");
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
enableGrid(document.getElementById("rename-table"), { pasteByName: pasteByOriginalName });
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
      <label for="d-preset">プリセット</label>
      <select id="d-preset">__PRESET_OPTIONS__</select>
      <label for="d-font">フォント</label>
      <select id="d-font">__FONT_OPTIONS__</select>
      <label for="d-main">メインカラーコード</label>
      <span class="color">
        <input type="color" id="d-main-pick"><input type="text" id="d-main" value="#2366e1">
      </span>
      <label for="d-sub1">サブカラー&#9312;</label>
      <span class="color">
        <input type="color" id="d-sub1-pick"><input type="text" id="d-sub1" value="#ce70f0">
      </span>
      <label for="d-sub2">サブカラー&#9313;</label>
      <span class="color">
        <input type="color" id="d-sub2-pick"><input type="text" id="d-sub2" value="#ccd500">
      </span>
      <label for="d-sub3">サブカラー&#9314;</label>
      <span class="color">
        <input type="color" id="d-sub3-pick"><input type="text" id="d-sub3" value="#4a9ca5">
      </span>
      <label for="d-accent">追加アクセント</label>
      <span class="color">
        <input type="color" id="d-accent-pick"><input type="text" id="d-accent" value="">
      </span>
      <label for="d-text1">文字色&#9312;</label>
      <span class="color">
        <input type="color" id="d-text1-pick"><input type="text" id="d-text1" value="#202020">
      </span>
      <label for="d-text2">文字色&#9313;</label>
      <span class="color">
        <input type="color" id="d-text2-pick"><input type="text" id="d-text2" value="#4e4e4e">
      </span>
      <label for="d-bg">背景色</label>
      <span class="color">
        <input type="color" id="d-bg-pick"><input type="text" id="d-bg" value="#f5f5f5">
      </span>
      <label for="d-border">枠線の色</label>
      <span class="color">
        <input type="color" id="d-border-pick"><input type="text" id="d-border" value="">
      </span>
      <label for="d-heat-min">ヒートマップ：最小値の色</label>
      <span class="color">
        <input type="color" id="d-heat-min-pick"><input type="text" id="d-heat-min" value="#ce70f0">
      </span>
      <label for="d-heat-mid">ヒートマップ：中間の色</label>
      <span class="color">
        <input type="color" id="d-heat-mid-pick"><input type="text" id="d-heat-mid" value="#ffffff">
      </span>
      <label for="d-heat-max">ヒートマップ：最大値の色</label>
      <span class="color">
        <input type="color" id="d-heat-max-pick"><input type="text" id="d-heat-max" value="#2366e1">
      </span>
      <label for="d-apply">フィルターに「適用」ボタン</label>
      <span><input type="checkbox" id="d-apply"> 入れる</span>
      <label>余白</label>
      <span>
        <label><input type="radio" name="d-space" value="wide"> 広い</label>
        <label><input type="radio" name="d-space" value="narrow" checked> 狭い</label>
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
          <col style="width: 3%"><col style="width: 17%"><col style="width: 20%">
          <col style="width: 17%"><col style="width: 18%"><col style="width: 12%">
          <col style="width: 13%">
        </colgroup>
        <thead><tr>
          <th></th><th>元カラム</th><th>リネーム後名称</th><th>フォルダ</th><th>階層</th>
          <th>データ型</th><th>役割</th>
        </tr></thead>
        <tbody id="rename-body"></tbody>
      </table>
    </div>
    <p class="errors" id="rename-errors"></p>
    <p><button class="act" id="prompt-open">選んだ行から AI 用プロンプトを作る</button>
      <button class="act" id="prompt-clear">行の選択を解除</button>
      <span class="note">Ctrl+クリックで行を選ぶ（離れた行も選べる）。Shift+クリックでそこまでまとめて選ぶ。
        選択が無いときは絞り込みで残っている全行。
        返ってきた 3 列は「リネーム後名称」のセルへ貼り付ける</span></p>
    </div>
  </div>

  <dialog id="prompt-dialog">
    <h3>AI 用プロンプト</h3>
    <div id="prompt-rule-options" hidden>
      <span>プロンプトに含める参照ルール</span>
      <div id="prompt-rule-checkboxes"></div>
      <div id="calc-prompt-rule-checkboxes" hidden></div>
    </div>
    <textarea id="prompt-text"></textarea>
    <p>
      <button class="act" id="prompt-copy">クリップボードにコピー</button>
      <span id="prompt-copied" class="note"></span>
      <button class="act" id="prompt-close">閉じる</button>
    </p>
  </dialog>

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
      <button class="act" id="calc-prompt-open">AI 用プロンプトを作る</button>
      <span class="note">リネーム・フォルダ設定で選んだフィールドと、この表の計算フィールドを
        一覧にして渡す。返ってきた 5 列はこの表の左上へ貼り付ける</span>
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
        <input type="text" id="h-title" value="ダッシュボード">
        <label for="h-height">高さ (px)</label>
        <input type="text" id="h-height" value="43">
        <!-- 色はデザインルールを参照する（2026-09-21）。中身は colorControl で作る -->
        <label>背景色</label>
        <span id="h-bg-mount"></span>
        <label>文字色</label>
        <span id="h-fg-mount"></span>
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
<script type="application/json" id="config-data">__CONFIG__</script>
<script type="application/json" id="design-presets">__DESIGN_PRESETS__</script>
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
    "Poppins",
)

#: デザインルールのプリセット（2026-09-25。ユーザーが作った 3 パターン）。
#: 選ぶと全項目へ反映し、あとから項目ごとに変えられる。
#: フォントは Tableau が 1 つの名前しか受けないので、CSS の並び（`Arial, sans-serif`）の
#: 先頭だけ使う。「適用」ボタンの色は受け皿が無い（チェックだけ）ので入れない。
#: 余白 `24px` は広い（`wide`）へ、指定の無いモスグリーンは既定の狭い（`narrow`）へ当てた。
DESIGN_PRESETS: dict[str, dict[str, Any]] = {
    "モスグリーン": {
        "font": "Arial",
        "main_color": "#1A7259",
        "sub_color_1": "#F65824",
        "sub_color_2": "#FBB6C9",
        "sub_color_3": "#C1E0BF",
        "accent_color": "",
        "text_color_1": "#111111",
        "text_color_2": "#555555",
        "background_color": "#FFFFFF",
        "border_color": "#E5E5E5",
        "min_color": "#DCEBD9",
        "mid_color": "#9CCBA8",
        "max_color": "#1A7259",
        "filter_apply_button": True,
        "spacing": "narrow",
    },
    "ネオン・ノワール": {
        "font": "Poppins",
        "main_color": "#742CDF",
        "sub_color_1": "#10D19D",
        "sub_color_2": "#FE8C4F",
        "sub_color_3": "#FA4E84",
        "accent_color": "",
        "text_color_1": "#2B2B2D",
        "text_color_2": "#79787F",
        "background_color": "#F5F7FB",
        "border_color": "#ECECF0",
        "min_color": "#F5EEFE",
        "mid_color": "#B895E5",
        "max_color": "#742CDF",
        "filter_apply_button": True,
        "spacing": "wide",
    },
    "ソメイヨシノ": {
        "font": "Noto Sans JP",
        "main_color": "#000000",
        "sub_color_1": "#9A4DAD",
        "sub_color_2": "#EAF5F7",
        "sub_color_3": "#F8463C",
        "accent_color": "#2E7664",
        "text_color_1": "#000000",
        "text_color_2": "#555555",
        "background_color": "#FBFAF7",
        "border_color": "#1A1A1A",
        "min_color": "#F3E5F5",
        "mid_color": "#D09BDC",
        "max_color": "#9A4DAD",
        "filter_apply_button": True,
        "spacing": "wide",
    },
}


#: グラフの引数のうち、画面に出さないもの。
#: 集計方法（`*aggregation`）は出さない。フィールドの役割とデータ型が分かっていれば
#: `draw.py` の `_auto_metric_aggregation()` が決められるため、人が選ぶ必要がない。
#: `value_color` / `budget_value_color` / `title_background_color` /
#: `vertical_alignment` は draw_card 固有。前3つは画面に出さず、タイトル背景は
#: main_color、メイン指標の数値は文字色①、予実比較の率は文字色②を当てる
#: （2026-09-12, 2026-09-13, 2026-09-22）。文字色・タイトル背景色を指標の色と
#: 別々に選ばせても、個別に変える需要が薄く混乱のもとだった。
#: `vertical_alignment` は「縦は常に中央でよい」との指摘
#: （2026-09-13）を受け、画面からは選ばせず API 既定の "center" のまま渡す。
#: `bar_metrics` / `color_metrics` は帳票の項目の並び替えモーダルで、行内のボタンから
#: 決める（2026-09-22）。詳細設定にも「（選ぶ）」が出ると同じ指定が 2 か所になり、
#: しかもそちらのモーダルには行内ボタンが付かないため、画面には出さない。
_DRAW_SKIP = {
    "self", "datasource", "name",
    "value_color", "budget_value_color", "title_background_color", "vertical_alignment",
    "bar_metrics", "color_metrics", "bar_colors", "color_starts", "color_ends",
}


#: グラフごとに画面へ出さない引数（2026-09-22）。帳票の `item_shelf` は、
#: メジャーを不連続で行へ並べる作りにも、棒・色帯の列を横へ足す作りにも
#: 「行」以外の選択肢が無いため出さない。API 側は既定の `"rows"` のまま残す。
_CHART_PARAM_SKIP: dict[str, set[str]] = {
    "draw_sheet": {"item_shelf"},
}


def _is_skipped(name: str, chart: str = "") -> bool:
    if name in _CHART_PARAM_SKIP.get(chart, ()):
        return True
    return name in _DRAW_SKIP or name == "aggregation" or name.endswith("_aggregation")

#: 「リネーム・フォルダ設定を AI に考えてもらう」ボタンが出すプロンプト（2026-09-21）。
#: `__ROWS__` に、画面で選んだ行のタブ区切り（元カラム / データ型 / 役割）が入る。
#: 返ってくるのも同じ行数のタブ区切り 3 列なので、そのまま表へ貼り戻せる。
_FIELD_PROMPT = """あなたは Tableau のデータソース設計を手伝うアシスタントです。
フィールドの一覧を渡すので、「リネーム後名称」「フォルダ」「階層」を決めてください。

# 入力
1 行 1 フィールドで、半角の縦棒 2 つ（||）区切りです。
列は左から 元カラム / データ型 / 役割 です。値に空白が入る名前（例: 商品 ID）があるので、
空白ではなく || だけを区切りとして読んでください。

__ROWS__

# 出力
入力と同じ行数・同じ並びで、4 列だけを出力してください。
列は左から **元カラム（入力のまま）** / リネーム後名称 / フォルダ / 階層 で、
**半角の縦棒 2 つ（||）で区切ります**。元カラムは 1 文字も変えずにそのまま返してください。
階層が無い行も区切りは省かず、末尾を空にします。
見出し行、番号、説明、コードブロックの記号は一切付けないでください。

"""

#: 「計算フィールドのプロンプトを作る」ボタンが出すプロンプト（2026-09-21）。
#: `__FIELDS__` に、いま使えるフィールド（名前 / データ型 / 役割）が入る。
#: 返ってくるのは計算フィールドの表と同じ 5 列なので、そのまま貼り戻せる。
_CALC_PROMPT = """あなたは Tableau の計算フィールドを作るアシスタントです。
使えるフィールドの一覧と作りたい指標を渡すので、計算フィールドの定義を返してください。

# 使えるフィールド
1 行 1 フィールドで、半角の縦棒 2 つ（||）区切りです。
列は左から 名前 / データ型 / 役割 です。式の中ではこの「名前」を [ ] で囲んで参照します。

__FIELDS__

# 作りたい指標
（ここに書いてください。例: 売上・利益・数量について 当年 / 昨年 / 昨年差 / 昨年比。
顧客数・注文数・顧客単価も。）

# 出力
1 行 1 計算フィールドで、5 列を半角の縦棒 2 つ（||）で区切って出力してください。
列は左から 名前 / 式 / フォルダ / データ型 / 役割 です。
データ型は string / integer / real / boolean / date / datetime、役割は measure / dimension です。
説明、見出し行、コードブロックの記号は一切付けないでください。
"""

#: グラフ種類の表示名。仕様 §6.14 の説明に合わせる。
#: **この並び順がそのまま画面の選択肢の順になる**（2026-09-21。よく使う順）。
_CHART_LABELS = {
    "draw_card": "KPIカード",
    "draw_bar": "棒グラフ",
    "draw_sheet": "帳票",
    "draw_crosstab": "クロス集計（ヒートマップ）",
    "draw_quadrant": "散布図（四象限）",
    "build_waterfall": "ウォーターフォール",
    "draw_info": "インフォメーション",
}

#: グラフ種類の選択肢（画面の「グラフ種類」プルダウン）には出さない `draw_*()`
#: （2026-09-23）。`draw_info` はエリア／ノードの「インフォメーションを追加」
#: チェックボックス（`infoControl()`）経由でのみ使う。`_draw_specs()` の出力自体からは
#: 消さない——`infoControl()` が `DRAW_SPECS["draw_info"]` から `icon` の選択肢と
#: 各引数の既定値を読み、表示名の訳し漏れチェックの対象にも含めたいため。
_HIDDEN_FROM_CHART_LIST = {"draw_info"}

#: フィールドを取る引数が、ディメンションとメジャーのどちらを求めるか。
#: 載っていない引数は絞り込まず全フィールドを出す。
_PARAM_ROLES = {
    "item": "dimension",
    # 帳票（draw_sheet）の items はメジャーも選べる（2026-09-21）。
    # メジャーは集計してからディメンションとして置く。
    "items": None,
    "x_item": "dimension",
    "y_item": "dimension",
    "index_partition_by": "dimension",
    "metric": "measure",
    "metrics": "measure",
    "main_metric": "measure",
    "sub_metric": "measure",
    "budget_metric": "measure",
    "line_metric": "measure",
    # 帳票の棒・色帯の列（2026-09-22）
    "bar_metrics": "measure",
    "color_metrics": "measure",
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
    "main_metric": "メインメジャー",
    "sub_metric": "サブメジャー",
    "mode": "モード",
    "budget_metric": "予算比指標",
    "budget_threshold": "境界値",
    "achieved_color": "達成時の色",
    "missed_color": "未達時の色",
    "main_aggregation": "メインメジャーの集計",
    "sub_aggregation": "サブメジャーの集計",
    "main_color": "メインカラー",
    "value_color": "数値の色",
    "budget_value_color": "予算比の色",
    "title_background_color": "タイトルの背景色",
    "vertical_alignment": "縦の揃え",
    "negative_color": "減少の色",
    "positive_color": "増加の色",
    "ratio_color": "比率の色",
    "mark_type": "マークの種類",
    "bar_color": "棒の色",
    # 帳票の中の棒・色帯（2026-09-22）
    "bar_metrics": "棒にするメジャー",
    "color_metrics": "色付けするメジャー",
    "bar_colors": "棒の色",
    "color_starts": "色付けの薄い側",
    "color_ends": "色付けの濃い側",
    # 棒グラフの二重軸（2026-09-22）。サブメジャーはバーインバー、
    # 折れ線メジャーは二重軸の折れ線。どちらか一方しか指定できない
    "line_metric": "折れ線メジャー",
    "sub_bar_color": "サブの棒の色",
    "line_color": "折れ線の色",
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
    "folder": "計算フィールドのフォルダ",
    # ウォーターフォール（2026-09-23 追加）。connector_color は画面に出さない固定値
    # （#cccccc）のため、ここには載せない。
    "connectors": "連結線を表示する",
    "landing": "着地バーを追加する",
    "increase_color": "増加の色",
    "decrease_color": "減少の色",
    "landing_color": "着地の色",
    # インフォメーション（2026-09-23 追加）
    "icon": "アイコン",
    "heading": "見出し",
    "text": "本文",
}

#: グラフごとの表示名の上書き（2026-09-21 追加）。同じ引数名でもグラフによって
#: 意味が変わるものだけ置く。散布図の `item` は点 1 つの単位を決める。
_CHART_PARAM_LABELS: dict[str, dict[str, str]] = {
    "draw_quadrant": {"item": "点の粒度"},
}

#: 値が固定の選択肢しか受け付けない引数。(値, 表示ラベル) の一覧。
#: API 側のバリデーション（`_shelves()` など）と一致させる。
_PARAM_CHOICES: dict[str, list[tuple[str, str]]] = {
    "item_shelf": [("rows", "横棒（行）"), ("columns", "縦棒（列）")],
    "mark_type": [("bar", "棒"), ("text", "テキスト")],
    # KPI カードのモード（2026-09-21 追加）
    "mode": [("sub_metric", "サブ指標モード"), ("budget", "予実比較モード")],
    # インフォメーションのアイコン（2026-09-23 追加）
    "icon": [
        ("info", "情報"), ("quest", "疑問"), ("setting", "設定"), ("attention", "注意"),
    ],
}


def _param_kind(name: str, annotation: str) -> str:
    if "list[FieldInput]" in annotation:
        return "fields"
    if "FieldInput" in annotation:
        return "field"
    if name in _PARAM_CHOICES:
        return "select"
    if name == "text":
        # インフォメーションの本文は複数行になりうるのでテキストエリア（2026-09-23）。
        # draw.py に "text" という名前の引数は他に無い。
        return "textarea"
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
            if _is_skipped(parameter.name, method_name):
                continue
            annotation = str(parameter.annotation)
            default = parameter.default
            if default is inspect.Parameter.empty or not isinstance(
                default, (str, int, float, bool)
            ):
                default = None
            params.append(
                {
                    "name": parameter.name,
                    "label": _CHART_PARAM_LABELS.get(method_name, {}).get(
                        parameter.name,
                        _PARAM_LABELS.get(parameter.name, parameter.name),
                    ),
                    "kind": _param_kind(parameter.name, annotation),
                    "role": _PARAM_ROLES.get(parameter.name),
                    "required": parameter.default is inspect.Parameter.empty,
                    "choices": _PARAM_CHOICES.get(parameter.name),
                    "default": default,
                }
            )
        specs[method_name] = {
            "label": _CHART_LABELS.get(method_name, method_name),
            "params": params,
            "selectable": method_name not in _HIDDEN_FROM_CHART_LIST,
        }
    return specs


def _preset_options() -> str:
    return '<option value="">（選ぶと全項目へ反映）</option>' + "".join(
        f'<option value="{_escape(name)}">{_escape(name)}</option>'
        for name in DESIGN_PRESETS
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


def _embed_json(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text.replace("</", "<\\/")


def _fill_slots(template: str, values: dict[str, str]) -> str:
    """テンプレート内の差し込み口だけを一度ずつ置換し、値は再走査しない。"""
    pattern = re.compile("|".join(re.escape(key) for key in values))
    return pattern.sub(lambda match: values[match.group()], template)


_PROMPT_RULES_DIR = Path(__file__).parent / "template" / "prompt_rules"
_CALC_PROMPT_RULES_DIR = Path(__file__).parent / "template" / "calc_prompt_rules"


def _load_prompt_rules(
    directory: Path | None = None, *, default_name: str = "00-common-rules.md"
) -> list[dict[str, str | bool]]:
    """HTML 生成時に固定フォルダ直下の Markdown ルールを読み込む。"""
    folder = _PROMPT_RULES_DIR if directory is None else directory
    rules: list[dict[str, str | bool]] = []
    for path in sorted(folder.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"cannot read prompt rule: {path.name}") from exc
        rules.append({
            "name": path.name,
            "text": content,
            "default_checked": path.name == default_name,
        })
    return rules


#: データソースそのものを表す擬似フィールド（Tableau のオブジェクト）。
#: 改名もフォルダ分類もできないので画面に出さない（2026-09-21）。
_OBJECT_FIELD_PREFIX = "[__tableau_internal_object_id__]"


def _without_object_fields(data: dict[str, Any]) -> dict[str, Any]:
    datasources = data.get("datasources")
    if not isinstance(datasources, list):
        return data
    data = dict(data)
    data["datasources"] = [
        {
            **datasource,
            "fields": [
                field
                for field in datasource.get("fields", [])
                if not str(field.get("id") or "").startswith(_OBJECT_FIELD_PREFIX)
            ],
        }
        if isinstance(datasource, dict)
        else datasource
        for datasource in datasources
    ]
    return data


#: 画面へ戻す設定 YAML の節（2026-09-21）。`datasources` は .twb に焼かれていて
#: そちらから読み直すため戻さない。
_SCREEN_CONFIG_SECTIONS = ("design", "dashboard", "kpi_tree")


def _screen_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    return {
        key: config[key]
        for key in _SCREEN_CONFIG_SECTIONS
        if isinstance(config.get(key), dict)
    }


def render_workbook_html(
    data: dict[str, Any],
    *,
    title: str = "twbpatch 設定",
    font: str = "Meiryo UI",
    config: dict[str, Any] | None = None,
) -> str:
    from .html_kpi_tree import KPI_TREE_NAV, KPI_TREE_SCRIPT, KPI_TREE_SECTION, KPI_TREE_STYLE

    data = _without_object_fields(data)
    body = _fill_slots(_BODY, {
        "__FONT_OPTIONS__": _font_options(font),
        "__PRESET_OPTIONS__": _preset_options(),
        "__KPI_TREE_NAV__": KPI_TREE_NAV,
        "__KPI_TREE_SECTION__": KPI_TREE_SECTION,
        "__TITLE__": _escape(title),
        "__DS_COUNT__": str(len(data.get("datasources", []))),
        "__WS_COUNT__": str(len(data.get("worksheets", []))),
        "__DB_COUNT__": str(len(data.get("dashboards", []))),
    })
    script = _fill_slots(_SCRIPT, {
        "__FIELD_PROMPT__": _embed_json(_FIELD_PROMPT),
        "__CALC_PROMPT__": _embed_json(_CALC_PROMPT),
        "__PROMPT_RULES__": _embed_json(_load_prompt_rules()),
        "__CALC_PROMPT_RULES__": _embed_json(_load_prompt_rules(
            _CALC_PROMPT_RULES_DIR, default_name="00-calculation-rules.md"
        )),
    })
    return _fill_slots(_TEMPLATE, {
        "__STYLE__": _STYLE + KPI_TREE_STYLE,
        "__BODY__": body,
        "__SCRIPT__": script + KPI_TREE_SCRIPT,
        "__DATA__": _embed_json(data),
        "__DRAW_SPECS__": _embed_json(_draw_specs()),
        # 設定 YAML のうち、.twb に残らない節だけを画面へ戻す（2026-09-21）
        "__CONFIG__": _embed_json(_screen_config(config)),
        "__DESIGN_PRESETS__": _embed_json(DESIGN_PRESETS),
        "__TITLE__": _escape(title),
    })
