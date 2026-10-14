import sys
import threading
import time

import pytest

from edit_detector.errors import AppError, Cancelled
from edit_detector.process import run_process


def test_nonzero_exit_reports_diagnostics():
    with pytest.raises(AppError, match="specific decoder error"):
        run_process([sys.executable, "-c", "import sys; sys.stderr.write('specific decoder error'); sys.exit(3)"])


def test_timeout_terminates_child():
    started = time.monotonic()
    with pytest.raises(AppError, match="timed out"):
        run_process([sys.executable, "-c", "import time; time.sleep(20)"], timeout=0.1)
    assert time.monotonic() - started < 5


def test_cancellation_terminates_child():
    cancel = threading.Event()
    timer = threading.Timer(0.1, cancel.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            run_process([sys.executable, "-c", "import time; time.sleep(20)"], cancel=cancel)
    finally:
        timer.join()
