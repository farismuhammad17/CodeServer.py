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
import tkinter as tk
from tkinter import filedialog

from flask import Flask, Response, jsonify, request

# Config

SERVER_PORT = 5000

SUC_OK          = 200   # Default for GET
SUC_CREATED     = 201   # Default for POST
SUC_NO_CONTENT  = 204   # POST successful, but nothing to return
SUC_PARTIAL_CON = 206   # POST successful, but streaming partial data
ERR_BAD_REQUEST = 400   # Invalid inputs
ERR_UNATHORIZED = 401   # User is unauthenticated
ERR_FORBIDDEN   = 402   # User is unauthorized

# Globals

PROJ = None

app = Flask(__name__)

# Helpers

def get_target_folder() -> str:
    """
    Opens a folder selection dialog and returns the selected folder path.

    Returns:
        str: The path of the selected folder, or None if no folder was selected.
    """

    root = tk.Tk()
    root.withdraw()                       # Hides the main empty window
    root.attributes('-topmost', True)     # Forces the dialog to the front

    folder_path = filedialog.askdirectory(title="Select Your Project Folder")

    root.destroy()

    return folder_path

# API

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
    path = os.path.join(PROJ, file)

    with open(path, 'r', encoding='utf-8') as f:
        return jsonify({
            'file': file,
            'content': f.read()
        }), SUC_OK

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

def main() -> None:
    """
    Main function to start the Flask server and configure Tailscale.
    """

    # pylint: disable=global-statement
    global PROJ

    if len(sys.argv) > 1:
        PROJ = ' '.join(sys.argv[1:])
    else:
        PROJ = get_target_folder()

    if not PROJ:
        print("No folder selected. Exiting.")
        return

    if '--no-tailscale' not in sys.argv:
        print("[*] Starting Tailscale Server ...")
        os.system(f"tailscale serve --bg http://localhost:{SERVER_PORT}")

    print(f"[*] Starting Flask server on port {SERVER_PORT} ...")
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False)

if __name__ == "__main__":
    main()
