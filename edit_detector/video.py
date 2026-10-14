"""PySceneDetect hard cuts, then a single FFmpeg pass for exact midpoint frames."""

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import tempfile
import threading

from PIL import Image
from scenedetect import ContentDetector, SceneManager, open_video

from .config import executable
from .errors import AppError
from .process import check_cancel, run_process


@dataclass(frozen=True)
class Shot:
    number: int
    start_frame: int
    end_frame: int  # Exclusive; the next shot starts here.
    fps: float

    @property
    def midpoint_frame(self) -> int:
        return self.start_frame + (self.end_frame - self.start_frame - 1) // 2

    @property
    def start_seconds(self) -> float:
        return self.start_frame / self.fps

    @property
    def end_seconds(self) -> float:
        return self.end_frame / self.fps

    def record(self) -> dict:
        return {**asdict(self), "midpoint_frame": self.midpoint_frame,
                "start_seconds": self.start_seconds, "end_seconds": self.end_seconds}


def probe_video(path: Path, *, cancel=None) -> dict:
    if not path.is_file():
        raise AppError(f"Video does not exist: {path}")
    output = run_process([
        executable("ffprobe"), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration",
        "-of", "json", str(path.resolve()),
    ], cancel=cancel, timeout=60)
    try:
        data = json.loads(output)
        stream = data["streams"][0]
        if int(stream["width"]) <= 0 or int(stream["height"]) <= 0:
            raise ValueError("empty video dimensions")
        return stream
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AppError("No decodable video stream was found in this file.") from exc


def detect_shots(path: Path, *, threshold=27.0, min_scene_frames=2, cancel=None, progress=None) -> list[Shot]:
    if not math.isfinite(threshold) or threshold <= 0 or min_scene_frames < 1:
        raise AppError("Cut threshold must be positive; minimum shot length must be at least one frame.")
    check_cancel(cancel)
    probe_video(path, cancel=cancel)
    if progress:
        progress("Detecting hard cuts…", None)
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold, min_scene_len=min_scene_frames))
    done = threading.Event()

    def monitor():
        while not done.wait(0.1):
            if cancel is not None and cancel.is_set():
                manager.stop()
                return

    watcher = threading.Thread(target=monitor, daemon=True)
    video = None
    try:
        video = open_video(str(path.resolve()), backend="opencv")
        watcher.start()
        count = manager.detect_scenes(video=video, show_progress=False)
        check_cancel(cancel)
        if count == 0:
            raise AppError("The video opened, but no frames could be decoded.")
        scenes = manager.get_scene_list(start_in_scene=True)
        shots = [Shot(i, start.get_frames(), end.get_frames(), video.frame_rate)
                 for i, (start, end) in enumerate(scenes, 1)]
        if not shots or any(s.end_frame <= s.start_frame for s in shots):
            raise AppError("Shot detection returned an invalid or empty scene list.")
        expected = video.duration.get_frames()
        if expected > count + max(2, expected * 0.01):
            raise AppError(f"Video decoding stopped early: read {count} of approximately {expected} frames.")
        return shots
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Shot detection failed: {exc}") from exc
    finally:
        done.set()
        if watcher.is_alive():
            watcher.join(timeout=1)
        # PySceneDetect 0.6 has no public close method; release the OpenCV handle.
        if video is not None and hasattr(video, "_cap"):
            video._cap.release()


def _frame_selector(indices: list[int]) -> str:
    # FFmpeg's expression parser cannot handle a long left-deep sum (1000+ cuts).
    # A balanced conditional tree has logarithmic depth and evaluates one branch.
    if len(indices) == 1:
        return f"eq(n\\,{indices[0]})"
    middle = len(indices) // 2
    return (f"if(lt(n\\,{indices[middle]})\\,"
            f"{_frame_selector(indices[:middle])}\\,{_frame_selector(indices[middle:])})")


def extract_frames(path: Path, shots: list[Shot], folder: Path, *, max_size=1280, cancel=None, progress=None) -> list[Path]:
    if not shots:
        raise AppError("There are no shots to extract.")
    if max_size < 64:
        raise AppError("Image size must be at least 64 pixels.")
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise AppError(f"Frame output folder must be empty: {folder}")
    if progress:
        progress(f"Extracting {len(shots)} midpoint images…", None)
    # A script avoids the Windows command-line length limit for many shots.
    # Using decoded frame indices avoids imprecise GOP seeking and VFR time drift.
    select = _frame_selector([s.midpoint_frame for s in shots])
    # Correct non-square pixels before bounding both dimensions; FFmpeg autorotates.
    scale = f"scale=iw*sar:ih,setsar=1,scale=w='min({max_size},iw)':h='min({max_size},ih)':force_original_aspect_ratio=decrease"
    with tempfile.TemporaryDirectory(prefix="shot-filter-") as temp:
        script = Path(temp) / "select.txt"
        script.write_text(f"select={select},{scale}", encoding="utf-8")
        run_process([
            executable("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
            "-xerror", "-i", str(path.resolve()), "-map", "0:v:0", "-an", "-sn", "-dn",
            "-/filter:v", str(script), "-fps_mode", "vfr", "-q:v", "3",
            str(folder.resolve() / "shot_%06d.jpg"),
        ], cancel=cancel, timeout=None)
    images = sorted(folder.glob("shot_*.jpg"))
    if len(images) != len(shots):
        raise AppError(f"Expected {len(shots)} midpoint images, but FFmpeg produced {len(images)}. The decoders may disagree or the video is damaged.")
    try:
        for image in images:
            with Image.open(image) as img:
                img.verify()
    except (OSError, ValueError) as exc:
        raise AppError(f"An extracted image is unreadable: {exc}") from exc
    return images


def extract_video(path: Path, folder: Path, **kwargs) -> list[Shot]:
    shots = detect_shots(path, **kwargs)
    extract_frames(path, shots, folder, cancel=kwargs.get("cancel"), progress=kwargs.get("progress"))
    (folder / "shots.json").write_text(json.dumps({
        "video": path.name,
        "time_note": "Frame indices are exact and end-exclusive. Times use nominal FPS; VFR times are approximate. Midpoints use decoded frame order.",
        "shots": [s.record() for s in shots],
    }, indent=2), encoding="utf-8")
    return shots
