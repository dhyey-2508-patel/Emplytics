import json
import os

DB_FILENAME = "app_users.json"

def _load_data():
    if not os.path.exists(DB_FILENAME):
        return {"users": {}, "chats": {}}
    with open(DB_FILENAME, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"users": {}, "chats": {}}

def _save_data(data):
    with open(DB_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def init_db():
    if not os.path.exists(DB_FILENAME):
        _save_data({"users": {}, "chats": {}})

def get_user(email):
    data = _load_data()
    user = data["users"].get(email)
    if user:
        return (email, user["name"])
    return None

def create_user(email, name):
    data = _load_data()
    if email in data["users"]:
        return False
    data["users"][email] = {"name": name}
    if email not in data["chats"]:
        data["chats"][email] = {}
    _save_data(data)
    return True

def get_user_chats(email):
    data = _load_data()
    user_chats = data["chats"].get(email, {})
    return user_chats

def save_chat(email, chat_id, title, messages, timestamp, date_str):
    data = _load_data()
    if email not in data["chats"]:
        data["chats"][email] = {}
    
    data["chats"][email][chat_id] = {
        "title": title,
        "messages": messages,
        "timestamp": timestamp,
        "date": date_str
    }
    _save_data(data)

def delete_chat(email, chat_id):
    data = _load_data()
    if email in data["chats"] and chat_id in data["chats"][email]:
        del data["chats"][email][chat_id]
        _save_data(data)

init_db()
