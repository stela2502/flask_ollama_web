from flask import Flask, request, render_template, session, redirect, url_for
import requests
import re
from flask import Response
import secrets
import markdown
import sqlite3

from flask_ollama_web.userdb import DB_PATH, verify_user, hash_password, generate_salt, add_user, get_user_id, add_chat_message, get_chat_history

from datetime import datetime, timedelta

SESSION_TIMEOUT = timedelta(minutes=30)

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Required for session use


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "username" not in session:
        return redirect(url_for("login"))

    message = None
    if request.method == "POST":
        username = session["username"]
        old = request.form["old_password"]
        new = request.form["new_password"]

        if verify_user(username, old):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            salt = generate_salt()
            new_hash = hash_password(new, salt)
            c.execute("UPDATE users SET password_hash=?, salt=? WHERE username=?",
                      (new_hash, salt, username))
            conn.commit()
            conn.close()
            message = "Password updated successfully."
        else:
            message = "Old password incorrect."

    return render_template("change_password.html", message=message)



@app.before_request
def check_session_timeout():
    now = datetime.utcnow()

    if "username" in session:
        last_seen = session.get("last_seen")
        if last_seen:
            last_seen = datetime.fromisoformat(last_seen)
            if now - last_seen > SESSION_TIMEOUT:
                session.clear()
                return redirect(url_for("login"))
        session["last_seen"] = now.isoformat()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if verify_user(username, password):
            session["username"] = username
            session["last_seen"] = datetime.utcnow().isoformat()
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid credentials.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    password = request.form["password"]
    if not username or not password:
        return render_template("login.html", error="Username and password required.")
    if add_user(username, password):
        return render_template("login.html", message="User created. You can log in now.")
    else:
        return render_template("login.html", error="User already exists.")


@app.route("/", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]

    if "chat_history" in session:
        session["chat_history"] = []

    if request.method == "POST":
        prompt = request.form["prompt"]

        add_chat_message(username, "user", prompt)

        try:

            updated_history = get_chat_history(username)

            result = requests.post("http://localhost:11434/api/chat", json={
                "model": "llama3",
                "stream": False,
                "messages": updated_history
            })

            
            if result.status_code != 200:
                # Try to extract error message from Ollama
                error_json = result.json()
                error_msg = error_json.get("error", "Unknown error from Ollama")
                return render_template("index.html", error=error_msg, chat_history=updated_history)

            raw = result.json()["message"]["content"] 

            # Save assistant reply to DB
            add_chat_message(username, "ai", raw)

            updated_history = get_chat_history(username)

            return render_template("index.html", chat_history=updated_history)

        except Exception as e:
            error_msg = f"Could not connect to Ollama at http://localhost:11434. Is it running? Error:{e}"
            db_history = get_chat_history(username)
            return render_template("index.html", error=error_msg, chat_history=db_history)
    updated_history = get_chat_history(username)
    return render_template("index.html", chat_history=updated_history )


@app.route('/new_chat', methods=['GET'])
def new_chat():
    if "username" not in session:
        return redirect(url_for("login"))

    user_id = get_user_id(session["username"])
    if user_id is None:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))



@app.route('/export_markdown', methods=['GET'])
def export_markdown():
    if "username" not in session:
        return redirect(url_for("login"))
    username = get_user_id(session["username"])
 
    chat_history = get_chat_history(username)
    
    # Convert chat history to markdown string
    md_lines = []
    for message in chat_history:
        role = message.get("role", "unknown")
        content = message.get("content") or ""
        if role == "user":
            md_lines.append(f"### User:\n{content}\n")
        elif role == "assistant":
            md_lines.append(f"### Assistant:\n{content}\n")
        else:
            md_lines.append(f"### {role.capitalize()}:\n{content}\n")
    
    md_text = "\n---\n".join(md_lines)

    # Send as downloadable markdown file
    return Response(
        md_text,
        mimetype="text/markdown",
        headers={
            "Content-Disposition": "attachment; filename=chat_export.md"
        }
    )