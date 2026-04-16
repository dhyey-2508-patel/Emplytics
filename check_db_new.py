import sqlite3
import os

db_path = "d:/SQL_Agentic_AI_Project/new_app/backend/employees.db"

if not os.path.exists(db_path):
    print(f"Error: {db_path} does not exist.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        for table in tables:
            cursor.execute(f"SELECT count(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"Table {table[0]} has {count} rows.")
    except Exception as e:
        print(f"Error: {e}")
    conn.close()
