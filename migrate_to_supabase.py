import os
import json
import sqlite3
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# Search for .env in potential locations
load_dotenv() # Tries current dir
load_dotenv("new_app/backend/.env")
load_dotenv(".env")

# Get the Supabase (PostgreSQL) connection string from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file.")
    print("Please ensure you have a .env file with DATABASE_URL=postgresql://...")
    exit(1)

def migrate():
    # 1. Connect to PostgreSQL
    try:
        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_cursor = pg_conn.cursor()
        print("Connected to PostgreSQL successfully.")
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        return

    # 2. Create Tables
    print("Creating tables if they don't exist...")
    pg_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)
    pg_cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id SERIAL PRIMARY KEY,
            user_email TEXT REFERENCES users(email) ON DELETE CASCADE,
            chat_id TEXT NOT NULL,
            title TEXT NOT NULL,
            messages JSONB NOT NULL,
            timestamp TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Employees table (Refresh schema to allow null IDs)
    pg_cursor.execute("DROP TABLE IF EXISTS employees CASCADE")
    pg_cursor.execute("""
        CREATE TABLE employees (
            id INTEGER,
            name TEXT,
            email TEXT,
            mobile TEXT,
            location TEXT,
            department TEXT,
            salary INTEGER
        )
    """)
    pg_conn.commit()

    # 3. Migrate Employee Data from SQLite
    # Try multiple common paths
    possible_db_paths = [
        "new_app/backend/employees.db",
        "backend/employees.db",
        "employees.db"
    ]
    db_path = None
    for p in possible_db_paths:
        if os.path.exists(p):
            db_path = p
            break
            
    if db_path:
        print(f"Migrating employees from {db_path}...")
        sl_conn = sqlite3.connect(db_path)
        sl_cursor = sl_conn.cursor()
        sl_cursor.execute("SELECT * FROM employees")
        employees = sl_cursor.fetchall()
        
        pg_cursor.execute("DELETE FROM employees")
        for emp in employees:
            pg_cursor.execute(
                "INSERT INTO employees (id, name, email, mobile, location, department, salary) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                emp
            )
        sl_conn.close()
        print(f"Migrated {len(employees)} employees.")
    else:
        print("SQLite database not found. Skipping employee migration.")

    # 4. Migrate User Data from JSON
    possible_json_paths = [
        "new_app/backend/backend/data/app_users.json",
        "new_app/backend/data/app_users.json",
        "backend/data/app_users.json",
        "data/app_users.json"
    ]
    json_path = None
    for p in possible_json_paths:
        if os.path.exists(p):
            json_path = p
            break
            
    if json_path:
        print(f"Migrating users and chats from {json_path}...")
        with open(json_path, "r") as f:
            data = json.load(f)
            
        for email, user_data in data.items():
            pg_cursor.execute(
                "INSERT INTO users (email, password, name) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET password = EXCLUDED.password, name = EXCLUDED.name",
                (email, user_data["password"], user_data["name"])
            )
            chats = user_data.get("chats", {})
            for c_id, chat_info in chats.items():
                pg_cursor.execute(
                    "INSERT INTO chats (user_email, chat_id, title, messages, timestamp) VALUES (%s, %s, %s, %s, %s)",
                    (email, c_id, chat_info["title"], Json(chat_info["messages"]), chat_info["timestamp"])
                )
        print("Migrated user data and chats.")
    else:
        print("JSON user data not found. Skipping user migration.")

    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
