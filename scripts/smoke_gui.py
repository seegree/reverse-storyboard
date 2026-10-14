"""Run the actual GUI worker and event loop with scripted file-dialog selections."""
import argparse
from pathlib import Path
import sys
import time
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import edit_detector.gui as gui

parser = argparse.ArgumentParser()
parser.add_argument("video", type=Path)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--cancel", action="store_true")
parser.add_argument("--caption-failure", action="store_true", help="Inject a last-shot caption failure")
parser.add_argument("--options-and-revise", action="store_true")
args = parser.parse_args()
if args.output.exists():
    parser.error("Use a new output filename for the GUI smoke test.")
gui.filedialog.asksaveasfilename = lambda **kwargs: str(args.output.resolve())
errors = []
gui.messagebox.showerror = lambda title, message: errors.append((title, message))
if args.caption_failure:
    from edit_detector.caption import Caption
    from edit_detector.errors import AppError
    real_analyze = gui.analyze
    class TestCaptioner:
        def __init__(self):
            self.count = 0
        def caption(self, image, **kwargs):
            self.count += 1
            if self.count == 3:
                raise AppError("Injected last-shot caption timeout")
            return Caption("Test scene", "Test scene", 0, 1)
    gui.analyze = lambda *a, **kw: real_analyze(*a, captioner=TestCaptioner(), **kw)
root = tk.Tk()
app = gui.Application(root)
app.path.set(str(args.video.resolve()))
def callback_error(cls, value, tb):
    errors.append((cls.__name__, str(value)))
    root.after_idle(root.destroy)
root.report_callback_exception = callback_error
if args.options_and_revise:
    app.include_timecodes.set(True)
    app.export_images.set(True)
revised = False
start = time.monotonic()
finished = []


def inspect():
    global revised
    if errors:
        root.destroy()
        return
    if app.worker is not None and not app.worker.is_alive() and app.events.empty():
        root.update_idletasks()
        if args.caption_failure and not revised:
            assert "Shot 3:" in app.caption_details
            assert str(app.details_button['state']) == 'normal'
            assert '1 caption needs writing.' in app.warning_text.get()
            assert app.warning.winfo_ismapped()
        if args.options_and_revise and not revised:
            assert app.images_folder.is_dir()
            assert app.revision_source.get() == str(args.output.resolve())
            assert root.winfo_height() >= root.winfo_reqheight()
            app.keep_numbers.set("3 1")
            gui.filedialog.asksaveasfilename = lambda **kwargs: str(args.output.with_stem(args.output.stem + "-selected").resolve())
            revised = True
            app.revise()
            root.after(50, inspect)
            return
        if args.caption_failure and revised:
            assert str(app.details_button['state']) == 'normal'
            dialogs = []
            gui.messagebox.showwarning = lambda title, message: dialogs.append(message)
            app.details_button.invoke()
            assert len(dialogs) == 1 and "Shot 3:" in dialogs[0]
            assert "Original analysis:" in dialogs[0]
            assert str(args.output.resolve()) in dialogs[0]
        finished.append(app.status.get())
        root.destroy()
        return
    if time.monotonic() - start > 120:
        app.stop()
        errors.append(("Timeout", "GUI did not complete in 120 seconds"))
        root.destroy()
        return
    root.after(50, inspect)


def deadline():
    app.stop()
    errors.append(("Timeout", "GUI did not complete in 120 seconds"))
    root.destroy()
root.after(120000, deadline)
root.after(100, app.start)
if args.cancel:
    root.after(400, app.stop)
root.after(200, inspect)
root.mainloop()
assert not errors, errors
assert finished, "GUI did not reach a terminal state"
if args.cancel:
    assert not args.output.exists(), "Cancellation published a document"
    assert "cancelled" in finished[0].lower(), finished
else:
    assert args.output.is_file(), "GUI did not write the document"
print("PASS:", finished[0])

if args.options_and_revise:
    from docx import Document
    selected = Document(args.output.with_stem(args.output.stem + "-selected"))
    assert len(selected.inline_shapes) == 2
    assert "00:00:" in selected.paragraphs[2].text
    assert "2 of 3" in finished[0]
