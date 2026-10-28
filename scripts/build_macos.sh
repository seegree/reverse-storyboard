#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x .venv/bin/python ]]; then PYTHON=.venv/bin/python; else PYTHON="$(command -v python3)"; fi
fi

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Build this portable app on an Apple Silicon Mac." >&2
  exit 1
fi

if ! "$PYTHON" -c 'import tkinter; tkinter.Tcl().eval("info patchlevel")' >/dev/null 2>&1; then
  if [[ -n "${EDIT_DETECTOR_TK_PYTHON:-}" && -x "$EDIT_DETECTOR_TK_PYTHON" ]]; then
    PYTHON="$EDIT_DETECTOR_TK_PYTHON"
    if [[ -d .venv/lib/python3.12/site-packages ]]; then
      export PYTHONPATH="$PWD:$PWD/.venv/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}"
    fi
  else
    echo "This Python has no working Tk support. Use a Tk-enabled Python 3.12, or set EDIT_DETECTOR_TK_PYTHON and keep dependencies installed in .venv." >&2
    exit 1
  fi
fi
"$PYTHON" -c 'import tkinter; tkinter.Tcl().eval("info patchlevel")'

"$PYTHON" scripts/fetch_runtime.py --platform macos --model 256
required=(
  runtime/bin/ffmpeg runtime/bin/ffprobe runtime/bin/llama/llama-mtmd-cli
  runtime/models/SmolVLM-256M-Instruct-Q8_0.gguf
  runtime/models/mmproj-SmolVLM-256M-Instruct-Q8_0.gguf
)
for path in "${required[@]}"; do
  [[ -f "$path" ]] || { echo "Missing runtime asset: $path" >&2; exit 1; }
done

"$PYTHON" -m PyInstaller --clean --noconfirm packaging/EditDetector-macos.spec
app="dist/Reverse Storyboard.app"
resources="$app/Contents/Resources"
mkdir -p "$resources/runtime/models" "$resources/runtime/bin/llama"
cp runtime/bin/ffmpeg runtime/bin/ffprobe "$resources/runtime/bin/"
cp -R runtime/bin/llama/. "$resources/runtime/bin/llama/"
cp runtime/models/SmolVLM-256M-Instruct-Q8_0.gguf \
  runtime/models/mmproj-SmolVLM-256M-Instruct-Q8_0.gguf "$resources/runtime/models/"
cp runtime/manifest-256.json "$resources/runtime/"
cp README.md docs/THIRD_PARTY.md "$app/Contents/Resources/"
cp -R docs/licenses "$app/Contents/Resources/"
"$PYTHON" scripts/collect_licenses.py "$app/Contents/Resources/licenses/python"
xattr -cr "$app"
codesign --force --deep --sign - "$app"

ditto -c -k --sequesterRsrc --keepParent "$app" "dist/Reverse-Storyboard-macOS-arm64.zip"
echo "Portable app: $(du -sh "$app" | cut -f1)"
echo "ZIP: $(du -sh dist/Reverse-Storyboard-macOS-arm64.zip | cut -f1) dist/Reverse-Storyboard-macOS-arm64.zip"
