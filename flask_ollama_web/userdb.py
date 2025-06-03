import sqlite3
import hashlib
import secrets
import os
from pathlib import Path
import markdown
import requests

DB_PATH = Path("/app/ollama/web/users.db")

def get_available_models() -> list[str]:
    try:
        resp = requests.get("http://localhost:11434/api/tags")
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"Error fetching models from Ollama: {e}")
        return []

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add 'role' column if missing (for upgrades)
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    if "role" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

    conn.commit()
    conn.close()

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100_000
    ).hex()

def generate_salt() -> str:
    return secrets.token_hex(16)

def add_user(username: str, password: str, role: str = "user") -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    salt = generate_salt()
    hashed = hash_password(password, salt)
    try:
        c.execute('''
            INSERT INTO users (username, password_hash, salt, role)
            VALUES (?, ?, ?, ?)
        ''', (username, hashed, salt, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username: str, password: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT password_hash, salt FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        expected_hash, salt = row
        return hash_password(password, salt) == expected_hash
    return False

def get_user_role(username: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def init_chats_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            role TEXT CHECK(role IN ('user', 'ai')) NOT NULL,
            model TEXT NOT NULL,
            message TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def get_user_id(username: str) -> int | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, model FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def add_chat_message(username: str, role: str, message: str, model: str):
    (user_id, model) = get_user_id(username)
    if user_id is None:
        raise ValueError("User not found")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chats (user_id, role, message, model)
        VALUES (?, ?, ?, ?)
    ''', (user_id, role, message, model))
    conn.commit()
    conn.close()

def get_chat_history(username: str, limit: int = 100) -> list[dict]:
    user_id = get_user_id(username)
    if user_id is None:
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT role, message, model, timestamp FROM chats
        WHERE user_id = ?
        ORDER BY timestamp ASC
        LIMIT ?
    ''', (user_id, limit))
    rows = c.fetchall()
    conn.close()

    chat_history = []

    for role, message, model, time in rows:
        if role == "ai":
            # For AI entries: parse markdown for "content" and keep raw original
            content = markdown.markdown(message)
            chat_history.append({"role": "assistant", "content": content, "raw": message, "model": model})
        else:
            # For user entries: just put content as message text
            chat_history.append({"role": role, "content": message})

    return chat_history
