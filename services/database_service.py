from services.db_connector import get_db_connection
from services.database_initialization_service import DatabaseInitializationService

class DatabaseService:
    def reset_db(self):
        """
        Drops all tables and re-initializes the database.
        """
        conn = get_db_connection()
        if not conn:
            return False, "Database connection failed."

        try:
            cur = conn.cursor()
            
            # Get all table names
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
            """)
            tables = cur.fetchall()
            
            # Drop all tables
            for table in tables:
                cur.execute(f"DROP TABLE IF EXISTS {table[0]} CASCADE;")
            
            conn.commit()
            cur.close()
            conn.close()

            # Re-initialize the database
            db_init_service = DatabaseInitializationService()
            db_init_service.init_db()

            return True, "Database has been reset successfully."

        except Exception as e:
            if conn:
                conn.close()
            return False, f"An error occurred: {e}"