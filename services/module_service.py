import yaml
from pathlib import Path
from config import MODULES_DIR

class ModuleService:
    def __init__(self):
        # Les modules sont maintenant chargés à la demande pour refléter les changements en temps réel.
        pass

    def _load_modules(self):
        modules = []
        if not MODULES_DIR.exists():
            return modules

        for f in MODULES_DIR.rglob("*.yaml"):
            try:
                with open(f, 'r', encoding='utf-8') as yf:
                    data = yaml.safe_load(yf)
                    if data and 'id' in data:
                        if 'steps' in data:
                            data['mode'] = 'auto'
                        else:
                            data['mode'] = 'manual'
                        modules.append(data)
            except Exception as e:
                # Il est préférable de logger l'erreur pour le débogage
                print(f"Erreur lors du chargement du module {f.name}: {e}")
        return modules

    def list_modules(self):
        """Charge et retourne la liste à jour des modules."""
        return self._load_modules()

    def get_module(self, module_id):
        """Charge les modules et retourne celui qui correspond à l'ID."""
        modules = self._load_modules()
        return next((m for m in modules if m["id"] == module_id), None)
