from dataclasses import asdict, dataclass
from pathlib import Path
import tempfile
import time
import json
import shutil

from .caption import Caption, LlamaCaptioner
from .document import format_timecode, write_document
from .errors import AppError, Cancelled
from .process import check_cancel
from .video import detect_shots, extract_frames


@dataclass
class AnalysisResult:
    output: str
    shots: list[dict]
    timings: dict[str, float]
    model: str
    images_folder: str | None = None

    @property
    def caption_failures(self):
        return [shot for shot in self.shots if shot.get("caption_error")]

    def record(self):
        return asdict(self)


def analyze(video: Path, output: Path, *, captioner=None, threshold=27.0, min_scene_frames=2,
            overwrite=False, cancel=None, progress=None, include_timecodes=False,
            export_images: Path | None = None) -> AnalysisResult:
    started = time.perf_counter()
    if output.suffix.lower() != ".docx":
        raise AppError("The output filename must end in .docx.")
    if output.exists() and not overwrite:
        raise AppError(f"Output already exists: {output}. Choose another name or use --overwrite.")
    if not video.is_file():
        raise AppError(f"Video does not exist: {video}")
    if video.resolve() == output.resolve():
        raise AppError("The output document must not replace the source video.")
    if export_images is not None:
        export_images = export_images.expanduser().resolve()
        if export_images.exists() or export_images == output.resolve():
            raise AppError(f"Choose a new image folder; this path is already in use: {export_images}")
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
            caption_started = time.perf_counter()
            caption_error = None
            try:
                caption = captioner.caption(image, cancel=cancel)
            except Cancelled:
                raise
            except (AppError, OSError) as exc:
                check_cancel(cancel)
                caption_error = str(exc)
                caption = Caption("[Caption unavailable — add a description in Word.]", "",
                                  time.perf_counter() - caption_started, 0)
                emit(f"Shot {shot.number}: caption unavailable; keeping its image and continuing.")
            captions.append(caption.text)
            records.append({**shot.record(), "caption": asdict(caption), "caption_error": caption_error})
        timings["captioning_seconds"] = time.perf_counter() - start
        emit("Writing Word document…", 1.0)
        start = time.perf_counter()
        timecodes = [f"{format_timecode(s.start_seconds)} – {format_timecode(s.end_seconds)}" for s in shots] if include_timecodes else None
        exported = False
        try:
            if export_images is not None:
                export_images.mkdir(parents=True, exist_ok=False)
                exported = True
                for shot, image in zip(shots, images):
                    check_cancel(cancel)
                    shutil.copyfile(image, export_images / f"shot_{shot.number:06d}.jpg")
                (export_images / "shots.json").write_text(json.dumps({
                    "video": video.name, "shots": records,
                    "time_note": "Elapsed time from nominal FPS; approximate on variable-frame-rate footage. Ends are exclusive.",
                }, indent=2), encoding="utf-8")
            result = write_document(video.name, images, captions, output, overwrite=overwrite,
                                    cancel=cancel, timecodes=timecodes)
        except BaseException:
            if exported:
                shutil.rmtree(export_images)
            raise
        timings["document_seconds"] = time.perf_counter() - start
    timings["total_seconds"] = time.perf_counter() - started
    return AnalysisResult(str(result), records, timings, str(getattr(captioner, "model", type(captioner).__name__)),
                          str(export_images) if export_images else None)
