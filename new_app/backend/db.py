import os
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from datetime import datetime
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

def register_user(email, password, name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return False
        
        cursor.execute(
            "INSERT INTO users (email, password, name) VALUES (%s, %s, %s)",
            (email, password, name)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error registering user: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def validate_login(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name FROM users WHERE email = %s AND password = %s",
            (email, password)
        )
        user = cursor.fetchone()
        return user["name"] if user else None
    except Exception as e:
        print(f"Error validating login: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_user_chats(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT chat_id, title, messages, timestamp FROM chats WHERE user_email = %s ORDER BY created_at DESC",
            (email,)
        )
        chats = cursor.fetchall()
        # Return as a dict keyed by chat_id to maintain compatibility with existing frontend
        return {chat["chat_id"]: chat for chat in chats}
    except Exception as e:
        print(f"Error getting chats: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()

def save_chat(email, chat_id, title, messages):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        timestamp = datetime.now().strftime("%H:%M")
        
        # Check if chat exists for this user and chat_id
        cursor.execute("SELECT id FROM chats WHERE user_email = %s AND chat_id = %s", (email, chat_id))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute(
                "UPDATE chats SET title = %s, messages = %s, timestamp = %s WHERE id = %s",
                (title, Json(messages), timestamp, existing["id"])
            )
        else:
            cursor.execute(
                "INSERT INTO chats (user_email, chat_id, title, messages, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (email, chat_id, title, Json(messages), timestamp)
            )
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving chat: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def delete_chat(email, chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM chats WHERE user_email = %s AND chat_id = %s",
            (email, chat_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def rename_chat(email, chat_id, new_title):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE chats SET title = %s WHERE user_email = %s AND chat_id = %s",
            (new_title, email, chat_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error renaming chat: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
