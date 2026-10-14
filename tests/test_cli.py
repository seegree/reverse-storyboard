from unittest.mock import Mock

import pytest

from edit_detector.cli import main
from edit_detector.pipeline import AnalysisResult


@pytest.mark.parametrize('report_name', ['shot_000001.jpg', 'shots.json', '.', 'nested/report.json'])
@pytest.mark.parametrize('automatic', [False, True])
def test_report_cannot_write_inside_export_folder(tmp_path, monkeypatch, capsys, report_name, automatic):
    monkeypatch.setattr('edit_detector.cli.LlamaCaptioner', Mock())
    analyze = Mock()
    monkeypatch.setattr('edit_detector.cli.analyze', analyze)
    output = tmp_path / 'result.docx'
    folder = tmp_path / ('result-images' if automatic else 'images')
    flags = ['--export-images'] if automatic else ['--images-dir', str(folder)]
    assert main(['analyze', 'video.mp4', '-o', str(output), *flags,
                 '--report', str(folder / report_name), '--overwrite']) == 1
    assert 'outside the shot image folder' in capsys.readouterr().err
    analyze.assert_not_called()
    assert not folder.exists()


def test_report_outside_export_folder_is_saved(tmp_path, monkeypatch):
    monkeypatch.setattr('edit_detector.cli.LlamaCaptioner', Mock())
    output = tmp_path / 'result.docx'
    images = tmp_path / 'images'
    analyze = Mock(return_value=AnalysisResult(str(output), [], {'total_seconds': 0}, 'fixture', str(images)))
    monkeypatch.setattr('edit_detector.cli.analyze', analyze)
    report = tmp_path / 'images-report.json'
    assert main(['analyze', 'video.mp4', '-o', str(output), '--images-dir', str(images), '--report', str(report)]) == 0
    assert report.is_file()
    assert analyze.call_args.kwargs['export_images'] == images
