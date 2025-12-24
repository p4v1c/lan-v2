from psycopg2.extras import RealDictCursor
import datetime
import logging
from services.db_connector import get_db_connection

class LoggerService:
    def __init__(self):
        self.table_initialized = False
        self._init_db()

    def _init_db(self):
        """Crée la table command_logs."""
        conn = get_db_connection(silent=True)
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS command_logs (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        command TEXT,
                        output TEXT
                    );
                """)
                conn.commit()
                cur.close()
                conn.close()
                self.table_initialized = True
                logging.info("✅ Service Logs connecté à la DB")
            except Exception as e:
                logging.error(f"❌ Erreur Init Table Logs: {e}")

    def add_log(self, command, output):
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO command_logs (timestamp, command, output) VALUES (%s, %s, %s)",
                    (datetime.datetime.now(), command, output)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"⚠️ Erreur insertion log : {e}")

    def get_all_logs(self):
        conn = get_db_connection(silent=True)
        if conn is None:
            return None

        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            query = "SELECT id, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp, command, output FROM command_logs ORDER BY id DESC"
            cur.execute(query)
            logs = cur.fetchall()
            cur.close()
            conn.close()
            return logs
        except Exception as e:
            print(f"❌ ERREUR LECTURE LOGS : {e}")
            return None
