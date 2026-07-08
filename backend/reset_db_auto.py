import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

def reset_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [row[0] for row in cursor.fetchall()]
        if not tables:
            print("Database already empty.")
            return
        drop_query = 'DROP TABLE IF EXISTS ' + ', '.join(f'"{t}"' for t in tables) + ' CASCADE;'
        cursor.execute(drop_query)
        print("Dropped all tables successfully.")

if __name__ == '__main__':
    reset_database()
