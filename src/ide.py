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
import uuid
from urllib.parse import quote
import requests
import socketio
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

class CodeServerIDE:
    """
    Main CodeServer IDE class containing the graphical user interface,
    file explorer tree, active collaborative users pane, text editor,
    terminal stream handler, and real-time SocketIO client bindings.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CodeServer")
        self.root.geometry("1200x750")

        self.server_url = ""
        self.current_file = None
        self.username = "Developer"

        # SocketIO client instance configured for robust polling transport fallback
        self.sio = socketio.Client(logger=False, engineio_logger=False)
        self._setup_socket_events()

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

        self.editor.bind("<BackSpace>", self._on_editor_backspace)
        self.editor.bind("<Delete>", self._on_editor_delete)
        self.editor.bind("<Return>", self._on_editor_return)

    def _configure_styles(self) -> None:
        """
        Configures global ttk widget styles to match the dark theme aesthetic.
        """
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
        """
        Builds and arranges the main split panes, sidebars, file trees, text editor, and terminal boxes.
        """
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

        tk.Label(self.server_tab, text="Active Users:", bg=self.bg_sidebar, fg=self.fg_muted, font=("Consolas", 9)).pack(anchor=tk.W, padx=10, pady=(10, 2))
        self.users_listbox = tk.Listbox(self.server_tab, bg=self.bg_input, fg=self.fg_light, relief=tk.FLAT, font=("Consolas", 9), height=10)
        self.users_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

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

        # Real-time event bindings for streaming keystrokes and cursor movements
        self.editor.bind("<KeyRelease>", self._on_editor_key_release)
        self.editor.bind("<ButtonRelease-1>", self._on_editor_cursor_move)
        self.editor.bind("<KeyRelease-Up>", self._on_editor_cursor_move)
        self.editor.bind("<KeyRelease-Down>", self._on_editor_cursor_move)
        self.editor.bind("<KeyRelease-Left>", self._on_editor_cursor_move)
        self.editor.bind("<KeyRelease-Right>", self._on_editor_cursor_move)

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

    def _setup_socket_events(self) -> None:
        """
        Binds incoming SocketIO handlers for real-time collaboration events.
        """
        @self.sio.on('user_join')
        def on_user_join(data):
            self.root.after(0, self._refresh_users_list)

        @self.sio.on('user_left')
        def on_user_left(data):
            self.root.after(0, self._refresh_users_list)

        @self.sio.on('broadcast_keystrokes')
        def on_broadcast_keystrokes(data):
            if data.get("file") == self.current_file:
                self.root.after(0, lambda: self._apply_remote_edits(data.get("edits", [])))

        @self.sio.on('broadcast_cursor')
        def on_broadcast_cursor(data):
            if data.get("file") == self.current_file:
                self.root.after(0, lambda: self._render_remote_cursor(data))

    def _refresh_users_list(self) -> None:
        """
        Fetches the latest active user list via the /users REST endpoint.
        """
        if not self.server_url:
            return
        try:
            res = requests.get(f"{self.server_url}/users", timeout=3)
            if res.status_code == 200:
                users = res.json()
                self.users_listbox.delete(0, tk.END)
                for u in users:
                    self.users_listbox.insert(tk.END, u)
        except Exception:
            pass

    def _setup_context_menu(self) -> None:
        """
        Sets up right-click context menu options for the project explorer.
        """
        self.context_menu = tk.Menu(self.root, tearoff=0, bg=self.bg_sidebar, fg=self.fg_light, activebackground=self.accent_blue, activeforeground="white")
        self.context_menu.add_command(label="New File...", command=self.prompt_new_file)
        self.context_menu.add_command(label="New Folder...", command=self.prompt_new_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Refresh", command=self.connect_to_server)

        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Button-2>", self._show_context_menu)

    def _show_context_menu(self, event) -> None:
        """
        Displays the context menu at mouse coordinates.
        """
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _get_selected_base_path(self) -> str:
        """
        Determines the parent directory based on the current tree selection.
        """
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
        """
        Prompts user for file name and creates a new file via REST API.
        """
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
        """
        Prompts user for folder name and creates a new folder via REST API.
        """
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
        """
        Connects to the backend server via HTTP and SocketIO client instance.
        """
        raw_url = self.url_entry.get().strip()
        if not raw_url.startswith("http"):
            raw_url = f"http://{raw_url}"
        self.server_url = raw_url.rstrip("/")

        uname = simpledialog.askstring("Username", "Enter Username:")
        if not uname:
            return
        self.username = uname.strip()

        # Generate or load a persistent client UUID so identity is constant across refreshes
        if not hasattr(self, "client_uuid"):
            self.client_uuid = str(uuid.uuid4())

        try:
            response = requests.get(f"{self.server_url}/files", timeout=5)
            if response.status_code == 200:
                files = response.json()
                self._populate_file_tree(files)
                self.root.title(f"CodeServer: {self.server_url} [{self.username}]")

                if self.sio.connected:
                    self.sio.disconnect()

                # URL-encode parameters to cleanly handle spaces in full names (e.g., "Faris Muhammad Nissam")
                encoded_username = quote(self.username)
                connect_url = f"{self.server_url}?uuid={self.client_uuid}&username={encoded_username}"

                self.sio.connect(connect_url)
                self._refresh_users_list()
            else:
                messagebox.showerror("Error", f"Code: {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")

    def _populate_file_tree(self, file_list: list) -> None:
        """
        Populates the file explorer treeview widget recursively.
        """
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
        """
        Handles double clicks on file explorer tree items to load files into the editor.
        """
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
        """
        Saves current editor contents back to the server.
        """
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

    def _on_editor_key_release(self, event) -> None:
        """
        Emits typing batches via SocketIO when keys are released.
        """
        if not self.current_file or not self.sio.connected:
            return
        try:
            row, col = map(int, self.editor.index(tk.INSERT).split('.'))
            payload = {
                "file": self.current_file,
                "edits": [{"file": self.current_file, "row": row, "column": col, "keystroke": event.char}]
            }
            self.sio.emit('send_keystrokes', payload)
        except Exception:
            pass

    def _on_editor_cursor_move(self, event) -> None:
        """
        Emits cursor position changes when clicked or navigated via arrow keys.
        """
        if not self.current_file or not self.sio.connected:
            return
        try:
            row, col = map(int, self.editor.index(tk.INSERT).split('.'))
            self.sio.emit('send_cursor', {
                "username": self.username,
                "file": self.current_file,
                "row": row,
                "column": col
            })
        except Exception:
            pass

    def _apply_remote_edits(self, edits: list) -> None:
        """
        Applies incoming remote keystrokes, backspaces, forward deletes,
        or newlines to the editor.
        """
        for edit in edits:
            char = edit.get("keystroke", "")
            row = edit.get("row")
            col = edit.get("column")

            if row is None or col is None:
                continue

            try:
                if char == "\b":
                    # Backspace: delete character *behind* the cursor (col - 1 to col)
                    if col > 0:
                        start_idx = f"{row}.{col-1}"
                        end_idx = f"{row}.{col}"
                        self.editor.delete(start_idx, end_idx)
                elif char == "\x7f":
                    # Delete: delete character *ahead* of the cursor (col to col + 1)
                    start_idx = f"{row}.{col}"
                    end_idx = f"{row}.{col+1}"
                    self.editor.delete(start_idx, end_idx)
                else:
                    # Regular character or newline insertion
                    if char:
                        target_idx = f"{row}.{col}"
                        self.editor.insert(target_idx, char)
            except Exception:
                pass

    def _on_editor_backspace(self, event) -> None:
        """
        Emits a backspace/deletion event when the user hits backspace.
        """
        if not self.current_file or not self.sio.connected:
            return
        try:
            row, col = map(int, self.editor.index(tk.INSERT).split('.'))
            payload = {
                "file": self.current_file,
                "edits": [{
                    "file": self.current_file,
                    "row": row,
                    "column": col,
                    "keystroke": "\b"  # Use backspace character or a flag
                }]
            }
            self.sio.emit('send_keystrokes', payload)
        except Exception:
            pass

    def _on_editor_delete(self, event) -> None:
        """
        Emits a forward-delete event when the user hits the Delete key.
        """
        if not self.current_file or not self.sio.connected:
            return
        try:
            row, col = map(int, self.editor.index(tk.INSERT).split('.'))
            payload = {
                "file": self.current_file,
                "edits": [{
                    "file": self.current_file,
                    "row": row,
                    "column": col,
                    "keystroke": "\x7f"  # Standard ASCII code for Delete (DEL)
                }]
            }
            self.sio.emit('send_keystrokes', payload)
        except Exception:
            pass

    def _on_editor_return(self, event) -> None:
        """
        Emits a newline/return event when the user hits Enter.
        """
        if not self.current_file or not self.sio.connected:
            return
        try:
            row, col = map(int, self.editor.index(tk.INSERT).split('.'))
            payload = {
                "file": self.current_file,
                "edits": [{
                    "file": self.current_file,
                    "row": row,
                    "column": col,
                    "keystroke": "\n"
                }]
            }
            self.sio.emit('send_keystrokes', payload)
        except Exception:
            pass

    def _render_remote_cursor(self, data: dict) -> None:
        """
        Highlights remote user cursor positions on the editor interface.
        """
        user = data.get("username")
        if user == self.username:
            return
        row = data.get("row")
        col = data.get("column")

        tag_name = f"cursor_{user}"
        self.editor.tag_remove(tag_name, "1.0", tk.END)

        start_idx = f"{row}.{col}"
        end_idx = f"{row}.{col+1}"

        self.editor.tag_config(tag_name, background="#3a3d41", underline=True)
        try:
            self.editor.tag_add(tag_name, start_idx, end_idx)
        except Exception:
            pass

    def execute_shell_command(self, event) -> None:
        """
        Sends a shell command to the backend to run inside the project workspace.
        """
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
        """
        Appends streamed output text into the terminal widget.
        """
        self.terminal.insert(tk.END, text)
        self.terminal.see(tk.END)

def main() -> None:
    """
    Main application entry point initializing the Tkinter root window.
    """
    root = tk.Tk()
    app = CodeServerIDE(root)
    root.mainloop()

if __name__ == "__main__":
    main()
