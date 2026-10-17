<p align="center">
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png">
        <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.png">
        <img alt="Project Banner" src="assets/banner-light.png" width="400px">
    </picture>
</p>

*This project is a submission for the CBSE Class 12 Computer Science project by Faris Muhammad, Pavithra Muthukumar, and Mrinalika Rajan.*

A pure Python project using a Flask backend to host a given project folder, automatically connecting the server using tailscale. The client is then able to connect to this server by the IDE, designed in Python's Tkinter, to access the files, folders, read files, write files, create directories, and, in essense, use the server folder as if it were on the client's computer.

# Setup

```bash
git clone https://github.com/farismuhammad17/CodeServer.py
cd codeserver
pip install .
```

## Starting the server

The following command will start up the server and request for the project directory if one is not provided in the path. The program also automatically starts up tailscale, unless the `--no-tailscale` argument is passed.

```bash
python src/server.py <optional path>  <optional --no-tailscale>
```

## Using the IDE

Once the server URL is provided, it functions as a standard IDE on the client computer for a folder on the server computer.

```bash
python src/ide.py
```

# Technologies

* [Tkinter](https://docs.python.org/3/library/tkinter.html): Client GUI
* [Flask](https://flask.palletsprojects.com/en/stable/): Server backend
* [Requests](https://requests.readthedocs.io/en/latest/): API calling and parsing
* [MySQL](https://dev.mysql.com/doc/)

# To do

*The current program is purposefully written unsafe and terribly.*

* Security vulnerabilities: Invalid file accesses
    * SOLUTION: Verify all actions do NOT fall outside the `proj` folder chosen by the server when it is launched. If the access is invalid, return the appropriate error message and error code to the requesting client.
    * If left undone, a client can go through the server's files willy-nilly, even as far as to access personal files, passwords, histories, etc. Even if the client application has no option for such, a client can use cURL, or even just a browser to do so.
* Exceptions
    * Server exceptions would crash the entire structure. If the server stops, the whole program stops. Catching exceptions and returing appropriate error messages and error codes to the user is the default solution.
* Unsafe client shell
    * The client can execute literally anything. Sometimes a problem considering the shell was designed to be an interface to the entire computer.
* No use of MySQL
* Pretty bland IDE

# Acknowledgments

*To be filled later*

---

*This project is licensed under the Apache 2.0 license. See [LICENSE](./LICENSE) for more information.*
