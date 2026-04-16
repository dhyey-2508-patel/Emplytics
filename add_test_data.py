import sqlite3
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "new_app", "backend", "employees.db")

# If that path doesn't exist, try relative to current workspace
if not os.path.exists(db_path):
    db_path = "d:/SQL_Agentic_AI_Project/new_app/backend/employees.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 1. Insert an employee with Mising fields and Fake Email
    cursor.execute("""
        INSERT INTO employees (name, email, mobile, location, department, salary)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("Anomalous User", "fake-email-no-at", "0000000000", "Testing", "", 999999))
    
    # 2. Insert another with an extremely high salary for comparison
    cursor.execute("""
        INSERT INTO employees (name, email, mobile, location, department, salary)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("High Earner", "rich@company.com", "9999999999", "HQ", "Sales", 5000000))

    conn.commit()
    print("Successfully added test anomaly records.")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
