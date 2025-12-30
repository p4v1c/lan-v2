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
            cur.execute("SELECT module_id, result_content, module_name, target FROM scan_tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
            
            def close_with_status(status):
                cur.execute("UPDATE scan_tasks SET status=%s WHERE id=%s", (status, task_id))
                conn.commit()
                if conn and not conn.closed:
                    cur.close()
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
                close_with_status('hidden')
                return

            mode = parsing.get('mode', 'line')
            ip_extract = parsing.get('ip_extract') or r"\b((?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"

            findings = []
            discovered_hosts = set()

            def is_valid_ip(s):
                if not s or not isinstance(s, str): return False
                try:
                    ipaddress.ip_address(s)
                    return True
                except ValueError:
                    return False

            db_target_is_ip = is_valid_ip(db_target)

            if mode == 'text':
                rules = parsing.get('rules', [])
                for line in log_content.splitlines():
                    if "---" in line or not line.strip(): continue
                    
                    line_ip = None
                    m_ip = re.search(ip_extract, line)
                    if m_ip:
                        ip_candidate = m_ip.group(0)
                        if is_valid_ip(ip_candidate):
                            line_ip = ip_candidate
                            discovered_hosts.add(line_ip)

                    finding_ip = line_ip or (db_target if db_target_is_ip else None)
                    if not finding_ip: continue

                    for rule in rules:
                        if re.search(rule.get('regex'), line):
                            severity = self._map_badge_to_severity(rule.get('badge', 'INFO'))
                            title = rule.get('name', 'Détection')
                            details = line.strip()[:250]
                            findings.append((finding_ip, severity, title, details))

            elif mode == 'block':
                sep = parsing.get('block_separator', '').replace('regex:', '')
                blocks = re.split(f"(?={sep})", log_content, flags=re.MULTILINE) if sep else [log_content]
                for b in blocks:
                    line_ip = None
                    m_ip = re.search(ip_extract, b)
                    if m_ip:
                        ip_candidate = m_ip.group(0)
                        if is_valid_ip(ip_candidate):
                            line_ip = ip_candidate
                            discovered_hosts.add(line_ip)

                    finding_ip = line_ip or (db_target if db_target_is_ip else None)
                    if not finding_ip: continue

                    if "open" in b: 
                        ports = re.findall(r"(\d+/tcp)\s+open\s+([\w-]+)", b)
                        if ports:
                            details = ", ".join([f"{p[0]}:{p[1]}" for p in ports])
                            findings.append((finding_ip, "INFO", "Ports Ouverts", details))

            elif mode == 'json':
                try:
                    start = log_content.find('[')
                    if start == -1: start = log_content.find('{')
                    if start != -1:
                        data = json.loads(log_content[start:])
                        if isinstance(data, dict): data = [data]
                        for entry in data:
                            entry_ip = None
                            for _, value in entry.items():
                                if isinstance(value, str):
                                    m_ip = re.search(ip_extract, value)
                                    if m_ip and is_valid_ip(m_ip.group(0)):
                                        entry_ip = m_ip.group(0)
                                        discovered_hosts.add(entry_ip)
                                        break
                            
                            finding_ip = entry_ip or (db_target if db_target_is_ip else None)
                            if not finding_ip: continue

                            for r in parsing.get('rules', []):
                                val = entry.get(r.get('condition_key'))
                                match = False
                                if r.get('check_existence') and val: match = True
                                elif r.get('condition_value') and val and str(r.get('condition_value')) in str(val): match = True
                                if match:
                                    sev = self._map_badge_to_severity(r.get('badge', 'INFO'))
                                    title = r.get('name', 'Vulnérabilité')
                                    findings.append((finding_ip, sev, title, f"Via {r.get('condition_key')}"))
                except Exception as e:
                    print(f"Error parsing JSON: {e}")

            for ip in discovered_hosts:
                cur.execute("INSERT INTO hosts (ip) VALUES (%s) ON CONFLICT (ip) DO NOTHING", (ip,))

            unique_findings = list(set(findings))
            for ip, severity, title, details in unique_findings:
                cur.execute("INSERT INTO hosts (ip) VALUES (%s) ON CONFLICT (ip) DO NOTHING", (ip,))
                
                if severity != "INFO":
                    cur.execute("SELECT id FROM vulnerabilities WHERE host_ip=%s AND title=%s", (ip, title))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO vulnerabilities (host_ip, module_source, title, severity, details)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (ip, module_name, title, severity, details))

            conn.commit()
            print(f"✅ Parsing terminé pour task {task_id} : {len(discovered_hosts)} hôtes découverts, {len(unique_findings)} résultats.")

        except (Exception, psycopg2.Error) as e:
            print(f"❌ Erreur Parsing: {e}")
            if conn: conn.rollback()
        finally:
            if conn and not conn.closed:
                close_with_status('completed')

    def get_results_tree(self):
            conn = get_db_connection()
            if not conn: return {}
            try:
                cur = conn.cursor()
                # On récupère aussi le contexte pour chercher des IPs alternatives
                cur.execute("""
                    SELECT id, module_name, target, context, to_char(created_at, 'YYYY-MM-DD HH24:MI'), 
                        (result_content IS NOT NULL AND length(result_content) > 0) as has_content
                    FROM scan_tasks 
                    WHERE target IS NOT NULL AND (status = 'completed' OR status = 'result')
                    ORDER BY created_at DESC
                """)
                rows = cur.fetchall()
                conn.close()

                tree = {}
                # Clés à vérifier dans le contexte pour trouver une IP, par ordre de priorité
                ip_keys_in_context = ['dc_ip', 'ip', 'host', 'hostname']

                for r in rows:
                    tid, mod, target, context_json, date, has_content = r
                    
                    display_target = str(target).strip()
                    
                    # Logique pour trouver la meilleure IP pour le regroupement
                    grouping_ip = None
                    potential_ips = [display_target]
                    context = json.loads(context_json) if context_json else {}
                    for key in ip_keys_in_context:
                        if key in context and context[key]:
                            potential_ips.append(str(context[key]))

                    for ip_str in potential_ips:
                        try:
                            # Test si c'est une IP valide
                            ipaddress.ip_address(ip_str)
                            grouping_ip = ip_str # C'est une IP valide, on l'utilise
                            break
                        except ValueError:
                            continue # Ce n'est pas une IP, on essaie la suivante

                    # On détermine le groupe basé sur l'IP trouvée
                    grp = "Global / Workflows" # Groupe par défaut
                    if grouping_ip:
                        try:
                            if "/" in grouping_ip:
                                ipaddress.ip_network(grouping_ip, strict=False)
                                grp = grouping_ip # C'est un CIDR
                            elif ":" in grouping_ip: 
                                grp = "IPv6"
                            else: 
                                ip_obj = ipaddress.ip_address(grouping_ip)
                                grp = str(ipaddress.ip_network(f"{ip_obj}/24", strict=False))
                        except ValueError:
                            # Si ce n'est pas une IP/CIDR valide, on laisse le groupe par défaut
                            pass

                    if grp not in tree: tree[grp] = {}
                    if display_target not in tree[grp]: tree[grp][display_target] = []
                    
                    tree[grp][display_target].append({
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

    def get_host_centric_summary(self):
        """
        Fetches and structures all vulnerability and scan data, grouped by subnet and host.
        This is the primary data source for the redesigned results page.
        """
        conn = get_db_connection()
        if not conn: return {}

        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
        
        try:
            cur = conn.cursor()
            
            # 1. Get all hosts from the dedicated 'hosts' table.
            cur.execute("SELECT ip FROM hosts")
            all_hosts_rows = cur.fetchall()
            
            # Filter for valid IPs to avoid processing errors
            all_host_ips = set()
            for row in all_hosts_rows:
                try:
                    ipaddress.ip_address(row[0])
                    all_host_ips.add(row[0])
                except ValueError:
                    pass # Ignore entries that are not valid IP addresses

            # 2. Fetch all vulnerabilities and tasks
            cur.execute("SELECT id, host_ip, title, severity, details, module_source, to_char(created_at, 'YYYY-MM-DD HH24:MI') FROM vulnerabilities")
            vuln_rows = cur.fetchall()
            
            cur.execute("SELECT id, target, module_name, to_char(created_at, 'YYYY-MM-DD HH24:MI') FROM scan_tasks WHERE status IN ('completed', 'result')")
            task_rows = cur.fetchall()
            
            conn.close()

            # 3. Initialize data structure for all valid hosts
            hosts_data = {ip: {
                "ip": ip, "vuln_count": 0, "highest_severity": "INFO",
                "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0},
                "vulnerabilities": [], "scans": []
            } for ip in all_host_ips}

            # 4. Process and map vulnerabilities
            for r in vuln_rows:
                vid, ip, title, severity, details, module, date = r
                if ip in hosts_data:
                    host = hosts_data[ip]
                    severity_norm = severity.upper()
                    
                    host["vulnerabilities"].append({
                        "id": vid, "title": title, "severity": severity_norm, 
                        "details": details, "module": module, "date": date
                    })
                    host["vuln_count"] += 1
                    
                    if severity_norm in host["severity_counts"]:
                        host["severity_counts"][severity_norm] += 1
                    
                    if severity_order.get(severity_norm, 0) > severity_order.get(host["highest_severity"], 0):
                        host["highest_severity"] = severity_norm

            # 5. Associate scans with hosts (The Fix)
            # Pre-process tasks into a more usable format
            networks_to_scan = []
            other_targets_to_scan = {}
            for tid, target, module, date in task_rows:
                if not target: continue
                scan_info = {"id": tid, "module": module, "date": date}
                if '/' in target:
                    try:
                        networks_to_scan.append((ipaddress.ip_network(target, strict=False), scan_info))
                    except ValueError: # Not a valid network, treat as a literal target
                        if target not in other_targets_to_scan: other_targets_to_scan[target] = []
                        other_targets_to_scan[target].append(scan_info)
                else:
                    if target not in other_targets_to_scan: other_targets_to_scan[target] = []
                    other_targets_to_scan[target].append(scan_info)

            # Iterate through hosts and check for matching scans
            for ip_str, host_data in hosts_data.items():
                # Check against literal targets
                if ip_str in other_targets_to_scan:
                    host_data["scans"].extend(other_targets_to_scan[ip_str])
                
                # Check against network targets
                try:
                    ip_addr = ipaddress.ip_address(ip_str)
                    for network, scan_info in networks_to_scan:
                        if ip_addr in network:
                            host_data["scans"].append(scan_info)
                except ValueError:
                    continue

            # 6. Group hosts by subnet
            subnets = {}
            for ip, data in hosts_data.items():
                try:
                    ip_obj = ipaddress.ip_address(ip)
                    network_key = "Autres"
                    if ip_obj.is_private:
                        network_key = str(ipaddress.ip_network(f"{ip}/24", strict=False))
                    elif ip_obj.is_loopback:
                        network_key = "Loopback"
                    
                    if network_key not in subnets:
                        subnets[network_key] = []
                    subnets[network_key].append(data)
                except ValueError:
                    if "Invalides" not in subnets:
                        subnets["Invalides"] = []
                    subnets["Invalides"].append(data)
            
            return subnets

        except (Exception, psycopg2.Error) as e:
            print(f"Error in get_host_centric_summary: {e}")
            return {}
        finally:
            if conn and not conn.closed: conn.close()

    def _map_badge_to_severity(self, badge):
        badge = str(badge).upper()
        if "CRITIQUE" in badge or "PWNED" in badge or "ADMIN" in badge: return "CRITIQUE"
        if "DANGER" in badge or "ELEVÉ" in badge or "GOLDEN" in badge: return "ELEVÉ"
        if "MOYEN" in badge or "RISQUE" in badge: return "MOYEN"
        return "INFO"
