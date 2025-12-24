import subprocess
import time
from services.base_service import BaseService
from config import PENTEST_CONTAINER, GOWITNESS_PORT


class ToolsService(BaseService):
    """
    Pilotage des outils (Neo4j, GoWitness, BloodHound CE)
    Adapté de la V2 pour fonctionner via docker exec
    """

    def __init__(self):
        super().__init__("Analysis Tools")

        self.NEO4J_PORT = 7474
        self.GOWITNESS_PORT = GOWITNESS_PORT
        
        # Nouveau : Port pour BloodHound CE (Exegol l'expose sur le 1030)
        self.BLOODHOUND_PORT = 1030

        # BloodHound CE Bin path
        self.BLOODHOUND_BIN = "/opt/tools/bin/bloodhound-ce"

        # Java utilisé par Neo4j (config V2)
        self.JAVA_HOME_V2 = "/usr/lib/jvm/java-11-openjdk"

    # ------------------------------------------------------------------
    # Docker exec helper
    # ------------------------------------------------------------------
    def _exec(self, cmd, detach=False):
        """
        Exécute une commande dans le conteneur Exegol
        """
        wrapped_cmd = f"source ~/.zshrc && {cmd}"
        safe_cmd = wrapped_cmd.replace('"', '\\"')

        flags = "-d" if detach else ""
        full_cmd = f'docker exec {flags} {PENTEST_CONTAINER} zsh -c "{safe_cmd}"'

        return subprocess.run(
            full_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    # ------------------------------------------------------------------
    # Generic checks
    # ------------------------------------------------------------------
    def _check_process(self, pattern):
        """
        Vérifie la présence d'un processus via pgrep
        """
        res = self._exec(f"pgrep -f '{pattern}'")
        return res.returncode == 0

    def _check_port(self, port):
        """
        Vérifie si un port est en écoute via ss
        """
        res = self._exec(f"ss -lntH | grep ':{port} '")
        return res.returncode == 0 and bool(res.stdout.strip())

    # ------------------------------------------------------------------
    # BloodHound detection (Via PORT 1030)
    # ------------------------------------------------------------------
    def _check_bloodhound(self):
        """
        Détection de BloodHound CE via son port d'écoute (1030)
        """
        return self._check_port(self.BLOODHOUND_PORT)

    # ------------------------------------------------------------------
    # Service status
    # ------------------------------------------------------------------
    def is_active(self):
        """
        La stack est considérée active si Neo4j est up
        """
        return self._check_port(self.NEO4J_PORT)

    # ------------------------------------------------------------------
    # Start services
    # ------------------------------------------------------------------
    def start(self):
        print(f"🚀 Démarrage de la stack dans {PENTEST_CONTAINER}...")

        # --------------------------------------------------------------
        # 1. Neo4j
        # --------------------------------------------------------------
        if self._check_port(self.NEO4J_PORT):
            print("   ✅ Neo4j est déjà en ligne.")
        else:
            print("   🔹 Démarrage de Neo4j...")
            neo4j_cmd = (
                f"export JAVA_HOME={self.JAVA_HOME_V2} && "
                f"neo4j start > /workspace/neo4j_start.log 2>&1"
            )
            self._exec(neo4j_cmd)

            print("      ⏳ Attente du démarrage de Neo4j...")
            for _ in range(15):
                if self._check_port(self.NEO4J_PORT):
                    print("      ✅ Neo4j est prêt !")
                    break
                time.sleep(1)

        # --------------------------------------------------------------
        # 2. GoWitness
        # --------------------------------------------------------------
        if self._check_port(self.GOWITNESS_PORT):
            print("   ✅ GoWitness est déjà en ligne.")
        else:
            print(f"   📸 Démarrage de GoWitness (port {self.GOWITNESS_PORT})...")

            # Init DB si absente
            self._exec(
                "gowitness scan single 127.0.0.1 "
                "--db-uri sqlite:///workspace/gowitness.sqlite3 > /dev/null"
            )

            gw_cmd = (
                "nohup gowitness report server "
                "--db-uri sqlite:///workspace/gowitness.sqlite3 "
                f"--port {self.GOWITNESS_PORT} "
                "--screenshot-path /workspace/screenshot "
                "> /workspace/gowitness.log 2>&1 &"
            )
            self._exec(gw_cmd, detach=True)
            time.sleep(1)

        # --------------------------------------------------------------
        # 3. BloodHound CE (GUI)
        # --------------------------------------------------------------
        if self._check_bloodhound():
            print("   ✅ BloodHound CE est déjà lancé (Port 1030 ouvert).")
        else:
            print("   🐶 Lancement de BloodHound CE (GUI)...")
            bh_cmd = (
                f"nohup {self.BLOODHOUND_BIN} "
                "--no-sandbox "
                "> /workspace/bloodhound.log 2>&1 &"
            )
            self._exec(bh_cmd, detach=True)

            print("      ⏳ Attente du démarrage de BloodHound...")
            for _ in range(10):
                if self._check_bloodhound():
                    print("      ✅ BloodHound est prêt !")
                    break
                time.sleep(1)

        print("\n" + self.get_status_text())

    # ------------------------------------------------------------------
    # Stop services
    # ------------------------------------------------------------------
    def stop(self):
        print("🛑 Arrêt des services...")

        # Neo4j
        self._exec("neo4j stop")

        # GoWitness
        self._exec("pkill -f gowitness")

        # BloodHound CE / Electron
        self._exec(f"pkill -f '{self.BLOODHOUND_BIN}'")
        self._exec("pkill -f electron")
        self._exec("pkill -f bloodhound")

        time.sleep(2)
        print("✅ Services arrêtés.")

    # ------------------------------------------------------------------
    # Status output
    # ------------------------------------------------------------------
    def get_status_text(self):
        neo4j_up = self._check_port(self.NEO4J_PORT)
        gw_up = self._check_port(self.GOWITNESS_PORT)
        bh_up = self._check_bloodhound() # Vérifie le port 1030

        status = [
            f"🕸️  Neo4j      : {'✅ ONLINE' if neo4j_up else '🔴 OFFLINE'}",
            f"📸 GoWitness  : {'✅ ONLINE' if gw_up else '🔴 OFFLINE'}",
            f"🐶 BloodHound : {'✅ ONLINE' if bh_up else '🔴 OFFLINE (GUI)'}",
        ]

        if not bh_up:
            status.append(
                "   (Info: BloodHound GUI nécessite un serveur X11 actif et écoute sur le port 1030)"
            )

        return "\n".join(status)