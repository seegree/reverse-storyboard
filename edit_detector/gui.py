"""Tk widgets stay on the main thread; all video and inference work runs in a worker."""

import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .errors import AppError, Cancelled
from .pipeline import analyze
from .revision import revise_document
from .gui_widgets import ACCENT, BG, BORDER, CARD, INSET, Card, Tooltip, configure_theme, placeholder


def open_path(path: Path):
    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.output = None
        self.images_folder = None
        self.closing = False
        self.caption_details = ""
        self.working = False
        self.caption_issue_count = 0
        root.title("Edit Detector")
        root.minsize(800, 560)
        root.geometry(f"900x{min(700, root.winfo_screenheight() - 100)}")
        root.protocol("WM_DELETE_WINDOW", self.close)
        configure_theme(root)
        # Keep every action reachable on laptop displays when Results expands.
        viewport = tk.Canvas(root, background=BG, highlightthickness=0, takefocus=0)
        scroll = ttk.Scrollbar(root, orient='vertical', command=viewport.yview)
        viewport.configure(yscrollcommand=scroll.set)
        viewport.pack(side='left', fill='both', expand=True)
        panel = ttk.Frame(viewport, padding=(24, 18))
        panel_id = viewport.create_window(0, 0, window=panel, anchor='nw')
        viewport.bind('<Configure>', lambda e: viewport.itemconfigure(panel_id, width=e.width))
        def update_scroll(event=None):
            viewport.configure(scrollregion=viewport.bbox('all'))
            if panel.winfo_reqheight() > viewport.winfo_height():
                if not scroll.winfo_manager():
                    scroll.pack(side='right', fill='y', before=viewport)
            else:
                scroll.pack_forget()
                viewport.yview_moveto(0)
        panel.bind('<Configure>', update_scroll)
        viewport.bind('<Configure>', update_scroll, add='+')
        self.content_panel = panel
        def wheel(event):
            if panel.winfo_height() > viewport.winfo_height():
                amount = -int(event.delta) if sys.platform == 'darwin' else -int(event.delta / 120)
                viewport.yview_scroll(amount, 'units')
        root.bind('<MouseWheel>', wheel, add='+')
        self.viewport = viewport
        root.bind('<FocusIn>', self.reveal_focus, add='+')
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text='EDIT DETECTOR', style='Eyebrow.TLabel').grid(row=1, sticky='e')
        ttk.Label(panel, text='Shot Breakdown', style='Title.TLabel').grid(row=1, sticky='w', pady=(2, 4))
        ttk.Label(panel, text='Turn a video into a Word document with one frame and one caption for every shot.',
                  style='Secondary.TLabel', wraplength=660).grid(row=2, sticky='w', pady=(0, 10))

        video_card = Card(panel, padding=12)
        video_card.grid(row=3, sticky='ew', pady=(0, 10))
        file_row = tk.Frame(video_card.content, background=INSET, padx=10, pady=8,
                            highlightbackground='#4A4B52', highlightthickness=1)
        file_row.pack(fill='x')
        self.path = tk.StringVar()
        self.video_name = tk.StringVar(value='No video chosen')
        ttk.Label(file_row, text='Video', style='Inset.TLabel').pack(side='left', padx=(0, 12))
        self.entry = ttk.Label(file_row, textvariable=self.video_name, style='Inset.TLabel', width=1)
        self.entry.pack(side='left', fill='x', expand=True, padx=(0, 12))
        Tooltip(self.entry, lambda: self.path.get())
        self.browse = ttk.Button(file_row, text='Choose video…', command=self.choose)
        self.browse.pack(side='right')

        options = Card(panel, padding=12)
        options.grid(row=4, sticky='ew', pady=(0, 10))
        option_row = tk.Frame(options.content, background=CARD)
        option_row.pack(fill='x')
        tiles = tk.Frame(option_row, background=CARD)
        tiles.pack(side='left', fill='x', expand=True)
        tiles.columnconfigure((0, 1), weight=1, uniform='tiles')
        self.include_timecodes = tk.BooleanVar(value=False)
        self.export_images = tk.BooleanVar(value=False)
        def option(column, text, helper, variable):
            tile = tk.Frame(tiles, background=INSET, padx=10, pady=8)
            tile.grid(row=0, column=column, sticky='nsew', padx=(0, 6) if column == 0 else (6, 0))
            check = ttk.Checkbutton(tile, text=text, variable=variable)
            check.pack(anchor='w')
            ttk.Label(tile, text=helper, style='Helper.TLabel', wraplength=210).pack(anchor='w', padx=(22, 0), pady=(4, 0))
            return check
        self.timecode_check = option(0, 'Add timecodes', 'Show elapsed time under each shot', self.include_timecodes)
        self.images_check = option(1, 'Save shot images', 'Also export every frame to a folder', self.export_images)
        actions = tk.Frame(option_row, background=CARD)
        actions.pack(side='right', padx=(12, 0))
        self.analyze_button = ttk.Button(actions, text='Analyze video', style='Primary.TButton', command=self.start, state='disabled')
        self.analyze_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='Cancel', command=self.stop, state='disabled')
        self.cancel_button.pack(side='left', padx=10)

        self.results = Card(panel, padding=12)
        self.results.grid(row=5, sticky='ew', pady=(0, 10))
        result = self.results.content
        result.columnconfigure(0, weight=1)
        status_row = tk.Frame(result, background=CARD)
        status_row.grid(row=0, sticky='ew')
        self.status_icon = ttk.Label(status_row, text='◌', style='CardHeading.TLabel', foreground=ACCENT)
        self.status_icon.pack(side='left', padx=(0, 10))
        self.status = tk.StringVar(value='Ready. Processing runs locally on your CPU.')
        self.percent = tk.StringVar(value='')
        ttk.Label(status_row, textvariable=self.percent, style='Percent.TLabel').pack(side='right')
        ttk.Label(status_row, textvariable=self.status, style='CardHeading.TLabel', wraplength=510).pack(side='left', fill='x', expand=True)
        self.bar = ttk.Progressbar(result, mode='indeterminate', maximum=100)
        self.bar.grid(row=1, sticky='ew', pady=(10, 0))
        self.warning = tk.Frame(result, background='#3A2F1A', highlightbackground='#6B5320', highlightthickness=1, padx=12, pady=8)
        self.warning.grid(row=2, sticky='ew', pady=(10, 0))
        self.warning.columnconfigure(1, weight=1)
        ttk.Label(self.warning, text='⚠', style='Warning.TLabel', foreground='#F4C15D').grid(row=0, column=0, padx=(0, 12))
        self.warning_text = tk.StringVar()
        ttk.Label(self.warning, textvariable=self.warning_text, style='Warning.TLabel', wraplength=490).grid(row=0, column=1, sticky='w')
        self.details_button = ttk.Button(self.warning, text='Caption issues…', style='Warning.TButton', state='disabled',
            command=lambda: messagebox.showwarning('Caption issues', self.caption_details))
        self.details_button.grid(row=0, column=2, padx=(12, 0))
        self.warning.grid_remove()
        buttons = tk.Frame(result, background=CARD)
        buttons.grid(row=3, sticky='ew', pady=(10, 0))
        self.open_button = ttk.Button(buttons, text='Open Word document', style='Open.TButton', command=lambda: self.open_result(False), state='disabled')
        self.open_button.pack(side='left')
        self.folder_button = ttk.Button(buttons, text='Show in folder', command=lambda: self.open_result(True), state='disabled')
        self.folder_button.pack(side='left', padx=10)
        self.images_button = ttk.Button(buttons, text='Open shot images', command=self.open_images, state='disabled')
        self.images_button.pack(side='left')
        Tooltip(self.images_button, lambda: 'Turn on "Save shot images" to use this' if not self.images_folder else str(self.images_folder))
        self.results.grid_remove()

        ttk.Separator(panel).grid(row=6, sticky='ew', pady=(0, 10))
        ttk.Label(panel, text='Make a shorter version', style='Heading.TLabel').grid(row=7, sticky='w')
        ttk.Label(panel, text='Keep only the shots you list. They stay in order and are renumbered from 1.',
                  style='Secondary.TLabel', wraplength=660).grid(row=8, sticky='w', pady=(4, 10))
        document_row = ttk.Frame(panel)
        document_row.grid(row=9, sticky='ew')
        document_row.columnconfigure(0, weight=1)
        document_field = tk.Frame(document_row, background=CARD, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=9)
        document_field.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        ttk.Label(document_field, text='▤', style='Card.TLabel').pack(side='left', padx=(0, 8))
        self.revision_source = tk.StringVar()
        self.document_name = tk.StringVar(value='No document chosen')
        self.revision_entry = ttk.Label(document_field, textvariable=self.document_name, style='Card.TLabel', width=1)
        self.revision_entry.pack(side='left', fill='x', expand=True)
        Tooltip(self.revision_entry, lambda: self.revision_source.get())
        self.revision_browse = ttk.Button(document_row, text='Choose…', command=self.choose_document)
        self.revision_browse.grid(row=0, column=1)
        keep_row = ttk.Frame(panel)
        keep_row.grid(row=11, sticky='ew', pady=(10, 0))
        keep_row.columnconfigure(1, weight=1)
        ttk.Label(keep_row, text='Shots to keep').grid(row=0, column=0, padx=(0, 12))
        self.keep_numbers = tk.StringVar()
        self.keep_entry = ttk.Entry(keep_row, textvariable=self.keep_numbers)
        self.keep_entry.grid(row=0, column=1, sticky='ew', padx=(0, 10))
        self.keep_hint = placeholder(self.keep_entry, self.keep_numbers, 'e.g. 3 6 11 13 14 25')
        self.revise_button = ttk.Button(keep_row, text='Save shorter version…', command=self.revise)
        self.revise_button.grid(row=0, column=2)
        self.path.trace_add('write', self.refresh_file_names)
        self.revision_source.trace_add('write', self.refresh_file_names)
        root.after(100, self.poll)

    def reveal_focus(self, event):
        """Keep keyboard-focused controls visible when the small-window fallback scrolls."""
        widget = event.widget
        if self.content_panel not in self._parents(widget):
            return
        self.root.after_idle(lambda: self._reveal_widget(widget))

    @staticmethod
    def _parents(widget):
        while widget is not None:
            yield widget
            widget = getattr(widget, 'master', None)

    def _reveal_widget(self, widget):
        if not widget.winfo_exists() or not widget.winfo_ismapped():
            return
        top = widget.winfo_rooty() - self.viewport.winfo_rooty()
        bottom = top + widget.winfo_height()
        height = self.viewport.winfo_height()
        offset = top - 8 if top < 0 else bottom - height + 8 if bottom > height else 0
        if offset:
            total = max(1, self.content_panel.winfo_height())
            self.viewport.yview_moveto((self.viewport.canvasy(0) + offset) / total)

    def refresh_file_names(self, *args):
        self.video_name.set(Path(self.path.get()).name if self.path.get() else 'No video chosen')
        self.document_name.set(Path(self.revision_source.get()).name if self.revision_source.get() else 'No document chosen')
        self.analyze_button.configure(state='normal' if self.path.get() and not self.working else 'disabled')

    def show_caption_warning(self, count):
        self.caption_issue_count = count
        if count:
            text = ("1 caption needs writing. It's marked as a placeholder in the document." if count == 1 else
                    f"{count} captions need writing. They're marked as placeholders in the document.")
            self.warning_text.set(text)
            self.warning.grid()
        else:
            self.warning.grid_remove()

    def choose(self):
        filename = filedialog.askopenfilename(title="Choose an edited video", filetypes=[
            ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mts *.mxf"), ("All files", "*.*")])
        if filename:
            self.path.set(filename)

    def busy(self, working):
        self.working = working
        self.results.grid()
        for button in (self.browse, self.analyze_button, self.entry, self.timecode_check, self.images_check,
                       self.revision_entry, self.revision_browse, self.keep_entry, self.revise_button):
            button.configure(state="disabled" if working else "normal")
        self.refresh_file_names()
        self.cancel_button.configure(state="normal" if working else "disabled")
        if working:
            self.percent.set("")
            self.status_icon.configure(text="◌")
            self.open_button.configure(state="disabled")
            self.folder_button.configure(state="disabled")
            self.images_button.configure(state="disabled")
            self.details_button.configure(state="disabled")
            self.bar.configure(mode="indeterminate")
            self.bar.start(12)
        else:
            self.bar.stop()
            self.open_button.configure(state="normal" if self.output else "disabled")
            self.folder_button.configure(state="normal" if self.output else "disabled")
            self.images_button.configure(state="normal" if self.images_folder else "disabled")
            self.details_button.configure(state="normal" if self.caption_details else "disabled")

    def start(self):
        video = Path(self.path.get().strip()).expanduser()
        if not video.is_file():
            messagebox.showerror("Select a video", "Choose an existing video file first.")
            return
        destination = filedialog.asksaveasfilename(title="Save the shot breakdown", defaultextension=".docx",
            initialdir=str(video.parent), initialfile=video.stem + "-shots.docx", filetypes=[("Word document", "*.docx")])
        if not destination:
            return
        self.cancel.clear()
        self.output = None
        self.images_folder = None
        self.caption_details = ""
        self.show_caption_warning(0)
        include_timecodes = self.include_timecodes.get()
        images_folder = None
        if self.export_images.get():
            document = Path(destination)
            images_folder = document.with_name(document.stem + "-images")
            suffix = 2
            while images_folder.exists():
                images_folder = document.with_name(f"{document.stem}-images-{suffix}")
                suffix += 1
        self.busy(True)
        self.status.set("Preparing local analysis…")

        def work():
            try:
                result = analyze(video, Path(destination), cancel=self.cancel, overwrite=True,
                                 include_timecodes=include_timecodes, export_images=images_folder,
                                 progress=lambda text, fraction: self.events.put(("progress", (text, fraction))))
                self.events.put(("done", result))
            except Cancelled:
                self.events.put(("cancelled", None))
            except (AppError, OSError) as exc:
                self.events.put(("error", str(exc)))
            except Exception as exc:
                self.events.put(("error", f"Unexpected analysis error: {type(exc).__name__}: {exc}"))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def choose_document(self):
        filename = filedialog.askopenfilename(title="Choose a shot breakdown", filetypes=[("Word document", "*.docx")])
        if filename:
            self.revision_source.set(filename)

    def revise(self):
        source = Path(self.revision_source.get().strip()).expanduser()
        selection = self.keep_numbers.get().strip()
        if not source.is_file() or not selection:
            messagebox.showerror("Choose shots", "Choose a shot document and enter the shot numbers to keep.")
            return
        destination = filedialog.asksaveasfilename(title="Save the shorter version", defaultextension=".docx",
            initialdir=str(source.parent), initialfile=source.stem + "-selected.docx", filetypes=[("Word document", "*.docx")])
        if not destination:
            return
        if source.resolve() == Path(destination).resolve():
            messagebox.showerror("Choose a new filename", "The original document is preserved. Save the shorter version under a new name.")
            return
        self.cancel.clear()
        self.busy(True)
        self.status.set("Creating the shorter document…")

        def work():
            try:
                result = revise_document(source, selection, Path(destination), overwrite=True, cancel=self.cancel)
                self.events.put(("revised", result))
            except Cancelled:
                self.events.put(("cancelled", None))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def stop(self):
        self.cancel.set()
        self.cancel_button.configure(state="disabled")
        self.status.set("Cancelling…")

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    text, fraction = value
                    if not self.cancel.is_set():
                        self.status.set(text)
                    if fraction is not None:
                        self.bar.stop()
                        self.bar.configure(mode="determinate", value=fraction * 100)
                        self.percent.set(f"{round(fraction * 100)}%")
                else:
                    self.busy(False)
                    if kind == "done":
                        self.output = Path(value.output)
                        self.revision_source.set(value.output)
                        self.images_folder = Path(value.images_folder) if value.images_folder else None
                        self.bar.configure(mode="determinate", value=100)
                        self.percent.set("100%")
                        self.status_icon.configure(text="✓")
                        self.status.set(f"Done — {len(value.shots)} shots saved")
                        self.show_caption_warning(len(value.caption_failures))
                        if value.caption_failures:
                            numbers = ", ".join(str(shot["number"]) for shot in value.caption_failures)
                            self.caption_details = (
                                f"Original analysis: {value.output}\nShot numbers below refer to that original document, before any selection or renumbering.\n\n"
                                f"The document was saved with every shot image. Missing captions: {numbers}.\n\n"
                                "Open the Word document and replace each [Caption unavailable] placeholder with your own description. "
                                "You can still use Save selected shots to make a shorter version.\n\n"
                                + "\n\n".join(f"Shot {shot['number']}: {shot['caption_error']}" for shot in value.caption_failures))
                            self.details_button.configure(state="normal")
                        self.open_button.configure(state="normal")
                        self.folder_button.configure(state="normal")
                        if self.images_folder:
                            self.images_button.configure(state="normal")
                    elif kind == "revised":
                        self.output = Path(value.output)
                        self.bar.configure(mode="determinate", value=100)
                        self.percent.set("100%")
                        self.status_icon.configure(text="✓")
                        self.status.set(f"Saved {len(value.kept_numbers)} of {value.original_count} shots, numbered from 1. Original document preserved.")
                        self.open_button.configure(state="normal")
                        self.folder_button.configure(state="normal")
                        if self.images_folder:
                            self.images_button.configure(state="normal")
                    elif kind == "cancelled":
                        self.percent.set("")
                        self.status_icon.configure(text="–")
                        self.status.set("Operation cancelled. No new document was saved.")
                    else:
                        self.percent.set("")
                        self.status_icon.configure(text="!")
                        self.status.set(f"Could not save the result: {value}")
                        if not self.closing:
                            messagebox.showerror("Analysis failed", value)
        except queue.Empty:
            pass
        if self.closing and (self.worker is None or not self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(100, self.poll)

    def open_result(self, folder):
        if self.output:
            try:
                open_path(self.output.parent if folder else self.output)
            except OSError as exc:
                messagebox.showerror("Cannot open result", str(exc))

    def open_images(self):
        if self.images_folder:
            try:
                open_path(self.images_folder)
            except OSError as exc:
                messagebox.showerror("Cannot open images", str(exc))

    def close(self):
        self.closing = True
        self.stop()


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
