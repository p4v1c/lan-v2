from services.database_initialization_service import DatabaseInitializationService
from services.tab_service import TabService
from services.task_service import TaskService
from services.module_service import ModuleService
from services.result_service import ResultService
from services.checklist_service import ChecklistService
from services.db_connector import get_db_connection

class ScanService:
    def __init__(self):
        self.db_init_service = DatabaseInitializationService()
        self.module_service = ModuleService()
        self.result_service = ResultService(self.module_service)
        self.task_service = TaskService(self.module_service, self.result_service)
        self.tab_service = TabService()
        self.checklist_service = ChecklistService()
        self.db_init_service.init_db()

    def get_tabs(self):
        return self.tab_service.get_tabs()

    def create_tab(self, name):
        return self.tab_service.create_tab(name)

    def rename_tab(self, tab_id, new_name):
        self.tab_service.rename_tab(tab_id, new_name)

    def delete_tab(self, tab_id):
        self.tab_service.delete_tab(tab_id)

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

    def set_global_var(self, key, value):
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO global_vars (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (key, value))
            conn.commit()
            conn.close()
            return True
        return False

    def delete_global_var(self, key):
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM global_vars WHERE key=%s", (key,))
            conn.commit()
            conn.close()
            return True
        return False

    def list_modules(self):
        return self.module_service.list_modules()

    def get_tasks(self, tab_id):
        return self.task_service.get_tasks(tab_id)

    def add_task(self, tab_id, module_id, inputs):
        return self.task_service.add_task(tab_id, module_id, inputs)

    def start_task(self, task_id):
        return self.task_service.start_task(task_id)

    def stop_task(self, task_id):
        return self.task_service.stop_task(task_id)

    def delete_task(self, task_id):
        return self.task_service.delete_task(task_id)

    def get_task_output(self, task_id):
        return self.task_service.get_task_output(task_id)

    def get_results_tree(self):
        return self.result_service.get_results_tree()

    def get_checklist_data(self):
        return self.checklist_service.get_checklist_data()