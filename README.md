# Edit Detector

An offline Python desktop MVP that detects hard cuts, extracts one midpoint JPEG per shot, captions each image with a local model, and embeds the results in a Word document.

Implementation and validation are in progress. See `docs/STATUS.md` for verified checkpoints.

## Stage 1

Python 3.10+ and FFmpeg/FFprobe are required for development. End users will receive a self-contained Windows folder.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m edit_detector extract input.mp4 --output shots
python -m pytest -q
```

The output directory must be empty. JPEGs and `shots.json` retain chronological order. Cut boundaries use end-exclusive frame indices. The midpoint is a decoded frame index, so extraction does not drift on variable-frame-rate footage; timestamp estimates use nominal FPS and are approximate on VFR footage.

ContentDetector defaults to threshold 27 and a minimum shot length of two frames. Lower `--threshold` detects smaller changes but can mistake motion for cuts. Use `--min-scene-frames 1` for one-frame shots. Hard cuts are the focus; no detector guarantees every edit on all material.
