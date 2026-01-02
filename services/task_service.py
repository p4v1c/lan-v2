import os
import signal
import subprocess
import datetime
import re
import json
import psycopg2
from pathlib import Path
from services.db_connector import get_db_connection
from config import PENTEST_CONTAINER, LOGS_DIR

class TaskService:
    def __init__(self, module_service, result_service):
        self.module_service = module_service
        self.result_service = result_service

    def get_tasks(self, tab_id):
        self.sync_tasks_status(tab_id)
        conn = get_db_connection()
        if not conn: return []
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, module_name, command_executed, status, log_file,
                       to_char(created_at,'HH24:MI:SS'), pid, target,
                       (result_content IS NOT NULL AND length(result_content) > 0) as has_db_content
                FROM scan_tasks
                WHERE tab_id=%s AND status!='result'
                ORDER BY id DESC
            """, (tab_id,))
            rows = cur.fetchall()
            conn.close()
            
            return [{
                "id": r[0], 
                "module": r[1], 
                "cmd": r[2], 
                "status": r[3],
                "log_file": "yes" if (r[4] or r[8]) else None, 
                "time": r[5], 
                "pid": r[6], 
                "target": r[7]
            } for r in rows]
        except Exception as e: 
            print(f"❌ Error GetTasks: {e}")
            if conn: conn.close()
            return []

    def add_task(self, tab_id, module_id, inputs):
        module = self.module_service.get_module(module_id)
        if not module: return {"error": "Module introuvable"}

        target = inputs.get("target") or inputs.get("ip") or inputs.get("range") or inputs.get("host") or inputs.get("dc_ip") or "Workflow"
        
        conn = get_db_connection()
        if not conn: return {"error": "DB Error"}

        try:
            cur = conn.cursor()

            # Check for existing task
            cur.execute("""
                SELECT id FROM scan_tasks 
                WHERE module_id = %s AND target = %s AND status IN ('running', 'completed', 'parsing', 'hidden')
            """, (module_id, target))
            existing_task = cur.fetchone()
            if existing_task:
                conn.close()
                return {"error": f"Ce module a déjà été lancé sur la cible '{target}'."}

            first_cmd = module.get("command", "Multi-step Workflow...")
            if "command" in module:
                for k, v in inputs.items():
                    first_cmd = first_cmd.replace(f"{{{{{k}}}}}", str(v))

            context_json = json.dumps(inputs)
            
            cur.execute("""
                INSERT INTO scan_tasks (tab_id, module_id, module_name, command_executed, target, status, current_step, context)
                VALUES (%s, %s, %s, %s, %s, 'pending', 0, %s) RETURNING id
            """, (tab_id, module_id, module["name"], first_cmd, target, context_json))
            tid = cur.fetchone()[0]
            conn.commit()
            conn.close()
            return {"task_id": tid}
        except Exception as e: 
            if conn: conn.close()
            return {"error": str(e)}

    def start_task(self, task_id):
        return self._run_step(task_id)

    def _run_step(self, task_id):
        conn = get_db_connection()
        if not conn: return {"error": "DB déconnectée"}
        
        try:
            cur = conn.cursor()
            cur.execute("SELECT module_id, current_step, context FROM scan_tasks WHERE id=%s", (task_id,))
            row = cur.fetchone()
            
            if not row: return {"error": "Tâche inconnue"}
            mod_id, step_idx, context_json = row
            context = json.loads(context_json) if context_json else {}
            
            module = self.module_service.get_module(mod_id)
            if not module: return {"error": "Module introuvable"}

            cmd_to_run = ""
            step_name = "Execution"

            if "steps" in module:
                if step_idx >= len(module["steps"]):
                    cur.execute("UPDATE scan_tasks SET status='completed' WHERE id=%s", (task_id,))
                    conn.commit()
                    conn.close()
                    self.result_service.universal_parser(task_id)
                    return {"status": "finished"}

                step = module["steps"][step_idx]
                cmd_to_run = step["command"]
                step_name = step.get("name", f"Step {step_idx+1}")
                
                if "condition" in step:
                    cond = step["condition"]
                    for k, v in context.items():
                        cond = cond.replace(f"{{{{{k}}}}}", str(v))
                    if "{{" in cond or not cond.strip(): # Condition pas prête ou vide
                        print(f"⏩ Skip étape '{step_name}'")
                        cur.execute("UPDATE scan_tasks SET current_step=current_step+1 WHERE id=%s", (task_id,))
                        conn.commit()
                        conn.close()
                        return self._run_step(task_id)
            else:
                if step_idx > 0:
                    cur.execute("UPDATE scan_tasks SET status='completed' WHERE id=%s", (task_id,))
                    conn.commit()
                    conn.close()
                    self.result_service.universal_parser(task_id)
                    return {"status": "finished"}
                cmd_to_run = module["command"]

            for k, v in context.items():
                cmd_to_run = cmd_to_run.replace(f"{{{{{k}}}}}", str(v))

            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = LOGS_DIR / f"task_{task_id}_step_{step_idx}_{ts}.log"

            gvars = self.get_global_vars()
            export_str = "".join([f'export {k}="{v}"; ' for k, v in gvars.items()])
            docker_cmd = (
                f'docker exec -w /workspace {PENTEST_CONTAINER} '
                f'zsh -c "source ~/.zshrc && {export_str} {cmd_to_run}"'
            )

            with open(log_path, "a") as f:
                f.write(f"\n--- STEP {step_idx}: {step_name} ---\n")
                f.write(f"--- CMD: {cmd_to_run} ---\n\n")
                f.flush()
                proc = subprocess.Popen(docker_cmd, shell=True, stdout=f, stderr=subprocess.STDOUT)

            cur.execute (
                """
                UPDATE scan_tasks 
                SET status='running', pid=%s, log_file=%s, command_executed=%s 
                WHERE id=%s
                """, (proc.pid, str(log_path), f"[{step_idx}] {cmd_to_run}", task_id)
            )
            
            conn.commit()
            conn.close()
            return {"status": "started"}

        except Exception as e: 
            if conn: conn.close()
            return {"error": str(e)}

    def stop_task(self, task_id):
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT pid FROM scan_tasks WHERE id=%s", (task_id,))
            row = cur.fetchone()
            if row and row[0]:
                try: os.kill(row[0], signal.SIGTERM) # type: ignore
                except: pass
            cur.execute("UPDATE scan_tasks SET status='aborted' WHERE id=%s", (task_id,))
            conn.commit()
            conn.close()
            return True
        return False

    def delete_task(self, task_id):
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT log_file FROM scan_tasks WHERE id=%s", (task_id,))
            row = cur.fetchone()
            if row and row[0] and os.path.exists(row[0]):
                try: os.remove(row[0])
                except: pass
            cur.execute("DELETE FROM scan_tasks WHERE id=%s", (task_id,))
            conn.commit()
            conn.close()
            return True
        return False

    def get_task_output(self, task_id):
        conn = get_db_connection()
        if not conn: return "DB Error"
        try:
            cur = conn.cursor()
            cur.execute("SELECT log_file, result_content FROM scan_tasks WHERE id=%s", (task_id,))
            row = cur.fetchone()
            conn.close()
            if not row: return "Tâche inconnue"
            
            log_path, content_db = row
            
            if log_path and Path(log_path).exists():
                return Path(log_path).read_text(encoding="utf-8", errors="replace")
            
            if content_db:
                return content_db
                
            return "Pas de log disponible."
        except Exception as e: 
            if conn: conn.close()
            return f"Error reading log: {e}"

    def sync_tasks_status(self, tab_id):
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            # On récupère aussi le contenu existant pour l'aggréger
            cur.execute("SELECT id, pid, module_id, current_step, context, log_file, target, result_content FROM scan_tasks WHERE tab_id=%s AND status='running'", (tab_id,))
            
            for task_id, pid, module_id, step_idx, context_json, log_file, target_ip, existing_content in cur.fetchall():
                
                if not self._check_process_alive(pid):
                    print(f"✅ Tâche {task_id} terminée. Traitement...")
                    
                    # 1. Gestion du Log (Fichier -> BDD -> Delete)
                    step_output = ""
                    if log_file and Path(log_file).exists():
                        try:
                            step_output = Path(log_file).read_text(encoding="utf-8", errors="replace")
                            os.remove(log_file)
                        except: pass

                    # Concaténation des résultats
                    if existing_content:
                        separator = "\n\n=========================\n\n"
                        updated_content = existing_content + separator + step_output
                    else:
                        updated_content = step_output


                    cur.execute("UPDATE scan_tasks SET status='parsing', result_content=%s, log_file=NULL WHERE id=%s", (updated_content, task_id))
                    conn.commit()

                    # --- COEUR DE LA CHECKLIST ---
                    try:
                        module = self.module_service.get_module(module_id)
                        
                        if module and "checklist_keys" in module and target_ip:
                            # target_ip peut être une IP ou un CIDR, on prend tel quel
                            for c_key in module["checklist_keys"]:
                                # On insère le fait que c'est FAIT (TRUE)
                                # ON CONFLICT : Si déjà fait, on met juste à jour la date
                                cur.execute (
                                    """
                                    INSERT INTO checklist_status (target, checklist_key, is_checked, updated_at)
                                    VALUES (%s, %s, TRUE, NOW())
                                    ON CONFLICT (target, checklist_key) DO UPDATE SET is_checked = TRUE, updated_at = NOW()
                                    """, (target_ip, c_key))
                            conn.commit()
                            print(f"   ☑️ Checklist mise à jour pour {target_ip} : {module['checklist_keys']}")
                    except Exception as e:
                        print(f"⚠️ Error updating checklist for task {task_id}: {e}")
                    # -----------------------------

                    # 2. Gestion Multi-step
                    context = json.loads(context_json) if context_json else {}
                    if module and "steps" in module and step_idx < len(module["steps"]):
                        step = module["steps"][step_idx]
                        if "extract" in step and step_output:
                            try:
                                for var, rgx in step["extract"].items():
                                    m = re.search(rgx, step_output)
                                    if m: context[var] = m.group(1).strip() if m.lastindex else m.group(0).strip()
                            except: pass

                    cur.execute("UPDATE scan_tasks SET context=%s, current_step=current_step+1 WHERE id=%s", (json.dumps(context), task_id))
                    conn.commit()

                    # 3. Parsing & Suite
                    try:
                        self.result_service.universal_parser(task_id)
                    except Exception as e:
                        print(f"⚠️ Error parsing task {task_id}: {e}")
                        
                    self._run_step(task_id)

            conn.commit()
            conn.close()
        except Exception as e: 
            print(f"❌ Error Sync: {e}")
            if conn: conn.close()

    def _check_process_alive(self, pid):
        if not pid: return False
        try:
            # waitpid avec WNOHANG est la solution clé pour les zombies
            pid_status, exit_code = os.waitpid(pid, os.WNOHANG)
            if pid_status == 0: return True # Toujours vivant
            else: return False # Mort et nettoyé
        except ChildProcessError:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
        except Exception:
            return False

    def get_global_vars(self):
        conn = get_db_connection()
        if not conn: return {}
        try:
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM global_vars")
            rows = cur.fetchall()
            conn.close()
            return {r[0]: r[1] for r in rows}
        except: return {}
