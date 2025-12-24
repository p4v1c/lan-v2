import psycopg2
import configparser
from services.db_connector import get_db_connection
from config import PROJECT_ROOT

class DatabaseInitializationService:
    def __init__(self):
        pass

    def _load_checklist_from_config(self):
        checklist = []
        config = configparser.ConfigParser()
        # To preserve case sensitivity of keys
        config.optionxform = str
        try:
            with open(PROJECT_ROOT / 'checklist.cfg') as f:
                # A bit of a hack to make it readable by configparser
                # We add a dummy section header
                config.read_string("[checklist]\n" + f.read())
            
            for key, value in config.items('checklist'):
                parts = value.split(',', 2)
                if len(parts) == 3:
                    checklist.append((key, parts[0], parts[1], parts[2]))
        except Exception as e:
            print(f"❌ Erreur de lecture de checklist.cfg: {e}")
        return checklist

    def init_db(self):
        conn = get_db_connection()
        if not conn:
            print("❌ DB inaccessible au démarrage du DatabaseInitializationService")
            return

        try:
            cur = conn.cursor()
            
            # --- TABLES STANDARD V3 ---
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scan_tabs (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS scan_tasks (
                    id SERIAL PRIMARY KEY,
                    tab_id INTEGER REFERENCES scan_tabs(id) ON DELETE CASCADE,
                    module_id TEXT,
                    module_name TEXT,
                    command_executed TEXT,
                    status TEXT DEFAULT 'pending',
                    pid INTEGER,
                    log_file TEXT,
                    result_content TEXT,
                    target TEXT,
                    current_step INTEGER DEFAULT 0,
                    context TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS hosts (
                    ip TEXT PRIMARY KEY,
                    hostname TEXT,
                    domain TEXT,
                    os_info TEXT,
                    criticality TEXT DEFAULT 'low',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS vulnerabilities (
                    id SERIAL PRIMARY KEY,
                    host_ip TEXT REFERENCES hosts(ip) ON DELETE CASCADE,
                    module_source TEXT,
                    title TEXT,
                    severity TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS global_vars (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                );
            """)

            # --- TABLES CHECKLIST ---
            cur.execute("""
                CREATE TABLE IF NOT EXISTS checklist_definitions (
                    key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS checklist_status (
                    target TEXT NOT NULL,
                    checklist_key TEXT REFERENCES checklist_definitions(key) ON DELETE CASCADE,
                    is_checked BOOLEAN DEFAULT FALSE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (target, checklist_key)
                );
            """)
            
            migrations = [
                "ALTER TABLE scan_tasks ADD COLUMN IF NOT EXISTS target TEXT",
                "ALTER TABLE scan_tasks ADD COLUMN IF NOT EXISTS current_step INTEGER DEFAULT 0",
                "ALTER TABLE scan_tasks ADD COLUMN IF NOT EXISTS context TEXT DEFAULT '{}'",
                "ALTER TABLE scan_tasks ADD COLUMN IF NOT EXISTS result_content TEXT",
                "ALTER TABLE scan_tasks ADD COLUMN IF NOT EXISTS log_file TEXT",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'"
            ]
            for query in migrations:
                try: cur.execute(query); conn.commit()
                except: conn.rollback()

            cur.execute("SELECT COUNT(*) FROM scan_tabs")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO scan_tabs (name) VALUES ('Scan 1')")
                conn.commit()

            # --- CHECKLIST DETAILLÉE (GRANULAIRE) ---
            
            detailed_checklist = self._load_checklist_from_config()

            for key, cat, name, desc in detailed_checklist:
                cur.execute("""
                    INSERT INTO checklist_definitions (key, category, name, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (key) DO NOTHING
                """, (key, cat, name, desc))
            conn.commit()

            cur.close()
            conn.close()
            print("✅ DB prête (DatabaseInitializationService V3 + Checklist Granulaire)")

        except Exception as e:
            if conn: conn.close()
            print(f"❌ Erreur Init DB DatabaseInitializationService: {e}")
