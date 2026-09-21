"""設定画面の「KPI ツリー」タブ（backlog I-2、計画は docs/tasks/I2_kpi_tree.md のステップ 4）。

タブの HTML・CSS・JS を文字列で持ち、`html_export.py` の差し込み口からそのままつなぐ。
JS は `html_export.py` の関数（`el()` / `labeled()` / `paramControl()` / `dsOptions()` /
`attachGrip()` / `generateSheetName()` / `uniqueName()` / `paramsYaml()` / `designYaml()` /
`datasourcesYaml()` など）を使い、ノードの入力欄は `DRAW_SPECS["draw_card"]` から作る。
画面の形は承認済みの試作（`tmp/kpi_tree_prototype.html`、2026-09-13）に合わせる。
"""

from __future__ import annotations

KPI_TREE_NAV = '<button data-tab="tab-kpi-tree">KPI ツリー</button>'

KPI_TREE_STYLE = """
/* ---- KPI ツリータブ（html_kpi_tree.py） ---- */
.kt-seg { display: inline-flex; width: max-content; border: 1px solid #c3cad6; border-radius: 4px;
          overflow: hidden; }
.kt-seg button { font: inherit; font-size: 12px; padding: 4px 12px; border: 0; cursor: pointer;
                 background: #fff; color: #46536e; }
.kt-seg button + button { border-left: 1px solid #c3cad6; }
.kt-seg button.on { background: #4a7dff; color: #fff; font-weight: 600; }
.kt-layout { display: flex; gap: 16px; align-items: flex-start; }
.kt-layout > .kt-main { flex: 1; min-width: 0; }
.kt-layout > .kt-side { flex: 0 0 330px; }
.kt-hint { font-size: 11px; color: #6b7688; margin: 6px 0 0; }
.kt-yaml { margin: 0; padding: 12px; background: #2f3b52; color: #dbe1ec; border-radius: 6px;
           font: 12px/1.6 "Consolas", "SF Mono", monospace; overflow: auto; max-height: 60vh;
           white-space: pre; }
/* ツリーは左から右へ展開する（生成されるダッシュボードと同じ向き） */
.kt-tree { overflow: auto; padding: 18px 14px; background: #fbfcfe; border: 1px solid #d8dde5;
           border-radius: 6px; }
.kt-subtree { display: flex; align-items: center; }
.kt-tree.kt-align-top .kt-subtree { align-items: flex-start; }
.kt-children { position: relative; display: flex; flex-direction: column; justify-content: center; }
.kt-node-wrap { display: flex; align-items: center; flex: 0 0 auto; }
.kt-node-no { font-weight: 600; font-size: 12px; color: #46536e; white-space: nowrap; }
/* エッジ（線）と、そのふもとの ＋ ボタン */
.kt-edge-out { position: relative; flex: 0 0 44px; height: 30px; display: flex; align-items: center; }
.kt-edge-out::before { content: ""; position: absolute; left: 0; right: 0; top: 50%;
                       height: 2px; margin-top: -1px; background: #c9d2e0; }
.kt-edge-out.kt-stub::before { right: 20px; }
.kt-edge-add { position: relative; z-index: 1; width: 20px; height: 20px; margin-left: 4px;
               border: 1px solid #c3cad6; border-radius: 50%; background: #fff; color: #46536e;
               font-size: 12px; line-height: 1; padding: 0; cursor: pointer;
               display: flex; align-items: center; justify-content: center; }
.kt-edge-add:hover { background: #4a7dff; border-color: #4a7dff; color: #fff; }
.kt-child-row { display: flex; padding: 8px 0; }
/* 上端揃えでは最初の子の上余白を落とす。残すと 1 階層ごとに 8px ずつ下がり、親と子の
   カードの上端が揃わない。:first-child ではなく明示クラスで指定する（縦線の要素が兄弟に混ざるため） */
.kt-tree.kt-align-top .kt-child-row.kt-first { padding-top: 0; }
/* 縦線は行の中心ではなくカードの中心を結ぶため、JS で実測して引く */
.kt-v-line { position: absolute; left: 0; width: 2px; background: #c9d2e0; }
.kt-edge-in { flex: 0 0 22px; height: 2px; background: #c9d2e0; align-self: center; }
.kt-node.drop-top { box-shadow: inset 0 3px 0 #4a7dff; }
.kt-node.drop-bottom { box-shadow: inset 0 -3px 0 #4a7dff; }
.kt-node.drop-into { outline: 2px dashed #4a7dff; outline-offset: 2px; }
"""

KPI_TREE_SECTION = """
<section id="tab-kpi-tree">
  <div class="tab-actions">
    <span class="tag">出力: デザインルール ＋ データソース ＋ KPI ツリー</span>
    <button class="dl" id="yaml-download-kpi-tree">設定 YAML をダウンロード</button>
  </div>

  <div class="panel acc open" id="acc-kpi-tree">
    <h2 class="acc-head">KPI ツリー</h2>
    <div class="acc-body">
    <p class="note">指標の親子関係を組み立てる。ノード 1 つが KPI カード 1 枚になり、左から右へ展開した
      ダッシュボードを新しく作る。ノードの大きさ（横 200 × 縦 150）とダッシュボードの大きさはツリーの形から決まる。</p>
    <div class="grid">
      <label for="kt-name">ダッシュボード名</label>
      <input type="text" id="kt-name" value="KPI ツリー">
      <label for="kt-datasource">データソース</label>
      <select id="kt-datasource"></select>
      <label>親ノードの位置</label>
      <span class="kt-seg" id="kt-align">
        <button type="button" data-align="center">中央</button>
        <button type="button" data-align="top" class="on">上端</button>
      </span>
    </div>
    <p class="kt-hint">親ノードの位置が「上端」ならエッジ（線）を描く。「中央」ではエッジを描けない。
      エッジに使う .hyper は .twb を保存するときにライブラリが隣へ置くので、ここでは指定しない。</p>
    </div>
  </div>

  <div class="kt-layout">
    <div class="kt-main">
      <div class="panel">
        <div class="toolbar"><strong>ツリー</strong></div>
        <div class="kt-tree" id="kt-root"></div>
        <p class="kt-hint">エッジのふもとの ＋ で子を追加。⠿ を掴んでドラッグし、カードの上端／下端へ落とすと
          兄弟として前後に、中央へ落とすとその子になる。</p>
      </div>
    </div>
    <div class="kt-side">
      <div class="panel">
        <div class="toolbar"><strong>設定 YAML（KPI ツリーの節）</strong></div>
        <pre class="kt-yaml" id="kt-yaml"></pre>
      </div>
    </div>
  </div>
</section>
"""

KPI_TREE_SCRIPT = r"""
/* ---- KPI ツリータブ（html_kpi_tree.py） ---- */
/* 既定は上端揃え。受け手は上端揃えのときだけエッジを描く */
const KT = { root: null, align: "top" };
let ktSeq = 0;
//: kpi_tree.py の _EDGE_MAX_OFFSET と同じ。エッジの表（同梱の edge.hyper）が持つ縦位置の上限
const KPI_EDGE_MAX_OFFSET = 13;

const ktDatasourceSelect = document.getElementById("kt-datasource");
dsOptions(0).forEach(option => ktDatasourceSelect.appendChild(option));
function ktDatasource() { return Number(ktDatasourceSelect.value) || 0; }

function newKpiNode() {
  return { id: ++ktSeq, chart: "draw_card", sheet: "", datasource: ktDatasource(),
           params: defaultParamsFor("draw_card"), moreOpen: false, children: [] };
}
function cloneKpiNode(node) {
  return Object.assign({}, node, {
    id: ++ktSeq,
    params: Object.assign({}, node.params),
    children: node.children.map(cloneKpiNode),
  });
}

/* ツリーをたどる。順番（行きがけ順）はカードの「ノード n」と検証メッセージの番号に使う */
function kpiNodes(node, out) {
  if (!node) return out;
  out.push(node);
  node.children.forEach(child => kpiNodes(child, out));
  return out;
}
function kpiParentOf(target, current) {
  const node = current || KT.root;
  if (!node) return null;
  for (const child of node.children) {
    if (child === target) return node;
    const found = kpiParentOf(target, child);
    if (found) return found;
  }
  return null;
}
function kpiContains(ancestor, target) {
  return ancestor === target || ancestor.children.some(child => kpiContains(child, target));
}
function kpiLeafCount(node) {
  return node.children.reduce((sum, child) => sum + kpiLeafCount(child), 0) || 1;
}

/* html_export.py の名前の重複チェックから呼ばれる */
function kpiTreeSheetNames(except) {
  return kpiNodes(KT.root, []).filter(node => node !== except && node.sheet).map(node => node.sheet);
}
function kpiTreeDashboardName() {
  return KT.root ? document.getElementById("kt-name").value.trim() : "";
}

function moveKpiNode(dragged, target, mode) {
  DRAG = null;
  const from = kpiParentOf(dragged);
  if (!from || kpiContains(dragged, target)) return;
  from.children.splice(from.children.indexOf(dragged), 1);
  if (mode === "into") {
    target.children.push(dragged);
  } else {
    const parent = kpiParentOf(target);
    parent.children.splice(parent.children.indexOf(target) + (mode === "after" ? 1 : 0), 0, dragged);
  }
  renderKpiTree();
}
function kpiDropMode(card, event, isRoot) {
  if (isRoot) return "into";
  const box = card.getBoundingClientRect();
  const ratio = (event.clientY - box.top) / box.height;
  return ratio < 0.25 ? "before" : ratio > 0.75 ? "after" : "into";
}
const KPI_DROP_CLASSES = { before: "drop-top", after: "drop-bottom", into: "drop-into" };

function kpiNodeCard(node, number) {
  const card = el("div", { class: "area kt-node" });
  const isRoot = node === KT.root;

  const grip = el("span", { class: "grip", text: "⠿", title: "ドラッグして移動" });
  if (!isRoot) attachGrip(grip, card, () => ({ kind: "kpi-node", node: node }));

  const head = [grip, el("span", { class: "kt-node-no", text: "ノード" + number }),
                el("span", { class: "spacer" })];
  if (!isRoot) {
    const duplicate = el("button", { class: "mini", text: "⧉", title: "このノードを配下ごと複製" });
    duplicate.addEventListener("click", () => {
      const parent = kpiParentOf(node);
      const copy = cloneKpiNode(node);
      parent.children.splice(parent.children.indexOf(node) + 1, 0, copy);
      kpiNodes(copy, []).forEach(item => {
        if (item.sheet) item.sheet = uniqueName(item.sheet, usedSheetNames(item));
      });
      renderKpiTree();
    });
    head.push(duplicate);
  }
  const remove = el("button", { class: "mini danger", text: "×",
    title: isRoot ? "ツリーを削除" : "このノードと配下を削除" });
  remove.addEventListener("click", () => {
    if (node.children.length && !confirm("配下のノードもまとめて削除します。よいですか")) return;
    if (isRoot) {
      KT.root = null;
    } else {
      const parent = kpiParentOf(node);
      parent.children.splice(parent.children.indexOf(node), 1);
    }
    renderKpiTree();
  });
  head.push(remove);
  card.appendChild(el("div", { class: "area-head" }, head));

  const sheet = el("input", { type: "text", value: node.sheet, placeholder: "シート名" });
  sheet.addEventListener("input", () => { node.sheet = sheet.value.trim(); });
  const genName = el("button", { class: "mini", text: "✎",
    title: "グラフ種類と選んだ項目からシート名を生成" });
  genName.addEventListener("click", () => {
    const generated = generateSheetName(node);
    if (generated) { node.sheet = generated; sheet.value = generated; renderKpiYaml(); }
  });
  /* グラフ種類は KPI カード固定。ダッシュボードタブと同じ並びに見せるため表示だけ置く */
  const chart = el("select", { disabled: "disabled" },
    [el("option", { text: (DRAW_SPECS.draw_card || {}).label || "draw_card" })]);
  card.appendChild(el("div", { class: "fields" }, [
    labeled("シート名", el("span", { class: "name-gen" }, [sheet, genName])),
    labeled("グラフ種類", chart),
  ]));

  const specs = (DRAW_SPECS.draw_card || {}).params || [];
  const required = specs.filter(spec => spec.required);
  const optional = specs.filter(spec => !spec.required);
  if (required.length) {
    card.appendChild(el("div", { class: "params" }, required.map(spec => paramControl(node, spec))));
  }
  if (optional.length) {
    const more = el("details", { class: "more" }, [
      el("summary", { text: "詳細設定（" + optional.length + "）" }),
      el("div", { class: "params" }, optional.map(spec => paramControl(node, spec))),
    ]);
    if (node.moreOpen) more.setAttribute("open", "open");
    more.addEventListener("toggle", () => { node.moreOpen = more.open; drawKpiEdges(); });
    card.appendChild(more);
  }

  card.addEventListener("dragover", event => {
    if (!DRAG || DRAG.kind !== "kpi-node" || kpiContains(DRAG.node, node)) return;
    event.preventDefault();
    event.stopPropagation();
    clearDropMarks();
    card.classList.add(KPI_DROP_CLASSES[kpiDropMode(card, event, isRoot)]);
  });
  card.addEventListener("dragleave", () => {
    card.classList.remove("drop-top", "drop-bottom", "drop-into");
  });
  card.addEventListener("drop", event => {
    if (!DRAG || DRAG.kind !== "kpi-node" || kpiContains(DRAG.node, node)) return;
    event.preventDefault();
    event.stopPropagation();
    const mode = kpiDropMode(card, event, isRoot);
    clearDropMarks();
    moveKpiNode(DRAG.node, node, mode);
  });
  return card;
}

/* 1 ノード分を「自分のカード ＋ 子を縦に積んだ列」の横並びで描く。
   build_kpi_tree() がコンテナで組む構造と同じ形 */
function kpiSubtree(node, hasParent, numbers) {
  const add = el("button", { class: "kt-edge-add", title: "子を追加", text: "＋" });
  add.addEventListener("click", () => { node.children.push(newKpiNode()); renderKpiTree(); });
  const edge = el("div", { class: node.children.length ? "kt-edge-out" : "kt-edge-out kt-stub" }, [add]);
  /* 親から来る横線はカードと同じ行に入れる。揃え方を変えても必ずカードの縦の中心に来る */
  const wrap = [];
  if (hasParent) wrap.push(el("div", { class: "kt-edge-in" }));
  wrap.push(kpiNodeCard(node, numbers.get(node)), edge);

  const box = el("div", { class: "kt-subtree" }, [el("div", { class: "kt-node-wrap" }, wrap)]);
  if (!node.children.length) return box;
  const column = el("div", { class: "kt-children" });
  node.children.forEach((child, index) => {
    column.appendChild(el("div", { class: index === 0 ? "kt-child-row kt-first" : "kt-child-row" },
                          [kpiSubtree(child, true, numbers)]));
  });
  box.appendChild(column);
  return box;
}

/* 縦線を実測で引く。親カードの中心から、最初と最後の子カードの中心までを覆う。
   タブが非表示のあいだは大きさが 0 なので、タブを開いたときにも引き直す */
function drawKpiEdges() {
  document.querySelectorAll("#kt-root .kt-children").forEach(column => {
    const rows = Array.from(column.querySelectorAll(":scope > .kt-child-row"));
    if (!rows.length) return;
    const top0 = column.getBoundingClientRect().top;
    const centerOf = element => {
      const box = element.getBoundingClientRect();
      return box.top + box.height / 2 - top0;
    };
    const centers = rows.map(row => centerOf(row.querySelector(":scope > .kt-subtree > .kt-node-wrap")));
    const parentCenter = centerOf(column.parentElement.querySelector(":scope > .kt-node-wrap"));
    let line = column.querySelector(":scope > .kt-v-line");
    if (!line) {
      line = el("div", { class: "kt-v-line" });
      column.appendChild(line);
    }
    const top = Math.min(parentCenter, centers[0]);
    const bottom = Math.max(parentCenter, centers[centers.length - 1]);
    line.style.top = top + "px";
    line.style.height = Math.max(0, bottom - top) + "px";
    line.style.display = rows.length === 1 && Math.abs(bottom - top) < 1 ? "none" : "block";
  });
}

function renderKpiTree() {
  const root = document.getElementById("kt-root");
  root.innerHTML = "";
  root.classList.toggle("kt-align-top", KT.align === "top");
  if (!KT.root) {
    const start = el("button", { class: "act", text: "ルートのノードを作る" });
    start.addEventListener("click", () => { KT.root = newKpiNode(); renderKpiTree(); });
    root.appendChild(el("p", { class: "empty", text: "ノードがありません。" }));
    root.appendChild(start);
  } else {
    const numbers = new Map(kpiNodes(KT.root, []).map((node, index) => [node, index + 1]));
    root.appendChild(kpiSubtree(KT.root, false, numbers));
  }
  drawKpiEdges();
  renderKpiYaml();
}

function kpiNodeYaml(node, pad) {
  let out = pad + "sheet: " + yamlKey(node.sheet) + "\n";
  out += paramsYaml("draw_card", node.params, pad);
  if (node.children.length) {
    out += pad + "children:\n";
    node.children.forEach(child => {
      out += pad + "  - " + kpiNodeYaml(child, pad + "    ").slice(pad.length + 4);
    });
  }
  return out;
}

function kpiTreeYaml() {
  const value = id => document.getElementById(id).value.trim();
  const ds = DATA.datasources[ktDatasource()];
  let out = "kpi_tree:\n";
  out += "  name: " + yamlKey(value("kt-name")) + "\n";
  out += "  datasource: " + yamlKey(ds ? (ds.name || ds.id) : "") + "\n";
  out += "  align: " + yamlKey(KT.align) + "\n";
  if (!KT.root) return out;
  out += "  root:\n" + kpiNodeYaml(KT.root, "    ");
  return out;
}

function renderKpiYaml() {
  document.getElementById("kt-yaml").textContent = kpiTreeYaml();
}

function validateKpiTree() {
  if (!KT.root) return ["KPI ツリー: ノードがありません"];
  const errors = duplicateDashboardErrors(
    document.getElementById("kt-name").value.trim(), "KPI ツリー",
    DASH.rows.length ? document.getElementById("db-name").value.trim() : "", "ダッシュボードタブ");
  const edges = KT.align === "top";  // 受け手は上端揃えのときだけエッジを描く
  const required = ((DRAW_SPECS.draw_card || {}).params || []).filter(spec => spec.required);
  const sheets = [];
  kpiNodes(KT.root, []).forEach((node, index) => {
    const label = "KPI ツリー / ノード" + (index + 1);
    if (!node.sheet) errors.push(label + ": シート名が空");
    sheets.push([node.sheet, label]);
    required.forEach(spec => {
      if (!node.params[spec.name]) errors.push(label + ": " + (spec.label || spec.name) + " が未選択");
    });
    // 上端揃えでの最後の子の縦位置は 2 ×（それより前の子の末端数）。表の上限を超えると描けない
    if (edges && node.children.length) {
      const offset = 2 * node.children.slice(0, -1).reduce((sum, child) => sum + kpiLeafCount(child), 0);
      if (offset > KPI_EDGE_MAX_OFFSET) {
        errors.push(label + ": 配下の末端が多すぎてエッジを描けない（1 つの親の下は 7 つまで。中央揃えならエッジなしで作れる）");
      }
    }
  });
  errors.push.apply(errors, duplicateSheetErrors(sheets, dashboardSheetNames(null), "ダッシュボードタブ"));
  return errors;
}

document.getElementById("yaml-download-kpi-tree").addEventListener("click", () => {
  const errors = datasourceErrors();
  errors.push.apply(errors, validateKpiTree());
  downloadYaml("twbpatch_kpi_tree.yaml", errors, () =>
    yamlHeader(["design", "datasources", "kpi_tree"])
    + designYaml() + "\n" + datasourcesYaml() + "\n" + kpiTreeYaml());
});

ktDatasourceSelect.addEventListener("change", () => {
  const nodes = kpiNodes(KT.root, []);
  const chosen = nodes.some(node => Object.keys(node.params).length);
  if (chosen && !confirm("データソースを変えると、全ノードの項目の選択を消します。よいですか")) {
    ktDatasourceSelect.value = String(nodes[0].datasource);
    return;
  }
  nodes.forEach(node => {
    node.datasource = ktDatasource();
    node.params = defaultParamsFor("draw_card");
  });
  renderKpiTree();
});
document.querySelectorAll("#kt-align button").forEach(button => {
  button.addEventListener("click", () => {
    KT.align = button.dataset.align;
    document.querySelectorAll("#kt-align button").forEach(other => {
      other.classList.toggle("on", other === button);
    });
    renderKpiTree();
  });
});
document.getElementById("kt-name").addEventListener("input", renderKpiYaml);
/* 入力欄の変更（paramControl が値を書き込んだ後に届く）で YAML の表示を追う */
["input", "change"].forEach(type => {
  document.getElementById("kt-root").addEventListener(type, renderKpiYaml);
});
document.querySelector('nav button[data-tab="tab-kpi-tree"]').addEventListener("click", () => {
  requestAnimationFrame(drawKpiEdges);
});
renderKpiTree();
"""
