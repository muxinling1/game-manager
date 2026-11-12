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
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh()

    def _build_ui(self):
        self.root.title("本地游戏库管理器")
        self.root.geometry("900x560")

        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=8, pady=6)
        ttk.Label(toolbar, text="搜索").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.keyword, width=24).pack(
            side="left", padx=4)
        ttk.Label(toolbar, text="标签").pack(side="left", padx=(10, 0))
        ttk.Entry(toolbar, textvariable=self.tag, width=14).pack(
            side="left", padx=4)
        for text, command in (
            ("刷新", self.refresh), ("扫描目录…", self._on_scan),
            ("添加…", self._on_add), ("编辑…", self._on_edit),
            ("删除", self._on_delete), ("启动", self._on_launch),
        ):
            ttk.Button(toolbar, text=text, command=command).pack(
                side="left", padx=2)
        self.keyword.trace_add("write", lambda *_: self.refresh())
        self.tag.trace_add("write", lambda *_: self.refresh())

        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(frame, columns=COLUMNS, show="headings",
                                 selectmode="browse")
        for column in COLUMNS:
            self.tree.heading(column, text=HEADERS[column])
            self.tree.column(column, width=WIDTHS[column], anchor="w",
                             stretch=(column == "path"))
        scroll = ttk.Scrollbar(frame, command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _event: self._on_launch())

        self.status = ttk.Label(self.root, text="", anchor="w",
                                style="Status.TLabel")
        self.status.pack(fill="x", padx=8, pady=4)
        theme.tint_native(self.root)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.row_ids.clear()
        rows = self.database.list(keyword=self.keyword.get(), tag=self.tag.get())
        for row in rows:
            state = "运行中" if row["id"] in self._running else "已退出"
            iid = self.tree.insert("", tk.END, values=(*row_values(row), state))
            self.row_ids[iid] = row["id"]
        self.status.configure(text=f"共 {len(rows)} 款游戏")

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
