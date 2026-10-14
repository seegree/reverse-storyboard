# Windows portable build

## Current boundary

The GUI and CLI executables were built by GitHub Actions on Windows Server 2022. The [successful run](https://github.com/seegree/reverse-storyboard/actions/runs/38609269862) passed 53 source tests, source Tk checks, and portable CLI validation from outside the checkout without Python/backend executables on PATH. The downloadable application artifact is 440,868,117 bytes compressed. Bundled dependencies, local inference, timecodes, JPEG exports, accented filenames and revision were exercised.

The packaged GUI's hands-on appearance/startup on Windows 10/11, clean consumer-machine behavior, and offline operation remain outstanding. A server-runner check does not establish those properties.

## Build and folder layout

Use Windows x64 Python 3.12:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
./scripts/build_windows.ps1
```

The script checks the platform, fetches pinned assets, builds the GUI/CLI EXEs, copies the 256M pair, and gathers licenses. The folder under `dist/EditDetector/` contains:

```text
EditDetector.exe
EditDetector-CLI.exe
_internal/                 Python, Tk and Python dependencies
runtime/
  bin/ffmpeg.exe
  bin/ffprobe.exe
  bin/llama/               CPU executable and required DLLs
  models/                  256M model and matching projector
  manifest-256.json
licenses/
README.md
THIRD_PARTY.md
```

Keep the folder together. There is no one-file extraction step or runtime download, server, API key or GPU dependency. The setup script runs only on developer/build machines. The 500M pair, sample media and download caches are not packaged.

The included GitHub Actions workflow tests the source, builds the folder, changes outside the checkout, removes Python/backend executables from PATH, and runs portable dependency, inference, timecode, image-export and revision checks through `scripts/validate_portable.py`. It also runs source Tk layout/keyboard and caption-recovery checks and uploads a separate review-evidence artifact. The workflow was uploaded to the private reverse-storyboard repository and executed successfully on 2026-10-14.

## Size evidence

| Selected asset | Bytes |
| --- | ---: |
| 256M language model | 175,054,528 |
| 256M vision projector | 103,769,856 |
| Windows llama.cpp executable and selected DLLs | 35,090,944 |
| Windows FFmpeg executable | 105,423,872 |
| Windows FFprobe executable | 105,221,120 |

These assets alone total about **524.6 MB** before Python, OpenCV, Tk, DOCX dependencies and notices. Expect hundreds of megabytes; no final installed or compressed size is claimed. A custom smaller FFmpeg build could reduce size later, at the cost of build maintenance and codec coverage.

The Windows llama.cpp download was 19,398,918 bytes and the FFmpeg ZIP was 114,768,076 bytes. The downloader selects only the inference executable/core DLLs and FFmpeg/FFprobe. Multiple CPU instruction variants remain so the backend can select an appropriate variant. No GPU backend is needed.

## Remaining platform checks

1. Run `EditDetector-CLI.exe self-test --output new-folder` outside the checkout without developer tools on PATH.
2. Disconnect networking and analyze a normal MP4 and MOV through the GUI. Check in Word or another DOCX reader; compare cuts/order and review captions.
3. Check cancellation during detection/inference, corrupt input, locked/unwritable output, paths with spaces/non-ASCII text, and an existing document.
4. Repeat on a clean Windows 10/11 x64 laptop without a dedicated GPU or developer environment. Record startup time, RAM, processing time, and ZIP/folder size.
5. Before a public binary release, include the applicable licenses and corresponding source materials described in `THIRD_PARTY.md`. Signing/installer polish is deferred.

These are outstanding checks, not reported successes. Reference: [PyInstaller operating modes](https://pyinstaller.org/en/stable/operating-mode.html).

The Mac-to-Windows review setup and hands-on acceptance checklist are in [WINDOWS_REVIEW.md](WINDOWS_REVIEW.md). The portable package includes it as START-HERE.md.
