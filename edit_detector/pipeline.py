from dataclasses import asdict, dataclass
from pathlib import Path
import tempfile
import time

from .caption import LlamaCaptioner
from .document import write_document
from .errors import AppError
from .process import check_cancel
from .video import detect_shots, extract_frames


@dataclass
class AnalysisResult:
    output: str
    shots: list[dict]
    timings: dict[str, float]
    model: str

    def record(self):
        return asdict(self)


def analyze(video: Path, output: Path, *, captioner=None, threshold=27.0, min_scene_frames=2,
            overwrite=False, cancel=None, progress=None) -> AnalysisResult:
    started = time.perf_counter()
    if output.suffix.lower() != ".docx":
        raise AppError("The output filename must end in .docx.")
    if output.exists() and not overwrite:
        raise AppError(f"Output already exists: {output}. Choose another name or use --overwrite.")
    if not video.is_file():
        raise AppError(f"Video does not exist: {video}")
    if video.resolve() == output.resolve():
        raise AppError("The output document must not replace the source video.")
    captioner = captioner or LlamaCaptioner()

    def emit(message, fraction=None):
        check_cancel(cancel)
        if progress:
            progress(message, fraction)

    timings = {}
    with tempfile.TemporaryDirectory(prefix="edit-detector-") as temp:
        start = time.perf_counter()
        shots = detect_shots(video, threshold=threshold, min_scene_frames=min_scene_frames,
                             cancel=cancel, progress=progress)
        timings["detection_seconds"] = time.perf_counter() - start
        start = time.perf_counter()
        images = extract_frames(video, shots, Path(temp) / "frames", cancel=cancel, progress=progress)
        timings["extraction_seconds"] = time.perf_counter() - start
        records, captions = [], []
        start = time.perf_counter()
        for shot, image in zip(shots, images):
            emit(f"Captioning shot {shot.number} of {len(shots)}…", (shot.number - 1) / len(shots))
            caption = captioner.caption(image, cancel=cancel)
            captions.append(caption.text)
            records.append({**shot.record(), "caption": asdict(caption)})
        timings["captioning_seconds"] = time.perf_counter() - start
        emit("Writing Word document…", 1.0)
        start = time.perf_counter()
        result = write_document(video.name, images, captions, output, overwrite=overwrite, cancel=cancel)
        timings["document_seconds"] = time.perf_counter() - start
    timings["total_seconds"] = time.perf_counter() - started
    return AnalysisResult(str(result), records, timings, str(getattr(captioner, "model", type(captioner).__name__)))
