from pathlib import Path
import os

# Racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent

# ======================================================
# CONFIGURATION GÉNÉRALE
# ======================================================
LOGS_DIR = PROJECT_ROOT / "scan_logs"
MODULES_DIR = PROJECT_ROOT / "modules"

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "super-secret-key-algohub-v3")

# Création des dossiers si nécessaire
LOGS_DIR.mkdir(exist_ok=True)
MODULES_DIR.mkdir(exist_ok=True)

# ======================================================
# CONFIGURATION DASHBOARD WEB
# ======================================================
WEBSERVER_PORT = 5000
GOWITNESS_PORT = 7070

# ======================================================
# CONFIGURATION PENTEST (EXEGOL)
# ======================================================
PENTEST_CONTAINER = "exegol-Lan"

# ======================================================
# CONFIGURATION DOCKER (PostgreSQL & pgAdmin)
# ======================================================
PG_CONTAINER = "postgres-container"
PGADMIN_CONTAINER = "pgadmin-container"
PG_VOLUME = "pgalgohub"
PG_IMAGE = "postgres:16"
PGADMIN_IMAGE = "dpage/pgadmin4"

# Credentials
PG_USER = os.getenv("PG_USER", "admin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "admin1234")
PG_DB = os.getenv("PG_DB", "algo")

PGADMIN_EMAIL = os.getenv("PGADMIN_EMAIL", "admin@admin.fr")
PGADMIN_PASSWORD = os.getenv("PGADMIN_PASSWORD", "admin1234")
