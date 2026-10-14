"""A portable-bundle smoke test that needs neither Python nor fixture downloads."""
import json
from pathlib import Path
from zipfile import ZipFile

from .config import executable
from .errors import AppError
from .pipeline import analyze
from .process import run_process


def run_selftest(folder: Path, progress=print):
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / "three-shots.mp4"
    args = [executable("ffmpeg"), "-v", "error", "-nostdin"]
    for color in ("red", "green", "blue"):
        args += ["-f", "lavfi", "-i", f"color={color}:s=320x180:r=24:d=1"]
    args += ["-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0", "-c:v", "mpeg4", str(video)]
    run_process(args)
    result = analyze(video, folder / "three-shots.docx", progress=lambda msg, fraction: progress(msg))
    if len(result.shots) != 3:
        raise AppError(f"Self-test expected 3 shots, found {len(result.shots)}.")
    with ZipFile(result.output) as doc:
        if len([n for n in doc.namelist() if n.startswith("word/media/")]) != 3:
            raise AppError("Self-test DOCX does not contain three embedded images.")
    (folder / "analysis.json").write_text(json.dumps(result.record(), indent=2), encoding="utf-8")
    runtime_failures = [shot for shot in result.caption_failures if shot.get("caption_error_kind") != "invalid_response"]
    if runtime_failures:
        raise AppError("Self-test caption runtime failed: " + "; ".join(
            f"shot {shot['number']}: {shot['caption_error']}" for shot in runtime_failures))
    if result.caption_failures:
        progress(f"WARNING: {len(result.caption_failures)} unusable model captions were saved as placeholders. See analysis.json.")
    progress(f"PASS: three ordered shots, local CPU inference, three embedded images. {result.output}")
    return result
