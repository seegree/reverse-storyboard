import argparse
import json
from pathlib import Path
import sys

from .errors import AppError
from .caption import LlamaCaptioner
from .pipeline import analyze
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
    full = sub.add_parser("analyze", help="Make a captioned Word document entirely offline")
    full.add_argument("video", type=Path)
    full.add_argument("--output", "-o", type=Path)
    full.add_argument("--threshold", type=float, default=27.0)
    full.add_argument("--min-scene-frames", type=int, default=2)
    full.add_argument("--overwrite", action="store_true")
    full.add_argument("--report", type=Path, help="Optional JSON diagnostics and stage timings")
    full.add_argument("--timecodes", action="store_true", help="Include elapsed start/end timecodes in Word")
    full.add_argument("--export-images", action="store_true", help="Keep a numbered JPEG folder beside the document")
    full.add_argument("--images-dir", type=Path, help="Export JPEGs to this new folder instead")
    revise = sub.add_parser("revise", help="Keep selected shots from an existing Word document and renumber them")
    revise.add_argument("document", type=Path)
    revise.add_argument("--keep", required=True, help="Shot numbers separated by spaces or commas, e.g. '3 6 11'")
    revise.add_argument("--output", "-o", type=Path)
    revise.add_argument("--overwrite", action="store_true")
    single = sub.add_parser("caption", help="Test local AI on one still image")
    single.add_argument("image", type=Path)
    for item in (full, single):
        item.add_argument("--model", type=Path)
        item.add_argument("--mmproj", type=Path)
        item.add_argument("--threads", type=int, default=4)
        item.add_argument("--temperature", type=float, default=0)
        item.add_argument("--caption-timeout", type=float, default=120)
    sub.add_parser("gui", help="Launch the minimal desktop interface")
    sub.add_parser("doctor", help="Check local runtime paths and versions")
    smoke = sub.add_parser("self-test", help="Exercise the complete portable application offline")
    smoke.add_argument("--output", type=Path, required=True, help="New folder for smoke-test artifacts")
    args = parser.parse_args(argv)
    try:
        if args.command == "gui":
            from .gui import main as gui_main
            gui_main()
        elif args.command == "revise":
            from .revision import revise_document
            output = args.output or args.document.with_name(args.document.stem + "-selected.docx")
            result = revise_document(args.document, args.keep, output, overwrite=args.overwrite)
            print(f"Saved {len(result.kept_numbers)} of {result.original_count} shots, renumbered from 1, to {result.output}")
        elif args.command == "self-test":
            from .selftest import run_selftest
            run_selftest(args.output)
        elif args.command == "doctor":
            from .config import executable, runtime_root
            from .process import run_process
            print(f"Runtime: {runtime_root()}")
            for name in ("ffmpeg", "ffprobe", "llama-mtmd-cli"):
                binary = executable(name)
                print(f"{name}: {binary}")
                flag = "-version" if name.startswith("ff") else "--version"
                print(run_process([binary, flag], timeout=30).strip())
            model = LlamaCaptioner()
            print(f"Model: {model.model}\nProjector: {model.mmproj}\nLocal files present; use caption for an inference test.")
        elif args.command == "extract":
            shots = extract_video(args.video, args.output, threshold=args.threshold,
                                  min_scene_frames=args.min_scene_frames, progress=progress)
            print(f"Saved {len(shots)} shots in {args.output.resolve()}")
        else:
            captioner = LlamaCaptioner(model=args.model, mmproj=args.mmproj, threads=args.threads,
                                       temperature=args.temperature, timeout=args.caption_timeout)
            if args.command == "caption":
                caption = captioner.caption(args.image)
                print(caption.text)
                print(f"{caption.seconds:.2f} seconds; {caption.attempts} attempt(s)", file=sys.stderr)
            else:
                output = args.output or args.video.with_name(args.video.stem + "-shots.docx")
                if args.report:
                    if args.report.resolve() in (output.resolve(), args.video.resolve()):
                        raise AppError("The diagnostic report must have a different path from the video and Word document.")
                    if args.report.exists() and not args.overwrite:
                        raise AppError("The diagnostic report already exists. Choose another path or use --overwrite.")
                result = analyze(args.video, output, captioner=captioner, threshold=args.threshold,
                                 min_scene_frames=args.min_scene_frames, overwrite=args.overwrite, progress=progress,
                                 include_timecodes=args.timecodes,
                                 export_images=args.images_dir or (output.with_name(output.stem + "-images") if args.export_images else None))
                if args.report:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(json.dumps(result.record(), indent=2), encoding="utf-8")
                print(f"Saved {len(result.shots)} shots to {result.output} in {result.timings['total_seconds']:.2f}s")
                if result.images_folder:
                    print(f"Images: {result.images_folder}")
        return 0
    except (AppError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
