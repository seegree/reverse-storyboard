from PIL import Image
import pytest

from edit_detector.document import write_document
from edit_detector.errors import AppError
from edit_detector.pipeline import AnalysisResult
from edit_detector.selftest import run_selftest


@pytest.mark.parametrize('kind', ['invalid_response', 'runtime'])
def test_selftest_distinguishes_response_recovery_from_runtime_failure(tmp_path, monkeypatch, kind):
    images = []
    for number, color in enumerate(('red', 'green', 'blue')):
        image = tmp_path / f'{number}.jpg'
        Image.new('RGB', (16, 16), color).save(image)
        images.append(image)
    output = write_document('fixture.mp4', images, ['Test scene'] * 3, tmp_path / 'fixture.docx')
    result = AnalysisResult(str(output), [{'number': 1, 'caption_error': 'test failure', 'caption_error_kind': kind},
        {'number': 2, 'caption_error': None}, {'number': 3, 'caption_error': None}], {}, 'fixture')
    monkeypatch.setattr('edit_detector.selftest.executable', lambda name: name)
    monkeypatch.setattr('edit_detector.selftest.run_process', lambda *a, **kw: '')
    monkeypatch.setattr('edit_detector.selftest.analyze', lambda *a, **kw: result)
    folder = tmp_path / 'self-test'
    messages = []
    if kind == 'runtime':
        with pytest.raises(AppError, match='caption runtime failed'):
            run_selftest(folder, messages.append)
    else:
        run_selftest(folder, messages.append)
        assert any('WARNING' in m for m in messages)
        assert messages[-1].startswith('PASS:')
    assert (folder / 'analysis.json').is_file()
