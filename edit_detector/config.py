import os
from pathlib import Path
import shutil
import sys

from .errors import AppError


def runtime_root() -> Path:
    override = os.environ.get("EDIT_DETECTOR_RUNTIME")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "runtime"
    return Path(__file__).resolve().parent.parent / "runtime"


def executable(name: str, root: Path | None = None) -> str:
    root = root or runtime_root()
    filename = name + (".exe" if os.name == "nt" else "")
    for candidate in (root / "bin" / filename, root / "bin" / "llama" / filename):
        if candidate.is_file():
            return str(candidate.resolve())
    # Packaged apps must be self-contained; a developer may use installed tools.
    found = None if getattr(sys, "frozen", False) else shutil.which(name)
    if found:
        return found
    raise AppError(f"Missing {filename}. Run scripts/fetch_runtime.py, or place it in {root / 'bin'}.")
