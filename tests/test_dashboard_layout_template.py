from __future__ import annotations

import copy
import zipfile

import pytest
from lxml import etree as ET

from twbpatch import TwbWorkbook


def _nodes(layout):
    for node in layout['nodes']:
        yield node
        yield from _nodes({'nodes': node.get('children', [])})


def _layout_workbook(tmp_path):
    path = tmp_path / 'layout.twb'
    path.write_text('''<workbook><worksheets><worksheet name="SourceSheet"/></worksheets>
    <dashboards><dashboard name="Source"><size sizing-mode="fixed" minwidth="1000"
    maxwidth="1000" minheight="200" maxheight="200"/><zones>
      <zone id="7" type-v2="layout-basic" x="0" y="0" w="100000" h="100000">
        <zone id="8" type-v2="layout-flow" param="horz" x="0" y="0" w="100000" h="100000">
          <zone id="9" type-v2="text" x="0" y="0" w="30000" h="100000" fixed-size="300" is-fixed="true">
            <formatted-text><run bold="true" fontcolor="#112233" fontsize="18">Header</run><run italic="true" fontsize="12"> suffix</run></formatted-text>
            <zone-style><format attr="background-color" value="#ffeedd"/><format attr="margin" value="6"/></zone-style>
          </zone>
          <zone id="10" name="SourceSheet" x="30000" y="0" w="70000" h="100000" show-title="false"/>
        </zone>
      </zone>
      <zone id="11" type-v2="text" x="1000" y="5000" w="20000" h="10000"><formatted-text><run>Floating</run></formatted-text></zone>
    </zones></dashboard></dashboards></workbook>''', encoding='utf-8')
    return TwbWorkbook.open(str(path))


def test_layout_roundtrip_preserves_geometry_and_styles(tmp_path):
    workbook = _layout_workbook(tmp_path)
    source = workbook.get_dashboards(id='Source')[0]
    layout = source.layout
    header = next(n for n in _nodes(layout) if n.get('text_runs', [{}])[0].get('text') == 'Header')
    assert (layout['width'], layout['height']) == (1000, 200)
    assert (header['x'], header['y'], header['width'], header['height']) == (0, 0, 300, 200)
    assert header['style']['background_color'] == '#ffeedd'
    assert header['text_runs'][0]['style']['bold'] == 'true'
    target = workbook.create_dashboard(name='Target')
    target.update(layout=layout)
    assert target.layout == layout
    assert len(target.get_containers()) == 1
    layout['nodes'].clear()
    assert source.layout['nodes']


def test_styled_nested_layout_saves_with_validation(tmp_path):
    source = _layout_workbook(tmp_path).get_dashboards()[0].layout
    source['nodes'][0]['style'] = {'background_color': '#ffffff', 'margin': '8'}
    source['nodes'][0]['children'][0]['style'] = {'background_color': '#eeeeee', 'padding': '4'}
    workbook = TwbWorkbook.open('tests/sample_minimal.twb')
    workbook.create_worksheet(name='SourceSheet')
    target = workbook.create_dashboard(name='Nested layout')
    target.update(layout=source)
    assert [m.code for m in workbook.validate() if m.severity == 'error'] == []
    output = tmp_path / 'nested.twb'
    workbook.save(str(output))
    assert TwbWorkbook.open(str(output)).get_dashboards()[0].layout == target.layout


def test_layout_roundtrip_preserves_generated_references(tmp_path):
    workbook = _layout_workbook(tmp_path)
    source = workbook.get_dashboards(id='Source')[0]
    target = workbook.create_dashboard(name='Target')
    target.update(layout=source.layout)
    assert [sheet.id for sheet in target.get_worksheets()] == ['SourceSheet']
    zone = next(zone for zone in target.get_zones() if zone.kind == 'worksheet')
    assert zone.attrs['show-title'] == 'false'
    assert workbook.tree.xpath('/workbook/windows/window[@name="Target"]/viewpoints/viewpoint/@name') == ['SourceSheet']


def test_layout_roundtrip_preserves_floating_nodes(tmp_path):
    workbook = _layout_workbook(tmp_path)
    target = workbook.create_dashboard(name='Target')
    target.update(layout=workbook.get_dashboards(id='Source')[0].layout)
    floating = next(n for n in _nodes(target.layout) if n['placement'] == 'floating')
    assert (floating['x'], floating['y'], floating['width'], floating['height']) == (10, 10, 200, 20)
    assert floating['text_runs'][0]['text'] == 'Floating'


def test_layout_preserves_floating_container_and_window_active_sheet(tmp_path):
    workbook = _layout_workbook(tmp_path)
    layout = workbook.get_dashboards()[0].layout
    floating = copy.deepcopy(layout['nodes'][0])
    floating['placement'] = 'floating'
    layout['nodes'] = [floating, *layout['nodes'][1:]]
    target = workbook.create_dashboard(name='Floating container')
    target.update(layout=layout)
    assert target.layout['nodes'][0]['placement'] == 'floating'
    control = {'kind': 'filter', 'placement': 'floating', 'x': 0, 'y': 0,
               'width': 40, 'height': 20, 'attributes': {'type-v2': 'filter', 'name': 'SourceSheet'}, 'style': {}}
    layout['nodes'].insert(0, control)
    target.update(layout=layout)
    active = workbook.tree.xpath('/workbook/windows/window[@name="Floating container"]/active/@id')[0]
    assert target.get_zones(id=active)[0].kind == 'worksheet'


def test_invalid_layout_does_not_mutate_dashboard(tmp_path):
    workbook = _layout_workbook(tmp_path)
    dashboard = workbook.get_dashboards(id='Source')[0]
    layout = dashboard.layout
    next(n for n in _nodes(layout) if n['kind'] == 'worksheet')['attributes']['name'] = 'MissingSheet'
    before = ET.tostring(workbook.tree)
    with pytest.raises(ValueError, match='MissingSheet'):
        dashboard.update(layout=layout)
    assert ET.tostring(workbook.tree) == before


def test_layout_rejects_invalid_canvas_and_multiple_roots(tmp_path):
    workbook = _layout_workbook(tmp_path)
    dashboard = workbook.get_dashboards(id='Source')[0]
    layout = dashboard.layout
    layout['width'] = 0
    with pytest.raises(ValueError):
        dashboard.update(layout=layout)
    layout = dashboard.layout
    layout['nodes'].append(copy.deepcopy(layout['nodes'][0]))
    with pytest.raises(ValueError, match='root'):
        dashboard.update(layout=layout)


def _template_root(tmp_path, workbook=None):
    root = tmp_path / 'templates'
    folder = root / 'sales'
    folder.mkdir(parents=True)
    source = workbook or _layout_workbook(tmp_path)
    source.save(str(folder / 'template.twb'), validate=False)
    return root


def test_template_replaces_data_controls_with_labels(tmp_path):
    from twbpatch.dashboard_template import load_dashboard_template
    workbook = _layout_workbook(tmp_path)
    dashboard = workbook.tree.find('.//dashboard')
    zones = dashboard.find('zones')
    for kind in ('filter', 'paramctrl', 'color'):
        ET.SubElement(zones, 'zone', attrib={'type-v2': kind, 'name': 'SourceSheet',
                      'param': '[ds].[secret]', 'x': '1000', 'y': '5000', 'w': '20000', 'h': '10000'})
    layout = load_dashboard_template(_template_root(tmp_path, workbook), 'sales', None).layout
    labels = {n['text_runs'][0]['text']: n for n in _nodes(layout) if n.get('text_runs')}
    for label in ('グラフ', 'フィルター', 'パラメーター'):
        assert label in labels
        assert labels[label]['style']['vertical_align'] == 'center'
        assert labels[label]['text_runs'][0]['style']['fontalignment'] == '1'
        assert not labels[label]['text_runs'][0]['style'].get('bold') == 'true'
    assert (labels['グラフ']['x'], labels['グラフ']['width']) == (300, 700)
    assert not layout['viewpoints']
    assert 'SourceSheet' not in repr(layout)
    assert 'secret' not in repr(layout)


def test_template_excludes_legend_actions_and_dynamic_references(tmp_path):
    from twbpatch.dashboard_template import load_dashboard_template
    workbook = _layout_workbook(tmp_path)
    container = workbook.tree.find('.//zone/zone')
    ET.SubElement(container, 'zone', attrib={'type-v2': 'color', 'name': 'SourceSheet',
                                           'x': '0', 'y': '0', 'w': '10000', 'h': '10000'})
    run = workbook.tree.find('.//run')
    ET.SubElement(run, 'field', attrib={'name': '[secret]'}).text = 'cached-value'
    run[-1].tail = ' static suffix'
    layout = load_dashboard_template(_template_root(tmp_path, workbook), 'sales', None).layout
    assert 'cached-value' not in repr(layout)
    assert 'secret' not in repr(layout)
    assert any(n['kind'] == 'spacer' for n in _nodes(layout))
    assert any('static suffix' in r['text'] for n in _nodes(layout) for r in n.get('text_runs', []))


def test_template_preserves_inherited_static_text_style(tmp_path):
    from twbpatch.dashboard_template import load_dashboard_template
    workbook = _layout_workbook(tmp_path)
    style = ET.SubElement(workbook.tree.getroot(), 'style')
    rule = ET.SubElement(style, 'style-rule', attrib={'element': 'all'})
    for attr, value in [('font-family', 'Source Font'), ('font-size', '22'), ('font-color', '#abcdef')]:
        ET.SubElement(rule, 'format', attrib={'attr': attr, 'value': value})
    layout = load_dashboard_template(_template_root(tmp_path, workbook), 'sales', None).layout
    floating = next(n for n in _nodes(layout) if n['placement'] == 'floating')
    style = floating['text_runs'][0]['style']
    assert style['fontname'] == 'Source Font'
    assert style['fontsize'] == '22'
    assert style['fontcolor'] == '#abcdef'


def test_template_default_typography_isolated_from_target_defaults(tmp_path):
    from twbpatch.dashboard_template import load_dashboard_template
    from twbpatch.dashboard_layout import stack_dashboard_layouts
    template = load_dashboard_template(_template_root(tmp_path), 'sales', None)
    target = _layout_workbook(tmp_path)
    rule = ET.SubElement(ET.SubElement(target.tree.getroot(), 'style'), 'style-rule', attrib={'element': 'all'})
    for attr, value in [('font-weight', 'bold'), ('font-style', 'italic'), ('text-align', 'center')]:
        ET.SubElement(rule, 'format', attrib={'attr': attr, 'value': value})
    content = target.get_dashboards()[0].layout
    dashboard = target.create_dashboard(name='Combined')
    dashboard.update(layout=stack_dashboard_layouts(template.layout, content))
    floating = next(n for n in dashboard.layout['nodes'] if n['placement'] == 'floating')
    style = floating['text_runs'][0]['style']
    assert style['bold'] == 'false'
    assert style['italic'] == 'false'
    assert style['fontalignment'] == '0'


def test_catalog_and_dashboard_selection(tmp_path):
    from twbpatch.dashboard_template import list_dashboard_templates, load_dashboard_template
    workbook = _layout_workbook(tmp_path)
    workbook.create_dashboard(name='Second')
    root = _template_root(tmp_path, workbook)
    entries = list_dashboard_templates(root)
    assert entries[0]['key'] == 'sales'
    assert [d['id'] for d in entries[0]['dashboards']] == ['Source', 'Second']
    with pytest.raises(ValueError, match='dashboard'):
        load_dashboard_template(root, 'sales', None)
    assert load_dashboard_template(root, 'sales', 'Source').layout['width'] == 1000
    with pytest.raises(ValueError, match='Missing'):
        load_dashboard_template(root, 'sales', 'Missing')
    (root / 'sales' / 'template.twbx').write_bytes(b'bad')
    assert list_dashboard_templates(root) == []


@pytest.mark.parametrize('key', ['../sales', '/sales', 'a/b', 'a\\b', '..', 'C:foo'])
def test_template_rejects_outside_paths(tmp_path, key):
    from twbpatch.dashboard_template import load_dashboard_template
    with pytest.raises(ValueError):
        load_dashboard_template(tmp_path, key, None)


def test_twbx_reads_only_required_assets(tmp_path, monkeypatch):
    from twbpatch.dashboard_template import load_dashboard_template
    workbook = _layout_workbook(tmp_path)
    zones = workbook.tree.find('.//dashboard/zones')
    ET.SubElement(zones, 'zone', attrib={'type-v2': 'bitmap', 'param': 'images/logo.png',
                                      'x': '0', 'y': '0', 'w': '10000', 'h': '10000'})
    root = tmp_path / 'templates'
    folder = root / 'sales'
    folder.mkdir(parents=True)
    archive = folder / 'template.twbx'
    with zipfile.ZipFile(archive, 'w') as package:
        package.writestr('workbook/source.twb', ET.tostring(workbook.tree))
        package.writestr('workbook/images/logo.png', b'image-bytes')
        package.writestr('Data/source.hyper', b'never-read')
    reads = []
    original = zipfile.ZipFile.read
    def read(package, name, *args, **kwargs):
        reads.append(name)
        return original(package, name, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, 'read', read)
    result = load_dashboard_template(root, 'sales', None)
    assert list(result.images.values()) == [b'image-bytes']
    assert 'Data/source.hyper' not in reads
    assert next(n for n in _nodes(result.layout) if n['kind'] == 'image')['image_path'] in result.images
    with zipfile.ZipFile(archive, 'a') as package:
        package.writestr('second.twb', b'<workbook/>')
    with pytest.raises(ValueError, match='one|1'):
        load_dashboard_template(root, 'sales', None)


@pytest.mark.parametrize('reference', ['missing.png', '../outside.png', 'C:\\outside.png'])
def test_missing_required_image_fails(tmp_path, reference):
    from twbpatch.dashboard_template import load_dashboard_template
    workbook = _layout_workbook(tmp_path)
    ET.SubElement(workbook.tree.find('.//dashboard/zones'), 'zone',
                  attrib={'type-v2': 'bitmap', 'param': reference, 'w': '10000', 'h': '10000'})
    with pytest.raises(ValueError, match='image'):
        load_dashboard_template(_template_root(tmp_path, workbook), 'sales', None)
