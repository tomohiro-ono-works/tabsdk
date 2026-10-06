from __future__ import annotations

import zipfile

import pytest

from twbpatch import SaveError, TwbWorkbook


IMAGE = b'\x89PNG\r\n\x1a\nimage-test-payload'


def _image_workbook(tmp_path, *, packed=False):
    path = tmp_path / 'source.twb'
    path.write_bytes(open('tests/sample_minimal.twb', 'rb').read())
    if packed:
        target = tmp_path / 'source.twbx'
        with zipfile.ZipFile(target, 'w') as archive:
            archive.write(path, 'workbooks/source.twb')
            archive.writestr('Data/destination.hyper', b'destination-data')
        path = target
    workbook = TwbWorkbook.open(str(path))
    dashboard = workbook.create_dashboard(name='Images', width=120, height=80)
    dashboard.update(layout={
        'width': 120, 'height': 80,
        'size': {'sizing-mode': 'fixed', 'minwidth': '120', 'maxwidth': '120', 'minheight': '80', 'maxheight': '80'},
        'style': {}, 'viewpoints': {},
        'nodes': [{'kind': 'image', 'x': 0, 'y': 0, 'width': 60, 'height': 40,
                   'placement': 'floating', 'attributes': {'type-v2': 'bitmap', 'is-centered': '1'},
                   'style': {}, 'image_path': 'template_logo.png'}],
    })
    workbook._add_image_assets({'template_logo.png': IMAGE})
    return workbook


def test_images_are_written_only_on_save(tmp_path):
    workbook = _image_workbook(tmp_path)
    assert not (tmp_path / 'template_logo.png').exists()
    out = tmp_path / 'out.twb'
    workbook.save(str(out), validate=False)
    assert (tmp_path / 'template_logo.png').read_bytes() == IMAGE
    assert TwbWorkbook.open(str(out)).get_dashboards()[0].layout['nodes'][0]['image_path'] == 'template_logo.png'


def test_images_survive_second_save(tmp_path):
    workbook = _image_workbook(tmp_path)
    workbook.save(str(tmp_path / 'first.twb'), validate=False)
    second = tmp_path / 'second'
    second.mkdir()
    workbook.save(str(second / 'second.twb'), validate=False)
    assert (second / 'template_logo.png').read_bytes() == IMAGE


def test_reload_clears_pending_images(tmp_path):
    workbook = _image_workbook(tmp_path)
    workbook.reload()
    output = tmp_path / 'reloaded'
    output.mkdir()
    workbook.save(str(output / 'reloaded.twb'), validate=False)
    assert not (output / 'template_logo.png').exists()


def test_image_save_respects_overwrite(tmp_path):
    workbook = _image_workbook(tmp_path)
    (tmp_path / 'template_logo.png').write_bytes(b'different')
    with pytest.raises(SaveError):
        workbook.save(str(tmp_path / 'out.twb'), validate=False)
    assert not (tmp_path / 'out.twb').exists()
    workbook.save(str(tmp_path / 'out.twb'), validate=False, overwrite=True)
    assert (tmp_path / 'template_logo.png').read_bytes() == IMAGE


def test_twbx_images_keep_destination_assets(tmp_path):
    workbook = _image_workbook(tmp_path, packed=True)
    output = tmp_path / 'out.twbx'
    workbook.save(str(output), validate=False)
    with zipfile.ZipFile(output) as archive:
        assert archive.read('workbooks/template_logo.png') == IMAGE
        assert archive.read('Data/destination.hyper') == b'destination-data'


def test_image_asset_paths_cannot_escape_output(tmp_path):
    workbook = _image_workbook(tmp_path)
    with pytest.raises(ValueError):
        workbook._add_image_assets({'../outside.png': IMAGE})


def test_image_parent_conflict_fails_before_writing_xml(tmp_path):
    workbook = _image_workbook(tmp_path)
    workbook._add_image_assets({'Images/logo.png': IMAGE})
    (tmp_path / 'Images').write_bytes(b'ordinary-file')
    output = tmp_path / 'out.twb'
    with pytest.raises(SaveError):
        workbook.save(str(output), validate=False)
    assert not output.exists()
    output.write_bytes(b'original-output')
    with pytest.raises(SaveError):
        workbook.save(str(output), validate=False, overwrite=True)
    assert output.read_bytes() == b'original-output'
