"""Exercise presentation states with fixture events; requires a desktop and Tk."""
import argparse
from pathlib import Path
import sys
import tkinter as tk
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edit_detector.gui import Application
from edit_detector.pipeline import AnalysisResult
from edit_detector.revision import RevisionResult
import edit_detector.gui as gui

parser = argparse.ArgumentParser()
parser.add_argument('--geometry', default='900x700', help='Window size for layout checks')
parser.add_argument('--preview', action='store_true', help='Leave the fixture window open for visual review')
args = parser.parse_args()
root = tk.Tk()
app = Application(root)
root.geometry(args.geometry)
root.update()
assert not app.results.winfo_ismapped()
assert str(app.analyze_button['state']) == 'disabled'
assert str(app.cancel_button['state']) == 'disabled'
assert app.video_name.get() == 'No video chosen'
assert not app.keep_numbers.get()
assert app.keep_hint.winfo_ismapped()
app.path.set('/demo/sample-video.mov')
assert app.video_name.get() == 'sample-video.mov'
assert str(app.analyze_button['state']) == 'normal'
app.busy(True)
root.update()
assert app.results.winfo_ismapped()
assert str(app.cancel_button['state']) == 'normal'
assert str(app.analyze_button['state']) == 'disabled'
app.events.put(('progress', ('Captioning shot 2 of 3…', 1/3)))
app.poll()
assert app.percent.get() == '33%'

source = str(Path('samples/gui-caption-failure.docx').resolve())
def finish(count, images=None):
    app.busy(True)
    app.caption_details = ''
    shots = [{'number': i, 'caption_error': 'Simulated caption timeout' if i <= count else None} for i in range(1, 4)]
    app.events.put(('done', AnalysisResult(source, shots, {'total_seconds': 1}, 'UI fixture', images)))
    app.poll()
    root.update()
    assert app.revision_source.get() == source
    assert app.document_name.get() == Path(source).name
    assert app.status.get() == 'Done — 3 shots saved'
    assert app.percent.get() == '100%'
    assert str(app.cancel_button['state']) == 'disabled'
    assert str(app.analyze_button['state']) == 'normal'
    assert bool(app.warning.winfo_ismapped()) == bool(count)

finish(0)
assert str(app.images_button['state']) == 'disabled'
finish(2, '/demo/images')
assert str(app.images_button['state']) == 'normal'
assert app.warning_text.get().startswith('2 captions need writing.')
finish(1)
assert app.warning_text.get().startswith('1 caption needs writing.')
app.busy(True)
app.events.put(('revised', RevisionResult('/demo/selected.docx', [1, 3], 3)))
app.poll()
assert str(app.details_button['state']) == 'normal'
assert app.revision_source.get() == source
for event in [('cancelled', None), ('error', 'Fixture save error')]:
    gui.messagebox.showerror = Mock()
    app.busy(True)
    app.events.put(event)
    app.poll()
    assert str(app.cancel_button['state']) == 'disabled'
    assert str(app.analyze_button['state']) == 'normal'
    assert str(app.details_button['state']) == 'normal'
finish(1)
app.keep_numbers.set('1 3')
assert not app.keep_hint.winfo_ismapped()
app.keep_numbers.set('')
root.update()
assert app.keep_hint.winfo_ismapped()
# All controls must fit horizontally; vertical overflow is intentionally scrollable.
assert app.revise_button.winfo_rootx() + app.revise_button.winfo_width() <= root.winfo_rootx() + root.winfo_width()
assert app.images_button.winfo_rootx() + app.images_button.winfo_width() <= root.winfo_rootx() + root.winfo_width()
assert app.content_panel.winfo_reqheight() <= app.viewport.winfo_height(), (app.content_panel.winfo_reqheight(), app.viewport.winfo_height())
print(f'Layout: content {app.content_panel.winfo_reqheight()}px, viewport {app.viewport.winfo_height()}px', flush=True)
print('PASS: idle, chosen, running, success, warning counts, revision, cancellation and error states', flush=True)
if args.preview:
    root.title('Edit Detector — Design preview (simulated caption issue)')
    root.lift()
    root.mainloop()
else:
    root.destroy()
