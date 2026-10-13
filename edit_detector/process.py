"""Run local executables without a shell, with cancellation and bounded diagnostics."""

import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time

from .errors import AppError, Cancelled


def check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled("Analysis cancelled.")


def run_process(args: list[str], *, cancel=None, timeout=300, env=None) -> str:
    check_cancel(cancel)
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            proc = subprocess.Popen(
                [str(a) for a in args], stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError as exc:
            raise AppError(f"Cannot start {Path(args[0]).name}: {exc}") from exc
        started = time.monotonic()
        try:
            while proc.poll() is None:
                check_cancel(cancel)
                if timeout is not None and time.monotonic() - started > timeout:
                    raise AppError(f"{Path(args[0]).name} timed out after {timeout:g} seconds.")
                time.sleep(0.05)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        check_cancel(cancel)
        stderr.seek(max(0, stderr.tell() - 6000))
        detail = stderr.read().decode("utf-8", errors="replace").strip()
        if proc.returncode:
            raise AppError(f"{Path(args[0]).name} failed (exit {proc.returncode}).\n{detail}")
        stdout.seek(0)
        return stdout.read().decode("utf-8", errors="replace")
