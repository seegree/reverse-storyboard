from pathlib import Path
import subprocess
import threading

from PIL import Image, ImageStat
import pytest

from edit_detector.errors import AppError, Cancelled
from edit_detector.config import executable
from edit_detector.video import Shot, detect_shots, extract_frames


@pytest.fixture
def cut_video(tmp_path):
    try:
        ffmpeg = executable("ffmpeg")
    except AppError:
        pytest.skip("FFmpeg is required for video integration tests")
    video = tmp_path / "three shots with spaces.mp4"
    subprocess.run([
        ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=red:s=320x180:r=24:d=1",
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
    subprocess.run([executable("ffmpeg"), "-v", "error", "-i", str(cut_video), "-t", "0.5", "-c:v", "mpeg4", str(single)], check=True)
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


@pytest.mark.integration
def test_fractional_rate_portrait_and_pixel_aspect_ratio(tmp_path):
    video = tmp_path / "portrait.mov"
    subprocess.run([executable("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=red:s=180x320:r=30000/1001:d=1",
                    "-vf", "setsar=2/1", "-c:v", "mpeg4", str(video)], check=True)
    shots = detect_shots(video)
    assert len(shots) == 1
    assert shots[0].fps == pytest.approx(30000 / 1001, rel=0.001)
    images = extract_frames(video, shots, tmp_path / "frames")
    with Image.open(images[0]) as image:
        assert image.width / image.height == pytest.approx(360 / 320, rel=0.01)


@pytest.mark.integration
def test_exact_middle_of_moving_shot(tmp_path):
    # A smoothly brightening shot makes start/middle/end visibly distinguishable.
    frames = tmp_path / "source"
    frames.mkdir()
    for i in range(21):
        Image.new("RGB", (160, 90), (20 + i * 8,) * 3).save(frames / f"{i:03d}.png")
    video = tmp_path / "ramp.mkv"
    subprocess.run([executable("ffmpeg"), "-v", "error", "-framerate", "10", "-i", str(frames / "%03d.png"),
                    "-c:v", "ffv1", str(video)], check=True)
    shots = detect_shots(video)
    assert len(shots) == 1 and shots[0].midpoint_frame == 10
    images = extract_frames(video, shots, tmp_path / "output")
    with Image.open(images[0]) as image:
        assert ImageStat.Stat(image).mean[0] == pytest.approx(100, abs=3)


@pytest.mark.integration
def test_thousand_shots_uses_filter_file(tmp_path):
    source = tmp_path / "alternating"
    source.mkdir()
    Image.new("RGB", (64, 64), "red").save(source / "0.png")
    Image.new("RGB", (64, 64), "blue").save(source / "1.png")
    video = tmp_path / "many.mp4"
    subprocess.run([executable("ffmpeg"), "-v", "error", "-stream_loop", "-1", "-framerate", "30", "-i", str(source / "%d.png"),
                    "-frames:v", "1001", "-c:v", "mpeg4", str(video)], check=True)
    shots = detect_shots(video, min_scene_frames=1)
    assert len(shots) == 1001
    images = extract_frames(video, shots, tmp_path / "frames")
    assert len(images) == 1001
    assert images[-1].name == "shot_001001.jpg"
