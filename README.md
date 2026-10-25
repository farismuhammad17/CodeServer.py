<p align="center">
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/banner/dark.png">
        <source media="(prefers-color-scheme: light)" srcset="assets/banner/light.png">
        <img alt="Project Banner" src="assets/banner/light.png" width="400px">
    </picture>
</p>

*This project is a submission for the CBSE Class 12 Computer Science project by Faris Muhammad, Pavithra Muthukumar, and Mrinalika Rajan.*

A pure Python project using a Flask backend to host a given project folder, automatically connecting the server using tailscale. The client is then able to connect to this server by the IDE, designed in Python's Tkinter, to access the files, folders, read files, write files, create directories, and, in essense, use the server folder as if it were on the client's computer.

Each client is treated as a "user" stored inside a MySQL database. Changes by one user is reflected to other users on the same project connection.

<table>
    <tr>
        <td align="center">
            <img src="assets/demo-connecting.png" width="400" alt="Connection demo"><br>
            <sub><b>Figure 1:</b> Connecting to a server</sub>
        </td>
        <td align="center">
            <img src="assets/demo-project.png" width="400" alt="A project file"><br>
            <sub><b>Figure 2:</b> Accessing a file (server.py)</sub>
        </td>
    </tr>
</table>

# Setup

```bash
git clone https://github.com/farismuhammad17/CodeServer.py
cd CodeServer.py
pip install .
```

## Starting the server

The following command will start up the server and request for the project directory if one is not provided in the path. The program also automatically starts up tailscale, unless the `--no-tailscale` argument is passed.

```bash
python src/server.py <optional path> <optional --no-tailscale>
```

## Using the IDE

Once the server URL is provided, it functions as a standard IDE on the client computer for a folder on the server computer.

```bash
python src/ide.py
```

# Technologies

* [Tailscale](https://tailscale.com/): Bridging server to WAN
* [Tkinter](https://docs.python.org/3/library/tkinter.html): Client GUI
* [Flask](https://flask.palletsprojects.com/en/stable/): Server backend
* [Flask-SocketIO](https://flask-socketio.readthedocs.io/en/latest/): Server Websocket engine
* [Requests](https://requests.readthedocs.io/en/latest/): API calling and parsing
* [python-socketio](https://python-socketio.readthedocs.io/en/stable/): Client WebSocket engine
* [MySQL](https://dev.mysql.com/doc/): User tracking
* [mysql-connector-python](https://pypi.org/project/mysql-connector-python/): The database driver managing persistent client tracking.
* [python-dotenv](https://pypi.org/project/python-dotenv/): Secure server configuration environment.

# Todo

* IDE was written mostly by LLMs. Should fix any minor code inconveniences.
* Use the IDE terminal as client-server logs for communication ease.
    * Connection phase
    * User joining/leaving
    * etc.
* A password request when connecting to a server. Also requires that the server password be put inside the `.env` file.

# Acknowledgments

*To be filled later*

---

*This project is licensed under the Apache 2.0 license. See [LICENSE](./LICENSE) for more information.*
