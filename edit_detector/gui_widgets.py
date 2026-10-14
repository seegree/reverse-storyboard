"""Presentation helpers for the Tk interface; no processing or file operations."""
import tkinter as tk
from tkinter import ttk, font

BG = '#1C1D20'
CARD = '#26272B'
INSET = '#202125'
BORDER = '#36373C'
TEXT = '#ECECEE'
MUTED = '#9C9CA3'
ACCENT = '#1F9D8A'


def configure_theme(root):
    family = font.nametofont('TkDefaultFont').actual('family')
    style = ttk.Style(root)
    style.theme_use('clam')  # Native Aqua buttons ignore custom background colors.
    style.configure('.', font=(family, -14), background=BG, foreground=TEXT)
    for name, color in [('TFrame', BG), ('Card.TFrame', CARD), ('Inset.TFrame', INSET)]:
        style.configure(name, background=color)
    for name, color, size, weight, background in [
        ('TLabel', TEXT, 14, 'normal', BG),
        ('Eyebrow.TLabel', MUTED, 12, 'normal', BG),
        ('Title.TLabel', TEXT, 28, 'bold', BG),
        ('Secondary.TLabel', '#B4B4BA', 14, 'normal', BG),
        ('Heading.TLabel', TEXT, 16, 'bold', BG),
        ('CardHeading.TLabel', TEXT, 16, 'bold', CARD),
        ('Card.TLabel', TEXT, 14, 'normal', CARD),
        ('Inset.TLabel', TEXT, 14, 'normal', INSET),
        ('Helper.TLabel', MUTED, 12, 'normal', INSET),
        ('Percent.TLabel', MUTED, 12, 'normal', CARD),
        ('Warning.TLabel', '#F6DDA6', 14, 'normal', '#3A2F1A'),
    ]:
        style.configure(name, foreground=color, background=background, font=(family, -size, weight))
    for name, background, foreground, border in [
        ('TButton', '#303136', TEXT, '#4A4B52'),
        ('Primary.TButton', ACCENT, '#0E1A18', ACCENT),
        ('Open.TButton', TEXT, BG, TEXT),
        ('Warning.TButton', '#3A2F1A', '#F6DDA6', '#8A6B2A'),
    ]:
        style.configure(name, background=background, foreground=foreground, bordercolor=border,
                        lightcolor=background, darkcolor=background, padding=(14, 8),
                        borderwidth=1, relief='flat', focuscolor=foreground, anchor='center')
        style.map(name, background=[('disabled', CARD), ('pressed', border), ('active', background)],
                  foreground=[('disabled', '#77787E')], bordercolor=[('disabled', BORDER)])
    style.configure('TCheckbutton', background=INSET, foreground=TEXT, padding=0,
                    indicatorbackground=INSET, indicatorforeground='#0E1A18')
    style.map('TCheckbutton', background=[('active', INSET)],
              foreground=[('disabled', MUTED)],
              indicatorbackground=[('selected', ACCENT), ('!selected', TEXT)])
    style.configure('TEntry', fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT,
                    bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, padding=(12, 8))
    style.map('TEntry', bordercolor=[('focus', ACCENT)], fieldbackground=[('disabled', INSET)])
    style.configure('Horizontal.TProgressbar', background=ACCENT, troughcolor=INSET,
                    borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT, thickness=6)
    style.configure('TSeparator', background=BORDER)
    root.configure(background=BG)


class Card(tk.Canvas):
    """Rounded background around a normal, keyboard-accessible widget container."""
    def __init__(self, parent, *, color=CARD, border=BORDER, padding=20, radius=12):
        super().__init__(parent, background=BG, highlightthickness=0, borderwidth=0, height=1, takefocus=0)
        self.color, self.border, self.padding, self.radius = color, border, padding, radius
        self.content = tk.Frame(self, background=color)
        self.window = self.create_window(padding, padding, window=self.content, anchor='nw')
        self.content.bind('<Configure>', self._layout)
        self.bind('<Configure>', self._layout)

    def _layout(self, event=None):
        width = self.winfo_width()
        height = self.content.winfo_reqheight() + 2 * self.padding
        self.itemconfigure(self.window, width=max(1, width - 2 * self.padding))
        if int(self.cget('height')) != height:
            self.configure(height=height)
        r, w, h = self.radius, width - 1, height - 1
        self.delete('surface')
        self.create_polygon(1+r, 1, w-r, 1, w, 1, w, 1+r, w, h-r, w, h,
                            w-r, h, 1+r, h, 1, h, 1, h-r, 1, 1+r, 1, 1,
                            smooth=True, splinesteps=24, fill=self.color, outline=self.border,
                            tags='surface')
        self.tag_lower('surface')


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.window, self.timer = widget, text, None, None
        widget.bind('<Enter>', self.schedule, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')
        widget.bind('<FocusIn>', self.schedule, add='+')
        widget.bind('<FocusOut>', self.hide, add='+')
        widget.bind('<Destroy>', self.hide, add='+')

    def schedule(self, event=None):
        self.hide()
        self.timer = self.widget.after(600, self.show)

    def show(self):
        self.timer = None
        text = self.text() if callable(self.text) else self.text
        if not text:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry(f'+{self.widget.winfo_rootx()+8}+{self.widget.winfo_rooty()+self.widget.winfo_height()+4}')
        tk.Label(self.window, text=text, background=TEXT, foreground=BG,
                 padx=10, pady=6, wraplength=480, justify='left').pack()

    def hide(self, event=None):
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.window:
            self.window.destroy()
            self.window = None


def placeholder(entry, variable, text):
    """Overlay a hint without ever adding it to the user's selection string."""
    hint = tk.Label(entry, text=text, background=CARD, foreground=MUTED,
                    font=ttk.Style().lookup('TEntry', 'font'), borderwidth=0)
    def refresh(*args):
        if not variable.get() and entry.focus_get() != entry:
            hint.place(x=12, rely=.5, anchor='w')
        else:
            hint.place_forget()
    hint.bind('<Button-1>', lambda event: entry.focus_set())
    entry.bind('<FocusIn>', refresh, add='+')
    entry.bind('<FocusOut>', refresh, add='+')
    variable.trace_add('write', refresh)
    refresh()
    return hint
