# Validation record

Checks performed on 2026-10-13 on macOS arm64. These results do not predict the user's Windows laptop performance. GPU offload was explicitly disabled for both model and projector.

## Functional checks

`python -m pytest -q`: **27 passed**. Tests cover known hard-cut boundaries/order, no cuts, one-frame shots, exact midpoint pixels in a changing shot, fractional FPS, pixel aspect ratio, 1,001 shots, missing/corrupt video, output protection, subprocess timeouts/cancellation, caption cleanup/retry, embedded DOCX images/numbering/aspect ratios, temporary-file cleanup, and preserving previous output after failure.

The 1,001-shot test exposed FFmpeg's limit on deeply nested expressions. A balanced conditional expression in a filter file fixed it and avoids Windows command-line length limits. There is still just one FFmpeg extraction pass.

GUI checks used the actual Tk window, background worker and progress queue. Analyze produced a document; Cancel stopped a second run without publishing one. The project venv's Homebrew Python lacks `_tkinter`, so GUI tests used Codex's bundled Python 3.12/Tk 9 with project dependencies. Windows GUI behavior has not been tested.

DOCX checks verified embedded media relationships, real numbering and successful reopening after source JPEG deletion. Both sample documents were rendered with bundled LibreOffice; every page was inspected. Numbering continuity, image placement, title formatting and page breaks passed visual review. Microsoft Word itself is unavailable here.

## Actual videos

| Input | Shots | Result |
| --- | --- | --- |
| Three color shots, 24 FPS | 3 | Exact boundaries/colors; complete real-model self-test passed |
| OpenCV Megamind clip, 270 frames at 23.976 FPS | 4 | Boundaries 0, 98, 154, 200, 270; four embedded midpoint images |
| Six-second video made from three photographs | 3 | Boundaries 0, 48, 96, 144; CLI and GUI documents generated |
| Alternating one-frame shots | 1,001 | All detected/extracted in chronological order |

The final measured four-shot CLI run took **8.86 seconds wall time**, including Python startup. The pipeline reported **8.68 seconds**. Peak combined RSS for Python and its children was **670.05 MiB**, sampled every 20 ms. Shared pages can be counted twice; this is a practical measurement, not a guaranteed RAM ceiling. Earlier uninstrumented runs took 5.21 seconds with 256M and 6.58 seconds with 500M. Image tiling, retries and system load affect timing.

The three-photo memory measurement overlapped a GUI check and took 16.22 seconds, so it is not an isolated performance claim. Initial process inspection was sandbox-blocked; completed measurements used approved access to the pipeline's processes.

## Caption quality

Both official Q8 model/projector pairs downloaded and matched their published SHA-256 checks. llama.cpp b11429 (v0.6.0) executed both on CPU, with explicit local paths and `--device none --gpu-layers 0 --no-mmproj-offload --offline`.

On the original three photographs, 256M at temperature zero produced:

- Coffee: “The cup of coffee is on the red saucer.”
- Cat: “The cat is in front of a blurry background.”
- Astronaut: “The woman is standing and smiling.”

All three repeated exactly in a second run here. Per-image times were about 1.19–1.31 seconds including process/model initialization. Temperature 0.2 changed coffee wording without a clear accuracy gain. Three images are insufficient to establish a general quality rate.

500M took about 1.46–1.56 seconds on those images, but produced fragments and unsupported details. In the cartoon clip it invented a knife and fork where a character held a glass. 256M sometimes called an animated frame a painting or merely said “It is a movie.” In the encoded photo clip, it called coffee tea. Resizing/compression and prompt wording changed answers. Neither model consistently met the desired 8–20 word objective-sentence standard.

A simpler prompt worked better than a long list of constraints for 256M. Bounded generation, one-sentence cleanup and one malformed-response retry are implemented; they do not detect invented objects. No outputs were manually corrected to improve reported results. 256M remains default because 500M did not earn its larger footprint in this test set. Caption accuracy remains a release-quality blocker, especially on animation and fine details.

## Retained evidence

Local `samples/` contains inputs, DOCX outputs, reports, comparisons and render images and is ignored by Git. Small JSON reports are copied to `docs/validation/` for preservation. Test media are not bundled in the app.

Sources: [OpenCV Megamind sample](https://github.com/opencv/opencv/blob/4.x/samples/data/Megamind.avi), [scikit-image v0.19.3 data](https://github.com/scikit-image/scikit-image/tree/v0.19.3/skimage/data) (`coffee.png`, `chelsea.png`, `astronaut.png`). The photo video is a generated slideshow fixture; the OpenCV clip is the separate motion-video test.

## Output options and revision — 2026-10-14

- All 38 automated tests pass on macOS arm64. Added coverage for the requested selection of 10 shots from a 51-shot fixture, preserved source bytes and caption formatting, shared images, removed unused media, repeated revisions, invalid selections, elapsed time formatting, exported manifests and export rollback on document failure.
- Real local inference on `samples/photo-demo.mp4`: three shots exported with timecodes and a persistent JPEG folder in 3.90 seconds. Phrase output was accepted (for example, “Cat, background is blurry.”). Caption factual errors remain: the coffee was described as tea.
- Revised the new document from three shots to two, and an older MVP document from four shots to two, without model inference.
- Rendered and visually checked both pages of the timecoded sample and the single page of its shortened version. Numbering, image placement and retained time ranges are correct.
- Actual Tk GUI worker/event-loop smoke test passed with both options enabled and a subsequent selection of shots 1 and 3. The resulting document contains two images and timecodes; its displayed list restarts at 1.
- Windows execution remains untested.

## Caption failure recovery — 2026-10-14

40 tests pass, including last-shot failure, all-caption failure, preserved successful captions/images, and cancellation preserving an existing document. An actual Mac GUI smoke test injected a failure on the final shot: all three shots saved, the persistent status and Caption issues button exposed the failure, and selection revision still succeeded. The revised Word page was rendered and visually checked with the placeholder and corresponding image intact. No claim is made to have reproduced the user's specific model failure; its original diagnostic was unavailable.
