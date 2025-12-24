import re
import json
import ipaddress
import psycopg2
from services.db_connector import get_db_connection

class ResultService:
    def __init__(self, module_service):
        self.module_service = module_service

    def universal_parser(self, task_id):
        conn = get_db_connection()
        if not conn: return
        cur = conn.cursor()
        
        try:
            # 1. Récupération des données brutes
            cur.execute("SELECT module_id, result_content, module_name, target FROM scan_tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
            
            # Fonction utilitaire pour fermer proprement avec un statut donné
            def close_with_status(status):
                cur.execute("UPDATE scan_tasks SET status=%s WHERE id=%s", (status, task_id))
                conn.commit()
                conn.close()

            if not row or not row[1]: 
                close_with_status('completed')
                return

            module_id, log_content, module_name, db_target = row
            module_config = self.module_service.get_module(module_id)
            
            if not module_config:
                close_with_status('completed')
                return

            parsing = module_config.get('parsing', {})
            
            if parsing.get('save_results') is False:
                print(f"⏩ Tâche {task_id} ignorée des résultats (save_results: false).")
                close_with_status('hidden')
                return

            mode = parsing.get('mode', 'line')
            ip_extract = parsing.get('ip_extract') or r"\b((?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"

            findings = []

            if mode == 'text':
                rules = parsing.get('rules', [])
                for line in log_content.splitlines():
                    if "---" in line or not line.strip(): continue
                    current_ip = db_target
                    m_ip = re.search(ip_extract, line)
                    if m_ip: current_ip = m_ip.group(0)

                    for rule in rules:
                        if re.search(rule.get('regex'), line):
                            severity = self._map_badge_to_severity(rule.get('badge', 'INFO'))
                            title = rule.get('name', 'Détection')
                            details = line.strip()[:250]
                            findings.append((current_ip, severity, title, details))

            elif mode == 'block':
                sep = parsing.get('block_separator', '').replace('regex:', '')
                blocks = re.split(f"(?={sep})", log_content, flags=re.MULTILINE) if sep else [log_content]
                for b in blocks:
                    current_ip = db_target
                    m_ip = re.search(ip_extract, b)
                    if m_ip: current_ip = m_ip.group(0)
                    if "open" in b: 
                        ports = re.findall(r"(\d+/tcp)\s+open\s+([\w-]+)", b)
                        if ports:
                            details = ", ".join([f"{p[0]}:{p[1]}" for p in ports])
                            findings.append((current_ip, "INFO", "Ports Ouverts", details))

            elif mode == 'json':
                try:
                    start = log_content.find('[')
                    if start == -1: start = log_content.find('{')
                    if start != -1:
                        data = json.loads(log_content[start:])
                        if isinstance(data, dict): data = [data]
                        for entry in data:
                            current_ip = db_target
                            for r in parsing.get('rules', []):
                                val = entry.get(r.get('condition_key'))
                                match = False
                                if r.get('check_existence') and val: match = True
                                elif r.get('condition_value') and val and str(r.get('condition_value')) in str(val): match = True
                                if match:
                                    sev = self._map_badge_to_severity(r.get('badge', 'INFO'))
                                    title = r.get('name', 'Vulnérabilité')
                                    findings.append((current_ip, sev, title, f"Via {r.get('condition_key')}"))
                except: pass

            unique_findings = list(set(findings))

            for ip, severity, title, details in unique_findings:
                if "/" in ip or not ip: continue
                
                cur.execute("INSERT INTO hosts (ip) VALUES (%s) ON CONFLICT (ip) DO NOTHING", (ip,))
                
                if severity != "INFO":
                    cur.execute("SELECT id FROM vulnerabilities WHERE host_ip=%s AND title=%s AND details=%s", (ip, title, details))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO vulnerabilities (host_ip, module_source, title, severity, details)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (ip, module_name, title, severity, details))

            close_with_status('completed')
            print(f"✅ Parsing terminé pour task {task_id} : {len(unique_findings)} résultats.")

        except Exception as e:
            print(f"❌ Erreur Parsing: {e}")
            if conn: conn.rollback()
        finally:
            if conn and not conn.closed:
                cur.close()
                conn.close()

    def get_results_tree(self):
            conn = get_db_connection()
            if not conn: return {}
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, module_name, target, to_char(created_at, 'YYYY-MM-DD HH24:MI'), 
                        (result_content IS NOT NULL AND length(result_content) > 0) as has_content
                    FROM scan_tasks 
                    WHERE target IS NOT NULL AND (status = 'completed' OR status = 'result')
                    ORDER BY created_at DESC
                """)
                rows = cur.fetchall()
                conn.close()

                tree = {}
                for r in rows:
                    tid, mod, target, date, has_content = r
                    target = str(target).strip()
                    
                    grp = "Autres"
                    try:
                        if "/" in target:
                            ipaddress.ip_network(target, strict=False)
                            grp = target
                        elif ":" in target: 
                            grp = "IPv6"
                        else: 
                            ip_obj = ipaddress.ip_address(target)
                            grp = str(ipaddress.ip_network(f"{ip_obj}/24", strict=False))
                    except: 
                        grp = "Global / Workflows"
                    
                    if grp not in tree: tree[grp] = {}
                    if target not in tree[grp]: tree[grp][target] = []
                    
                    tree[grp][target].append({
                        "id": tid,
                        "module": mod,
                        "date": date,
                        "has_log": has_content,
                        "is_vuln": False
                    })
                return tree
            except Exception as e: 
                print(f"Tree Error: {e}")
                return {}

    def _map_badge_to_severity(self, badge):
        badge = str(badge).upper()
        if "CRITIQUE" in badge or "PWNED" in badge or "ADMIN" in badge: return "CRITIQUE"
        if "DANGER" in badge or "ELEVÉ" in badge or "GOLDEN" in badge: return "ELEVÉ"
        if "MOYEN" in badge or "RISQUE" in badge: return "MOYEN"
        return "INFO"
