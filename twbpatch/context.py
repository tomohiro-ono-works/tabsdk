from __future__ import annotations

import copy

from lxml import etree as ET

from .errors import DetachedModelError


def xml_equal(left: ET._Element, right: ET._Element) -> bool:
    """2 つの要素が同じ XML かを比べる。

    `ET.tostring()` の結果は要素がツリーに繋がっているかで変わる。繋がっている
    要素は非 ASCII を 16 進の文字参照（`&#x58F2;`）で、`copy.deepcopy()` で
    切り離した要素は 10 進（`&#22770;`）で出力するため、中身が同じでもバイト列が
    一致しない。`encoding="unicode"` でも解消しない（実測 2026-09-07）。

    更新処理は「元の要素」と「deepcopy して書き換えた要素」を比べるので、
    日本語を含むワークブックではほぼ全ての比較が「変更あり」になり、
    `is_dirty` が保存要否の指標として使えなくなっていた。

    両辺を deepcopy して出力形式を揃えることで比較を成立させる。
    """
    return ET.tostring(copy.deepcopy(left)) == ET.tostring(copy.deepcopy(right))


class _UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _UnsetType()


def validate_style_group(
    argument: str,
    value: object,
    allowed_keys: frozenset[str] | None = None,
) -> dict | _UnsetType:
    """`update()` が受け取る属性グループを検証して dict へ正規化する。

    `allowed_keys` が None のときはキー集合が開いているグループとして、
    キー名が文字列であることだけを確認する。
    """
    if value is UNSET:
        return UNSET
    if not isinstance(value, dict):
        raise TypeError(f"{argument} must be a dict")
    for key in value:
        if not isinstance(key, str):
            raise TypeError(f"{argument} keys must be strings")
        if allowed_keys is not None and key not in allowed_keys:
            expected = ", ".join(sorted(allowed_keys))
            raise ValueError(f"unknown {argument} key: {key} (expected: {expected})")
    return dict(value)


class WorkbookContext:
    def __init__(self, tree: ET._ElementTree):
        self.tree = tree
        self.generation = 0
        self.revision = 0
        self.cache_epoch = 0
        self.is_dirty = False
        self.layout_weights: dict[tuple[str, str], float] = {}
        self.pending_image_assets: dict[str, bytes] = {}
        #: `draw_*()` が描いたワークシート名 → 関数名。ダッシュボードへ置くときの
        #: 余白をグラフごとに変えるために使う（2026-09-21）。.twb には残らないので、
        #: 開き直した後や手で作ったシートでは既定の余白になる。
        self.chart_kinds: dict[str, str] = {}
        #: 帳票のシート名 → (行に置いた項目のピルの参照, 棒・色帯の列の見出し)
        #: （2026-09-22）。参照で持つのは、同じメジャーが行にも列にも居ると
        #: 表示名では一意に決まらないため。
        #: **Tableau は行に置いた項目の名前は出すが、棒・色帯の列の名前だけ出さない。**
        #: その消えている分を `build_report()` が浮動テキストで補うのに使う。
        #: 列幅はゾーンの幅を列数で割って決めるので、ここでは名前だけ覚える。
        self.sheet_columns: dict[str, tuple[list[str], list[str]]] = {}

    def mark_dirty(self) -> None:
        self.revision += 1
        self.is_dirty = True

    def mark_saved(self) -> None:
        self.is_dirty = False

    def invalidate_caches(self) -> None:
        self.cache_epoch += 1

    def replace_tree(self, tree: ET._ElementTree) -> None:
        self.tree = tree
        self.generation += 1
        self.revision += 1
        self.is_dirty = False
        self.layout_weights.clear()
        self.pending_image_assets.clear()
        self.chart_kinds.clear()
        self.sheet_columns.clear()


class ConnectedModel:
    def __init__(self, context: WorkbookContext):
        self._context = context
        self._generation = context.generation
        self._is_detached = False

    def _ensure_attached(self) -> None:
        if self._is_detached or self._generation != self._context.generation:
            raise DetachedModelError("model is detached; acquire it again with get_*()")

    def _detach(self) -> None:
        self._is_detached = True
