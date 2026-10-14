# Windows review from a Mac

**Status:** Windows build and execution are pending. The Mac checks pass; they do not establish Windows compatibility.

## Your Windows review area

Use [Windows 365 Business](https://www.microsoft.com/en-us/windows-365/business/all-pricing) for a Windows desktop accessible in your Mac browser. A 2-vCPU, 8-GB plan is a reasonable starting point for functional review; processing speed will depend on the Cloud PC. This is a paid service. Check current pricing and any trial terms yourself before subscribing. The app needs CPU inference, not a GPU.

Once a Cloud PC is provisioned, sign in at [Windows Cloud](https://windows.cloud.microsoft/) and select **Open in browser**. Microsoft documents browser access from macOS and transferring files at [Access a Cloud PC](https://learn.microsoft.com/en-us/windows-365/end-user-access-cloud-pc).

A static website preview does not execute the native Tk app, Windows executables or their bundled dependencies. The Cloud PC is the interactive review area; the GitHub Actions page is the automated build/report area.

A cloud review uploads your selected test video to that Cloud PC. Start with generated or non-sensitive sample footage. The app's caption processing still runs locally within the Windows session.

## Getting the first build

The private repository is [seegree/reverse-storyboard](https://github.com/seegree/reverse-storyboard). The first Windows build was started on 2026-10-14. Open [Windows portable build runs](https://github.com/seegree/reverse-storyboard/actions/workflows/windows.yml) to see the current result.

A successful run provides **EditDetector-Windows-x64** (the portable app) and **Windows-review-evidence** (reports and test output). A failed run still attempts to upload available review evidence. Sign in to GitHub with access to the private repository to download artifacts. Future pushes to main start another build; you can also use **Actions → Windows portable build → Run workflow**.

The Cloud PC subscription/setup has not been performed. You can review the automated Windows outputs on your Mac and transfer the portable folder to an available PC for hands-on testing instead of subscribing to a Cloud PC.

## Open the app in Windows

1. Transfer the downloaded app ZIP to the Cloud PC using the browser client's file-transfer feature.
2. Extract the entire ZIP. Keep `_internal` and `runtime` beside `EditDetector.exe`.
3. Double-click **EditDetector.exe**. End users do not install Python or download a model.
4. Review the app in the Windows browser session. Open a generated DOCX in Word if licensed, or transfer it back to your Mac to inspect it there. Word is not required to generate or shorten documents.

## Automated evidence

The workflow performs source tests, actual Tk state/keyboard checks, and a caption-failure/revision GUI smoke test. `scripts/validate_portable.py` invokes the bundled CLI from outside the checkout with Python/backend executables removed from the child PATH. It verifies bundled dependencies, real inference, three embedded/exported images, timecodes, paths containing spaces and accented characters, and selection revision preserving the original file. `validation.json` records command results, durations and failure details.

The automated Tk tests exercise fixture states and source GUI code. They do not replace manually launching the packaged GUI or checking its visual appearance on Windows 11. GitHub's Windows runner is also not a clean consumer laptop.

## Hands-on acceptance

Record pass/fail and any notes beside each item:

- [ ] The packaged GUI opens without Python or developer tools installed.
- [ ] All controls fit at 900×700 and 800×700, including the caption warning. No horizontal clipping.
- [ ] Tab reaches Choose video, checkboxes, Analyze, result actions, Choose document, shot numbers and Save shorter version. Space toggles checkboxes. Focus remains visible in a short window.
- [ ] Analyze a short, ordinary MP4. The Word document contains every detected shot in order.
- [ ] Repeat with both Add timecodes and Save shot images. Check time ranges and all exported JPEGs.
- [ ] The generated Word document automatically populates Make a shorter version.
- [ ] Enter `3 1`; the new document keeps shots 1 and 3, renumbers from 1, and leaves the original intact.
- [ ] Cancel analysis during inference. No partial Word document replaces a previous output.
- [ ] Read the injected-caption-failure sample in the evidence artifact: a placeholder retains its shot image. The source GUI smoke test verifies Caption issues opens the original details after revision.
- [ ] Try video/document paths containing spaces and non-ASCII characters.
- [ ] Check locked/unwritable Word output and invalid input. The error identifies the problem.
- [ ] Check an ordinary MOV with a supported codec and a longer representative edit; review caption accuracy.
- [ ] After transfer/setup, disconnect networking within the test environment and confirm the app's analysis still works. Browser access to a Cloud PC itself requires networking, so use an appropriate administrator-controlled test rather than disconnecting your Mac.

## Report back

- Build/run URL or commit:
- Windows edition/version:
- Cloud PC CPU/RAM:
- Window dimensions and display scaling:
- Test video duration and shot count:
- Processing time:
- Caption failures:
- Failed checklist items/error text:
- Overall: ready for beta / needs fixes
