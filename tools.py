import sqlite3

def run_sql_query(query):
    conn = sqlite3.connect("employees.db")
    cursor = conn.cursor()

    try:
        cursor.execute(query)
        result = cursor.fetchall()
    except Exception as e:
        result = str(e)

    conn.close()
    return str(result)