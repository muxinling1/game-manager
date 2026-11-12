"""F3 主窗口：tkinter GUI，零第三方依赖。

运行：python -m src.app
"""

from __future__ import annotations

import sqlite3
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from src import db, launcher, scanner, theme

COLUMNS = ("name", "tags", "path", "last_played", "play_count", "state")
HEADERS = {
    "name": "名称", "tags": "标签", "path": "路径",
    "last_played": "最后游玩", "play_count": "次数", "state": "状态",
}
WIDTHS = {"name": 180, "tags": 100, "path": 320,
          "last_played": 150, "play_count": 50, "state": 80}
FORM_FIELDS = ("name", "path", "exe", "args", "tags", "note")
FORM_LABELS = {
    "name": "名称 *", "path": "游戏目录 *", "exe": "可执行文件 *",
    "args": "启动参数", "tags": "标签（逗号分隔）", "note": "备注",
}


def validate_form(values: dict[str, str]) -> dict[str, str]:
    """校验并归一化表单，返回可直接交给 db.add/update 的字段。"""
    fields = {k: (values.get(k) or "").strip() for k in FORM_FIELDS}
    for key in ("name", "path", "exe"):
        if not fields[key]:
            raise ValueError(f"{FORM_LABELS[key].rstrip(' *')} 不能为空")
    return fields


def row_values(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (row["name"], row["tags"], row["path"],
            row["last_played"] or "-", str(row["play_count"]))


def existing_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {(r["path"], r["exe"]) for r in rows}


def exit_text(name: str, returncode: int) -> str:
    suffix = "正常退出" if returncode == 0 else f"异常退出（返回码 {returncode}）"
    return f"「{name}」{suffix}"


class GameDialog(tk.Toplevel):
    """添加/编辑共用的模态表单；关闭后 self.result 为字段字典或 None。"""

    def __init__(self, master, title: str,
                 initial: dict[str, Any] | None = None):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.resizable(True, False)
        self.result: dict[str, str] | None = None
        self.vars = {
            key: tk.StringVar(value=str((initial or {}).get(key) or ""))
            for key in FORM_FIELDS
        }
        for index, key in enumerate(FORM_FIELDS):
            ttk.Label(self, text=FORM_LABELS[key]).grid(
                row=index, column=0, sticky="w", padx=8, pady=4)
            ttk.Entry(self, textvariable=self.vars[key], width=46).grid(
                row=index, column=1, padx=8, pady=4, sticky="ew")
        self.columnconfigure(1, weight=1)
        bar = ttk.Frame(self)
        bar.grid(row=len(FORM_FIELDS), column=0, columnspan=2, pady=10)
        ttk.Button(bar, text="确定", command=self._on_ok).pack(side="left", padx=6)
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="left", padx=6)
        self.bind("<Return>", lambda _event: self._on_ok())
        self.bind("<Escape>", lambda _event: self.destroy())
        theme.tint_native(self)
        self.grab_set()
        self.wait_window()

    def _on_ok(self):
        try:
            self.result = validate_form(
                {key: var.get() for key, var in self.vars.items()})
        except ValueError as exc:
            messagebox.showerror("输入有误", str(exc), parent=self)
            return
        self.destroy()


class ScanDialog(tk.Toplevel):
    """选目录 → 扫描 → 勾选候选 → 导入。只有勾选的才会入库。"""

    def __init__(self, master, database: db.GameDB):
        super().__init__(master)
        self.title("扫描游戏目录")
        self.transient(master)
        self.geometry("720x460")
        self.database = database
        self.roots: list[str] = []
        self.candidates: list[scanner.Candidate] = []

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="添加目录…", command=self._add_root).pack(
            side="left", padx=3)
        ttk.Button(top, text="移除选中目录", command=self._remove_root).pack(
            side="left", padx=3)
        ttk.Button(top, text="扫描", command=self._scan).pack(side="left", padx=3)
        self.root_list = tk.Listbox(self, height=4)
        self.root_list.pack(fill="x", padx=8)

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=8, pady=6)
        self.listbox = tk.Listbox(mid, selectmode=tk.MULTIPLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(mid, command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=6)
        self.hint = ttk.Label(bottom, text="先添加目录，再点「扫描」。")
        self.hint.pack(side="left")
        ttk.Button(bottom, text="全选", command=self._select_all).pack(
            side="right", padx=3)
        ttk.Button(bottom, text="导入选中", command=self._import).pack(
            side="right", padx=3)
        ttk.Button(bottom, text="关闭", command=self.destroy).pack(
            side="right", padx=3)
        theme.tint_native(self)
        self.grab_set()
        self.wait_window()

    def _add_root(self):
        chosen = filedialog.askdirectory(parent=self, title="选择游戏根目录")
        if chosen and chosen not in self.roots:
            self.roots.append(chosen)
            self.root_list.insert(tk.END, chosen)
            self.hint.configure(text=f"已选 {len(self.roots)} 个目录，点「扫描」。")

    def _remove_root(self):
        for index in reversed(self.root_list.curselection()):
            self.roots.pop(index)
            self.root_list.delete(index)

    def _scan(self):
        if not self.roots:
            messagebox.showinfo("提示", "请先添加至少一个目录。", parent=self)
            return
        try:
            found = scanner.scan_many(self.roots)
        except ValueError as exc:
            messagebox.showerror("扫描失败", str(exc), parent=self)
            return
        fresh = scanner.filter_existing(found, existing_keys(self.database.list()))
        self.candidates = fresh
        self.listbox.delete(0, tk.END)
        for candidate in fresh:
            self.listbox.insert(
                tk.END,
                f"{candidate.name}  —  {Path(candidate.path) / candidate.exe}")
        self.hint.configure(
            text=f"发现 {len(found)} 个，其中 {len(fresh)} 个是新的；勾选后导入。")

    def _select_all(self):
        self.listbox.select_set(0, tk.END)

    def _import(self):
        selected = [self.candidates[i] for i in self.listbox.curselection()]
        if not selected:
            messagebox.showinfo("提示", "没有勾选任何候选项。", parent=self)
            return
        count = 0
        for candidate in selected:
            try:
                self.database.add(name=candidate.name,
                                  path=candidate.path, exe=candidate.exe)
                count += 1
            except sqlite3.IntegrityError:
                continue
        self.hint.configure(text=f"已导入 {count} 个，关闭后主列表刷新。")


class GameManagerApp:
    def __init__(self, root: tk.Tk, database: db.GameDB | None = None):
        self.root = root
        theme.apply_theme(self.root)
        self.database = database or db.GameDB()
        self.database.init()
        self.keyword = tk.StringVar()
        self.tag = tk.StringVar()
        self.row_ids: dict[str, int] = {}
        self._running: dict[int, subprocess.Popen] = {}
        self._poll_job: str | None = None
        self.view = "all"           # all / recent
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh()

    def _build_ui(self):
        self.root.title("本地游戏库管理器")
        self.root.geometry("1080x660")
        self.root.minsize(880, 520)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        # ---- 顶栏 ----
        top = ttk.Frame(self.root, style="Panel.TFrame", padding=(14, 0))
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(top, text="▦", style="Logo.TLabel").pack(
            side="left", padx=(0, 9))
        ttk.Label(top, text="本地游戏库", style="Brand.TLabel").pack(side="left")
        ttk.Label(top, text="搜索", style="Subtle.TLabel").pack(
            side="left", padx=(24, 6))
        ttk.Entry(top, textvariable=self.keyword, width=26).pack(side="left")
        ttk.Label(top, text="标签", style="Subtle.TLabel").pack(
            side="left", padx=(16, 6))
        ttk.Entry(top, textvariable=self.tag, width=13).pack(side="left")
        ttk.Button(top, text="刷新", command=self.refresh).pack(
            side="right", padx=3)
        ttk.Button(top, text="扫描目录…", command=self._on_scan).pack(
            side="right", padx=3)
        ttk.Button(top, text="编辑", command=self._on_edit).pack(
            side="right", padx=3)
        ttk.Button(top, text="删除", command=self._on_delete).pack(
            side="right", padx=3)
        ttk.Button(top, text="＋ 添加游戏", style="Accent.TButton",
                   command=self._on_add).pack(side="right", padx=(3, 0))
        self.keyword.trace_add("write", lambda *_: self.refresh())
        self.tag.trace_add("write", lambda *_: self.refresh())

        # ---- 左栏 ----
        self.side = ttk.Frame(self.root, style="Panel.TFrame", padding=(10, 14))
        self.side.grid(row=1, column=0, sticky="nsew")
        ttk.Label(self.side, text="游戏库", style="Side.TLabel").pack(
            anchor="w", padx=8, pady=(0, 6))
        self.nav_all = ttk.Button(
            self.side, text="▦  所有游戏", style="NavOn.TButton",
            command=lambda: self._set_view("all"))
        self.nav_all.pack(fill="x", pady=1)
        self.nav_recent = ttk.Button(
            self.side, text="◷  最近游玩", style="Nav.TButton",
            command=lambda: self._set_view("recent"))
        self.nav_recent.pack(fill="x", pady=1)

        ttk.Label(self.side, text="按标签筛选", style="Side.TLabel").pack(
            anchor="w", padx=8, pady=(18, 6))
        self.tag_frame = ttk.Frame(self.side, style="Panel.TFrame")
        self.tag_frame.pack(fill="x")

        self.stat_box = ttk.Frame(self.side, style="Card.TFrame", padding=10)
        self.stat_box.pack(fill="x", side="bottom", pady=(16, 0))
        self.stat_lines = {}
        for key, label in (("total", "游戏总数"), ("played", "已启动过"),
                           ("launches", "累计启动")):
            line = ttk.Frame(self.stat_box, style="Card.TFrame")
            line.pack(fill="x", pady=2)
            ttk.Label(line, text=label, style="CardSub.TLabel").pack(side="left")
            value = ttk.Label(line, text="—", style="Card.TLabel")
            value.pack(side="right")
            self.stat_lines[key] = value

        # ---- 主区 ----
        main = ttk.Frame(self.root)
        main.grid(row=1, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        head = ttk.Frame(main, padding=(18, 14, 18, 8))
        head.grid(row=0, column=0, sticky="ew")
        self.view_title = ttk.Label(head, text="所有游戏", style="Title.TLabel")
        self.view_title.pack(side="left")
        self.view_count = ttk.Label(head, text="", style="Count.TLabel")
        self.view_count.pack(side="left", padx=(10, 0))

        tree_frame = ttk.Frame(main)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=18)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=COLUMNS,
                                 show="headings", selectmode="browse")
        for column in COLUMNS:
            self.tree.heading(column, text=HEADERS[column])
            self.tree.column(column, width=WIDTHS[column], anchor="w",
                             stretch=(column == "path"))
        scroll = ttk.Scrollbar(tree_frame, command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _event: self._on_launch())
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._on_select())

        # ---- 详情条 ----
        self.detail = ttk.Frame(main, style="Card.TFrame", padding=(14, 10))
        self.detail.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 12))
        self.detail.columnconfigure(1, weight=1)
        self.detail_name = ttk.Label(self.detail, text="", style="Card.TLabel",
                                     font=theme.FONT_BOLD)
        self.detail_name.grid(row=0, column=0, sticky="w")
        self.detail_sub = ttk.Label(self.detail, text="", style="CardSub.TLabel")
        self.detail_sub.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.detail_fields = ttk.Frame(self.detail, style="Card.TFrame")
        self.detail_fields.grid(row=0, column=1, rowspan=2, sticky="w", padx=24)
        self.detail_launch = ttk.Button(
            self.detail, text="▶  启动游戏", style="Accent.TButton",
            command=self._on_launch)
        self.detail_launch.grid(row=0, column=2, rowspan=2, sticky="e")
        self._update_detail(None)

        # ---- 状态栏 ----
        bar = ttk.Frame(self.root, style="Panel.TFrame", padding=(14, 0))
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status = ttk.Label(bar, text="", style="Status.TLabel")
        self.status.pack(side="left")
        ttk.Label(bar, text="v0.1 MVP", style="Status.TLabel").pack(side="right")
        self.stat_live = ttk.Label(bar, text="", style="Status.TLabel")
        self.stat_live.pack(side="right", padx=(0, 14))
        self.stat_total = ttk.Label(bar, text="", style="Status.TLabel")
        self.stat_total.pack(side="right", padx=(0, 14))

        theme.tint_native(self.root)

    def refresh(self):
        selected = self.tree.selection()
        selected_id = self.row_ids.get(selected[0]) if selected else None
        self.tree.delete(*self.tree.get_children())
        self.row_ids.clear()
        all_rows = self.database.list()
        rows = self.database.list(keyword=self.keyword.get(),
                                  tag=self.tag.get())
        if self.view == "recent":
            rows.sort(key=lambda r: r["last_played"] or "", reverse=True)
        restored = None
        for row in rows:
            state = "运行中" if row["id"] in self._running else "已退出"
            iid = self.tree.insert("", tk.END, values=(*row_values(row), state))
            self.row_ids[iid] = row["id"]
            if row["id"] == selected_id:
                restored = iid
        if restored is not None:
            self.tree.selection_set(restored)
        self._rebuild_tags(all_rows)
        self._update_status(all_rows, rows)
        self._on_select()

    def _set_view(self, view: str) -> None:
        self.view = view
        self.nav_all.configure(
            style="NavOn.TButton" if view == "all" else "Nav.TButton")
        self.nav_recent.configure(
            style="NavOn.TButton" if view == "recent" else "Nav.TButton")
        self.view_title.configure(
            text="所有游戏" if view == "all" else "最近游玩")
        self.refresh()

    def _filter_tag(self, tag: str) -> None:
        self.tag.set("" if self.tag.get().strip() == tag else tag)

    def _rebuild_tags(self, rows: list[dict[str, Any]]) -> None:
        """按库里实际出现的标签生成左栏按钮，点一次筛选、再点一次取消。"""
        for child in self.tag_frame.winfo_children():
            child.destroy()
        counts: dict[str, int] = {}
        for row in rows:
            for tag in (t.strip() for t in row["tags"].split(",")):
                if tag:
                    counts[tag] = counts.get(tag, 0) + 1
        if not counts:
            ttk.Label(self.tag_frame, text="（暂无标签）",
                      style="Side.TLabel").pack(anchor="w", padx=8)
            return
        active = self.tag.get().strip()
        for tag in sorted(counts):
            style = "NavOn.TButton" if tag == active else "Nav.TButton"
            ttk.Button(self.tag_frame, text=f"●  {tag}   {counts[tag]}",
                       style=style,
                       command=lambda t=tag: self._filter_tag(t)).pack(
                           fill="x", pady=1)

    def _on_select(self) -> None:
        selection = self.tree.selection()
        game = None
        if selection:
            game_id = self.row_ids.get(selection[0])
            if game_id is not None:
                game = self.database.get(game_id)
        self._update_detail(game)

    def _update_detail(self, game: dict[str, Any] | None) -> None:
        for child in self.detail_fields.winfo_children():
            child.destroy()
        if game is None:
            self.detail_name.configure(text="未选中游戏")
            self.detail_sub.configure(text="单击列表选中一款游戏，双击可直接启动")
            self.detail_launch.configure(state="disabled")
            return
        self.detail_name.configure(text=game["name"])
        self.detail_sub.configure(text=game["tags"] or "无标签")
        state = "运行中" if game["id"] in self._running else "已退出"
        for label, value in (
            ("游玩次数", f"{game['play_count']} 次"),
            ("最后游玩", game["last_played"] or "—"),
            ("状态", state),
            ("路径", game["path"]),
        ):
            cell = ttk.Frame(self.detail_fields, style="Card.TFrame")
            cell.pack(side="left", padx=(0, 20))
            ttk.Label(cell, text=label, style="CardSub.TLabel").pack(anchor="w")
            ttk.Label(cell, text=value, style="Card.TLabel").pack(anchor="w")
        self.detail_launch.configure(state="normal")

    def _update_status(self, all_rows: list[dict[str, Any]],
                       rows: list[dict[str, Any]]) -> None:
        total = len(all_rows)
        shown = len(rows)
        played = sum(1 for r in all_rows if r["play_count"] > 0)
        launches = sum(r["play_count"] for r in all_rows)
        live = len(self._running)
        self.stat_lines["total"].configure(text=str(total))
        self.stat_lines["played"].configure(text=str(played))
        self.stat_lines["launches"].configure(text=f"{launches} 次")
        self.stat_total.configure(text=f"共 {total} 款游戏")
        self.stat_live.configure(
            text=f"运行中 {live}" if live else "无运行中的游戏")
        self.view_count.configure(text=f"显示 {shown} / {total} 款")
        self.status.configure(text=f"共 {shown} 款游戏")

    def _selected_game(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选中一款游戏。", parent=self.root)
            return None
        return self.database.get(self.row_ids[selection[0]])

    def _on_add(self):
        dialog = GameDialog(self.root, "添加游戏")
        if dialog.result:
            self.database.add(**dialog.result)
            self.refresh()

    def _on_edit(self):
        game = self._selected_game()
        if not game:
            return
        dialog = GameDialog(self.root, "编辑游戏", initial=game)
        if dialog.result:
            self.database.update(game["id"], **dialog.result)
            self.refresh()

    def _on_delete(self):
        game = self._selected_game()
        if not game:
            return
        if messagebox.askyesno("确认删除", f"删除「{game['name']}」？",
                               parent=self.root):
            self.database.delete(game["id"])
            self.refresh()

    def _on_scan(self):
        ScanDialog(self.root, self.database)
        self.refresh()

    def _on_launch(self):
        game = self._selected_game()
        if not game:
            return
        try:
            process = launcher.launch(game)
        except OSError as exc:
            messagebox.showerror(
                "启动失败",
                f"无法启动「{game['name']}」\n\n{type(exc).__name__}: {exc}",
                parent=self.root)
            return
        self.database.record_play(game["id"])
        self._running[game["id"]] = process
        self._start_polling()
        self.refresh()
        self.status.configure(text=f"「{game['name']}」运行中…")

    def _start_polling(self):
        if self._poll_job is None:
            self._poll_job = self.root.after(500, self._poll)

    def _poll(self):
        # 用主线程定时轮询而非后台线程：Tkinter 控件只能由主线程更新，
        # 跨线程调用 after 并不保证安全。poll() 非阻塞，开销可忽略。
        self._poll_job = None
        finished = [(gid, proc.returncode) for gid, proc in self._running.items()
                    if proc.poll() is not None]
        for game_id, _ in finished:
            self._running.pop(game_id, None)
        if finished:
            self.refresh()
            game_id, returncode = finished[-1]
            game = self.database.get(game_id)
            if game:
                self.status.configure(text=exit_text(game["name"], returncode))
        if self._running:
            self._poll_job = self.root.after(500, self._poll)

    def _on_close(self):
        if self._poll_job is not None:
            self.root.after_cancel(self._poll_job)
        self.root.destroy()


def main():
    root = tk.Tk()
    GameManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
