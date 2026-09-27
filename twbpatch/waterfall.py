"""ウォーターフォールグラフの縦持ち変換（backlog は未起票、設計は会話で確定）。

ロードマップ: ①データソースへ 1=1 のクロスジョインでリレーションを追加 → ②指標を縦持ちに
変換 → ③ガントチャート指標を作成 → ④ウォーターフォールグラフを作成。

**①は `add_index_relation()` が担う（2026-09-22）。** 当初は「twbpatch では自動化できず
Tableau 側の手作業」と判断したが、それは誤り。twbpatch が組み立てられないのは
**`<extract>` の中身（.hyper のバイナリ）だけ**で、`<connection>` の物理リレーション・
`<object-graph>` の論理オブジェクトと `1=1` の `<relationship>` は、`examples/ウォーターフォール.twb`
の `edge.txt`（EC Orders データソースへの実際の追加）を実測した形をそのまま書けば足りる、
純粋な XML 操作。追加するテーブルもタブ区切りの .txt（`1, 2, 3, ...` の連番だけ）で、
これも twbpatch が直接書く。**`<extract>` にだけは触れない。** 追加した表を実際にクエリに
使うには、Tableau で開いて一度「データソースの更新」（抽出の更新）をする必要があるが、これは
抽出済みのデータソースへ表やリレーションを足したときに毎回要る通常の手順であって、
twbpatch 特有の制約ではない。

この module が担う②③: 選んだ指標の並び順に連番 1, 2, 3... を割り当てる（既定。
`connectors=True` は奇数番号だけに割り当て、偶数番号を値 0 の薄い連結線にする）。
値が 0 以上なら「増加」、負なら「減少」と動的に判定する。合計（終了）バーは作らない
（実測した手作業のシートには無かったため）が、`landing=True` で選んだ指標すべての
合計をマイナスで足し、累計を 0 まで戻す「着地」バーを最後に足せる（ユーザーの
手作業の例に合わせて追加、connectors とは別物）。③のガントバー用の `size`
（`-値`、符号反転）も同じ関数で作る。④の `build_waterfall_chart()` がワークシートを組む。
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree as ET

from .connected import TwbDatasource, TwbField, TwbFolder, _insert_field_column
from .connected_worksheet import TwbWorksheet
from .draw import _metric_aggregation, _metric_formula, _record_chart, _resolve_fields
from .errors import UnsupportedFeatureError
from .field_input import FieldInput
from .hyper_datasource import HyperField, _metadata_record, _tableau_id

if TYPE_CHECKING:
    from .workbook import TwbWorkbook


@dataclass
class WaterfallMetric:
    """`build_waterfall_metric()` が作る 4 つの計算フィールド。

    `count` は `metrics` に渡した指標の数。`used_index` は実際に使う連番の上限
    （`connectors=False` なら `count` と同じ、`True` なら奇数番号が指標・偶数番号が
    連結線で `2 * count - 1`）。`build_waterfall_chart()` が連番を `1..used_index` に
    絞るフィルタを作るのに使う（①の連番テーブルは `max_index` まで容量を持つが、
    `metrics` で使わなかった分は値が無い）。
    """

    value: TwbField
    label: TwbField
    kind: TwbField
    size: TwbField
    count: int
    used_index: int


def _quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _object_id(stem: str) -> str:
    """`object-graph` のオブジェクト id。`examples/ウォーターフォール.twb` の edge.txt が
    `edge.txt_4AC93E4E30104D68ADF32485C3BD8D99` の形（元の名前 + `_` + 32桁の16進数）
    だったのに合わせる。"""
    return f"{stem}_{secrets.token_hex(16).upper()}"


def _live_text_relation(
    parent: ET._Element, leaf: str, filename: str, table_id: str, fields: list[HyperField]
) -> ET._Element:
    """ライブのテキストファイル接続の `<relation>`。

    `create_hyper_datasource()` の `_text_relation()` は `name` に table（`stem#txt`）を
    使うが、それは抽出だけが実際に読まれる（テキスト側は形だけ）前提だから。
    こちらは①のとおりテキスト側が実際に読まれるので、`examples/ウォーターフォール.twb` の
    edge.txt を実測したとおり **`name` はファイル名（`edge.txt`）、`table` は `[edge#txt]`** と
    別にする。
    """
    relation = ET.SubElement(
        parent,
        "relation",
        attrib={"connection": leaf, "name": filename, "table": f"[{table_id}]", "type": "table"},
    )
    columns = ET.SubElement(
        relation,
        "columns",
        attrib={"character-set": "UTF-8", "header": "yes", "locale": "ja_JP", "separator": "\t"},
    )
    for ordinal, field in enumerate(fields):
        ET.SubElement(
            columns,
            "column",
            attrib={"datatype": field["datatype"], "name": field["name"], "ordinal": str(ordinal)},
        )
    return relation


def add_index_relation(
    workbook: TwbWorkbook,
    datasource: TwbDatasource,
    *,
    join_to: FieldInput,
    path: str,
    column: str = "連番",
    max_index: int = 20,
    folder: str | TwbFolder | None = None,
    overwrite: bool = False,
) -> TwbField:
    """①: 既存データソースへ、`column`（1〜`max_index` の整数）だけを持つ表を `1=1` で
    クロスジョインする。

    `path`（.twb からの相対、または絶対パス）へ新しいタブ区切りの .txt ファイルを書く
    （既存ファイルは既定では上書きしない。`overwrite=True` を渡すと上書きする——
    `build_waterfall()` が同じ内容のファイルへ複数回書く可能性があるため、2026-09-23 追加）。
    `join_to` は結合したい既存のロジカルテーブル側の
    フィールドを 1 つ渡す（抽出の `<cols>` マップから、そのフィールドがどのオブジェクトに
    属すかを引く）。`folder` を渡すとそのフォルダへ入れる（無ければ作る）。

    **`<extract>` には触れない。** 追加した表を実際に使うには、Tableau で開いて一度
    「データソースの更新」（抽出の更新）をする必要がある。抽出済みのデータソースへ表や
    リレーションを足したときに毎回要る通常の手順で、twbpatch 特有の制約ではない。

    `examples/ウォーターフォール.twb`（EC Orders データソースへの `edge.txt` の追加）を
    実測した形をそのまま書く。この形の datasource（`<connection class="federated">` +
    `<object-graph>` の関連モデル）以外は `UnsupportedFeatureError`。
    """
    if not isinstance(path, str) or not path.lower().endswith(".txt"):
        raise ValueError("path must be a .txt file")
    if not isinstance(max_index, int) or isinstance(max_index, bool) or max_index < 1:
        raise ValueError("max_index must be a positive integer")
    if not isinstance(column, str) or not column.strip() or "[" in column or "]" in column:
        raise ValueError(f"invalid column name: {column!r}")
    column = column.strip()

    [join_field] = _resolve_fields(workbook, [join_to], datasource)
    datasource_el = datasource._resolve_element()

    connection = datasource_el.find("./connection")
    if connection is None or connection.get("class") != "federated":
        raise UnsupportedFeatureError("datasource must use a federated connection")
    named_connections = connection.find("./named-connections")
    if named_connections is None:
        raise UnsupportedFeatureError("datasource must already declare named-connections")
    top_relation = connection.find("./relation")
    if top_relation is None or top_relation.get("type") != "collection":
        raise UnsupportedFeatureError("datasource's physical relation must be a collection")
    graph = datasource_el.find("./object-graph")
    if graph is None:
        raise UnsupportedFeatureError(
            "datasource must already use the relationships (object-graph) model"
        )
    objects = graph.find("./objects")
    if objects is None:
        raise UnsupportedFeatureError("object-graph must have objects")

    cols_map = datasource_el.xpath(
        "./extract/connection/cols/map[@key=$key]/@value", key=join_field.id
    )
    if not cols_map:
        raise UnsupportedFeatureError(
            "join_to field must be resolvable via the datasource's extract column map"
        )
    target_object_id = str(cols_map[0]).split(".", 1)[0].strip("[]")

    stem = path.replace("\\", "/").rsplit("/", 1)[-1]
    if stem.lower().endswith(".txt"):
        stem = stem[: -len(".txt")]
    if not stem or "[" in stem or "]" in stem:
        raise ValueError(f"unsupported .txt file name: {path}")
    if objects.xpath("./object[starts-with(@id, $prefix)]", prefix=f"{stem}_"):
        raise ValueError(f"relation already exists: {stem}")
    if datasource.get_fields(name=column):
        raise ValueError(f"field already exists: {column}")

    resolved_path = Path(path).resolve()
    previous_content: str | None = None
    if resolved_path.exists():
        if not overwrite:
            raise ValueError(f"file already exists: {path}")
        previous_content = resolved_path.read_text(encoding="utf-8")

    object_id = _object_id(stem)
    leaf = f"textscan.{_tableau_id()}"
    table_id = f"{stem}#txt"
    fields: list[HyperField] = [{"name": column, "datatype": "integer", "role": "dimension"}]

    # 検証はここまでで終わり。ここから先は失敗しない前提の組み立てだけにする
    # （原子性: XML を変える前に .txt を書き切っておき、書けなければ XML には触れない）。
    new_content = "\n".join([column, *(str(index) for index in range(1, max_index + 1))]) + "\n"
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    if new_content != previous_content:
        resolved_path.write_text(new_content, encoding="utf-8")

    try:
        named = ET.SubElement(
            named_connections, "named-connection", attrib={"caption": stem, "name": leaf}
        )
        directory = str(resolved_path.parent).replace("\\", "/")
        ET.SubElement(
            named,
            "connection",
            attrib={"class": "textscan", "directory": directory, "filename": resolved_path.name},
        )
        _live_text_relation(top_relation, leaf, resolved_path.name, table_id, fields)

        records = connection.find("./metadata-records")
        if records is not None:
            next_ordinal = len(records.findall("./metadata-record"))
            _metadata_record(
                records,
                fields[0],
                next_ordinal,
                parent_name=f"[{resolved_path.name}]",
                object_id=object_id,
                family=None,
            )

        graph_object = ET.SubElement(objects, "object", attrib={"caption": stem, "id": object_id})
        _live_text_relation(
            ET.SubElement(graph_object, "properties", attrib={"context": ""}),
            leaf,
            resolved_path.name,
            table_id,
            fields,
        )
        # Orders/People/edge.txt はどれも `context="extract"` の properties も持つ
        # （実測どおり）。無いと Tableau のリレーションシップ画面で未接続に見える
        # （2026-09-23、実際に確認した）。<extract> 自体（.hyper のバイナリ）には
        # 触れていないので、更新するまでは名前だけの宣言。
        ET.SubElement(
            ET.SubElement(graph_object, "properties", attrib={"context": "extract"}),
            "relation",
            attrib={"name": object_id, "table": f"[Extract].[{object_id}]", "type": "table"},
        )

        relationships = graph.find("./relationships")
        if relationships is None:
            relationships = ET.SubElement(graph, "relationships")
        relationship = ET.SubElement(relationships, "relationship")
        expression = ET.SubElement(relationship, "expression", attrib={"op": "="})
        ET.SubElement(expression, "expression", attrib={"op": "1"})
        ET.SubElement(expression, "expression", attrib={"op": "1"})
        ET.SubElement(relationship, "first-end-point", attrib={"object-id": target_object_id})
        ET.SubElement(relationship, "second-end-point", attrib={"object-id": object_id})

        _insert_field_column(
            datasource_el,
            ET.Element(
                "column",
                attrib={
                    "caption": column,
                    "datatype": "integer",
                    "name": f"[{column}]",
                    "role": "dimension",
                    "type": "ordinal",
                },
            ),
        )
    except Exception:
        # 新規に書いたファイルは削除、上書きしたファイルは元の内容へ戻す
        # （既存の他の用途のファイルを壊さないため）。
        if previous_content is None:
            resolved_path.unlink(missing_ok=True)
        elif new_content != previous_content:
            resolved_path.write_text(previous_content, encoding="utf-8")
        raise

    workbook._context.mark_dirty()
    field = TwbField(workbook._context, datasource.id, f"[{column}]")
    if folder is not None:
        field.move_to_folder(folder, create_folder_if_missing=True)
    return field


def _waterfall_used_index(count: int, connectors: bool, landing: bool) -> int:
    """`build_waterfall_metric()` が最終的に使う連番の上限（`WaterfallMetric.used_index`
    と同じ計算）を、指標数だけから前もって求める。`build_waterfall()` が共有の連番
    テーブルの容量を超えないか、計算フィールドを作る前に検証するために使う。"""
    last_item_position = (2 * count - 1) if connectors else count
    if not landing:
        return last_item_position
    return last_item_position + 2 if connectors else last_item_position + 1


def build_waterfall_metric(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    index: FieldInput,
    metrics: list[FieldInput],
    aggregation: str | None = "auto",
    folder: str | TwbFolder | None = None,
    connectors: bool = False,
    landing: bool = False,
) -> WaterfallMetric:
    """指標を縦持ちに変換する 4 つの計算フィールド（値・項目名・種別・サイズ）を作る。

    `index` は連番フィールド（既存データソースへ 1=1 のクロスジョインで足したもの、①は
    `add_index_relation()`）。既定（`connectors=False`）は `metrics` の並び順に
    1, 2, 3... を割り当てる。値が 0 以上なら「増加」、負なら「減少」と動的に判定する。
    `size`（`-値`）は③のガントバー用（2026-09-23、実測した手作業の例の符号反転に合わせる）。

    `connectors=True`（2026-09-23）は奇数番号（1, 3, 5, ...）だけに指標を割り当て、
    間の偶数番号（2, 4, ...）を値 0 の「連結」枠にする。値 0 の Gantt バーは長さが
    無いので、太さ（`mark_size`）だけの薄い横線に見える。種別は 0 のときだけ固定で
    `"連結"`、それ以外は符号で `"増加"`/`"減少"`。`build_waterfall_chart()` は
    `increase_color`/`decrease_color` に加えて `connector_color` をこの `"連結"` へ
    割り当てる。

    `landing=True`（2026-09-23）は最後にもう 1 枠（連番の続き）を足し、選んだ指標
    すべての合計を**マイナス**で入れる（`-<式1>-<式2>-...`）。累計がちょうど 0 まで
    戻る「着地」バーになる。項目名は固定で `"着地"`、種別も固定で `"着地"`
    （`connectors` の判定より先に見る）。②③で一度は「合計バーは作らない」とした
    ものだが、あちらは合計をプラスで足す「終了」だった。こちらはマイナスで着地させる
    別物として、要望を受けて追加した。
    `folder` を渡すと 4 つとも同じフォルダへ入れる（無ければ作る）。
    """
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("metrics must be a non-empty list")
    if not isinstance(connectors, bool):
        raise TypeError("connectors must be bool")
    if not isinstance(landing, bool):
        raise TypeError("landing must be bool")

    [index_field] = _resolve_fields(workbook, [index], datasource)
    metric_fields = _resolve_fields(workbook, metrics, datasource)
    if any(field.datasource_id != index_field.datasource_id for field in metric_fields):
        raise ValueError("index and metrics must belong to the same datasource")
    [datasource] = workbook.get_datasources(id=index_field.datasource_id)

    index_ref = f"[{index_field.name}]"
    expressions = [
        _metric_formula(field, _metric_aggregation(workbook, field, aggregation, "auto"))
        for field in metric_fields
    ]
    count = len(metric_fields)
    # connectors=True は奇数番号（1, 3, 5, ...）に指標を割り当て、間の偶数番号を
    # 値 0 の連結枠にする。connectors=False は今までどおり 1, 2, 3...。
    item_positions = (
        [2 * i - 1 for i in range(1, count + 1)] if connectors else list(range(1, count + 1))
    )
    last_item_position = item_positions[-1]
    connector_positions = list(range(2, last_item_position, 2)) if connectors else []
    # landing=True は最後の指標のさらに続き（connectors ありなら奇数を維持するため + 2）
    # へ着地バーを足す。間にも connectors なら連結枠を挟む。
    if landing:
        landing_position = last_item_position + 2 if connectors else last_item_position + 1
        if connectors:
            connector_positions.append(last_item_position + 1)
    else:
        landing_position = None
    used_index = _waterfall_used_index(count, connectors, landing)

    value_lines = [f"CASE ATTR({index_ref})"]
    for position, expression in zip(item_positions, expressions):
        value_lines.append(f"    WHEN {position} THEN {expression}")
    for position in connector_positions:
        value_lines.append(f"    WHEN {position} THEN 0")
    if landing:
        landing_expression = "".join(f"-{expression}" for expression in expressions)
        value_lines.append(f"    WHEN {landing_position} THEN {landing_expression}")
    value_lines.append("END")
    value = datasource.create_calculated_field(
        name=f"{name}_値",
        formula="\n".join(value_lines),
        datatype="real",
        role="measure",
        folder=folder,
        create_folder_if_missing=True,
    )

    # 項目名はディメンションなので ATTR() を付けない（実測どおり。値は集計が要る
    # メジャーなので ATTR() が要るが、項目名は行単位でそのまま評価する。
    # 2026-09-23、Tableau 上で ATTR() 付きのままだと不要だったと実機で確認・修正）。
    # 連結枠（偶数番号）は分岐を作らず NULL のまま（ラベルを出さない）。
    label_lines = [f"CASE {index_ref}"]
    for position, field in zip(item_positions, metric_fields):
        label_lines.append(f'    WHEN {position} THEN "{_quote(field.name)}"')
    if landing:
        label_lines.append(f'    WHEN {landing_position} THEN "着地"')
    label_lines.append("END")
    label = datasource.create_calculated_field(
        name=f"{name}_項目名",
        formula="\n".join(label_lines),
        datatype="string",
        role="dimension",
        folder=folder,
        create_folder_if_missing=True,
    )

    # 判定の優先順位: 着地（固定）→ 連結（値 0、connectors のときだけ）→ 符号。
    # 0 は「0 以上」にも当てはまるので、連結・着地を先に判定する。
    kind_lines = []
    if landing:
        kind_lines.append(f'IF ATTR({index_ref}) = {landing_position} THEN "着地"')
        branch = "ELSEIF"
    else:
        branch = "IF"
    if connectors:
        kind_lines.append(f'{branch} [{value.name}] = 0 THEN "連結"')
        kind_lines.append(f'ELSEIF [{value.name}] > 0 THEN "増加"')
    else:
        kind_lines.append(f'{branch} [{value.name}] >= 0 THEN "増加"')
    kind_lines.append('ELSE "減少"')
    kind_lines.append("END")
    kind_formula = "\n".join(kind_lines)
    kind = datasource.create_calculated_field(
        name=f"{name}_種別",
        formula=kind_formula,
        datatype="string",
        role="dimension",
        folder=folder,
        create_folder_if_missing=True,
    )

    size = datasource.create_calculated_field(
        name=f"{name}_サイズ",
        formula=f"-[{value.name}]",
        datatype="real",
        role="measure",
        folder=folder,
        create_folder_if_missing=True,
    )

    return WaterfallMetric(
        value=value, label=label, kind=kind, size=size, count=count, used_index=used_index
    )


#: `build_waterfall()`（設定画面向けの一括版）が使う共有の連番テーブルの列名・容量。
#: データソースにつき 1 つだけ作り、複数のウォーターフォールで使い回す
#: （2026-09-23、ユーザー承認）。21 は「指標 10 個 + connectors + landing」の
#: 最大構成（`2 * 10 - 1 + 2 = 21`）に合わせた固定値。超えたら `ValueError`。
_SHARED_INDEX_COLUMN = "連番"
_SHARED_INDEX_MAX = 21
#: 連番テーブルの .txt ファイル名。ワークブックを開いた元ファイルの隣に書く
#: （`add_index_relation()` 自体はファイルシステムへ即座に書き込む実装のため、
#: KPI ツリーの `.hyper` のような「保存時に動的配置」は使わない）。
_SHARED_INDEX_FILENAME = "twbpatch_waterfall_index.txt"


def build_waterfall(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    metrics: list[FieldInput],
    connectors: bool = False,
    landing: bool = False,
    increase_color: str = "#2f9e44",
    decrease_color: str = "#e03131",
    landing_color: str = "#4263eb",
    title: str | None = None,
    visible: bool = True,
    folder: str | TwbFolder | None = None,
) -> TwbWorksheet:
    """設定画面向け: ①〜④をまとめて 1 回で実行する。

    `add_index_relation()` / `build_waterfall_metric()` / `build_waterfall_chart()` を
    個別に呼ぶ代わりに、`metrics`（メジャーの複数選択）だけを受け取って組み上げる。

    **連番テーブルはデータソースにつき 1 つだけ作り、複数のウォーターフォールで
    使い回す**（2026-09-23、ユーザー承認の「共有テーブル方式」）。列名は固定で
    `"連番"`、容量は固定で `21`（指標 10 個 + connectors + landing の最大構成が
    ちょうど収まる数）。**計算フィールド（値・項目名・種別・サイズ）はウォーター
    フォールごとに個別に作る**（`name` で名前空間を分ける）。

    `connector_color`（連結線の色）は画面に出さない固定値 `#cccccc`。薄い線という
    位置づけで、色を変える需要が薄いため（2026-09-23、ユーザー承認）。
    """
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("metrics must be a non-empty list")
    if not isinstance(connectors, bool):
        raise TypeError("connectors must be bool")
    if not isinstance(landing, bool):
        raise TypeError("landing must be bool")

    metric_fields = _resolve_fields(workbook, metrics, datasource)
    if any(field.datasource_id != metric_fields[0].datasource_id for field in metric_fields):
        raise ValueError("metrics must belong to the same datasource")
    used_index = _waterfall_used_index(len(metric_fields), connectors, landing)
    if used_index > _SHARED_INDEX_MAX:
        raise ValueError(
            f"metrics is too long for the shared index table "
            f"(used_index={used_index} > {_SHARED_INDEX_MAX})"
        )
    [resolved_datasource] = workbook.get_datasources(id=metric_fields[0].datasource_id)

    existing = resolved_datasource.get_fields(name=_SHARED_INDEX_COLUMN)
    if existing:
        index_field = existing[0]
    else:
        # join_to は `<extract>` の cols マップに乗る物理フィールドでなければならない
        # （`add_index_relation()` の前提）。計算フィールドはマップに無いので使えない
        # （2026-09-23、実機で確認したバグ。metrics[0] が計算フィールドだと必ず
        # UnsupportedFeatureError になっていた）。metrics の中に無ければデータソース
        # 全体から探す。
        join_field = next((field for field in metric_fields if not field.is_calculated), None)
        if join_field is None:
            join_field = next(
                (field for field in resolved_datasource.get_fields() if not field.is_calculated),
                None,
            )
        if join_field is None:
            raise UnsupportedFeatureError(
                "datasource has no physical field to join the shared index table to"
            )
        directory = Path(workbook._parsed.source_path).resolve().parent
        txt_path = str(directory / _SHARED_INDEX_FILENAME)
        # overwrite=True: 同じ元ファイルへ繰り返し apply_config() をかけるワークフロー
        # （毎回 source を開き直し、別名で保存する）では、対象データソースには
        # 「連番」がまだ無いのに .txt だけ前回分が残っている状態になる。ファイルの
        # 中身は常に同じ（1..21）なので、上書きしてよい（2026-09-23、実機で確認した
        # バグ修正。「既にあるなら追加しない」は連番フィールドの有無で判定するので、
        # ファイルの重複だけを理由に別名へ逃げるのは筋が違うと指摘を受けた）。
        index_field = add_index_relation(
            workbook,
            resolved_datasource,
            join_to=join_field,
            path=txt_path,
            column=_SHARED_INDEX_COLUMN,
            max_index=_SHARED_INDEX_MAX,
            overwrite=True,
        )

    metric = build_waterfall_metric(
        workbook,
        resolved_datasource,
        name=name,
        index=index_field,
        metrics=metric_fields,
        connectors=connectors,
        landing=landing,
        folder=folder,
    )

    return build_waterfall_chart(
        workbook,
        resolved_datasource,
        name=name,
        index=index_field,
        metric=metric,
        increase_color=increase_color,
        decrease_color=decrease_color,
        connector_color="#cccccc",
        landing_color=landing_color,
        title=title,
        visible=visible,
    )


#: ガントバーの太さ。`examples/ウォーターフォール.twb` の手作業のシートから採った実測値。
_WATERFALL_BAR_SIZE = 1.9890055656433105


def build_waterfall_chart(
    workbook: TwbWorkbook,
    datasource: TwbDatasource | None = None,
    *,
    name: str,
    index: FieldInput,
    metric: WaterfallMetric,
    increase_color: str = "#2f9e44",
    decrease_color: str = "#e03131",
    connector_color: str = "#cccccc",
    landing_color: str = "#4263eb",
    title: str | None = None,
    visible: bool = True,
) -> TwbWorksheet:
    """④: ウォーターフォールグラフ本体。②③で作った `WaterfallMetric` を並べる。

    `index`（①の連番フィールド）を列へ、`metric.value`（値）を行へ `running_total=True` で
    置く。マークはガントチャート、色は `metric.kind`（"増加"/"減少"、`connectors=True` で
    作った場合は連結枠の "連結"、`landing=True` で作った場合は着地バーの "着地" も）、
    サイズは `metric.size`（`-値`）、ラベルは `metric.label`。`connector_color`/
    `landing_color` はそれぞれ "連結"/"着地" の色（`build_waterfall_metric` がその種類を
    作らなかった場合は使われない）。

    **列には `metric.label` を置かない**（2026-09-23、実機で確認して変更。当初は
    `examples/ウォーターフォール.twb` の手作業のシートに合わせて列へも置いていたが、
    `index` だけで列の位置は決まり、`metric.label` はラベルのマークだけで表示できる。
    列から外しても行の累計（`running_total` の `ordering-type="Rows"`）に影響は無い
    ——`ordering-type` は値を置いた `shelf`（`rows`）で決まり、列に何を置くかとは別のため）。

    見た目の細部（列ヘッダーの非表示・セル幅・回転したラベルなど）は実測した手作業の
    シートにあったが、ここでは組んでいない（2026-09-23。構造が先、見た目は後で足す）。
    """
    if not isinstance(metric, WaterfallMetric):
        raise TypeError("metric must be WaterfallMetric")
    index_field, label_field, value_field, kind_field, size_field = _resolve_fields(
        workbook,
        [index, metric.label, metric.value, metric.kind, metric.size],
        datasource,
    )
    if len({index_field.datasource_id, label_field.datasource_id, value_field.datasource_id,
            kind_field.datasource_id, size_field.datasource_id}) != 1:
        raise ValueError("index and metric fields must belong to the same datasource")

    worksheet = workbook.create_worksheet(name=name, visible=visible)
    if title is not None:
        worksheet.update(title=title)
    index_placement = worksheet.add_field(field=index_field, shelf="columns", discrete=True)
    # 連番の数字（1, 2, 3...）はバーの横位置を決めるためだけに置くので、見出しラベルは
    # 隠す（2026-09-23、ユーザーの指摘。ラベルのマークで項目名を出すので、軸の数字は
    # 見せる意味が無い。`examples/ウォーターフォール.twb` で実測した形）。
    worksheet._apply_field_header_display(index_placement, show=False)
    # 累計の計算対象は「特定のディメンション」で連番・項目名を明示する
    # （2026-09-23、実機で確認。列に置いていない項目名も対象にできる）。
    worksheet.add_field(
        field=value_field,
        shelf="rows",
        aggregation="agg",
        running_total=True,
        running_total_fields=[index_field, label_field],
    )
    # 連番テーブルは①の `max_index` まで容量を持つが、`metrics` で使わなかった分は
    # 値が NULL になるだけで残ってしまう（2026-09-23、実機で確認）。使った分だけに絞る。
    worksheet.add_filter(field=index_field)
    worksheet.get_filters()[0].update(
        values=[str(position) for position in range(1, metric.used_index + 1)]
    )

    pane = worksheet.get_panes()[0]
    pane.update(
        mark_type="gantt",
        mark_size=_WATERFALL_BAR_SIZE,
        label_style={"show": True, "cull": True},
    )
    kind_placement = pane.add_field(
        field=kind_field, encoding="color", aggregation="agg", discrete=True
    )
    pane.add_field(field=size_field, encoding="size", aggregation="agg", discrete=False)
    pane.add_field(field=label_field, encoding="label", discrete=True)
    pane.set_categorical_colors(
        kind_placement,
        {
            "増加": increase_color,
            "減少": decrease_color,
            "連結": connector_color,
            "着地": landing_color,
        },
    )

    return _record_chart(workbook, worksheet, "build_waterfall_chart")
