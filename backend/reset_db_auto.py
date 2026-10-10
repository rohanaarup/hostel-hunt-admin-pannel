import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.db import connection
from utils.db_safety import guard_or_exit

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
    guard_or_exit(sys.argv[1:], settings.DATABASES['default'].get('HOST'))
    reset_database()
