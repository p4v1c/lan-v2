import psycopg2
from config import PG_DB, PG_USER, PG_PASSWORD

def get_db_connection(host="db", silent=True):
    """
    Crée et retourne une connexion à la base de données PostgreSQL.
    Retourne None en cas d'échec.
    """
    try:
        conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
            host=host,
            port="5432",
            connect_timeout=3
        )
        return conn
    except Exception as e:
        if not silent:
            print(f"❌ Erreur de connexion DB ({host}): {e}")
        return None
