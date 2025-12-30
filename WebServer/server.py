import sys
import os
import logging
import re
import subprocess
from collections import deque
from pathlib import Path
import io
import csv
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# =========================================================
# 1. CONFIGURATION
# =========================================================
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
sys.path.append(str(PROJECT_ROOT))

from config import WEBSERVER_PORT, PENTEST_CONTAINER, FLASK_SECRET_KEY, MODULES_DIR
from services.db_connector import get_db_connection

# =========================================================
# 2. INIT FLASK & LOGIN
# =========================================================
TEMPLATE_DIR = CURRENT_DIR / 'templates'
STATIC_DIR = CURRENT_DIR / 'static'

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
app.secret_key = FLASK_SECRET_KEY

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirection si non authentifié

# --- VARIABLES WEBSHELL ---
CONTAINER_NAME = PENTEST_CONTAINER 
CONTAINER_WORKDIR = "/workspace"

# --- LOGS FLASK ---
LOG_BUFFER = deque(maxlen=500)
class InMemoryHandler(logging.Handler):
    def emit(self, record):
        try:
            LOG_BUFFER.append(self.format(record))
        except Exception:
            self.handleError(record)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
memory_handler = InMemoryHandler()
memory_handler.setFormatter(formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(memory_handler)

# =========================================================
# 3. SERVICES
# =========================================================
from services.logger_service import LoggerService
from services.note_service import NoteService
from services.scan_service import ScanService
from services.database_service import DatabaseService
from services.tools_service import ToolsService

logging.info("⏳ Initialisation des services...")
db_logger = LoggerService()
note_service = NoteService()
scan_service = ScanService()
db_service = DatabaseService()
tools_service = ToolsService()

# =========================================================
# 4. GESTION UTILISATEURS (Auth)
# =========================================================
class User(UserMixin):
    def __init__(self, id, username, password_hash, role='user'):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role # Nouveau champ

    @property
    def is_admin(self):
        return self.role == 'admin'

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection(silent=True)
    if not conn: return None
    cur = conn.cursor()
    # On récupère aussi le role
    cur.execute("SELECT id, username, password, role FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        # row[3] est le rôle
        return User(id=row[0], username=row[1], password_hash=row[2], role=row[3])
    return None

def init_default_user():
    """Crée l'admin par défaut et s'assure qu'il a le bon rôle."""
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        # Vérifier si la table existe
        cur.execute("SELECT to_regclass('public.users')")
        if cur.fetchone()[0]:
            # 1. Création si vide
            cur.execute("SELECT COUNT(*) FROM users")
            if cur.fetchone()[0] == 0:
                p_hash = generate_password_hash("admin")
                # On force le rôle admin
                cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'admin')", ("admin", p_hash))
                conn.commit()
                logging.info("👤 Compte 'admin' créé par défaut.")
            
            # 2. Mise à jour de sécurité : Assurer que l'user 'admin' est bien rôle 'admin'
            # (Cas où la migration s'est faite après la création du user)
            cur.execute("UPDATE users SET role='admin' WHERE username='admin' AND role!='admin'")
            conn.commit()

    except Exception as e:
        print(f"Auth Init Error: {e}")
    finally:
        cur.close()
        conn.close()

# On lance l'init user au démarrage
init_default_user()

# =========================================================
# 5. ROUTES AUTHENTIFICATION
# =========================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password, role FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row and check_password_hash(row[2], password):
            user = User(id=row[0], username=row[1], password_hash=row[2])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants invalides', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# =========================================================
# 6. ROUTES PAGES (PROTÉGÉES)
# =========================================================
@app.route('/')
@login_required
def dashboard(): return render_template('dashboard.html', active_page='scan')

@app.route('/result')
@login_required
def result(): return render_template('result.html', active_page='result')

@app.route('/note')
@login_required
def note(): return render_template('note.html', active_page='note')

@app.route('/logs')
@login_required
def logs(): return render_template('logs.html', active_page='logs')

@app.route('/vulns')
@login_required
def vulns_page():
    return render_template('vulns.html', active_page='vulns')

# =========================================================
# 7. API SCANNER (PROTÉGÉES)
# =========================================================
@app.route('/api/modules', methods=['GET'])
@login_required
def list_modules(): return jsonify(scan_service.list_modules())

@app.route('/api/tabs', methods=['GET'])
@login_required
def list_tabs(): return jsonify(scan_service.get_tabs())

@app.route('/api/tabs', methods=['POST'])
@login_required
def add_tab():
    data = request.json
    tid = scan_service.create_tab(data.get('name', 'Nouveau Scan'))
    return jsonify({'id': tid})

@app.route('/api/tabs/<int:tid>', methods=['PUT'])
@login_required
def update_tab(tid):
    data = request.json
    scan_service.rename_tab(tid, data.get('name'))
    return jsonify({'status': 'ok'})

@app.route('/api/tabs/<int:tid>', methods=['DELETE'])
@login_required
def del_tab(tid):
    scan_service.delete_tab(tid)
    return jsonify({'status': 'ok'})

@app.route('/api/tabs/<int:tid>/tasks', methods=['GET'])
@login_required
def list_tasks(tid): return jsonify(scan_service.get_tasks(tid))

@app.route('/api/tasks/add', methods=['POST'])
@login_required
def add_task_api():
    data = request.json
    res = scan_service.add_task(data['tab_id'], data['module_id'], data['inputs'])
    return jsonify(res)

@app.route('/api/tasks/<int:task_id>/start', methods=['POST'])
@login_required
def start_task_api(task_id): return jsonify(scan_service.start_task(task_id))

@app.route('/checklist')
@login_required
def checklist_page():
    # Affiche la page HTML
    return render_template('checklist.html', active_page='checklist')

@app.route('/api/checklist', methods=['GET'])
@login_required
def get_checklist_api():
    # Renvoie le JSON des données
    return jsonify(scan_service.get_checklist_data())

@app.route('/api/checklist/toggle', methods=['POST'])
@login_required
def toggle_checklist_api():
    data = request.json
    checklist_key = data.get('key')
    target = data.get('target')
    is_checked = data.get('is_checked')

    if not checklist_key or not target:
        return jsonify({'error': 'Missing key or target'}), 400
    
    # Ensure is_checked is a boolean
    if not isinstance(is_checked, bool):
        return jsonify({'error': 'is_checked must be a boolean'}), 400

    success = scan_service.checklist_service.toggle_checklist_item(checklist_key, target, is_checked)
    if success:
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'error': 'Failed to toggle checklist item'}), 500

@app.route('/api/tasks/<int:task_id>/stop', methods=['POST'])
@login_required
def stop_task_api(task_id):
    scan_service.stop_task(task_id)
    return jsonify({'status': 'stopped'})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task_api(task_id):
    scan_service.delete_task(task_id)
    return jsonify({'status': 'deleted'})

@app.route('/api/tasks/<int:task_id>/output', methods=['GET'])
@login_required
def get_task_output_api(task_id):
    # Cette route est utilisée pour le suivi temps réel et les logs bruts
    return jsonify({'output': scan_service.get_task_output(task_id)})

# --- API RESULTATS (ARBRE & DOWNLOAD) ---
@app.route('/api/results/tree', methods=['GET'])
@login_required
def get_results_tree():
    return jsonify(scan_service.get_results_tree())

@app.route('/api/results/host-summary', methods=['GET'])
@login_required
def get_host_centric_summary():
    return jsonify(scan_service.get_host_centric_summary())

@app.route('/api/results/download/<int:task_id>', methods=['GET'])
@login_required
def download_log(task_id):
    # On récupère le chemin via le service
    conn = get_db_connection(silent=True)
    cur = conn.cursor()
    cur.execute("SELECT log_file FROM scan_tasks WHERE id = %s", (task_id,))
    row = cur.fetchone()
    conn.close()
    
    if row and row[0] and os.path.exists(row[0]):
        return send_file(row[0], as_attachment=True, download_name=os.path.basename(row[0]))
    return "Fichier non trouvé (Probablement nettoyé après parsing)", 404

# --- API VARIABLES GLOBALES ---
@app.route('/api/vars', methods=['GET'])
@login_required
def get_vars(): return jsonify(scan_service.get_global_vars())

@app.route('/api/vars', methods=['POST'])
@login_required
def set_var():
    data = request.json
    scan_service.set_global_var(data['key'], data['value'])
    return jsonify({'status': 'ok'})

@app.route('/api/vars/<key>', methods=['DELETE'])
@login_required
def delete_var(key):
    scan_service.delete_global_var(key)
    return jsonify({'status': 'ok'})

# =========================================================
# 8. API VULNERABILITES (SEARCH & DETAILS) - NOUVEAU
# =========================================================

# API de recherche globale (pour vulns.html)
@app.route('/api/vulns/search', methods=['GET'])
@login_required
def search_vulns():
    query_text = request.args.get('q', '').strip()
    severity_filter = request.args.get('severity', 'All')

    conn = get_db_connection(silent=True)
    if not conn:
        return jsonify({'error': 'DB Error'}), 500

    try:
        cur = conn.cursor()
        
        sql = """
            SELECT id, host_ip, title, severity, module_source, details, 
                   to_char(created_at, 'YYYY-MM-DD HH24:MI') as date
            FROM vulnerabilities 
        """
        params = []
        where_conditions = []

        if severity_filter != 'All':
            where_conditions.append("severity = %s")
            params.append(severity_filter)

        # Si la nouvelle syntaxe de recherche est utilisée
        if 'element.' in query_text:
            field_map = {
                "ip": "host_ip", "title": "title", "details": "details",
                "module": "module_source", "severity": "severity", "vuln": None
            }
            expr_pattern = re.compile(r'element\.(\w+)\s*([=~!]+)\s*"([^"]*)"', re.IGNORECASE)
            
            processed_query = query_text.replace('&', ' AND ').replace('|', ' OR ')
            tokens = re.split(r' (AND|OR) ', processed_query)
            
            query_parts = []
            query_params = []

            for token in tokens:
                token = token.strip()
                if not token: continue
                
                if token.upper() in ["AND", "OR"]:
                    query_parts.append(token.upper())
                else:
                    match = expr_pattern.match(token)
                    if not match:
                        return jsonify({'error': f'Expression invalide : {token}'}), 400
                    
                    field, op, value = match.groups()
                    field = field.lower()

                    if field not in field_map:
                        return jsonify({'error': f'Champ invalide : {field}'}), 400
                    
                    if field == 'vuln':
                        if op == '~':
                            query_parts.append("(title ILIKE %s OR details ILIKE %s)")
                            query_params.extend([f"%{value}%", f"%{value}%"])
                        elif op in ['=', '==', '===']:
                            query_parts.append("(title = %s OR details = %s)")
                            query_params.extend([value, value])
                        elif op in ['!=', '!==']:
                            query_parts.append("(title != %s AND details != %s)")
                            query_params.extend([value, value])
                        else:
                            return jsonify({'error': f'Opérateur non supporté pour "vuln": {op}'}), 400
                        continue

                    db_field = field_map[field]
                    
                    if op == '~':
                        sql_op = "ILIKE"
                        param_value = f"%{value}%"
                    elif op in ['=', '==', '===']:
                        sql_op = "ILIKE" if db_field in ['title', 'details', 'module_source'] else "="
                        param_value = value
                    elif op in ['!=', '!==']:
                        sql_op = "NOT ILIKE" if db_field in ['title', 'details', 'module_source'] else "!="
                        param_value = value
                    else:
                        return jsonify({'error': f'Opérateur non supporté : {op}'}), 400
                    
                    query_parts.append(f"{db_field} {sql_op} %s")
                    query_params.append(param_value)
            
            if query_parts:
                where_conditions.append("(" + " ".join(query_parts) + ")")
                params.extend(query_params)

        # Ancien mode de recherche pour les requêtes simples
        elif query_text:
            where_conditions.append("""(
                host_ip ILIKE %s OR 
                title ILIKE %s OR 
                details ILIKE %s OR 
                module_source ILIKE %s
            )""")
            wildcard = f"%{query_text}%"
            params.extend([wildcard, wildcard, wildcard, wildcard])

        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)

        sql += " ORDER BY created_at DESC LIMIT 100"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        
        results = []
        for r in rows:
            results.append({
                "id": r[0], "ip": r[1], "title": r[2], "severity": r[3],
                "module": r[4], "details": r[5], "date": r[6]
            })

        return jsonify(results)

    except Exception as e:
        logging.error(f"❌ Erreur Search Vulns: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

# API pour récupérer les détails d'une vulnérabilité spécifique (pour l'onglet Result)
@app.route('/api/vulns/<int:vuln_id>/details', methods=['GET'])
@login_required
def get_vuln_details(vuln_id):
    conn = get_db_connection(silent=True)
    if not conn: return jsonify({'output': 'DB Error'})
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT details FROM vulnerabilities WHERE id = %s", (vuln_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return jsonify({'output': row[0]})
        return jsonify({'output': 'Détails introuvables.'})
    except Exception as e:
        return jsonify({'output': f'Erreur lecture détail: {e}'})

@app.route('/api/vulns/export/csv', methods=['GET'])
@login_required
def export_vulns_csv():
    """Exporte les vulnérabilités filtrées au format CSV."""
    query_text = request.args.get('q', '').strip()
    severity_filter = request.args.get('severity', 'All')

    conn = get_db_connection(silent=True)
    if not conn:
        return "Database connection error", 500

    try:
        cur = conn.cursor()
        
        sql = "SELECT host_ip, severity, title, details, module_source, to_char(created_at, 'YYYY-MM-DD HH24:MI') FROM vulnerabilities"
        params = []
        where_conditions = []

        if severity_filter != 'All':
            where_conditions.append("severity = %s")
            params.append(severity_filter)

        if 'element.' in query_text:
            field_map = {
                "ip": "host_ip", "title": "title", "details": "details",
                "module": "module_source", "severity": "severity", "vuln": None
            }
            expr_pattern = re.compile(r'element\.(\w+)\s*([=~!]+)\s*"([^"]*)"', re.IGNORECASE)
            processed_query = query_text.replace('&', ' AND ').replace('|', ' OR ')
            tokens = re.split(r' (AND|OR) ', processed_query)
            
            query_parts = []
            query_params = []

            for token in tokens:
                token = token.strip()
                if not token: continue
                
                if token.upper() in ["AND", "OR"]:
                    query_parts.append(token.upper())
                else:
                    match = expr_pattern.match(token)
                    if not match: continue
                    
                    field, op, value = match.groups()
                    field = field.lower()

                    if field not in field_map: continue
                    
                    if field == 'vuln':
                        if op == '~':
                            query_parts.append("(title ILIKE %s OR details ILIKE %s)")
                            query_params.extend([f"%{value}%", f"%{value}%"])
                        elif op in ['=', '==', '===']:
                            query_parts.append("(title = %s OR details = %s)")
                            query_params.extend([value, value])
                        elif op in ['!=', '!==']:
                            query_parts.append("(title != %s AND details != %s)")
                            query_params.extend([value, value])
                    else:
                        db_field = field_map[field]
                        if op == '~':
                            sql_op, param_value = "ILIKE", f"%{value}%"
                        elif op in ['=', '==', '===']:
                            sql_op, param_value = ("ILIKE", value) if db_field in ['title', 'details', 'module_source'] else ("=", value)
                        elif op in ['!=', '!==']:
                            sql_op, param_value = ("NOT ILIKE", value) if db_field in ['title', 'details', 'module_source'] else ("!=", value)
                        else: continue
                        query_parts.append(f"{db_field} {sql_op} %s")
                        query_params.append(param_value)
            
            if query_parts:
                where_conditions.append("(" + " ".join(query_parts) + ")")
                params.extend(query_params)

        elif query_text:
            where_conditions.append("(host_ip ILIKE %s OR title ILIKE %s OR details ILIKE %s OR module_source ILIKE %s)")
            wildcard = f"%{query_text}%"
            params.extend([wildcard, wildcard, wildcard, wildcard])

        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
        sql += " ORDER BY severity, host_ip"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['IP', 'Severity', 'Title', 'Details', 'Source Module', 'Date'])
        writer.writerows(rows)
        
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=vulnerabilities.csv"
        response.headers["Content-type"] = "text/csv"
        
        return response

    except Exception as e:
        logging.error(f"❌ Erreur Export CSV: {e}")
        return "Error generating CSV", 500
    finally:
        if conn: conn.close()


# =========================================================
# 9. API NOTES & LOGS (PROTÉGÉES)
# =========================================================
@app.route('/api/note', methods=['GET'])
@login_required
def get_note_content(): return jsonify({'content': note_service.get_note()})

@app.route('/api/note', methods=['POST'])
@login_required
def save_note_content():
    data = request.json
    success = note_service.save_note(data.get('content', ''))
    if success: return jsonify({'status': 'saved'})
    return jsonify({'error': 'db_error'}), 500

@app.route('/api/logs_history', methods=['GET'])
@login_required
def get_logs_history():
    history = db_logger.get_all_logs()
    if history is None: return jsonify({'error': 'db_down'}), 503
    return jsonify(history)

# =========================================================
# 10. API WEBSHELL (TRÈS PROTÉGÉE)
# =========================================================
@app.route('/api/shell', methods=['POST'])
@login_required
def shell_command():
    global CONTAINER_WORKDIR
    data = request.json
    user_cmd = data.get('cmd')
    
    if not user_cmd: return jsonify({'output': ''})

    if user_cmd.strip().startswith('cd '):
        try:
            target_dir = user_cmd.split(' ', 1)[1].strip()
            if target_dir == "" or target_dir == "~":
                CONTAINER_WORKDIR = "/workspace"
                output_txt = f'Directory changed to {CONTAINER_WORKDIR}'
            else:
                resolve_cmd = f'docker exec -w {CONTAINER_WORKDIR} {CONTAINER_NAME} sh -c "cd {target_dir} && pwd"'
                process = subprocess.Popen(resolve_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                if process.returncode == 0:
                    CONTAINER_WORKDIR = stdout.strip()
                    output_txt = f'Directory changed to {CONTAINER_WORKDIR}'
                else:
                    output_txt = f'Error: {stderr.strip()}'
            db_logger.add_log(user_cmd, output_txt)
            return jsonify({'output': output_txt})
        except Exception as e:
            return jsonify({'output': str(e)})

    try:
        g_vars = scan_service.get_global_vars()
        export_str = ""
        for k, v in g_vars.items():
            safe_val = v.replace('"', '\\"').replace('$', '\\$')
            export_str += f'export {k}="{safe_val}"; '

        safe_user_cmd = user_cmd.replace('"', '\\"').replace('$', '\\$')
        
        full_docker_cmd = (
            f'docker exec -w {CONTAINER_WORKDIR} {CONTAINER_NAME} '
            f'zsh -c "setopt aliases && source ~/.zshrc && {export_str} eval \\"{safe_user_cmd}\\""'
        )
        process = subprocess.Popen(full_docker_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        stdout, _ = process.communicate()
        final_output = stdout if stdout else ' '
        db_logger.add_log(user_cmd, final_output)
        return jsonify({'output': final_output})
    except Exception as e:
        return jsonify({'output': str(e)})

# =========================================================
# 11. ADMINISTRATION (Routes Admin)
# =========================================================
@app.route('/admin')
@login_required
def admin_panel():
    # Vérification du rôle
    if not current_user.is_admin:
        flash("⛔ Accès interdit : Réservé aux administrateurs.", "error")
        return redirect(url_for('dashboard'))

    conn = get_db_connection(silent=True)
    if not conn: return "Erreur DB"
    
    cur = conn.cursor()
    
    # Récupérer les utilisateurs
    cur.execute("SELECT id, username, role FROM users ORDER BY id")
    users = cur.fetchall()
    
    # Récupérer les statistiques
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scan_tasks")
    scan_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM vulnerabilities")
    vuln_count = cur.fetchone()[0]
    
    conn.close()
    
    stats = {
        'users': user_count,
        'scans': scan_count,
        'vulns': vuln_count
    }

    tools_status = tools_service.get_status_text()
    
    return render_template('admin.html', users=users, stats=stats, active_page='admin', tools_status=tools_status)

@app.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    
    if not username or not password:
        flash("Champs manquants", "error")
        return redirect(url_for('admin_panel'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        p_hash = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, p_hash, role))
        conn.commit()
        conn.close()
        flash(f"Utilisateur {username} créé !", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/reset_password', methods=['POST'])
@login_required
def reset_password():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password')
    
    if not new_password:
        flash("Mot de passe vide interdit", "error")
        return redirect(url_for('admin_panel'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        p_hash = generate_password_hash(new_password)
        cur.execute("UPDATE users SET password=%s WHERE id=%s", (p_hash, user_id))
        conn.commit()
        conn.close()
        flash("Mot de passe mis à jour.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")

    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    # Sécurité : ne pas se supprimer soi-même
    if user_id == current_user.id:
        flash("Impossible de supprimer son propre compte.", "error")
        return redirect(url_for('admin_panel'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        conn.close()
        flash("Utilisateur supprimé.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")

    return redirect(url_for('admin_panel'))


@app.route('/admin/reset_db', methods=['POST'])
@login_required
def reset_db():
    if not current_user.is_admin:
        flash("⛔ Accès interdit : Réservé aux administrateurs.", "error")
        return redirect(url_for('dashboard'))

    success, message = db_service.reset_db()
    if success:
        flash(message, "success")
        # Ré-authentifier l'admin après le reset
        user = load_user(current_user.id)
        if user:
            login_user(user)
    else:
        flash(message, "error")

    return redirect(url_for('admin_panel'))

# =========================================================
# 12. EDITOR (Gestion des Modules YAML)
# =========================================================

def _is_safe_path(filename):
    """Vérifie que le fichier reste bien dans le dossier MODULES_DIR."""
    try:
        # On force l'extension .yaml si elle n'est pas présente pour éviter d'éditer autre chose
        if not filename.endswith('.yaml'):
            return False, None
        
        base_dir = MODULES_DIR.resolve()
        # Le chemin de la cible est résolu pour éviter les attaques par traversée de répertoire (../)
        target_path = (base_dir / filename).resolve()
        
        # is_relative_to est une méthode sûre (Python 3.9+) pour vérifier que le chemin cible
        # est bien un sous-élément du répertoire de base.
        if target_path.is_relative_to(base_dir) and target_path != base_dir:
            return True, target_path
            
        return False, None
    except Exception:
        return False, None

@app.route('/editor')
@login_required
def editor():
    return render_template('editor.html', active_page='editor')

@app.route('/api/editor/list', methods=['GET'])
@login_required
def list_editor_files():
    files = []
    if MODULES_DIR.exists():
        # On liste les fichiers .yaml triés par nom
        files = sorted([f.name for f in MODULES_DIR.glob('*.yaml')])
    return jsonify(files)

@app.route('/api/editor/load', methods=['GET'])
@login_required
def load_editor_file():
    filename = request.args.get('file')
    if not filename: return jsonify({'error': 'Nom de fichier manquant'}), 400
    
    safe, path = _is_safe_path(filename)
    if not safe or not path.exists():
        return jsonify({'error': 'Fichier invalide ou introuvable'}), 404
        
    try:
        content = path.read_text(encoding='utf-8')
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/editor/save', methods=['POST'])
@login_required
def save_editor_file():
    data = request.json
    filename = data.get('filename')
    content = data.get('content')
    
    if not filename: return jsonify({'error': 'Nom de fichier manquant'}), 400
    
    # Sécurité : on force .yaml si l'utilisateur l'a oublié
    if not filename.endswith('.yaml'):
        filename += '.yaml'

    safe, path = _is_safe_path(filename)
    if not safe:
        return jsonify({'error': 'Chemin de fichier interdit'}), 403
        
    try:
        # Écriture du fichier
        path.write_text(content, encoding='utf-8')
        return jsonify({'status': 'saved', 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/editor/delete', methods=['DELETE'])
@login_required
def delete_editor_file():
    filename = request.args.get('file')
    safe, path = _is_safe_path(filename)
    
    if not safe or not path.exists():
        return jsonify({'error': 'Fichier introuvable'}), 404
        
    try:
        os.remove(path)
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =========================================================
# 13. API TOOLS (Admin)
# =========================================================
@app.route('/api/tools/start', methods=['POST'])
@login_required
def start_tools():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    tools_service.start()
    return jsonify({"status": "starting"})

@app.route('/api/tools/stop', methods=['POST'])
@login_required
def stop_tools():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    tools_service.stop()
    return jsonify({"status": "stopping"})

if __name__ == '__main__':
    logging.info(f"🚀 Serveur Web démarré sur le port {WEBSERVER_PORT}")
    app.run(debug=False, host='0.0.0.0', port=WEBSERVER_PORT)