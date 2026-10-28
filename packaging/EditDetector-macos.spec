# Build on Apple Silicon macOS using Python 3.12. Runtime assets are added to Resources.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "packaging" / "launcher.py")], pathex=[str(root)],
    binaries=[], datas=[], hiddenimports=["PIL.JpegImagePlugin"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["pytest", "psutil", "matplotlib", "scipy", "torch", "transformers"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Reverse Storyboard", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Reverse Storyboard")
app = BUNDLE(coll, name="Reverse Storyboard.app", bundle_identifier="com.seegree.reversestoryboard")
