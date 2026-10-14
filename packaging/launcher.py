import sys
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) > 1 or Path(sys.executable).stem.lower().endswith("-cli"):
        from edit_detector.cli import main
        raise SystemExit(main())
    else:
        from edit_detector.gui import main
        main()
