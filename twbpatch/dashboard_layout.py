"""XML を含まない、ピクセル単位のダッシュボードレイアウト値。"""
from __future__ import annotations

from typing import TypedDict


class TextRun(TypedDict, total=False):
    text: str
    style: dict[str, str]
    dynamic: bool


class LayoutNode(TypedDict, total=False):
    kind: str
    x: float
    y: float
    width: float
    height: float
    placement: str
    attributes: dict[str, str]
    style: dict[str, str | int]
    children: list[LayoutNode]
    text_runs: list[TextRun]
    image_path: str


class DashboardLayout(TypedDict):
    width: float
    height: float
    size: dict[str, str]
    nodes: list[LayoutNode]
    style: dict[str, dict[str, str]]
    viewpoints: dict[str, dict[str, str]]


class TemplateSelection(TypedDict):
    key: str
    dashboard_id: str | None


class TemplateDashboardEntry(TypedDict):
    id: str
    name: str


class TemplateCatalogEntry(TypedDict):
    key: str
    dashboards: list[TemplateDashboardEntry]


def stack_dashboard_layouts(template: DashboardLayout, content: DashboardLayout | None) -> DashboardLayout:
    """Keep absolute pixel rectangles; combine tiled regions and floating overlays."""
    from copy import deepcopy

    if content is None:
        result = deepcopy(template)
        result['size'] = _fixed_size(result['width'], result['height'])
        return result
    width = max(template['width'], content['width'])
    height = template['height'] + content['height']

    def container(x, y, w, h, children, direction='vert'):
        return {'kind': 'container', 'placement': 'tiled', 'x': x, 'y': y,
                'width': w, 'height': h, 'attributes': {'type-v2': 'layout-flow', 'param': direction},
                'style': {'margin': '0', 'padding': '0', 'border_style': 'none'}, 'children': children}

    rows, overlays = [], []
    for layout, offset in ((template, 0), (content, template['height'])):
        nodes = deepcopy(layout['nodes'])
        def shift(node):
            node['y'] += offset
            for child in node.get('children', []):
                shift(child)
        for node in nodes:
            shift(node)
        tiled = [node for node in nodes if node['placement'] == 'tiled']
        overlays.extend(node for node in nodes if node['placement'] == 'floating')
        region = container(0, offset, layout['width'], layout['height'], tiled)
        for element in ('all', 'dashboard'):
            region['style'].update({key.replace('-', '_'): value
                                    for key, value in layout['style'].get(element, {}).items()})
        region['attributes'].update({'fixed-size': str(round(layout['width'])), 'is-fixed': 'true'})
        # A horizontal row fixes the region's width even when the other region is wider.
        row = container(0, offset, width, layout['height'], [region], 'horz')
        row['attributes'].update({'fixed-size': str(round(layout['height'])), 'is-fixed': 'true'})
        if layout['width'] < width:
            row['children'].append({'kind': 'spacer', 'placement': 'tiled',
                'x': layout['width'], 'y': offset, 'width': width - layout['width'],
                'height': layout['height'], 'attributes': {'type-v2': 'empty'},
                'style': {'margin': '0', 'padding': '0', 'border_style': 'none'}})
        rows.append(row)
    root = container(0, 0, width, height, rows)
    root['attributes'] = {'type-v2': 'layout-basic'}
    return {'width': width, 'height': height, 'size': _fixed_size(width, height),
            'nodes': [root, *overlays], 'style': deepcopy(content['style']),
            'viewpoints': deepcopy(content['viewpoints'])}


def _fixed_size(width: float, height: float) -> dict[str, str]:
    return {'sizing-mode': 'fixed', 'minwidth': str(round(width)), 'maxwidth': str(round(width)),
            'minheight': str(round(height)), 'maxheight': str(round(height))}
