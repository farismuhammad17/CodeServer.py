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
import subprocess
import sys
import threading
import queue

import mysql.connector as sql

from flask import Flask, Response, jsonify, request
from flask_socketio import SocketIO, emit

from dotenv import load_dotenv

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    print("[#] Tkinter not found.")
    tk = None

load_dotenv()

SUC_OK          = 200   # Default for GET
SUC_CREATED     = 201   # Default for POST
SUC_NO_CONTENT  = 204   # POST successful, but nothing to return
SUC_PARTIAL_CON = 206   # POST successful, but streaming partial data
ERR_BAD_REQUEST = 400   # Invalid inputs
ERR_UNATHORIZED = 401   # User is unauthenticated
ERR_FORBIDDEN   = 402   # User is unauthorized

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'user':     os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'codeserver_db')
}
SERVER_PORT = int(os.getenv('SERVER_PORT', '5000'))

PROJ = None

# Session processes per SID
ACTIVE_TERMINALS = {}

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Helpers

def get_target_folder() -> str:
    """
    Opens a folder selection dialog and returns the selected folder path.

    Returns:
        str: The path of the selected folder, or None if no folder was
            selected.
    """

    if not tk:
        print("[!] Pass project by CLI (python3 src/server.py path/to/proj)")
        return ''

    root = tk.Tk()
    root.withdraw()                       # Hides the main empty window
    root.attributes('-topmost', True)     # Forces the dialog to the front

    folder_path = filedialog.askdirectory(title="Select Your Project Folder")

    root.destroy()

    return folder_path

def get_db_connection() -> sql.MySQLConnection:
    """
    Opens and returns a new MySQL database connection using global
    configurations.

    Returns:
        MySQLConnection: The active database connection object.
    """

    return sql.connect(**DB_CONFIG)

def is_path_safe(path: str) -> bool:
    """
    Verifies that the given absolute path resides strictly inside the global
    PROJ directory, resolving symlinks to prevent traversal.

    Returns:
        bool: True if safe, False if not
    """

    if not path or not PROJ:
        return False

    target_abs = os.path.realpath(path)
    base_abs   = os.path.realpath(PROJ)

    try:
        return os.path.commonpath([base_abs, target_abs]) == base_abs
    except ValueError:
        return False

def sandbox_proj() -> None:
    """
    OS-level helper to lock the current process working directory and
    environment inside the global PROJ directory safely.
    """

    global PROJ

    PROJ = os.path.abspath(PROJ)

    # Permanently lock the server process working directory
    os.chdir(PROJ)

    # Set environment anchor for subprocesses and custom tools
    os.environ['PROJ_ROOT'] = PROJ

    if os.name == 'posix':
        print(f"[*] Workspace boundary locked to {PROJ} (POSIX CWD & Environment secured).")
    elif os.name == 'nt':
        os.environ['SYSTEMROOT'] = os.environ.get('SystemRoot', 'C:\\Windows')
        print(f"[*] Workspace boundary locked to {PROJ} (Windows Environment secured).")

# API

@app.route('/', methods=['GET'])
def api_root() -> tuple[Response, int]:
    """
    Root endpoint providing raw informational text and repository redirection.

        GET /

    Response format:
        (str) info_text, (int) RESPONSE_CODE
    """

    return Response((
        "This application is powered by CodeServer.py\n"
        "--------------------------------------------------\n"
        "Repository & Documentation:\n"
        "https://github.com/farismuhammad17/CodeServer.py\n"
    ), mimetype='text/plain'), SUC_OK

@app.route('/read', methods=['GET'])
def api_read() -> tuple[Response, int]:
    """
    Reads and returns the contents of a specified file from the
    project directory.

        GET /read?file=path/to/file

    Response format:
        (tuple) ({
            'file': (str) path/to/file,
            'content': (str) file content
        }, (int) RESPONSE_CODE)
    """

    file = request.args.get('file')
    if not file:
        return jsonify({
            'file': '',
            'content': 'Missing file parameter'
        }), ERR_BAD_REQUEST

    file_rel = file.lstrip('/\\')
    path = os.path.normpath(os.path.join(PROJ, file_rel))

    # Verify file in project
    if not is_path_safe(path):
        return jsonify({
            'file': file,
            'content': 'FILE_INACCESSIBLE'
        }), ERR_BAD_REQUEST

    # Verify file exists
    if not os.path.exists(path) or not os.path.isfile(path):
        return jsonify({
            'file': file,
            'content': 'FILE_NOT_FOUND'
        }), ERR_BAD_REQUEST

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({
            'file': file,
            'content': content
        }), SUC_OK
    except PermissionError:
        return jsonify({
            'file': file,
            'content': 'Error: Permission denied to access this file.'
        }), ERR_FORBIDDEN
    except UnicodeDecodeError:
        return jsonify({
            'file': file,
            'content': 'Error: Failed to decode file using UTF-8 encoding.'
        }), ERR_BAD_REQUEST

@app.route('/files', methods=['GET'])
def api_files() -> tuple[Response, int]:
    """
    Retrieves a sorted, recursive list of all files and directories
    in the project workspace, with directories listed before files.

        GET /files

    Response format:
        (tuple) ([
            (str) path/to/file_or_directory,
            ...
        ], (int) RESPONSE_CODE)
    """

    def load_ignore_patterns() -> set:
        """Loads ignore patterns from .csignore if present."""

        ignored = {'.csignore'}
        ignore_path = os.path.join(PROJ, '.csignore')
        if not os.path.exists(ignore_path) or not os.path.isfile(ignore_path):
            return ignored
        try:
            with open(ignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith('#'):
                        pattern = cleaned.rstrip('/\\')
                        if pattern:
                            ignored.add(pattern)
        except (OSError, UnicodeDecodeError) as e:
            print(f"[!] Error on .csignore: {e}")
        return ignored

    ignored = load_ignore_patterns()
    dir_list, file_list = [], []

    def is_ignored(name: str, current_rel_root: str) -> bool:
        rel_path = os.path.join(current_rel_root, name).replace('\\', '/')
        return name in ignored or rel_path in ignored or any(
            rel_path.startswith(p + '/') or rel_path == p for p in ignored
        )

    for root, dirs, files in os.walk(PROJ):
        rel_root = '' if os.path.relpath(root, PROJ) == '.' \
            else os.path.relpath(root, PROJ)
        dirs[:] = [d for d in dirs if not is_ignored(d, rel_root)]

        for d in dirs:
            rel_path = os.path.join(rel_root, d).replace('\\', '/')
            if not is_ignored(d, rel_root):
                dir_list.append(rel_path)

        for f in files:
            rel_path = os.path.join(rel_root, f).replace('\\', '/')
            if not is_ignored(f, rel_root):
                file_list.append(rel_path)

    return jsonify(sorted(dir_list) + sorted(file_list)), SUC_OK

@app.route('/save', methods=['POST'])
def api_save() -> tuple[Response, int]:
    """
    Saves or overwrites text content to an existing file in the
    project workspace and clears its keystroke buffer.

        POST /save + payload:
        {
            "filename": "path/to/file",
            "content": "file content"
        }

    Response format:
        (tuple) ({
            "status": (str),
            "message": (str)
        }, (int) RESPONSE_CODE)
    """

    data = request.get_json()

    if not data or 'filename' not in data or 'content' not in data:
        return jsonify({
            "status": "error",
            "message": "Missing 'filename' or 'content' in JSON"
        }), ERR_BAD_REQUEST

    filename = data['filename']
    content = data['content']

    file_path = os.path.join(PROJ, filename)

    # Verify file exists
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return jsonify({
            "status": "error",
            "message": "File does not exist"
        }), ERR_BAD_REQUEST

    # Verify file is safe
    if not is_path_safe(file_path):
        return jsonify({
            "status": "error",
            "message": "File inaccessible"
        }), ERR_BAD_REQUEST

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # Clear keystrokes buffer for this file upon saving
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_buffers WHERE file_path = %s;",
            (filename.lstrip('/\\'),))
        conn.commit()
        cursor.close()
        conn.close()
    except sql.Error:
        pass

    return jsonify({
        "status": "success",
        "message": f"'{filename}' saved"
    }), SUC_CREATED

@app.route('/new/file', methods=['POST'])
def api_new_file() -> tuple[Response, int]:
    """
    Creates a new file at the specified relative path, auto-creating
    missing parent directories.

        POST /new/file?file=path/to/newfile + payload:
        {
            "content": "initial file content"
        }

    Response body:
        (tuple) ({
            "status": (str),
            "message": (str)
        }, (int) RESPONSE_CODE)
    """

    file = request.args.get('file')
    path = os.path.join(PROJ, file)

    # Verify path is safe
    if not is_path_safe(path):
        return jsonify({
            "status": "error",
            "message": "Path outside project scope"
        }), ERR_BAD_REQUEST

    data = request.get_json() or {}
    content = data.get('content', '')

    # Create all folders till file
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding='utf-8') as f:
        f.write(content)

    return jsonify({
        "status": "success",
        "message": f"'{file}' created"
    }), SUC_CREATED

@app.route('/new/folder', methods=['POST'])
def api_new_folder() -> tuple[Response, int]:
    """
    Creates a new directory (and any necessary parent directories)
    within the project workspace.

        POST /new/folder?folder=path/to/newfolder

    Response body:
        (tuple) ({
            "status": (str),
            "message": (str)
        }, (int) RESPONSE_CODE)
    """

    folder = request.args.get('folder')
    path = os.path.join(PROJ, folder)

    # Verify path is safe
    if not is_path_safe(path):
        return jsonify({
            "status": "error",
            "message": "Path outside project scope"
        }), ERR_BAD_REQUEST

    os.makedirs(path, exist_ok=True)

    return jsonify({
        "status": "success",
        "message": f"'{folder}' created"
    }), SUC_CREATED

@app.route('/users', methods=['GET'])
def api_users() -> tuple[Response, int]:
    """
    Retrieves a list of all active usernames currently connected to the server.

        GET /users

    Response format:
        (tuple) ([
            (str) username,
            ...
        ], (int) RESPONSE_CODE)
    """

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username FROM active_clients;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    usernames = [row['username'] for row in rows]

    return jsonify(usernames), SUC_OK

@app.route('/keystrokes', methods=['GET'])
def api_keystrokes() -> tuple[Response, int]:
    """
    Retrieves all un-saved keystrokes for a specified file from MySQL.

        GET /keystrokes?file=path/to/file

    Response format:
        (tuple) ([
            {
                "file": (str),
                "keystroke": (str),
                "row": (int),
                "column": (int)
            },
            ...
        ], (int) RESPONSE_CODE)
    """

    file = request.args.get('file')
    if not file:
        return jsonify([]), ERR_BAD_REQUEST

    file_rel = file.lstrip('/\\')
    path = os.path.normpath(os.path.join(PROJ, file_rel))

    if not is_path_safe(path):
        return jsonify([]), ERR_BAD_REQUEST

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT file_path AS file, keystroke, `row`, `col` AS `column` "
        "FROM file_buffers WHERE file_path = %s;",
        (file_rel,)
    )
    edits = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(edits), SUC_OK

# Sockets

@socketio.on('connect')
def handle_connect() -> bool:
    """
    Handles incoming WebSocket connection attempts, authenticating the user
    via database lookup or handshake query parameters and registering active
    sessions.

        Socket event: 'connect'
        Query parameters:
        {
            "username": (str) optional username passed during connection
        }

    Response:
        Returns False to abort connection if no username is found;
        otherwise emits 'user_join' to all other connected clients.
    """

    sid = request.sid
    username = request.args.get('username')
    client_uuid = request.args.get('uuid')

    if not username or not client_uuid:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO active_clients (client_uuid, username, sid) "
                            "VALUES (%s, %s, %s) "
                            "ON DUPLICATE KEY UPDATE username = %s, sid = %s;",
        (client_uuid, username, sid, username, sid)
    )
    conn.commit()
    cursor.close()
    conn.close()

    emit('user_join', {"username": username},
        broadcast=True,
        include_self=False)

    return True

@socketio.on('disconnect')
def handle_disconnect() -> None:
    """
    Handles client disconnections by purging their active session from
    the database and notifying all other participants of their departure.

        Socket event: 'disconnect'

    Response:
        Emits 'user_left' containing the disconnected username to all
            remaining clients.
    """

    sid = request.sid

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch username before deleting so we can announce the leave
    cursor.execute("SELECT username FROM active_clients WHERE sid = %s;",
        (sid,))
    row = cursor.fetchone()
    username = row['username'] if row else f"User_{sid}"

    cursor.execute("DELETE FROM active_clients WHERE sid = %s;",
        (sid,))
    conn.commit()
    cursor.close()
    conn.close()

    sid = request.sid
    if sid in ACTIVE_TERMINALS:
        try:
            ACTIVE_TERMINALS[sid].terminate()
        except (OSError, subprocess.SubprocessError):
            pass
        del ACTIVE_TERMINALS[sid]

    if username:
        print(f"[*] Client disconnected: {username} (SID: {sid})")
        emit('user_left', {"username": username},
            broadcast=True)

@socketio.on('send_keystrokes')
def handle_keystrokes(data) -> None:
    """
    Receives, validates, and broadcasts a buffered batch of keystroke edits
    from a connected client to all other workspace participants.

        Socket event: 'send_keystrokes' + payload:
        {
            "file": (str) path/to/file.py,
            "edits": [
                {
                    "file": (str),
                    "row": (int),
                    "column": (int),
                    "keystroke": (str)
                },
                ...
            ]
        }

    Response:
        Emits 'broadcast_keystrokes' to all other connected clients.
    """

    # Verify that client data passed
    if not isinstance(data, dict) or 'file' not in data or 'edits' not in data:
        return

    file_rel = data['file'].lstrip('/\\')
    file_path = os.path.normpath(os.path.join(PROJ, file_rel))

    if not os.path.exists(file_path) or  \
        not os.path.isfile(file_path) or \
        not is_path_safe(file_path):
        return

    # Verify the list edits
    edits = data.get('edits')
    if not isinstance(edits, list):
        return

    # Validate each individual edit structure inside the batch
    for edit in edits:
        if not isinstance(edit, dict) or                                     \
            not all(k in edit for k in                                      \
                ('file', 'row', 'column', 'keystroke')) or                  \
            not isinstance(edit['row'], int) or                             \
            not isinstance(edit['column'], int) or                          \
            not isinstance(edit['keystroke'], str) or                       \
            edit['row'] < 0 or edit['column'] < 0: return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for edit in edits:
            cursor.execute(
                "INSERT INTO file_buffers (file_path, keystroke, `row`, `col`) "
                "VALUES (%s, %s, %s, %s);",
                (file_rel, edit['keystroke'], edit['row'], edit['column'])
            )
        conn.commit()
        cursor.close()
        conn.close()
    except sql.Error:
        pass

    emit('broadcast_keystrokes', data,
        broadcast=True,
        include_self=False)

@socketio.on('start_terminal')
def handle_start_terminal(_data) -> None:
    """
    Spawns an interactive shell session for the connected client and
    streams stdout/stderr without race conditions or prompt hanging.

        Socket event: 'start_terminal'
    """

    sid = request.sid

    if sid in ACTIVE_TERMINALS:
        try:
            ACTIVE_TERMINALS[sid].terminate()
        except OSError:
            pass

    if os.name == "nt": # Windows
        shell_cmd = "cmd.exe"
    elif sys.platform == "darwin": # MacOS
        sandbox_profile = (
            f"(version 1)\n"
            f"(allow default)\n"
            f"(deny file-write* (subpath \"/\"))\n"
            f"(allow file-write* (subpath \"{PROJ}\"))\n"
        )
        shell_cmd = f"bash" # macOS terminal relies on strict cwd=PROJ
    else: # Linux / Posix compliant OSs
        if os.path.exists("/usr/bin/bwrap"):
            shell_cmd = (
                f"bwrap "
                f"--ro-bind /usr /usr "
                f"--ro-bind /lib /lib "
                f"--ro-bind /lib64 /lib64 "
                f"--bind {PROJ} /app "
                f"--chdir /app "
                f"--proc /proc "
                f"--dev /dev "
                f"/bin/bash"
            )
        else:
            print("[#] bwrap not found, defaulting to bash.")
            shell_cmd = "bash"

    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        # pylint: disable=consider-using-with
        process = subprocess.Popen(
            shell_cmd,
            shell=True,
            cwd=PROJ,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        ACTIVE_TERMINALS[sid] = process

        def read_output():
            """
            Batches stdout characters into a queue and flushes them periodically
            to prevent network packet scrambling while keeping prompts instant.
            """

            q = queue.Queue()

            def reader_loop():
                try:
                    while True:
                        char = process.stdout.read(1)
                        if not char:
                            break
                        q.put(char)
                except (OSError, ValueError):
                    pass
                finally:
                    q.put(None)

            threading.Thread(target=reader_loop, daemon=True).start()

            buffer = []
            try:
                while True:
                    try:
                        # Wait up to 30ms for characters
                        char = q.get(timeout=0.03)
                        if char is None:
                            break
                        buffer.append(char)

                        # Flush immediately on newline or if buffer gets full
                        if char == '\n' or len(buffer) >= 32:
                            socketio.emit('terminal_output',
                                {'output': "".join(buffer)},
                                room=sid)
                            buffer.clear()
                    except queue.Empty:
                        # Flush partial text
                        if buffer:
                            socketio.emit('terminal_output',
                                {'output': "".join(buffer)},
                                room=sid)
                            buffer.clear()
            except (OSError, ValueError):
                pass
            finally:
                if buffer:
                    socketio.emit('terminal_output',
                        {'output': "".join(buffer)},
                        room=sid)
                socketio.emit('terminal_output',
                    {'output': '\n[Process exited]\n'},
                    room=sid)
                if sid in ACTIVE_TERMINALS:
                    del ACTIVE_TERMINALS[sid]

        threading.Thread(target=read_output, daemon=True).start()
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        socketio.emit('terminal_output',
            {'output': f'[Failed to start shell: {e}]\n'},
            room=sid)

@socketio.on('terminal_input')
def handle_terminal_input(data) -> None:
    """
    Sends keystrokes/commands into the running shell process stdin.

        Socket event: 'terminal_input' + payload:
        {
            "input": (str) text to feed into stdin
        }
    """

    sid = request.sid
    if sid in ACTIVE_TERMINALS and 'input' in data:
        process = ACTIVE_TERMINALS[sid]
        try:
            process.stdin.write(data['input'])
            process.stdin.flush()
        except (OSError, ValueError) as e:
            print(f"[!] Terminal input error: {e}")

# MySQL

def init_db() -> None:
    """
    Initializes the MySQL database and the required tables
    including 'active_clients' and 'file_buffers'.
    """

    conn = sql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )
    cursor = conn.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']};")
    cursor.execute(f"USE {DB_CONFIG['database']};")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_clients (
            client_uuid VARCHAR(255) PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            sid VARCHAR(255),
            connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_buffers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            file_path VARCHAR(500) NOT NULL,
            keystroke VARCHAR(10) NOT NULL,
            `row` INT NOT NULL,
            `col` INT NOT NULL
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()

def main() -> None:
    """
    Main function to initialize database, start the Flask server and
    configure Tailscale.
    """

    # pylint: disable=global-statement
    global PROJ

    # CLI flags
    if len(sys.argv) > 1:
        PROJ = ' '.join(sys.argv[1:])
    else:
        PROJ = get_target_folder()

    if not PROJ:
        print("[!] No folder selected.")
        return

    PROJ = os.path.abspath(PROJ)

    # Ensure PROJ actually exists
    if not os.path.exists(PROJ) or not os.path.isdir(PROJ):
        print(f"[!] '{PROJ}' not found or not directory.")
        return

    sandbox_proj()

    # MySQL
    try:
        init_db()
        print("[*] MySQL database initialised")
    except sql.Error as e:
        print(f"[!] Database connection/initialisation failed:\n\t{e}")
        return

    # Tailscale
    if '--no-tailscale' not in sys.argv:
        print("[*] Starting Tailscale Server ...")
        os.system(f"tailscale serve --bg http://localhost:{SERVER_PORT}")

    print(f"[*] Starting Flask server on port {SERVER_PORT} ...")
    socketio.run(app, host='0.0.0.0', port=SERVER_PORT, debug=False)

if __name__ == "__main__":
    main()
