import datetime
import logging
from services.db_connector import get_db_connection

class NoteService:
    def __init__(self):
        self.table_initialized = False
        # On tente une première fois, mais sans insister si ça échoue
        self._init_db()

    def _init_db(self):
        """Crée la table persistent_notes si elle n'existe pas."""
        conn = get_db_connection(silent=True)
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS persistent_notes (
                        id INTEGER PRIMARY KEY,
                        content TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Initialiser la note vide (ID 1) si elle n'existe pas
                cur.execute("INSERT INTO persistent_notes (id, content) VALUES (1, '') ON CONFLICT (id) DO NOTHING;")
                conn.commit()
                cur.close()
                conn.close()
                self.table_initialized = True
                logging.info("✅ Table Notes initialisée.")
            except Exception as e:
                # On log l'erreur mais on ne crash pas, on réessaiera plus tard
                logging.error(f"⚠️ Init Table Notes reporté (DB non prête ?) : {e}")

    def _ensure_table_ready(self):
        """Si la table n'est pas marquée comme initialisée, on réessaie."""
        if not self.table_initialized:
            self._init_db()

    def get_note(self):
        """Récupère le contenu de la note unique."""
        self._ensure_table_ready()  # <--- CORRECTION IMPORTANTE
        
        conn = get_db_connection(silent=True)
        if conn is None: 
            return ""
        try:
            cur = conn.cursor()
            cur.execute("SELECT content FROM persistent_notes WHERE id = 1")
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row[0] if row else ""
        except Exception as e:
            logging.error(f"❌ Erreur lecture note : {e}")
            return ""

    def save_note(self, content):
        """Sauvegarde (Upsert) la note unique."""
        self._ensure_table_ready()  # <--- CORRECTION IMPORTANTE
        
        conn = get_db_connection(silent=True)
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO persistent_notes (id, content, updated_at) 
                    VALUES (1, %s, %s)
                    ON CONFLICT (id) DO UPDATE 
                    SET content = EXCLUDED.content, 
                        updated_at = EXCLUDED.updated_at;
                """, (content, datetime.datetime.now()))
                conn.commit()
                cur.close()
                conn.close()
                return True
            except Exception as e:
                logging.error(f"❌ Erreur sauvegarde note : {e}")
                return False
        return False
