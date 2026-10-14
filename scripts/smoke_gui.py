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
parser.add_argument("--options-and-revise", action="store_true")
args = parser.parse_args()
if args.output.exists():
    parser.error("Use a new output filename for the GUI smoke test.")
gui.filedialog.asksaveasfilename = lambda **kwargs: str(args.output.resolve())
errors = []
gui.messagebox.showerror = lambda title, message: errors.append((title, message))
root = tk.Tk()
app = gui.Application(root)
app.path.set(str(args.video.resolve()))
root.report_callback_exception = lambda cls, value, tb: errors.append((cls.__name__, str(value)))
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
        finished.append(app.status.get())
        root.destroy()
        return
    if time.monotonic() - start > 120:
        app.stop()
        errors.append(("Timeout", "GUI did not complete in 120 seconds"))
        root.destroy()
        return
    root.after(50, inspect)


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
