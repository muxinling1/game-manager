"""深色主题（Playnite 风格）：只用 ttk / tk 标准控件，零第三方依赖。

配色 token 与 design/preview.html 里的 CSS 变量一一对应。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BG        = "#15181e"
PANEL     = "#1c2028"
PANEL_2   = "#232833"
PANEL_3   = "#2b3140"
LINE      = "#303644"
LINE_SOFT = "#262b36"
TEXT      = "#e7eaf1"
MUTED     = "#8d95a6"
MUTED_2   = "#666e80"
ACCENT    = "#4c8bf5"
ACCENT_HI = "#6aa0ff"
OK        = "#43c088"
STAR      = "#f0b64a"
WHITE     = "#ffffff"

FONT      = ("Segoe UI", 10)
FONT_SM   = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")

# 封面占位色：按游戏名稳定取一个纯色（tkinter 不支持渐变与圆角）
COVER_COLORS = (
    "#3b2f6b", "#2f6b4a", "#1f3a5c", "#7a5b17",
    "#6b2323", "#2d6b63", "#4a2f5c", "#2b4a6b",
)


def cover_color(name: str) -> str:
    """按游戏名稳定取一个封面占位色。"""
    return COVER_COLORS[sum(name.encode("utf-8")) % len(COVER_COLORS)]


def apply_theme(root: tk.Misc) -> None:
    """把深色主题装到 root 上；必须在创建 ttk 控件之前调用。"""
    root.configure(background=BG)
    style = ttk.Style(root)
    # clam 是唯一允许完整自定义颜色的内置主题；Windows 默认主题会忽略多数 configure
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT,
                    fieldbackground=PANEL_2, font=FONT,
                    bordercolor=LINE, lightcolor=PANEL_3, darkcolor=BG,
                    troughcolor=BG, selectbackground=ACCENT,
                    selectforeground=WHITE)

    style.configure("TFrame", background=BG, borderwidth=0)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Card.TFrame", background=PANEL_2)

    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED,
                    font=FONT_SM)
    style.configure("Status.TLabel", background=PANEL, foreground=MUTED_2,
                    font=FONT_SM)
    style.configure("Title.TLabel", background=BG, foreground=TEXT,
                    font=("Segoe UI", 13, "bold"))

    style.configure("TButton", background=PANEL_2, foreground=TEXT,
                    bordercolor=LINE, borderwidth=1, relief="flat",
                    padding=(10, 5), font=FONT_SM)
    style.map("TButton",
              background=[("active", PANEL_3), ("pressed", ACCENT)],
              foreground=[("active", TEXT)])
    style.configure("Accent.TButton", background=ACCENT, foreground=WHITE,
                    bordercolor=ACCENT, padding=(12, 5),
                    font=("Segoe UI", 9, "bold"))
    style.map("Accent.TButton",
              background=[("active", ACCENT_HI), ("pressed", ACCENT)])

    style.configure("TEntry", fieldbackground=PANEL_2, foreground=TEXT,
                    insertcolor=TEXT, bordercolor=LINE, borderwidth=1,
                    relief="flat", padding=(6, 4))

    style.configure("Treeview", background=PANEL_2, fieldbackground=PANEL_2,
                    foreground=TEXT, borderwidth=0, relief="flat",
                    rowheight=28, font=FONT)
    style.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", WHITE)])
    style.configure("Treeview.Heading", background=PANEL, foreground=MUTED,
                    borderwidth=0, relief="flat", padding=(8, 6), font=FONT_SM)
    style.map("Treeview.Heading", background=[("active", PANEL_3)])

    style.configure("TScrollbar", background=PANEL_3, troughcolor=BG,
                    bordercolor=BG, arrowcolor=MUTED, relief="flat", width=10)
    style.map("TScrollbar", background=[("active", ACCENT)])


# 原生 tk 控件不读 ttk.Style，需要单独上色
_NATIVE_STYLES = (
    (tk.Listbox, dict(background=PANEL_2, foreground=TEXT,
                      selectbackground=ACCENT, selectforeground=WHITE,
                      borderwidth=0, highlightthickness=0, relief="flat",
                      activestyle="none", font=FONT_SM)),
    (tk.Canvas,  dict(background=PANEL_2, highlightthickness=0, borderwidth=0)),
    (tk.Text,    dict(background=PANEL_2, foreground=TEXT,
                      insertbackground=TEXT, borderwidth=0,
                      highlightthickness=0, relief="flat", font=FONT)),
    (tk.Frame,   dict(background=BG)),
    (tk.Label,   dict(background=BG, foreground=TEXT, font=FONT)),
    (tk.Toplevel, dict(background=BG)),
)


def tint_native(root: tk.Misc) -> None:
    """递归给已创建的原生 tk 控件上色（控件创建完成后调用）。"""
    def walk(widget):
        for cls, options in _NATIVE_STYLES:
            if isinstance(widget, cls):
                widget.configure(options)
                break
        for child in widget.winfo_children():
            walk(child)
    walk(root)
