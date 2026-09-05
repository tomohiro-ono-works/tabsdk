from __future__ import annotations

from lxml import etree as ET

from .errors import DetachedModelError


class _UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _UnsetType()


class WorkbookContext:
    def __init__(self, tree: ET._ElementTree):
        self.tree = tree
        self.generation = 0
        self.revision = 0
        self.cache_epoch = 0
        self.is_dirty = False
        self.layout_weights: dict[tuple[str, str], float] = {}

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
