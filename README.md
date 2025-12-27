# AlgoHub

## Description
AlgoHub is a Flask-based web application designed to manage and orchestrate various pentesting modules. It leverages Docker Compose to deploy and run services, including a web dashboard, a PostgreSQL database, and a pgAdmin interface, alongside customizable pentesting containers. This platform aims to streamline the execution and reporting of security assessments.

## Features
-   **Module Orchestration**: Execute various pentesting modules defined in YAML files.
-   **Web Dashboard**: A Flask web interface for managing scans, viewing results, and configuring the environment.
-   **Database Integration**: Utilizes PostgreSQL for storing scan results, configurations, and other project data.
-   **Containerized Environment**: Services run in isolated Docker containers for consistency and ease of deployment.
-   **Customizable Pentesting Containers**: Supports specifying a custom pentesting container (e.g., Exegol) for module execution.
-   **Advanced Vulnerability Search**: A powerful search syntax to filter vulnerabilities with precision. You can combine multiple conditions using logical operators.
    -   **Syntax**: `element.<field> <operator> "<value>"`
    -   **Fields**:
        -   `ip`: The IP address of the host.
        -   `title`: The title of the vulnerability.
        -   `details`: The details of the vulnerability.
        -   `module`: The module that found the vulnerability.
        -   `severity`: The severity of the vulnerability (`Low`, `Medium`, `High`, `Critical`).
        -   `vuln`: A special field that searches in both `title` and `details`.
    -   **Operators**:
        -   `=` or `==` or `===`: Exact match (case-insensitive for text fields).
        -   `!=` or `!==`: Not equal.
        -   `~`: Contains (case-insensitive).
    -   **Logical Operators**:
        -   `&`: AND
        -   `|`: OR
    -   **Examples**:
        -   `element.ip = "192.168.1.10"`
        -   `element.title ~ "http" & element.severity = "High"`
        -   `element.vuln ~ "SQL Injection" | element.vuln ~ "XSS"`

## Prerequisites
Before running AlgoHub, ensure you have the following installed:
-   [**Docker**](https://docs.docker.com/get-docker/): Containerization platform.
-   [**Docker Compose**](https://docs.docker.com/compose/install/): Tool for defining and running multi-container Docker applications.
-   **Python 3.x**: Programming language for the AlgoHub CLI and web application.
-   **pip**: Python package installer.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/AlgoHub.git
    cd AlgoHub
    ```

2.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment variables** (optional but recommended for production):
    You can create a `.env` file in the project root or set them directly in your shell.
    ```
    FLASK_SECRET_KEY="your_flask_secret_key"
    PG_USER="your_db_user"
    PG_PASSWORD="your_db_password"
    PG_DB="your_db_name"
    PGADMIN_EMAIL="your_pgadmin_email"
    PGADMIN_PASSWORD="your_pgadmin_password"
    ```
    If not set, default values from `config.py` will be used.

## Usage

AlgoHub is controlled via the `algohub.py` command-line interface.

### Starting AlgoHub
To start all AlgoHub services, including the web dashboard, database, and a specified pentesting container:

```bash
python3 algohub.py start <pentest_container_name>
```
Replace `<pentest_container_name>` with the name of your desired pentesting container (e.g., `exegol-Lan`).

Example:
```bash
python3 algohub.py start exegol-Lan
```
This will bring up the following services:
-   AlgoHub Web Dashboard (accessible at `http://localhost:5000` by default)
-   PostgreSQL Database
-   pgAdmin (accessible at `http://localhost:8080` by default)
-   Your specified pentesting container

### Stopping AlgoHub
To stop all running AlgoHub services:

```bash
python3 algohub.py stop
```

## Configuration
The `config.py` file contains various configurable parameters for the application, such as:
-   `LOGS_DIR`: Directory for scan logs.
-   `MODULES_DIR`: Directory where pentesting module YAML files are located.
-   `FLASK_SECRET_KEY`: Secret key for Flask sessions.
-   `WEBSERVER_PORT`: Port for the AlgoHub web dashboard.
-   `PENTEST_CONTAINER`: Default pentesting container name.
-   PostgreSQL and pgAdmin container names, images, and credentials.

You can modify these values in `config.py` or override them using environment variables.

## Project Structure
-   `algohub.py`: Main CLI entry point for starting and stopping services.
-   `config.py`: Global configuration settings.
-   `requirements.txt`: Python dependencies.
-   `docker-compose.yml`: Defines the Docker services (web, db, pgadmin).
-   `modules/`: Contains YAML definitions for various pentesting modules.
-   `services/`: Python modules implementing various backend services (database, scanning, logging, etc.).
-   `WebServer/`: Contains the Flask web application code, including static assets (CSS, JS) and HTML templates.
    -   `WebServer/server.py`: Flask application entry point.
    -   `WebServer/static/`: Static files (CSS, JS).
    -   `WebServer/templates/`: HTML templates for the web dashboard.

## Common Issues

### Docker Client/Daemon API Version Mismatch

**Error Message:**
```
Error response from daemon: client version 1.52 is too new. Maximum supported API version is 1.41
```

**Explanation:**
This error occurs when your Docker client (the `docker` command in your terminal) is a newer version than your Docker daemon (the Docker server process running in the background). The client is trying to use a newer API version (e.g., 1.52) that the older daemon doesn't support (e.g., maximum supported is 1.41).

**Temporary Workaround:**
You can tell your Docker client to use an older API version by setting the `DOCKER_API_VERSION` environment variable. This will only affect your current terminal session.

```bash
export DOCKER_API_VERSION=1.41 # Replace 1.41 with the maximum supported API version from your error message
```
After setting this, try your Docker command again. For a more permanent temporary fix, add this line to your shell's configuration file (e.g., `~/.bashrc`, `~/.zshrc`).

**Permanent Solution:**
The best long-term solution is to upgrade your Docker daemon to a version that supports a newer API. This typically involves updating your Docker installation. The exact steps depend on your operating system and Docker installation method.

For most Linux distributions, you would update your `docker-ce` package. For example, on Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl restart docker
```
Ensure that `docker-compose-plugin` is installed, as AlgoHub relies on Docker Compose. After upgrading and restarting Docker, your client and daemon should be in sync.