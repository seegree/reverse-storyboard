"""Developer setup only. The distributed application never downloads anything.

Downloads are pinned by version and SHA-256. Use Python's standard library only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[1]
LLAMA_TAG = "b11429"  # v0.6.0 points to this binary release.
LLAMA = {
    "macos": ("llama-b11429-bin-macos-arm64.tar.gz", "740288ec6887be94280a5dfa25b5e23a78285cab104519e6c7e218904ee82459"),
    "windows": ("llama-b11429-bin-win-cpu-x64.zip", "1283323272b04cd07905816a597a0da810918102de958f4ff6f7bbaa70ed2efe"),
}
MODELS = {
    "256": {
        "revision": "b9e4379657e1450d04d02eec8e345667265b0a00",
        "model": "2a31195d3769c0b0fd0a4906201666108834848db768af11de1d2cef7cd35e65",
        "mmproj": "7e943f7c53f0382a6fc41b6ee0c2def63ba4fded9ab8ed039cc9e2ab905e0edd",
    },
    "500": {
        "revision": "72e986006ef53e37cdd3f6d4241c90b0f01df376",
        "model": "9d4612de6a42214499e301494a3ecc2be0abdd9de44e663bda63f1152fad1bf4",
        "mmproj": "d1eb8b6b23979205fdf63703ed10f788131a3f812c7b1f72e0119d5d81295150",
    },
}
FFMPEG_FILE = "ffmpeg-9.0.2-essentials_build.zip"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/packages/" + FFMPEG_FILE
FFMPEG_SHA256 = "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, path, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and sha256(path) == expected:
        print(f"Verified {path.name}", flush=True)
        return path
    temporary = path.with_suffix(path.suffix + ".part")
    print(f"Downloading {path.name}…", flush=True)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "EditDetector-Setup/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
        actual = sha256(temporary)
        if actual != expected:
            raise RuntimeError(f"Checksum mismatch for {path.name}: expected {expected}, got {actual}")
        os.replace(temporary, path)
        return path
    finally:
        temporary.unlink(missing_ok=True)


def unpack_selected(archive, destination, *, kind):
    """Copy only regular files by basename; never follow archive links or paths."""
    destination.mkdir(parents=True, exist_ok=True)
    def wanted(name):
        base = Path(name).name
        if kind == "ffmpeg":
            return base in ("ffmpeg.exe", "ffprobe.exe", "LICENSE", "LICENSE.txt", "README.txt")
        return (base in ("llama-mtmd-cli", "llama-mtmd-cli.exe", "LICENSE", "llama.dll", "llama-common.dll", "mtmd.dll", "libomp.dll")
                or base.startswith("ggml") and base.endswith(".dll")
                or base.startswith(("libggml", "libllama.", "libllama-common.", "libmtmd")) and base.endswith(".dylib"))
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                if not item.is_dir() and wanted(item.filename):
                    with z.open(item) as src, (destination / Path(item.filename).name).open("wb") as out:
                        shutil.copyfileobj(src, out)
    else:
        with tarfile.open(archive, "r:gz") as tar:
            for item in tar.getmembers():
                if wanted(item.name) and (item.isfile() or item.issym() or item.islnk()):
                    # extractfile resolves an internal link without extracting to the filesystem.
                    with tar.extractfile(item) as src, (destination / Path(item.name).name).open("wb") as out:
                        shutil.copyfileobj(src, out)
                    (destination / Path(item.name).name).chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=LLAMA, default="windows" if os.name == "nt" else "macos")
    parser.add_argument("--model", choices=MODELS, default="256")
    parser.add_argument("--runtime", type=Path, default=REPO / "runtime")
    parser.add_argument("--models-only", action="store_true")
    args = parser.parse_args()
    root = args.runtime.resolve()
    record = {"llama_release": LLAMA_TAG, "model_size": args.model, "platform": args.platform, "files": []}
    spec = MODELS[args.model]
    for key, prefix in (("model", ""), ("mmproj", "mmproj-")):
        name = f"{prefix}SmolVLM-{args.model}M-Instruct-Q8_0.gguf"
        url = f"https://huggingface.co/ggml-org/SmolVLM-{args.model}M-Instruct-GGUF/resolve/{spec['revision']}/{name}"
        download(url, root / "models" / name, spec[key])
        record["files"].append({"name": name, "url": url, "sha256": spec[key]})
    if not args.models_only:
        filename, digest = LLAMA[args.platform]
        url = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/{filename}"
        archive = download(url, root / "downloads" / filename, digest)
        unpack_selected(archive, root / "bin" / "llama", kind="llama")
        record["files"].append({"name": filename, "url": url, "sha256": digest})
        if args.platform == "windows":
            archive = download(FFMPEG_URL, root / "downloads" / FFMPEG_FILE, FFMPEG_SHA256)
            unpack_selected(archive, root / "bin", kind="ffmpeg")
            record["files"].append({"name": FFMPEG_FILE, "url": FFMPEG_URL, "sha256": FFMPEG_SHA256})
        else:
            print("macOS developer runtime: FFmpeg 7+ and FFprobe must already be on PATH.")
    (root / f"manifest-{args.model}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Runtime ready: {root}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        sys.exit(1)
