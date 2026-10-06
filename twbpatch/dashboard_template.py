"""Dashboard templates composed exclusively through the connected class API."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .dashboard_layout import DashboardLayout, TemplateCatalogEntry

DEFAULT_TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / 'template' / 'dashboard_template'

# Only static appearance and layout properties cross the workbook boundary.
_ATTRS = {'type-v2', 'type', 'param', 'fixed-size', 'is-fixed', 'layout-strategy-id',
          'is-centered', 'is-scaled', 'is-floating'}
_STYLES = {'background_color', 'border_color', 'border_style', 'border_width',
           'corner_radius', 'margin', 'padding', 'vertical_align', 'text_align',
           'font_family', 'font_size', 'font_color', 'font_weight'}
_STYLES |= {f'{side}_{edge}' for side in ('margin', 'padding', 'border')
            for edge in ('top', 'right', 'bottom', 'left')}
_LABELS = {'worksheet': 'グラフ', 'filter': 'フィルター', 'parameter_control': 'パラメーター'}


@dataclass
class LoadedDashboardTemplate:
    layout: DashboardLayout
    images: dict[str, bytes]


def _resolve(root: Path, key: str) -> Path:
    if not isinstance(key, str) or not key or key in {'.', '..'} or any(c in key for c in '/\\:'):
        raise ValueError('template key must be one folder name')
    root = Path(root).resolve()
    folder = (root / key).resolve()
    if not folder.is_relative_to(root):
        raise ValueError('template folder is outside template root')
    paths = [folder / name for name in ('template.twb', 'template.twbx') if (folder / name).is_file()]
    if len(paths) != 1 or not paths[0].resolve().is_relative_to(folder):
        raise ValueError(f'template {key}: exactly one template.twb or template.twbx is required')
    return paths[0]


def list_dashboard_templates(root: Path | None = None) -> list[TemplateCatalogEntry]:
    from .workbook import TwbWorkbook

    root = Path(root) if root is not None else DEFAULT_TEMPLATE_ROOT
    if not root.is_dir():
        return []
    catalog = []
    for folder in sorted(root.iterdir(), key=lambda p: p.name):
        if not folder.is_dir():
            continue
        try:
            workbook = TwbWorkbook._open_template(str(_resolve(root, folder.name)))
            dashboards = [{'id': dashboard.id, 'name': dashboard.name} for dashboard in workbook.get_dashboards()]
            if dashboards:
                catalog.append({'key': folder.name, 'dashboards': dashboards})
        except (OSError, ValueError):
            # Catalog discovery quietly omits malformed folders; apply reports input errors.
            continue
    return catalog


def load_dashboard_template(root: Path | None, key: str, dashboard_id: str | None) -> LoadedDashboardTemplate:
    from .workbook import TwbWorkbook

    workbook = TwbWorkbook._open_template(str(_resolve(root or DEFAULT_TEMPLATE_ROOT, key)))
    dashboards = workbook.get_dashboards()
    if dashboard_id is None or dashboard_id == '':
        if len(dashboards) != 1:
            raise ValueError(f'template {key}: select a dashboard')
        selected = dashboards[0]
    else:
        selected = next((dashboard for dashboard in dashboards if dashboard.id == dashboard_id), None)
        if selected is None:
            raise ValueError(f'template {key}: dashboard not found: {dashboard_id}')
    layout = selected.layout
    images = {}

    def normalize(original):
        node = deepcopy(original)
        kind = node['kind']
        node['attributes'] = {k: v for k, v in node.get('attributes', {}).items() if k in _ATTRS}
        node['style'] = {k: v for k, v in node.get('style', {}).items() if k in _STYLES}
        if kind in _LABELS:
            node['kind'] = 'text'
            node['attributes'] = {k: v for k, v in node['attributes'].items()
                                  if k in {'fixed-size', 'is-fixed', 'is-floating'}}
            node['attributes']['type-v2'] = 'text'
            node['style']['vertical_align'] = 'center'
            node['text_runs'] = [{'text': _LABELS[kind], 'dynamic': False,
                                 'style': {'fontname': 'Tableau Book', 'fontsize': '12',
                                           'fontcolor': '#333333', 'bold': 'false', 'fontalignment': '1'}}]
        elif kind == 'container':
            node['children'] = [value for child in node.get('children', []) if (value := normalize(child)) is not None]
        elif kind == 'text':
            node['attributes'].pop('param', None)
            node['text_runs'] = [run for run in node.get('text_runs', []) if not run.get('dynamic')]
        elif kind == 'image':
            reference = node.get('image_path', '')
            data = workbook._read_template_image(reference)
            extension = Path(reference).suffix.lower()
            if extension not in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.tif', '.tiff'}:
                extension = '.png'
            name = f'Images/template_{sha256(data).hexdigest()}{extension}'
            images[name] = data
            node['image_path'] = name
            node['attributes']['param'] = name
        elif kind != 'spacer':
            if node['placement'] == 'floating':
                return None
            node['kind'] = 'spacer'
            node['attributes'] = {k: v for k, v in node['attributes'].items() if k in {'fixed-size', 'is-fixed'}}
            node['attributes']['type-v2'] = 'empty'
            node['style'] = {'border_style': 'none', 'margin': '0', 'padding': '0'}
        return node

    layout['nodes'] = [value for node in layout['nodes'] if (value := normalize(node)) is not None]
    layout['viewpoints'] = {}
    layout['style'] = {element: {k: v for k, v in values.items() if k.replace('-', '_') in _STYLES}
                       for element, values in layout['style'].items() if element in {'dashboard', 'all'}}
    return LoadedDashboardTemplate(layout, images)
