"""
--------------------------------------------------------------------------
Copyright 2026-27 Faris Muhammad, Pavithra Muthukumar, Mrinalika Rajan
Source: https://github.com/farismuhammad17/CodeServer.py

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
--------------------------------------------------------------------------
"""

import os
import threading
import requests
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

class CodeServerIDE:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CodeServer")
        self.root.geometry("1200x750")

        self.server_url = ""
        self.current_file = None

        self.bg_main = "#1e1e1e"
        self.bg_sidebar = "#252526"
        self.bg_input = "#3c3c3c"
        self.fg_light = "#cccccc"
        self.fg_muted = "#858585"
        self.accent_blue = "#007acc"
        self.border_color = "#1e1e1e"

        self.root.configure(bg=self.bg_main)
        self._configure_styles()
        self._build_layout()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TNotebook", background=self.bg_sidebar, borderwidth=0, lightcolor=self.bg_sidebar, darkcolor=self.bg_sidebar)
        style.configure("TNotebook.Tab", background="#2d2d2d", foreground=self.fg_muted, padding=[10, 5], font=("Consolas", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", self.bg_main)],
                  foreground=[("selected", "#ffffff")])

        style.configure("Treeview", background=self.bg_sidebar, foreground=self.fg_light, fieldbackground=self.bg_sidebar, borderwidth=0, font=("Consolas", 10))
        style.configure("Treeview.Heading", background="#333333", foreground=self.fg_light, font=("Consolas", 9))

        style.configure("Server.TFrame", background=self.bg_sidebar)

    def _build_layout(self) -> None:
        main_paned = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg=self.border_color, sashwidth=4, bd=0
        )
        main_paned.pack(fill=tk.BOTH, expand=True)

        sidebar_frame = tk.Frame(main_paned, bg=self.bg_sidebar, width=260)
        main_paned.add(sidebar_frame, minsize=200)

        self.notebook = ttk.Notebook(sidebar_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.explorer_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.explorer_tab, text="Explorer")

        self.tree = ttk.Treeview(self.explorer_tab, selectmode="browse", show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self._on_file_double_click)

        self.server_tab = ttk.Frame(self.notebook, style="Server.TFrame")
        self.notebook.add(self.server_tab, text="Server")

        self.url_entry = tk.Entry(self.server_tab, bg=self.bg_input, fg=self.fg_light, insertbackground="white", relief=tk.FLAT, font=("Consolas", 10))
        self.url_entry.insert(0, "http://localhost:5000")
        self.url_entry.pack(anchor=tk.W, fill=tk.X, padx=10, pady=(15, 0), ipady=4)

        btn_connect = tk.Button(
            self.server_tab,
            text="Connect",
            bg=self.accent_blue,
            fg="white",
            activebackground="#1c97ea",
            activeforeground="white",
            relief=tk.FLAT,
            font=("Consolas", 9),
            command=self.connect_to_server,
        )
        btn_connect.pack(anchor=tk.W, fill=tk.X, padx=10, pady=10, ipady=3)

        right_paned = tk.PanedWindow(
            main_paned, orient=tk.VERTICAL, bg=self.border_color, sashwidth=4, bd=0
        )
        main_paned.add(right_paned)

        editor_container = tk.Frame(right_paned, bg=self.bg_main)

        editor_top_bar = tk.Frame(editor_container, bg="#2d2d2d", height=30)
        editor_top_bar.pack(side=tk.TOP, fill=tk.X)
        editor_top_bar.pack_propagate(False)

        self.lbl_current_file = tk.Label(
            editor_top_bar, text="", bg="#2d2d2d", fg=self.fg_muted, font=("Consolas", 9)
        )
        self.lbl_current_file.pack(side=tk.LEFT, padx=10)

        btn_save = tk.Button(
            editor_top_bar,
            text="Save",
            bg="#3c3c3c",
            fg=self.fg_light,
            activebackground="#505050",
            activeforeground="white",
            relief=tk.FLAT,
            font=("Consolas", 8),
            command=self.save_current_file,
        )
        btn_save.pack(side=tk.RIGHT, padx=6, pady=4, ipadx=6)

        self.editor = tk.Text(
            editor_container,
            bg=self.bg_main,
            fg=self.fg_light,
            insertbackground="white",
            selectbackground="#264f78",
            relief=tk.FLAT,
            undo=True,
            font=("Consolas", 11),
        )
        self.editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        right_paned.add(editor_container, minsize=350)

        term_container = tk.Frame(right_paned, bg="#111111")

        term_top_bar = tk.Frame(term_container, bg="#252526", height=26)
        term_top_bar.pack(side=tk.TOP, fill=tk.X)
        term_top_bar.pack_propagate(False)

        tk.Label(
            term_top_bar, text="Terminal", bg="#252526", fg=self.fg_muted, font=("Consolas", 9)
        ).pack(side=tk.LEFT, padx=10)

        self.cmd_entry = tk.Entry(
            term_container, bg="#1e1e1e", fg=self.fg_light, insertbackground="white", relief=tk.FLAT, font=("Consolas", 10)
        )
        self.cmd_entry.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=6, ipady=4)
        self.cmd_entry.bind("<Return>", self.execute_shell_command)

        self.terminal = tk.Text(
            term_container,
            bg="#111111",
            fg="#4ec9b0",
            insertbackground="white",
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        right_paned.add(term_container, minsize=140)

        self._setup_context_menu()

    def _setup_context_menu(self) -> None:
        self.context_menu = tk.Menu(self.root, tearoff=0, bg=self.bg_sidebar, fg=self.fg_light, activebackground=self.accent_blue, activeforeground="white")
        self.context_menu.add_command(label="New File...", command=self.prompt_new_file)
        self.context_menu.add_command(label="New Folder...", command=self.prompt_new_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Refresh", command=self.connect_to_server)

        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Button-2>", self._show_context_menu)

    def _show_context_menu(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _get_selected_base_path(self) -> str:
        selected_items = self.tree.selection()
        if not selected_items:
            return ""
        item = selected_items[0]
        values = self.tree.item(item, "values")
        if not values:
            return ""
        path = values[0]
        if "." in os.path.basename(path):
            parent_dir = os.path.dirname(path)
            return parent_dir if parent_dir != "." else ""
        return path

    def prompt_new_file(self) -> None:
        if not self.server_url:
            messagebox.showwarning("Warning", "Not connected.")
            return
        base_path = self._get_selected_base_path()
        filename = simpledialog.askstring("New File", "File name:")
        if not filename:
            return
        full_path = f"{base_path}/{filename}" if base_path else filename
        try:
            res = requests.post(f"{self.server_url}/new/file", params={"file": full_path}, json={"content": ""}, timeout=5)
            if res.status_code in [200, 201]:
                self.connect_to_server()
            else:
                messagebox.showerror("Error", "Failed.")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"{e}")

    def prompt_new_folder(self) -> None:
        if not self.server_url:
            messagebox.showwarning("Warning", "Not connected.")
            return
        base_path = self._get_selected_base_path()
        foldername = simpledialog.askstring("New Folder", "Folder name:")
        if not foldername:
            return
        full_path = f"{base_path}/{foldername}" if base_path else foldername
        try:
            res = requests.post(f"{self.server_url}/new/folder", params={"folder": full_path}, timeout=5)
            if res.status_code in [200, 201]:
                self.connect_to_server()
            else:
                messagebox.showerror("Error", "Failed.")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"{e}")

    def connect_to_server(self) -> None:
        raw_url = self.url_entry.get().strip()
        if not raw_url.startswith("http"):
            raw_url = f"http://{raw_url}"
        self.server_url = raw_url.rstrip("/")

        try:
            response = requests.get(f"{self.server_url}/files", timeout=5)
            if response.status_code == 200:
                files = response.json()
                self._populate_file_tree(files)
                self.root.title(f"CodeServer: {self.server_url}")
            else:
                messagebox.showerror("Error", f"Code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"{e}")

    def _populate_file_tree(self, file_list: list) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        paths = {}
        for path in file_list:
            parts = path.split("/")
            parent = ""
            for i, part in enumerate(parts):
                current_path = "/".join(parts[:i+1])
                if current_path not in paths:
                    node = self.tree.insert(parent, "end", text=part, values=[current_path])
                    paths[current_path] = node
                parent = paths[current_path]

    def _on_file_double_click(self, event) -> None:
        selected_item = self.tree.selection()
        if not selected_item:
            return
        file_path = self.tree.item(selected_item[0], "values")
        if not file_path:
            return

        rel_path = file_path[0]
        try:
            response = requests.get(f"{self.server_url}/read", params={"file": rel_path}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.current_file = data["file"]
                self.lbl_current_file.config(text=self.current_file, fg=self.fg_light)

                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", data["content"])
            else:
                messagebox.showerror("Error", "Read failed.")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"{e}")

    def save_current_file(self) -> None:
        if not self.current_file:
            messagebox.showwarning("Warning", "No file open.")
            return

        content = self.editor.get("1.0", tk.END)
        payload = {"filename": self.current_file, "content": content}

        try:
            response = requests.post(f"{self.server_url}/save", json=payload, timeout=5)
            if response.status_code in [200, 201]:
                self.lbl_current_file.config(fg="#4ec9b0")
                self.root.after(1500, lambda: self.lbl_current_file.config(fg=self.fg_light))
            else:
                messagebox.showerror("Error", "Save failed.")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"{e}")

    def execute_shell_command(self, event) -> None:
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return

        self.terminal.insert(tk.END, f"$ {cmd}\n")
        self.cmd_entry.delete(0, tk.END)

        def run_stream():
            try:
                url = f"{self.server_url}/cmd"
                with requests.post(url, json={"command": cmd}, stream=True, timeout=60) as resp:
                    for line in resp.iter_lines(decode_unicode=True):
                        if line:
                            self.terminal.after(0, self._append_terminal, line + "\n")
            except Exception as e:
                self.terminal.after(0, self._append_terminal, f"[Error: {e}]\n")

        threading.Thread(target=run_stream, daemon=True).start()

    def _append_terminal(self, text: str) -> None:
        self.terminal.insert(tk.END, text)
        self.terminal.see(tk.END)

def main() -> None:
    root = tk.Tk()
    app = CodeServerIDE(root)
    root.mainloop()

if __name__ == "__main__":
    main()
