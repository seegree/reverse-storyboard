from pathlib import Path
import threading
from zipfile import ZipFile

from PIL import Image
import pytest

from edit_detector.caption import Caption
from edit_detector.errors import AppError, Cancelled
from edit_detector.pipeline import analyze
from edit_detector.video import Shot


@pytest.fixture
def staged_video(monkeypatch, tmp_path):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"fixture")
    monkeypatch.setattr("edit_detector.pipeline.detect_shots", lambda *a, **kw: [Shot(1, 0, 24, 24), Shot(2, 24, 48, 24)])
    seen = []
    def extract(path, shots, folder, **kw):
        folder.mkdir()
        images = []
        for i, color in enumerate(("red", "blue"), 1):
            image = folder / f"{i}.jpg"
            Image.new("RGB", (320, 180), color).save(image)
            images.append(image)
        seen.extend(images)
        return images
    monkeypatch.setattr("edit_detector.pipeline.extract_frames", extract)
    return video, seen


def test_pipeline_order_embedding_and_cleanup(staged_video, tmp_path):
    video, frames = staged_video
    class FixtureCaptioner:
        def caption(self, image, **kw):
            return Caption(f"Fixture caption for image {image.stem}.", "", 0, 1)
    result = analyze(video, tmp_path / "result.docx", captioner=FixtureCaptioner())
    assert [r["number"] for r in result.shots] == [1, 2]
    assert [r["caption"]["text"] for r in result.shots] == ["Fixture caption for image 1.", "Fixture caption for image 2."]
    assert all(not p.exists() for p in frames)
    with ZipFile(result.output) as doc:
        assert len([n for n in doc.namelist() if n.startswith("word/media/")]) == 2


def test_inference_failure_leaves_previous_document_and_cleans_temp(staged_video, tmp_path):
    video, frames = staged_video
    target = tmp_path / "result.docx"
    target.write_bytes(b"previous result")
    class FailingCaptioner:
        def caption(self, *a, **kw):
            raise AppError("inference failed")
    with pytest.raises(AppError, match="inference failed"):
        analyze(video, target, captioner=FailingCaptioner(), overwrite=True)
    assert target.read_bytes() == b"previous result"
    assert all(not p.exists() for p in frames)


def test_cancel_during_caption_never_publishes_document(staged_video, tmp_path):
    video, frames = staged_video
    cancel = threading.Event()
    class CancellingCaptioner:
        def caption(self, image, **kw):
            cancel.set()
            return Caption("A fixture caption is returned.", "", 0, 1)
    with pytest.raises(Cancelled):
        analyze(video, tmp_path / "cancelled.docx", captioner=CancellingCaptioner(), cancel=cancel)
    assert not (tmp_path / "cancelled.docx").exists()
    assert all(not p.exists() for p in frames)
