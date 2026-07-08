import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

def reset_database():
    print("Fetching list of all tables in the database...")
    with connection.cursor() as cursor:
        # Get all tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("No tables found. Database is already empty.")
            return
            
        print(f"Found {len(tables)} tables to drop: {tables}")
        confirm = input("Are you sure you want to drop all tables and reset the database? (y/N): ")
        if confirm.lower() != 'y':
            print("Reset cancelled.")
            return
            
        # Drop all tables with CASCADE
        drop_query = 'DROP TABLE IF EXISTS ' + ', '.join(f'"{t}"' for t in tables) + ' CASCADE;'
        cursor.execute(drop_query)
        print("Successfully dropped all tables.")

if __name__ == '__main__':
    reset_database()
