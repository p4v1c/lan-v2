import sys
import os
import subprocess
import time
from services.base_service import BaseService
from config import WEBSERVER_PORT, PROJECT_ROOT

class ReportServerService(BaseService):
    """
    Service qui gère le cycle de vie du serveur Flask.
    """

    def __init__(self):
        super().__init__("WebServer")
        self.port = WEBSERVER_PORT
        self.script_path = PROJECT_ROOT / "WebServer" / "server.py"
        self.process = None

    def is_active(self):
        if self.process is not None and self.process.poll() is None:
            return True
        return False

    def start(self):
        if self.is_active():
            print(f"⚠️ Le serveur Web est déjà actif sur http://127.0.0.1:{self.port}")
            return

        print(f"🚀 Démarrage du serveur Web sur http://127.0.0.1:{self.port} ...")
        
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(PROJECT_ROOT)
            env["PYTHONUNBUFFERED"] = "1" 

            # Redirection vers null pour ne pas polluer le terminal
            self.process = subprocess.Popen(
                [sys.executable, str(self.script_path)],
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                cwd=str(PROJECT_ROOT),
                env=env
            )
            
            time.sleep(2)
            
            if self.is_active():
                print(f"✅ Serveur démarré.")
            else:
                print(f"❌ Échec du démarrage immédiat.")

        except Exception as e:
            print(f"❌ Erreur inattendue : {e}")

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            print("✅ Serveur Web arrêté.")
            self.process = None
            return
        print("⚠️ Aucune instance connue du serveur Web à arrêter.")
