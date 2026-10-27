*This documentation is still unfinished*

# CodeServer.py Documentation

CodeServer.py is a client-server application designed to simplify collaborative project development across multiple developers. A single host device, containing the actual files and folders of the project, runs the server application, which establishes the necessary REST API endpoints and WebSockets. Clients can then connect to the server to interact with the remote project workspace as if it were present locally on their own machines.

As a developer, I, Faris, managed to keep the code mostly self-documenting. This file serves to provide a structured, step-by-step explanation towards this project, doubling as the project report.

- [Aim](#aim)
- [Technologies Used](#technologies-used)
- [Overview](#overview)
  - [Use of API Endpoints](#use-of-api-endpoints)
  - [Use of WebSockets](#use-of-websockets)
- [Satisfying Requirements](#satisfying-requirements)
- [Environment Variables](#environment-variables)
- [MySQL Database Schema](#mysql-database-schema)

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

The python `init_db` function, called upon boot, executes the following command.

```sql
CREATE DATABASE IF NOT EXISTS codeserver_db;
USE codeserver_db;

CREATE TABLE IF NOT EXISTS active_clients (
    client_uuid VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    sid VARCHAR(255),
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## Server API endpoints

## Server boot configurations

## Code Cleanliness

## Choice of License
