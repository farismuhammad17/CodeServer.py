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

import mysql.connector as sql

from flask import Flask, Response, jsonify, request
from flask_socketio import SocketIO, emit

from dotenv import load_dotenv

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
SERVER_PORT = int(os.getenv('SERVER_PORT', 5000))

PROJ = None

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

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("[!] Tkinter is not found on this machine. Provide path directly.")
        print("    Syntax: python3 src/server.py /path/to/project")
        return None

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
    PROJ directory.

    Returns:
        bool: True if safe, False if not
    """

    if not path or not PROJ:
        return False

    target_abs = os.path.abspath(path)
    base_abs   = os.path.abspath(PROJ)

    try:
        return os.path.commonpath([base_abs, target_abs]) == base_abs
    except ValueError:
        return False

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
def api_list() -> tuple[Response, int]:
    """
    Retrieves a sorted, recursive list of all files and directories
    in the project workspace.

        GET /files

    Response format:
        (tuple) ([
            (str) path/to/file_or_directory,
            ...
        ], (int) RESPONSE_CODE)
    """

    file_list = []

    for root, dirs, files in os.walk(PROJ):
        rel_root = os.path.relpath(root, PROJ)
        if rel_root == '.':
            rel_root = ''
        for d in dirs:
            file_list.append(os.path.join(rel_root, d).replace('\\', '/'))
        for f in files:
            file_list.append(os.path.join(rel_root, f).replace('\\', '/'))

    return jsonify(sorted(file_list)), SUC_OK

@app.route('/save', methods=['POST'])
def api_save() -> tuple[Response, int]:
    """
    Saves or overwrites text content to an existing file in the
    project workspace.

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

@app.route('/cmd', methods=['POST'])
def api_cmd() -> tuple[Response, int]:
    """
    Executes a shell command within the project workspace directory
    and streams the output.

        POST /cmd + payload:
        {
            "command": "your_shell_command"
        }

    Response body:
        (tuple) (streamed command output, (int) RESPONSE_CODE)
    """

    data = request.get_json() or {}
    command = data.get('command')

    if not command:
        return jsonify({
            "error": "Missing 'command' in JSON payload"
        }), ERR_BAD_REQUEST

    def generate():
        # pylint: disable=consider-using-with
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=PROJ,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        try:
            yield from process.stdout
        finally:
            process.terminate()
            process.wait()

    return Response(generate(), mimetype='text/plain'), SUC_OK

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

    # Verify that the target file exists
    file_path = os.path.join(PROJ, data['file'])
    if not os.path.exists(file_path) or \
        not os.path.isfile(file_path) or \
        not is_path_safe(file_path):
        return

    # Verify the list edits
    edits = data.get('edits')
    if not isinstance(edits, list):
        return

    # Validate each individual edit structure inside the batch
    for edit in edits:
        if not isinstance(edit, dict) or                                       \
            not all(k in edit for k in                                         \
                ('file', 'row', 'column', 'keystroke')) or                     \
            not isinstance(edit['row'], int) or                                \
            not isinstance(edit['column'], int) or                             \
            not isinstance(edit['keystroke'], str) or                          \
            edit['row'] < 0 or edit['column'] < 0: return

    emit('broadcast_keystrokes', data,
        broadcast=True,
        include_self=False)

# MySQL

def init_db() -> None:
    """
    Initializes the MySQL database and the 'active_clients' table
    using a persistent client_uuid primary key.
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
        PROJ = os.path.abspath(' '.join(sys.argv[1:]))
    else:
        PROJ = get_target_folder()

    if not PROJ:
        print("[!] No folder selected.")
        return

    PROJ = os.path.abspath(PROJ)

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
