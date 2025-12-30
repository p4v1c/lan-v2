import psycopg2
from services.db_connector import get_db_connection

class ChecklistService:
    def get_checklist_data(self):
        """
        API: Récupère la checklist groupée par catégorie + les cibles qui l'ont validée.
        """
        conn = get_db_connection()
        if not conn: return {}
        try:
            cur = conn.cursor()
            
            # Récupère l'item et la liste des cibles (array_agg) qui l'ont validé
            cur.execute("""
                SELECT d.category, d.name, d.description, d.key, 
                       array_agg(DISTINCT s.target) FILTER (WHERE s.is_checked IS TRUE) as targets_done
                FROM checklist_definitions d
                LEFT JOIN checklist_status s ON d.key = s.checklist_key
                GROUP BY d.category, d.name, d.description, d.key
                ORDER BY d.category, d.name
            """)
            
            rows = cur.fetchall()
            conn.close()

            grouped = {}
            for r in rows:
                cat, name, desc, key, targets = r
                if cat not in grouped: grouped[cat] = []
                
                grouped[cat].append({
                    "key": key,
                    "name": name,
                    "description": desc,
                    "targets": targets if targets else [] # Liste vide si personne
                })
            
            return grouped

        except Exception as e:
            print(f"Checklist Error: {e}")
            if conn: conn.close()
            return {}

    def toggle_checklist_item(self, checklist_key, target, is_checked):
        conn = get_db_connection()
        if not conn: return False
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO checklist_status (target, checklist_key, is_checked, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (target, checklist_key) DO UPDATE SET is_checked = EXCLUDED.is_checked, updated_at = NOW()
            """, (target, checklist_key, is_checked))
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error toggling checklist item: {e}")
            if conn: conn.close()
            return False

