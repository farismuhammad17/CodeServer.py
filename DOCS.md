# CodeServer.py Documentation

CodeServer.py is a client-server application designed to simplify collaborative project development across multiple developers. A single host device, containing the actual files and folders of the project, runs the server application, which establishes the necessary REST API endpoints and WebSockets. Clients can then connect to the server to interact with the remote project workspace as if it were present locally on their own machines.

As a developer, I, Faris, managed to keep the code mostly self-documenting. This file serves to provide a structured, step-by-step explanation towards this project, doubling *(kind of)* as the project report.

- [Aim](#aim)
- [Technologies Used](#technologies-used)
- [Overview](#overview)
    - [Use of API Endpoints](#use-of-api-endpoints)
    - [Use of WebSockets](#use-of-websockets)
- [Satisfying Requirements](#satisfying-requirements)
- [Environment Variables](#environment-variables)
- [MySQL Database Schema](#mysql-database-schema)
- [Server API endpoints](#server-api-endpoints)
    - [/](#root-)
    - [/read](#read)
    - [/files](#files)
    - [/save](#save)
    - [/new/file](#newfile)
    - [/new/folder](#newfolder)
    - [/cmd](#cmd)
    - [/users](#users)
    - [/keystrokes](#keystrokes)
- [Server WebSocket endpoints](#server-websocket-endpoints)
    - [Connection & Handshake](#connection--handshake)
    - [user_join](#user_join)
    - [user_left](#user_left)
    - [send_keystrokes](#send_keystrokes)
    - [broadcast_keystrokes](#broadcast_keystrokes)
    - [start_terminal](#start_terminal)
    - [terminal_input](#terminal_input)
- [Server Security](#server-security)
- [Code Cleanliness](#code-cleanliness)
- [Choice of Licence](#choice-of-licence)

## Aim

To provide a dedicated, multi-user collaborative remote development environment over a localized project directory without third-party access or interference.

## Technologies Used

- **[Tailscale](https://tailscale.com/)**: Bridges the local server securely to the WAN via mesh networking.
- **[Tkinter](https://docs.python.org/3/library/tkinter.html)**: Native desktop client graphical user interface.
- **[Flask](https://flask.palletsprojects.com/)**: Acts as the core lightweight server backend.
- **[Flask-SocketIO](https://flask-socketio.readthedocs.io/)**: Provides real-time bidirectional WebSocket communication.
- **[Requests](https://requests.readthedocs.io/)**: Handles HTTP client-side API calls and parsing.
- **[python-socketio](https://python-socketio.readthedocs.io/)**: Manages the client-side WebSocket engine.
- **[MySQL](https://dev.mysql.com/)**: Tracks active client sessions persistently.
  - `mysql-connector-python`: The underlying database driver.
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: Secures environment configuration management.
- **[Multithreading](https://docs.python.org/3/library/threading.html)**: To run multiple client terminal sessions

## Overview

The project is split into two primary components: the server and the client. 

The server exposes a suite of API endpoints and WebSocket channels. The API endpoints allow clients to inspect project structures, read and write files, and instantiate new directories or files dynamically. Meanwhile, the client provides a standardised graphical user interface for interacting with these remote assets.

Simple stateless operations (such as reading or saving a file) utilise one-way HTTP requests from the client to the server. Conversely, broadcasting live user keystrokes requires real-time synchronisation. Since HTTP polling is inefficient and wasteful, WebSockets are employed to enable instantaneous, event-driven communication between the server and all connected clients.

### Use of API Endpoints
API routes are ideal for operations where the server does not need an active, persistent stream back to the client at that precise millisecond. By passing structured JSON payloads or query parameters, clients can seamlessly query file states, execute shell subprocesses, or fetch active user lists.

### Use of WebSockets
WebSockets establish a two-way communication channel. In CodeServer.py, this is leveraged for inter-client change reflectivity. When a user types inside a file editor, keystrokes are buffered locally and emitted to the server at set intervals. The server validates the payload against the active workspace and broadcasts the edits to all *other* connected participants, enabling real-time collaboration.

## Satisfying Requirements

As a Class 12 CBSE Computer Science project submission, the architecture satisfies several core criteria:
- **Pure Python Implementation:** Uses Python's extensive standard library and ecosystem to handle low-level networking, process execution, and GUI rendering.
- **Database Integration:** Incorporates MySQL to manage active clients, functioning as a complete CRUD (Create, Read, Update, Delete) application.

## Environment Variables

The application relies on a `.env` file for secure configuration prior to launch. A template file (`.env.example`) is provided in the repository.

- `DB_HOST`: The IP address or hostname of the MySQL server (defaults to `localhost`).
- `DB_USER`: The MySQL username (defaults to `root`).
- `DB_PASSWORD`: The access password for the MySQL user.
- `DB_NAME`: The name of the database utilised by the application (defaults to `codeserver_db`).
- `SERVER_PORT`: The network port on which the Flask server runs (defaults to `5000`).

## MySQL Database Schema

On boot, the server initialises a database (if it does not already exist) and ensures the following tracking table is present:

**Table Name:** `active_clients`

| Field | Type | Null | Key | Default | Extra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `client_uuid` | `VARCHAR(255)` | NO | PRI | `NULL` | |
| `username` | `VARCHAR(255)` | NO | | `NULL` | |
| `sid` | `VARCHAR(255)` | YES | | `NULL` | |
| `connected_at` | `TIMESTAMP` | YES | | `CURRENT_TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP |

**Table Name:** `file_buffers`

| Field | Type | Null | Key | Default | Extra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `int` | NO | PRI | `NULL` | `auto_increment` |
| `file_path` | `VARCHAR(500)` | NO | | `NULL` | |
| `keystroke` | `varchar(10)` | NO | | `NULL` | |
| `row` | `int` | NO | | `NULL` | |
| `col` | `int` | NO | | `NULL` | |

These tables are created in the python `init_db` function, called upon boot, executes the following command.

```sql
CREATE DATABASE IF NOT EXISTS codeserver_db;
USE codeserver_db;

CREATE TABLE IF NOT EXISTS active_clients (
    client_uuid VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    sid VARCHAR(255),
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_buffers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_path VARCHAR(500) NOT NULL,
    keystroke VARCHAR(10) NOT NULL,
    `row` INT NOT NULL,
    `col` INT NOT NULL
);
```

## Server API endpoints

To allow the clients to communicate with the server, it opens up API endpoints for the clients to get and send data through.

### ROOT `/`

```
GET /

Response format:
    (str) info_text, (int) RESPONSE_CODE
```

If a user tries to paste the server address into a browser or any other software without passing another API, the server responses with the following text, which is useful to test if the server is alive or not, or to provide clients with necessary instructions on acquiring the IDE code.

```
This application is powered by CodeServer.py
--------------------------------------------------
Repository & Documentation:
https://github.com/farismuhammad17/CodeServer.py
```

### `/read`

```
GET /read?file=path/to/file

Response format:
    (tuple) ({
        'file': (str) path/to/file,
        'content': (str) file content
    }, (int) RESPONSE_CODE)
```

Reads and returns the contents of a specified file from the project directory.

### `/files`

```
GET /files

Response format:
    (tuple) ([
        (str) path/to/file_or_directory,
        ...
    ], (int) RESPONSE_CODE)
```

Retrieves a sorted, recursive list of all files and directories in the project workspace, with directories listed before files.

### `/save`

```
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
```

Saves or overwrites text content to an existing file in the project workspace and clears its keystroke buffer.

### `/new/file`

```
POST /new/file?file=path/to/newfile + payload:
{
    "content": "initial file content"
}

Response body:
    (tuple) ({
        "status": (str),
        "message": (str)
    }, (int) RESPONSE_CODE)
```

Creates a new file at the specified relative path, auto-creating missing parent directories.

### `/new/folder`

```
POST /new/folder?folder=path/to/newfolder

Response body:
    (tuple) ({
        "status": (str),
        "message": (str)
    }, (int) RESPONSE_CODE)
```

Creates a new directory (and any necessary parent directories) within the project workspace.

### `/cmd`

```
POST /cmd + payload:
{
    "command": "your_shell_command"
}

Response body:
    (tuple) (streamed command output, (int) RESPONSE_CODE)
```

Executes a shell command within the project workspace directory and streams the output.

### `/users`

```
GET /users

Response format:
    (tuple) ([
        (str) username,
        ...
    ], (int) RESPONSE_CODE)
```

Retrieves a list of all active usernames currently connected to the server.

### `/keystrokes`

```
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
```

Retrieves all un-saved keystrokes for a specified file from MySQL.

## Server WebSocket endpoints

To allow real-time collaboration (such as user presence and live keystroke sharing), the server uses Socket.IO. Clients can connect to the root namespace and listen to or emit specific events.

### Connection & Handshake

```
Connection URL: ws://<server_ip>:<port>
Query Parameters:
    {
        "username": (str) user's display name,
        "uuid": (str) unique client identifier
    }
```

Clients must provide both a `username` and a `uuid` as query parameters during the connection handshake. If either is missing, the connection is immediately rejected.

### `user_join`

Server $\rightarrow$ Client

```json
{
    "username": (str)
}
```

Broadcasted to all *other* connected clients when a new user successfully completes the handshake and joins the workspace.

### `user_left`

Server $\rightarrow$ Client

```json
{
    "username": (str)
}
```

Broadcasted to all remaining clients when a user disconnects from the server, announcing their departure.

### `send_keystrokes`

Client $\rightarrow$ Server

```json
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
```

Sent by a client when typing or making edits. The server validates the file path and individual edits against the workspace, records un-saved keystrokes into the MySQL `file_buffers` table, and broadcasts the batch to other peers.

### `broadcast_keystrokes`

Server $\rightarrow$ Client

```json
{
    "file": (str) path/to/file.py,
    "edits": [...]
}
```

Relays the validated batch of keystrokes received from `send_keystrokes` to all other active participants in the workspace so they can render real-time collaborative edits.

### `start_terminal`

Server $\leftrightarrow $ Client

Spawns an interactive shell session (command prompt on Windows, bash on Linux, etc.) mapped directly to the connected client's session ID (`sid`). It configures unbuffered standard output and spawns a background reader thread using a queue data structure to avoid race fragmentation with timed flushing to stream output securely without prompt hanging or packet interleaving.

### `terminal_input`

Client $\rightarrow$ Server

```json
{
    "input": (str) text to feed into stdin
}
```

Receives command text or keystrokes from the client IDE terminal and streams them directly into the standard input of that specific client's active persistent shell subprocess.

## Server Security

Since the clients are able to access server files via the API, nothing is stopping any user from accessing the following:

```
/read?file=../../../../../../../../etc/passwd
```

If the server was running on Linux, this would print out the every password on the server machine. This is obviously a vulnerability, accounted for by the `is_path_safe` function, which makes sure that any endpoint accesses do **not** let the user past the project chosen at server boot.

## Code Cleanliness

A "Linter", a special software designed to maintain a "code standard" a default cleanliness measures, was used during the creation of the server code. Namely, pylint, whose configurations are mentioned inside the [`.pylintrc`](./.pylintrc) file.

## Choice of Licence

Besides the explicit patent guarantee clause, legal clarity, and trademark protection that makes Apache 2.0 a great programmer's license, we chose it because it places accountability on specific shoulders. The program is delivered "as-is", and, since this is a simple proof-of-concept work, *all* accountability of data loss or server hackings are placed upon the user of this source code.

This obviously does not imply that the code is terrible, misconfigured, or prone to errors. We have tried to fix as much errors as we could find, patch as much vulnerabilities as we could think of, and have written these files with love.
