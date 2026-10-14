import os
from pathlib import Path

import pytest

from scripts.validate_portable import portable_environment


@pytest.mark.parametrize('root_key', ['SYSTEMROOT', 'SystemRoot'])
def test_portable_children_cannot_use_developer_runtime(root_key):
    source = {root_key: 'windows-root', 'Path': 'developer-tools', 'PythonPath': 'source-checkout',
              'edit_detector_runtime': 'developer-models', 'TEMP': 'temporary-files'}
    result = portable_environment(source)
    assert result['PATH'] == os.pathsep.join([str(Path('windows-root') / 'System32'), 'windows-root'])
    assert not any(key.casefold() in {'pythonpath', 'edit_detector_runtime'} for key in result)
    assert result['TEMP'] == source['TEMP']
    assert source['Path'] == 'developer-tools'
