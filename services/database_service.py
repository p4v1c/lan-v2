from services.db_connector import get_db_connection
from services.database_initialization_service import DatabaseInitializationService

class DatabaseService:
    def reset_db(self):
        """
        Resets the database by deleting all data, but preserves the 'users' table.
        """
        conn = get_db_connection()
        if not conn:
            return False, "Database connection failed."

        try:
            cur = conn.cursor()
            
            # Get all table names EXCEPT 'users'
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                AND table_name != 'users'; -- Exclude the users table
            """)
            tables_to_drop = cur.fetchall()
            
            # Drop selected tables
            for table in tables_to_drop:
                cur.execute(f"DROP TABLE IF EXISTS {table[0]} CASCADE;")
            
            conn.commit()
            cur.close()
            conn.close()

            # Re-initialize the database (this will recreate the tables that were dropped)
            db_init_service = DatabaseInitializationService()
            db_init_service.init_db()

            return True, "Database has been reset successfully (users preserved)."

        except Exception as e:
            if conn:
                conn.close()
            return False, f"An error occurred: {e}"