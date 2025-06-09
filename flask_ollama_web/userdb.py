import sqlite3
import hashlib
import secrets
import os
from pathlib import Path
import requests
import html2text;
from typing import Optional, Tuple
from markdown_it import MarkdownIt

md_parser = MarkdownIt()
html2md = html2text.HTML2Text()
html2md.body_width = 0  # Don't wrap lines
html2md.ignore_links = False

DB_PATH = Path(os.getenv("FLASK_OLLAMA_DB_PATH", "database")) / "users.db"

#DB_PATH = Path("/app/ollama/web/users.db")

def get_available_models() -> list[str]:
    try:
        resp = requests.get("http://localhost:11434/api/tags")
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"Error fetchinglast_models from Ollama: {e}")
        return []

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get the firstlast_model from availablelast_models
    first_model = get_available_models()[0]
    # Create table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            last_model TEXT NOT NULL DEFAULT '{0}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''.format(first_model) )

    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            last_model TEXT NOT NULL,  
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

def get_secret():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Check if .env file exists
    secret_f =  os.path.join(DB_PATH.parent, '.info')
    if not os.path.exists( secret_f ):
        # Generate a secure secret key
        secret_key = secrets.token_hex(32)

        # Create the .env file with necessary variables
        with open( secret_f , 'w') as f:
            f.write(f'{secret_key}')

        print(f"Created new secret file with random secret key.")
    # Ensure the file exists before reading
    if not os.path.exists(secret_f):
        raise FileNotFoundError(f"The secret file '{secret_f}' does not exist.")

    try:
        with open(secret_f, 'r') as f:
            secret = f.read().strip()
            return secret
    except IOError:
        print(f"Error reading the secret file: {secret_f}")
        return None

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100_000
    ).hex()

def username_not_taken(username):
    """Check if the given username is available.

    Args:
        username (str): The username to check.

    Returns:
        bool: True if the username is available, False otherwise.
    """
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        return not result  # Return False if result exists (username taken), True otherwise
    finally:
        db.close()

def generate_salt() -> str:
    return secrets.token_hex(16)

def add_user(username: str, password: str, role: str = "user") -> bool:   
    salt = generate_salt()
    hashed = hash_password(password, salt)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
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

def verify_user(username: str, password: str) -> Optional[Tuple[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if the username exists and verify password
    c.execute("SELECT id, salt, last_model, password_hash  FROM users WHERE username = ?", (username,))
    result = c.fetchone()

    if not result:
        conn.close()
        return False

    user_id, salt, last_model, password_hash = result
    
    hashed = hash_password(password, salt)

    if password_hash != hashed :
        conn.close()
        return None

    conn.close()
    return (user_id,last_model )

def get_user_role(username: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def update_user_model(username: str, new_model: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Update both session and database
    c.execute('''
        UPDATE users
        SET last_model = ?
        WHERE username = ?
    ''', (new_model, username))

    conn.commit()
    conn.close()

def get_user_id(username: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,last_model FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return (row[0], row[1]) if row else None

def add_chat_message(username: str, role: str, message: str,last_model: str):
    data = get_user_id(username)
    if data is None:
        raise ValueError("User not found")
    user_id,last_model = data

    message = html_to_markdown_with_js_blocks( message )

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chats (user_id, role, message,last_model)
        VALUES (?, ?, ?, ?)
    ''', (user_id, role, message,last_model))
    conn.commit()
    conn.close()

def html_to_markdown_with_js_blocks(input_text):

    # Step 1: Markdown → HTML
    #html = md_parser.render(input_text)

    # Step 2: HTML → cleaned Markdown
    #cleaned_md = html2md.handle(html)
    return cleaned_md.strip()

def get_history_markdown(username: str ) -> list[dict]:
    data = get_user_id(username)
    if data is None:
        return []
    user_id,last_model = data
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT role, message,last_model, timestamp FROM chats
        WHERE user_id = ?
        ORDER BY timestamp ASC
    ''', (user_id, ))
    rows = c.fetchall()
    conn.close()

    md_lines=[]

    for role, content, model, time in rows:
        if role == "user":
            md_lines.append(f"### User #{time}:\n{content}\n")
        elif role == "assistant":
            md_lines.append(f"### Assistant ({model}) #{time}:\n{content}\n")
        else:
            md_lines.append(f"### {role.capitalize()} #{time}:\n{content}\n")

    return "\n---\n".join(md_lines)


def get_chat_history(username: str, limit: int = 100) -> list[dict]:
    data = get_user_id(username)
    if data is None:
        return []
    user_id,last_model = data

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT role, message,last_model, timestamp FROM chats
        WHERE user_id = ?
        ORDER BY timestamp ASC
        LIMIT ?
    ''', (user_id, limit))
    rows = c.fetchall()
    conn.close()

    chat_history = []

    for role, message,last_model, time in rows:
        content =md_parser.render(message)
        if role == "ai":
            chat_history.append({"role": "assistant", "content": content, "raw": message, "model":last_model})
        else:
            chat_history.append({"role": role, "content": message})

    return chat_history
