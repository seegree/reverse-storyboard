"""Generate a reproducible three-shot MP4 for development (requires FFmpeg)."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edit_detector.config import executable

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
parser.add_argument("--images", nargs=3, type=Path, help="Optional three photos instead of color cards")
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
command = [executable("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin"]
if args.images:
    for image in args.images:
        command += ["-loop", "1", "-framerate", "24", "-t", "2", "-i", str(image)]
    filters = ";".join(f"[{i}:v]scale=640:480:force_original_aspect_ratio=decrease,pad=640:480:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]" for i in range(3))
    filters += ";[v0][v1][v2]concat=n=3:v=1:a=0[out]"
else:
    for color in ("red", "green", "blue"):
        command += ["-f", "lavfi", "-i", f"color={color}:s=640x360:r=24:d=2"]
    filters = "[0:v][1:v][2:v]concat=n=3:v=1:a=0[out]"
command += ["-filter_complex", filters, "-map", "[out]", "-c:v", "mpeg4", "-q:v", "3", str(args.output)]
subprocess.run(command, check=True)
