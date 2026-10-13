import argparse
from pathlib import Path
import sys

from .errors import AppError
from .video import extract_video


def progress(message, fraction):
    print(message, flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline video shot breakdowns")
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="Detect shots and extract midpoint JPEGs (no AI required)")
    extract.add_argument("video", type=Path)
    extract.add_argument("--output", "-o", type=Path, required=True)
    extract.add_argument("--threshold", type=float, default=27.0)
    extract.add_argument("--min-scene-frames", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        shots = extract_video(args.video, args.output, threshold=args.threshold,
                              min_scene_frames=args.min_scene_frames, progress=progress)
        print(f"Saved {len(shots)} shots in {args.output.resolve()}")
        return 0
    except (AppError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
