"""Development-only quality/timing probe. No benchmark fixture supplies captions to the app."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edit_detector.caption import LlamaCaptioner
from edit_detector.errors import AppError

parser = argparse.ArgumentParser()
parser.add_argument("images", nargs="+", type=Path)
parser.add_argument("--model", type=Path)
parser.add_argument("--mmproj", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
records = []
for temperature in (0.0, 0.0, 0.2):
    model = LlamaCaptioner(model=args.model, mmproj=args.mmproj, temperature=temperature)
    for image in args.images:
        try:
            caption = model.caption(image)
            record = {"image": image.name, "temperature": temperature, **asdict(caption)}
        except AppError as exc:
            record = {"image": image.name, "temperature": temperature, "error": str(exc)}
        records.append(record)
        print(json.dumps(record), flush=True)
        args.output.write_text(json.dumps(records, indent=2), encoding="utf-8")
