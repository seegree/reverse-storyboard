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
        root.title("Edit Detector")
        root.minsize(720, 540)
        root.protocol("WM_DELETE_WINDOW", self.close)
        panel = ttk.Frame(root, padding=24)
        panel.pack(fill="both", expand=True)
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text="Video Shot Breakdown", font=("Segoe UI", 20)).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="One caption and image per shot, saved as an editable Word document.", wraplength=540).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 20))
        self.path = tk.StringVar()
        self.entry = ttk.Entry(panel, textvariable=self.path, width=58)
        self.entry.grid(row=2, column=0, sticky="ew", padx=(0, 10))
        self.browse = ttk.Button(panel, text="Choose video…", command=self.choose)
        self.browse.grid(row=2, column=1)
        options = ttk.Frame(panel)
        options.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.include_timecodes = tk.BooleanVar(value=False)
        self.export_images = tk.BooleanVar(value=False)
        self.timecode_check = ttk.Checkbutton(options, text="Include elapsed timecodes", variable=self.include_timecodes)
        self.timecode_check.pack(side="left")
        self.images_check = ttk.Checkbutton(options, text="Also save a folder of shot images", variable=self.export_images)
        self.images_check.pack(side="left", padx=(18, 0))
        actions = ttk.Frame(panel)
        actions.grid(row=4, column=0, columnspan=2, sticky="w", pady=16)
        self.analyze_button = ttk.Button(actions, text="Analyze Video", command=self.start)
        self.analyze_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self.stop, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.bar = ttk.Progressbar(panel, mode="indeterminate", maximum=100)
        self.bar.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.status = tk.StringVar(value="Ready. Processing runs locally on your CPU.")
        ttk.Label(panel, textvariable=self.status, wraplength=640).grid(row=6, column=0, columnspan=2, sticky="w", pady=12)
        result = ttk.Frame(panel)
        result.grid(row=7, column=0, columnspan=2, sticky="w")
        self.open_button = ttk.Button(result, text="Open Word document", command=lambda: self.open_result(False), state="disabled")
        self.open_button.pack(side="left")
        self.folder_button = ttk.Button(result, text="Open folder", command=lambda: self.open_result(True), state="disabled")
        self.folder_button.pack(side="left", padx=8)
        self.images_button = ttk.Button(result, text="Open shot images", command=self.open_images, state="disabled")
        self.images_button.pack(side="left")
        ttk.Separator(panel).grid(row=8, column=0, columnspan=2, sticky="ew", pady=18)
        ttk.Label(panel, text="Make a shorter version", font=("Segoe UI", 14)).grid(row=9, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Keep the numbers you want from this document. Save a new list numbered from 1.", wraplength=640).grid(row=10, column=0, columnspan=2, sticky="w", pady=(5, 10))
        self.revision_source = tk.StringVar()
        self.revision_entry = ttk.Entry(panel, textvariable=self.revision_source)
        self.revision_entry.grid(row=11, column=0, sticky="ew", padx=(0, 10))
        self.revision_browse = ttk.Button(panel, text="Choose document…", command=self.choose_document)
        self.revision_browse.grid(row=11, column=1)
        keep_row = ttk.Frame(panel)
        keep_row.grid(row=12, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(keep_row, text="Shots to keep:").pack(side="left", padx=(0, 10))
        self.keep_numbers = tk.StringVar()
        self.keep_entry = ttk.Entry(keep_row, textvariable=self.keep_numbers)
        self.keep_entry.pack(side="left", fill="x", expand=True)
        ttk.Label(panel, text="Example: 3 6 11 13 14 25 34 35 38 42  •  Original shot order is preserved.").grid(row=13, column=0, columnspan=2, sticky="w")
        self.revise_button = ttk.Button(panel, text="Save selected shots…", command=self.revise)
        self.revise_button.grid(row=14, column=0, columnspan=2, sticky="w", pady=(10, 0))
        root.after(100, self.poll)

    def choose(self):
        filename = filedialog.askopenfilename(title="Choose an edited video", filetypes=[
            ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mts *.mxf"), ("All files", "*.*")])
        if filename:
            self.path.set(filename)

    def busy(self, working):
        for button in (self.browse, self.analyze_button, self.entry, self.timecode_check, self.images_check,
                       self.revision_entry, self.revision_browse, self.keep_entry, self.revise_button):
            button.configure(state="disabled" if working else "normal")
        self.cancel_button.configure(state="normal" if working else "disabled")
        if working:
            self.open_button.configure(state="disabled")
            self.folder_button.configure(state="disabled")
            self.images_button.configure(state="disabled")
            self.bar.configure(mode="indeterminate")
            self.bar.start(12)
        else:
            self.bar.stop()

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
                else:
                    self.busy(False)
                    if kind == "done":
                        self.output = Path(value.output)
                        self.revision_source.set(value.output)
                        self.images_folder = Path(value.images_folder) if value.images_folder else None
                        self.bar.configure(mode="determinate", value=100)
                        self.status.set(f"Saved {len(value.shots)} shots in {value.timings['total_seconds']:.1f} seconds. Review captions in Word.")
                        self.open_button.configure(state="normal")
                        self.folder_button.configure(state="normal")
                        if self.images_folder:
                            self.images_button.configure(state="normal")
                    elif kind == "revised":
                        self.output = Path(value.output)
                        self.bar.configure(mode="determinate", value=100)
                        self.status.set(f"Saved {len(value.kept_numbers)} of {value.original_count} shots, numbered from 1. Original document preserved.")
                        self.open_button.configure(state="normal")
                        self.folder_button.configure(state="normal")
                        if self.images_folder:
                            self.images_button.configure(state="normal")
                    elif kind == "cancelled":
                        self.status.set("Analysis cancelled.")
                    else:
                        self.status.set("Analysis failed. You can correct the issue and try again.")
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
