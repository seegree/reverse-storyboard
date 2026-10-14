# Build on Windows using Python 3.12 x64. Runtime assets remain beside the EXEs.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "packaging" / "launcher.py")], pathex=[str(root)],
    binaries=[], datas=[], hiddenimports=["PIL.JpegImagePlugin"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["pytest", "psutil", "matplotlib", "scipy", "torch", "transformers"], noarchive=False,
)
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EditDetector", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EditDetector-CLI", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(gui, cli, a.binaries, a.datas, strip=False, upx=False, name="EditDetector")
