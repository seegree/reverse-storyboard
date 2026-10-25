# Edit Detector

Turn an edited video into an editable Word storyboard. Edit Detector finds each hard cut, saves one still from the middle of every shot, writes a short AI caption for it, and builds a numbered DOCX with the images embedded. Everything runs offline on your computer: no account, no upload, no API key.

## Use it (Windows)

1. Download the portable Windows build from a [successful Windows build run](https://github.com/seegree/reverse-storyboard/actions/runs/38609269862) (you need to be signed in to GitHub to download it).
2. Unzip the **entire** folder. Keep `runtime` and `_internal` next to the EXE.
3. Launch `EditDetector.exe`, click **Choose video…**, then **Analyze video**.
4. Open the Word document it saves. **Review the captions:** the small local AI model makes mistakes.

No Python or other installs are needed. If a caption fails, the shot is still included with the note **[Caption unavailable — add a description in Word.]**. The **Caption issues…** button lists which shots were affected.

On macOS, run it from source (see [macOS development](#macos-development)).

## Status

The CLI and GUI have been exercised on macOS (Apple Silicon). The Windows build passes automated checks on Windows Server 2022; hands-on testing on Windows 10/11 is still outstanding. Caption accuracy is a known limitation. See [validation](docs/VALIDATION.md) and [stage status](docs/STATUS.md).

## Output options and shorter versions

The dark Tkinter interface groups video selection, options and results into cards. Results appear when work begins; caption failures appear in a separate amber banner. The window scrolls on smaller displays.

The GUI has checkboxes for **Add timecodes** and **Save shot images**. The image folder is saved beside the Word document, with numbered JPEGs and a `shots.json` manifest. Existing image folders are preserved by choosing a new folder name. With the checkbox off, intermediate images remain temporary.

After analysis, **Make a shorter version** automatically uses the latest full document. Enter shot numbers such as `3 6 11 13 14 25 34 35 38 42`, then click **Save shorter version…**. Choose a new filename. The selected shots retain their captions, images, formatting and timecodes, in original order, with numbering restarted at 1. Spaces or commas work; duplicates are ignored. The source document stays intact. You can also choose an older Edit Detector Word document; no video or AI model is needed. Numbers refer to the selected source document's current list. The source field stays on the original document so you can make alternate selections.

Timecodes show each shot's elapsed start and end in `HH:MM:SS.mmm`, calculated from nominal frame rate. Ends are exclusive. These are not embedded camera/SMPTE timecodes and are approximate for variable-frame-rate footage.

## Commands

After activating the development environment, or using its Python executable directly:

```sh
# Stage 1 alone: JPEGs plus a diagnostic JSON manifest
python -m edit_detector extract input.mp4 --output shots

# Entire pipeline; default output is input-shots.docx
python -m edit_detector analyze input.mp4
python -m edit_detector analyze input.mov -o breakdown.docx --report timing.json

# Optional timecodes and persistent JPEG folder
python -m edit_detector analyze input.mp4 --timecodes --export-images

# Make a new, shorter document without rerunning video or AI
python -m edit_detector revise input-shots.docx --keep "3 6 11 13 14 25 34 35 38 42" -o selected.docx

# Test local inference on one image
python -m edit_detector caption picture.jpg

# Desktop interface and local dependency checks
python -m edit_detector gui
python -m edit_detector doctor

# Generate three shots and exercise the real model and DOCX output
python -m edit_detector self-test --output new-smoke-test-folder
```

Use `--overwrite` explicitly to replace existing CLI output. The GUI save dialog confirms replacing a file. Failures and cancellation preserve a previous document. Unless image export is enabled, the full pipeline cleans up temporary JPEGs; the `extract` command intentionally keeps them and requires an empty output folder. The optional JSON report contains boundaries, frame indices, raw/cleaned captions, retries and stage timings. DOCX is the primary deliverable; no CSV is generated.

## Detection and inference behavior

- PySceneDetect ContentDetector analyzes every frame. Defaults: `--threshold 27`, `--min-scene-frames 2`. Lower thresholds can mistake motion for cuts. Use `--min-scene-frames 1` for one-frame shots. Hard cuts are the focus; complex transitions and similar adjacent shots need review.
- Boundaries are zero-based, end-exclusive frame indices. A shot `[start, end)` selects `start + (end - start - 1) // 2`. FFmpeg selects exact decoded frames in one additional pass; it does not transcode the video or seek separately for each shot. A filter file and balanced expression support many shots without command-line or expression-depth limits encountered in testing.
- JSON times use nominal FPS. On variable-frame-rate footage these times are approximate, and the middle decoded frame need not be the temporal midpoint. Time-accurate VFR reporting remains a follow-up.
- JPEGs fit within 1280×1280, preserve display aspect ratio including non-square pixels, and use FFmpeg autorotation. Detection uses OpenCV and extraction uses FFmpeg; codec support is their intersection. The first video stream is used. MP4/MOV/MKV/AVI support depends on the codec inside the container.
- Inference uses local files and forces CPU execution for both model and projector with `--offline`. Each image gets a fresh CLI process, so no chat history carries between shots. Model reload cost is an accepted MVP tradeoff that avoids running a service.
- Defaults: four CPU threads, temperature zero, seed 42, context 2,048 tokens, maximum 64 generated tokens, 120-second timeout. Change `--threads`, `--temperature`, or `--caption-timeout` as needed.
- Captions may be short phrases or one sentence. Cleanup accepts descriptions of 2–35 words and retries malformed responses once. It does not validate facts. Hallucination-free captions are **not** a verified property.

## Optional 500M model

```sh
python scripts/fetch_runtime.py --models-only --model 500
python -m edit_detector analyze input.mp4 -o larger-model.docx --model runtime/models/SmolVLM-500M-Instruct-Q8_0.gguf --mmproj runtime/models/mmproj-SmolVLM-500M-Instruct-Q8_0.gguf
```

Always replace the model and matching projector together. The 256M pair totals 278,824,384 bytes; the 500M pair totals 545,590,272 bytes. The larger model did not consistently improve accuracy in the test set, so 256M remains the default. A replacement captioner only needs a `caption(image, cancel=...)` method returning a `Caption`; it can be passed to `pipeline.analyze`.

## Windows development setup

Use 64-bit Python 3.12 from python.org, including Tcl/Tk. Run these in the project folder in PowerShell. Internet is needed for developer setup only.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python scripts/fetch_runtime.py --platform windows
.venv\Scripts\python -m edit_detector doctor
.venv\Scripts\python -m edit_detector gui
```

The setup script downloads FFmpeg, FFprobe, the CPU build of llama.cpp, and the Q8 SmolVLM 256M model plus its matching Q8 vision projector. Downloads have pinned versions, immutable model revisions and SHA-256 checks. No Ollama, PyTorch, Transformers, API keys, web server or GPU is used.

## Tests and Windows packaging

```sh
python -m pytest -q
python scripts/make_sample.py samples/three-shots.mp4
python -m edit_detector analyze samples/three-shots.mp4
python scripts/benchmark_captions.py image1.jpg image2.jpg image3.jpg --output captions.json
python scripts/measure.py --output memory.json -- python -m edit_detector analyze input.mp4 -o measured.docx
```

Tests use generated videos and fixture captioners for deterministic failure cases; `self-test` uses actual local AI. Test fixtures never supply captions to normal analysis. `scripts/smoke_gui.py` tests the actual GUI worker/event loop and requires a working desktop display and Tk.

Build on Windows after activating `.venv`:

```powershell
.venv\Scripts\Activate.ps1
./scripts/build_windows.ps1
dist\EditDetector\EditDetector-CLI.exe self-test --output portable-smoke
```

The portable folder contains a GUI EXE and console EXE sharing `_internal`, plus the native runtime, model and licenses. One-folder packaging avoids unpacking hundreds of megabytes at every launch. See [packaging instructions](docs/PACKAGING.md) for the CI workflow, clean-machine checks and size evidence.

## macOS development

Use Python 3.10+ and installed FFmpeg/FFprobe 7+. The runtime downloader supports Apple Silicon for development:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/fetch_runtime.py --platform macos
.venv/bin/python -m edit_detector analyze input.mp4
```

The GUI needs a Python build with Tk: check `python -m tkinter`. Some Homebrew Python builds omit `_tkinter`. The standard Windows python.org installer includes Tk.

Set `EDIT_DETECTOR_RUNTIME` to an absolute alternate runtime directory if needed. Source builds can find tools on PATH; packaged builds use only bundled files so developer installations cannot silently hide missing dependencies.

## Project map

`edit_detector/video.py` handles detection/extraction; `caption.py` runs the model; `document.py` writes Word output; `pipeline.py`, `cli.py` and `gui.py` connect the stages. `scripts/` contains setup and validation helpers. `packaging/` and `.github/workflows/windows.yml` define the Windows build. `docs/` retains test results, limitations and [component provenance](docs/THIRD_PARTY.md).
