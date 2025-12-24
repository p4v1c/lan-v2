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
