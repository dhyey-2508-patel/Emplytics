import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    # If DATABASE_URL doesn't already have sslmode, we add it for Supabase/Render compatibility
    url = DATABASE_URL
    if "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url += f"{separator}sslmode=require"
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

def run_sql_query(query):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # PostgreSQL uses double quotes for case-sensitive names or special characters, 
        # but standard SQL should be fine.
        cursor.execute(query)
        # Cap results at 15 to keep LLM context small and response times snappy
        result = cursor.fetchmany(15)
        
        # results are already dicts due to RealDictCursor
        if len(result) == 15:
            result.append({"_info": "Results capped at 15 for maximum speed."})
    except Exception as e:
        result = [{"error": str(e)}]

    cursor.close()
    conn.close()
    return result

def check_data_quality():
    """Runs a suite of data quality checks and returns findings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    findings = {}
    
    # 1. Check for invalid email patterns
    cursor.execute("SELECT name, email FROM employees WHERE email NOT LIKE '%@%.%'")
    findings["invalid_emails"] = cursor.fetchall()
    
    # 2. Check for missing mandatory fields
    cursor.execute("SELECT name, department FROM employees WHERE name = '' OR department IS NULL OR department = '' OR email = ''")
    findings["missing_fields"] = cursor.fetchall()
    
    # 3. Check for salary outliers (e.g. > 1M or unusual for role)
    cursor.execute("SELECT name, salary, department FROM employees WHERE salary > 1000000 OR salary < 0")
    findings["salary_outliers"] = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return findings