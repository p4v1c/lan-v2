import yaml
from pathlib import Path
from config import MODULES_DIR

class ModuleService:
    def __init__(self):
        self.modules = self._load_modules()

    def _load_modules(self):
        modules = []
        if not MODULES_DIR.exists():
            return modules

        for f in MODULES_DIR.rglob("*.yaml"):
            try:
                with open(f) as yf:
                    data = yaml.safe_load(yf)
                    if data and 'id' in data:
                        if 'steps' in data:
                            data['mode'] = 'auto'
                        else:
                            data['mode'] = 'manual'
                        modules.append(data)
            except Exception:
                pass
        return modules

    def list_modules(self):
        return self.modules

    def get_module(self, module_id):
        return next((m for m in self.modules if m["id"] == module_id), None)
