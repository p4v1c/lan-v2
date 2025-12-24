import psycopg2
from services.db_connector import get_db_connection

class TabService:
    def get_tabs(self):
        conn = get_db_connection()
        if not conn: return []
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM scan_tabs ORDER BY id")
            rows = cur.fetchall()
            conn.close()
            return [{"id": r[0], "name": r[1]} for r in rows]
        except: return []

    def create_tab(self, name):
        if not name or not name.strip(): name = "Scan"
        conn = get_db_connection()
        if not conn: return None
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO scan_tabs (name) VALUES (%s) RETURNING id", (name,))
            tid = cur.fetchone()[0]
            conn.commit()
            conn.close()
            return tid
        except: return None

    def rename_tab(self, tab_id, new_name):
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("UPDATE scan_tabs SET name=%s WHERE id=%s", (new_name, tab_id))
            conn.commit()
            conn.close()

    def delete_tab(self, tab_id):
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM scan_tabs WHERE id=%s", (tab_id,))
            conn.commit()
            conn.close()
