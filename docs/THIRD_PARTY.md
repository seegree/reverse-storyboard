# Third-party components and provenance

Checked 2026-10-13. Native/model versions, immutable URLs and SHA-256 hashes are in `scripts/fetch_runtime.py`. Setup records them in a runtime manifest.

| Component | Selected version | Source/license |
| --- | --- | --- |
| PySceneDetect | 0.6.7.1 | [API](https://www.scenedetect.com/docs/0.6.7/api/detectors.html), BSD-3-Clause |
| OpenCV headless | 5.0.0.93 wheel | [Packaging](https://github.com/opencv/opencv-python), collect bundled notices from wheel |
| python-docx | 1.2.0 | [Project](https://github.com/python-openxml/python-docx), MIT |
| Pillow | 12.3.0 | [Project](https://github.com/python-pillow/Pillow), HPND |
| llama.cpp | b11429, v0.6.0 binary tag | [Release](https://github.com/ggml-org/llama.cpp/releases/tag/b11429), MIT |
| SmolVLM 256M/500M | Q8_0 model and matching Q8_0 mmproj | [256M](https://huggingface.co/ggml-org/SmolVLM-256M-Instruct-GGUF/tree/main), [500M](https://huggingface.co/ggml-org/SmolVLM-500M-Instruct-GGUF/tree/main), Apache-2.0 |
| FFmpeg/FFprobe (Windows) | Gyan Windows 9.0.2 essentials | [Provider](https://www.gyan.dev/ffmpeg/builds/), GPLv3 build |
| FFmpeg/FFprobe (macOS arm64) | Martin Riedl FFmpeg 9.0.2 static release | [Provider and release](https://ffmpeg.martin-riedl.de/), GPLv3 build; runtime fetch verifies the provider's SHA-256 sidecars |
| Python/Tcl/Tk | Python 3.12 for Windows | [Python license](https://docs.python.org/3/license.html), retain Tcl/Tk notices |
| PyInstaller | 6.x build tool | [Project](https://github.com/pyinstaller/pyinstaller), GPL with bootloader exception |

NumPy, lxml, click, platformdirs, tqdm and typing_extensions are transitive dependencies. `scripts/collect_licenses.py` copies the installed license/notice files and metadata. `development-lock-macos.txt` records the tested environment; it is not a Windows lock file.

[llama.cpp multimodal documentation](https://github.com/ggml-org/llama.cpp/blob/b11429/docs/multimodal.md) lists both SmolVLM variants and documents explicit model/projector paths and CPU projector execution. The actual b11429 `llama-mtmd-cli` was tested with both pairs. Upstream labels this CLI experimental, so its version is pinned and upgrades must repeat the model checks. It avoids a web server and large Python inference framework.

License texts are retained in `docs/licenses/`. Setup also retains the Windows FFmpeg archive's LICENSE/README and llama.cpp's LICENSE when present. The Mac FFmpeg provider publishes static arm64 binaries and SHA-256 sidecars; the build manifest records the verified archive digests. Source locations include [llama.cpp b11429](https://github.com/ggml-org/llama.cpp/tree/b11429), [FFmpeg n9.0.2](https://github.com/FFmpeg/FFmpeg/tree/n9.0.2), and the source/build links in the retained provider README. Before public binary distribution, prepare applicable complete corresponding source materials, including enabled third-party FFmpeg libraries; upstream links alone are not claimed to complete redistribution preparation.

Test media remain separate local QA fixtures. See `VALIDATION.md` for origins. The portable smoke test generates its color-card video offline.
