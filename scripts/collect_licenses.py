"""Keep installed package licenses/notices with a portable distribution."""
import argparse
import importlib.metadata as metadata
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument("destination", type=Path)
args = parser.parse_args()
args.destination.mkdir(parents=True, exist_ok=True)
packages = ["scenedetect", "opencv-python-headless", "numpy", "python-docx", "lxml", "pillow",
            "click", "platformdirs", "tqdm", "typing_extensions", "pyinstaller"]
lines = []
for name in packages:
    package = metadata.distribution(name)
    lines.append(f"{name} {package.version}")
    target = args.destination / name
    target.mkdir(exist_ok=True)
    (target / "METADATA.txt").write_text(package.read_text("METADATA") or "", encoding="utf-8")
    for file in package.files or []:
        if any(term in str(file).lower() for term in ("license", "copying", "notice")):
            source = Path(package.locate_file(file))
            if source.is_file():
                # Preserve relative path to avoid license basename collisions.
                safe_parts = [part for part in file.parts if part not in ("..", "/")]
                destination = target.joinpath(*safe_parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
(args.destination / "versions.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
