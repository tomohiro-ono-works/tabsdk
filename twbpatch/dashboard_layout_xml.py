"""接続型 Dashboard の内部 XML アダプター。高水準 API からは利用しない。"""
from __future__ import annotations

import math
from copy import deepcopy

from lxml import etree as ET

from .context import WorkbookContext
from .dashboard_layout import DashboardLayout, LayoutNode

_ATTRIBUTES = frozenset({
    'type-v2', 'type', 'param', 'name', 'friendly-name', 'fixed-size', 'is-fixed',
    'layout-strategy-id', 'show-title', 'show-caption', 'can-show-title',
    'is-centered', 'is-scaled', 'is-floating', 'mode', 'show-apply', 'value',
    'show-clear', 'show-none', 'show-all', 'show-context', 'show-search',
    'show-filter', 'show-highlighter', 'show-navigation', 'forceUpdate',
})
_RUN_STYLE = frozenset({'fontname', 'fontfamily', 'fontcolor', 'fontsize', 'bold',
                         'italic', 'underline', 'fontalignment'})


def read_dashboard_layout(context: WorkbookContext, dashboard: ET._Element) -> DashboardLayout:
    from .connected_dashboard import (
        _default_zones, _direct_child, _direct_zones, _local_name, _zone_kind,
        _zone_style_values, _worksheet_names,
        _ZOOM_TYPE,
    )
    size = _direct_child(dashboard, 'size')
    size_attrs = dict(size.attrib) if size is not None else {'sizing-mode': 'automatic'}
    width = float(size_attrs.get('maxwidth') or size_attrs.get('minwidth') or 1200)
    height = float(size_attrs.get('maxheight') or size_attrs.get('minheight') or 800)
    known = _worksheet_names(context)
    def style_rules(element):
        result = {}
        style = _direct_child(element, 'style')
        if style is not None:
            for rule in style:
                if rule.get('element'):
                    result[rule.get('element')] = {item.get('attr'): item.get('value', '')
                        for item in rule if item.get('attr') and item.get('value') is not None}
        return result

    styles = {}
    global_rules = style_rules(context.tree.getroot())
    if 'all' in global_rules:
        styles['all'] = global_rules['all']
    for element, values in style_rules(dashboard).items():
        styles.setdefault(element, {}).update(values)
    inherited = {}
    for element in ('all', 'dashboard', 'text'):
        inherited.update(styles.get(element, {}))

    def run_style(zone):
        effective = dict(inherited)
        effective.update({key.replace('_', '-'): value for key, value in _zone_style_values(zone).items()})
        result = {'fontname': effective.get('font-family', 'Tableau Book'),
                  'fontsize': effective.get('font-size', '12'),
                  'fontcolor': effective.get('font-color', '#333333'),
                  'bold': 'true' if effective.get('font-weight') == 'bold' else 'false',
                  'italic': 'true' if effective.get('font-style') == 'italic' else 'false',
                  'underline': 'true' if effective.get('text-decoration') == 'underline' else 'false',
                  'fontalignment': {'left': '0', 'center': '1', 'right': '2'}.get(effective.get('text-align'), '0')}
        return result

    def read(zone, top=False):
        kind = _zone_kind(zone, known)
        attrs = {key: value for key, value in zone.attrib.items() if key in _ATTRIBUTES}
        attrs.pop('forceUpdate', None)
        node: LayoutNode = {
            'kind': kind, 'x': float(zone.get('x', '0')) * width / 100000,
            'y': float(zone.get('y', '0')) * height / 100000,
            'width': float(zone.get('w', '100000')) * width / 100000,
            'height': float(zone.get('h', '100000')) * height / 100000,
            'placement': 'floating' if top and (kind != 'container' or zone.get('is-floating') == 'true') else 'tiled',
            'attributes': attrs, 'style': _zone_style_values(zone),
        }
        if kind == 'container':
            node['children'] = [read(child) for child in _direct_zones(zone)]
        if kind == 'text':
            runs = []
            formatted = _direct_child(zone, 'formatted-text')
            if formatted is not None:
                for run in formatted:
                    if _local_name(run) != 'run':
                        continue
                    style = run_style(zone)
                    style.update({key: value for key, value in run.attrib.items() if key in _RUN_STYLE})
                    # A run may contain static text on both sides of a dynamic field/cache.
                    if run.text:
                        runs.append({'text': run.text, 'style': dict(style), 'dynamic': False})
                    for child in run:
                        runs.append({'text': ''.join(child.itertext()), 'style': dict(style), 'dynamic': True})
                        if child.tail:
                            runs.append({'text': child.tail, 'style': dict(style), 'dynamic': False})
                    if not run.text and not len(run):
                        runs.append({'text': '', 'style': style, 'dynamic': False})
            node['text_runs'] = runs
        if kind == 'image':
            node['image_path'] = zone.get('param') or zone.get('filename') or ''
        return node

    zones = _default_zones(dashboard)
    viewpoints = {
        zone.get('name'): {'type': _ZOOM_TYPE(context, zone.get('name'))}
        for zone in ([] if zones is None else zones.iter('zone'))
        if _zone_kind(zone, known) == 'worksheet'
    }
    for view in context.tree.xpath('/workbook/windows/window[@class="dashboard"][@name=$name]/viewpoints/viewpoint', name=dashboard.get('name')):
        zoom = _direct_child(view, 'zoom')
        if zoom is not None:
            viewpoints[view.get('name', '')] = dict(zoom.attrib)
    return {'width': width, 'height': height, 'size': size_attrs,
            'nodes': [] if zones is None else [read(zone, True) for zone in _direct_zones(zones)],
            'style': styles, 'viewpoints': viewpoints}


def write_dashboard_layout(context: WorkbookContext, dashboard: ET._Element, layout: DashboardLayout) -> None:
    from .connected_dashboard import _default_zones, _direct_child, _px_to_raw, _set_zone_styles, _worksheet_names
    if not isinstance(layout, dict):
        raise TypeError('layout must be a dict')
    width, height = layout.get('width'), layout.get('height')
    for name, value in (('width', width), ('height', height)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'layout {name} must be positive and finite')
    nodes = layout.get('nodes')
    if not isinstance(nodes, list):
        raise TypeError('layout nodes must be a list')
    if sum(node.get('kind') == 'container' and node.get('placement') == 'tiled' for node in nodes) > 1:
        raise ValueError('layout may have only one tiled root')
    known = _worksheet_names(context)
    next_id = 0

    def build(node):
        nonlocal next_id
        next_id += 1
        attrs = node.get('attributes', {})
        if not isinstance(attrs, dict) or any(key not in _ATTRIBUTES for key in attrs):
            raise ValueError('unknown layout node attributes')
        if any(not isinstance(value, str) for value in attrs.values()):
            raise TypeError('layout attributes must be strings')
        attrs = dict(attrs)
        kind = node.get('kind')
        if kind == 'worksheet' and attrs.get('name') not in known:
            raise ValueError(f'layout references missing worksheet: {attrs.get("name")}')
        if node.get('placement') not in {'tiled', 'floating'}:
            raise ValueError('layout placement must be tiled or floating')
        attrs['id'] = str(next_id)
        for key, raw, canvas in (('x', 'x', width), ('y', 'y', height), ('width', 'w', width), ('height', 'h', height)):
            value = node.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'layout node {key} must be nonnegative and finite')
            attrs[raw] = str(_px_to_raw(value, canvas))
        if kind == 'container':
            if attrs.get('type-v2', attrs.get('type')) not in {'layout-basic', 'layout-flow'}:
                raise ValueError('layout container needs a container type')
            if node['placement'] == 'floating':
                attrs['is-floating'] = 'true'
            else:
                attrs.pop('is-floating', None)
        elif kind in {'text', 'image', 'spacer'}:
            attrs['type-v2'] = {'text': 'text', 'image': 'bitmap', 'spacer': 'empty'}[kind]
        zone = ET.Element('zone', attrib=attrs)
        if kind == 'text':
            zone.set('forceUpdate', 'true')
            formatted = ET.SubElement(zone, 'formatted-text')
            for run in node.get('text_runs', []):
                style = run.get('style', {})
                if not isinstance(style, dict) or any(key not in _RUN_STYLE for key in style):
                    raise ValueError('unknown text run style')
                # Dynamic references are not representable as static text on apply.
                if not run.get('dynamic'):
                    ET.SubElement(formatted, 'run', attrib=dict(style)).text = run.get('text', '')
        if kind == 'image':
            zone.set('param', node.get('image_path', ''))
        for child in node.get('children', []):
            zone.append(build(child))
        _set_zone_styles(zone, node.get('style', {}), context)
        return zone

    new_zones = ET.Element('zones')
    for node in nodes:
        new_zones.append(build(node))
    size_attrs = layout.get('size', {})
    if not isinstance(size_attrs, dict) or any(key not in {'sizing-mode', 'minwidth', 'maxwidth', 'minheight', 'maxheight'} for key in size_attrs):
        raise ValueError('unknown layout size attributes')
    size = _direct_child(dashboard, 'size')
    if size is not None:
        dashboard.remove(size)
    dashboard.insert(0, ET.Element('size', attrib=dict(size_attrs)))
    old_zones = _default_zones(dashboard)
    if old_zones is not None:
        dashboard.replace(old_zones, new_zones)
    else:
        dashboard.append(new_zones)
    old_style = _direct_child(dashboard, 'style')
    if old_style is not None:
        dashboard.remove(old_style)
    if layout.get('style'):
        style = ET.Element('style')
        for element, formats in layout['style'].items():
            rule = ET.SubElement(style, 'style-rule', attrib={'element': element})
            for attr, value in formats.items():
                ET.SubElement(rule, 'format', attrib={'attr': attr, 'value': value})
        dashboard.insert(0, style)


def restore_layout_viewpoints(context: WorkbookContext, dashboard_id: str, layout: DashboardLayout) -> None:
    for view in context.tree.xpath('/workbook/windows/window[@name=$name]/viewpoints/viewpoint', name=dashboard_id):
        value = layout.get('viewpoints', {}).get(view.get('name'))
        if value:
            old = view.find('zoom')
            if old is not None:
                view.remove(old)
            ET.SubElement(view, 'zoom', attrib=deepcopy(value))
