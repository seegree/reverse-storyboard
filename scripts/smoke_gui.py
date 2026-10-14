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
start = time.monotonic()
finished = []


def inspect():
    if errors:
        root.destroy()
        return
    if app.worker is not None and not app.worker.is_alive() and app.events.empty():
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
