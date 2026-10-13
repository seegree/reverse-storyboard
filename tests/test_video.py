from pathlib import Path
import shutil
import subprocess
import threading

from PIL import Image, ImageStat
import pytest

from edit_detector.errors import AppError, Cancelled
from edit_detector.video import Shot, detect_shots, extract_frames


@pytest.fixture
def cut_video(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is required for video integration tests")
    video = tmp_path / "three shots with spaces.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=320x180:r=24:d=1",
        "-f", "lavfi", "-i", "color=green:s=320x180:r=24:d=1",
        "-f", "lavfi", "-i", "color=blue:s=320x180:r=24:d=1",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0", "-c:v", "mpeg4", str(video),
    ], check=True)
    return video


@pytest.mark.integration
def test_order_boundaries_and_midpoint_pixels(cut_video, tmp_path):
    shots = detect_shots(cut_video)
    assert [(s.start_frame, s.end_frame) for s in shots] == [(0, 24), (24, 48), (48, 72)]
    assert [s.midpoint_frame for s in shots] == [11, 35, 59]
    images = extract_frames(cut_video, shots, tmp_path / "frames")
    assert len(images) == 3
    for image, channel in zip(images, (0, 1, 2)):
        with Image.open(image) as img:
            colors = ImageStat.Stat(img).mean
            assert colors[channel] > 100
            assert all(colors[i] < 10 for i in range(3) if i != channel)
            assert img.size == (320, 180)


@pytest.mark.integration
def test_no_cut_is_one_shot(cut_video, tmp_path):
    single = tmp_path / "single.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(cut_video), "-t", "0.5", "-c:v", "mpeg4", str(single)], check=True)
    shots = detect_shots(single)
    assert len(shots) == 1
    assert (shots[0].start_frame, shots[0].end_frame) == (0, 12)


def test_one_frame_midpoint():
    assert Shot(1, 6, 7, 24).midpoint_frame == 6


def test_missing_and_corrupt_video(tmp_path):
    with pytest.raises(AppError, match="does not exist"):
        detect_shots(tmp_path / "missing.mp4")
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(AppError, match="ffprobe failed"):
        detect_shots(bad)


def test_cancelled_before_detection(tmp_path):
    event = threading.Event()
    event.set()
    with pytest.raises(Cancelled):
        detect_shots(tmp_path / "missing.mp4", cancel=event)


@pytest.mark.integration
def test_extraction_never_overwrites_files(cut_video, tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    existing = out / "keep.txt"
    existing.write_text("keep")
    with pytest.raises(AppError, match="must be empty"):
        extract_frames(cut_video, [Shot(1, 0, 24, 24)], out)
    assert existing.read_text() == "keep"
