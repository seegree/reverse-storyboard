# Implementation checkpoints

Updated 2026-10-13. Working environment: macOS arm64, Python 3.12.14, FFmpeg 9.0.2.

| Stage | Status | Evidence |
| --- | --- | --- |
| 1 Video processing | Implemented and tested | Known cuts/order, no cuts, exact midpoint pixels, 29.97 FPS, non-square pixels, 1,001 shots, corrupt input |
| 2 Local captioning | Inference verified; quality needs work | Actual CPU runs with 256M and 500M Q8 pairs; deterministic/0.2 comparison; errors documented |
| 3 Word output | Implemented and tested | Embedded images, real list numbering, aspect ratios, reopen, rendered page inspection |
| 4 Integration | Implemented and tested | Four-shot motion clip, three-photo clip, three-color self-test; timing and memory measurements |
| 5 GUI | Implemented and tested on Mac | Real Tk event loop, Analyze completion, Cancel without publishing output |
| 6 Windows distribution | Prepared, not executed | Verified Windows archives/wheels, PyInstaller spec, build script and CI smoke test |

The automated suite passes 27 tests. No Windows executable or benchmark is claimed. Caption accuracy does not yet meet a reliable automatic-acceptance standard.

## Checkpoints

- `d4b4c0c`: independently passing Stage 1 prototype, six initial tests.
- The subsequent MVP checkpoint adds inference, Word output, GUI, packaging and expanded tests; see `git log --oneline`.

## Next steps

1. Run the Windows build and portable EXE smoke test on the user's laptop or the provided Windows workflow, then on a clean Windows machine.
2. Score cuts and captions on representative user footage. Both tested small models produced unsupported details; 500M did not justify replacing 256M by default.
3. Validate long/4K videos, rotated phone footage, VFR temporal midpoints and unusual codecs. These remain outside the established test coverage.
4. Measure Windows startup, RAM and actual compressed/folder size. Prepare redistribution source/notice materials before a public binary release.

No database, network service, cloud API, GPU requirement or heavyweight Python ML framework was introduced. File selection is implemented; drag-and-drop is deferred to avoid another GUI dependency.
