from flask import Flask, request, render_template, session, redirect, url_for
import requests
import re
from flask import Response
import secrets
import markdown
import sqlite3
import os

from flask_ollama_web.userdb import *

from datetime import datetime, timedelta


SESSION_TIMEOUT = timedelta(minutes=30)

app = Flask(__name__)

app.secret_key = get_secret()  # Required for session use


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "username" not in session:
        return redirect(url_for("login"))

    message = None
    if request.method == "POST":
        username = session["username"]
        old = request.form["old_password"]
        new = request.form["new_password"]
        confirm = request.form["confirm_password"] 
        if new != confirm:
            message = "New passwords do not match."
        elif not verify_user(username, old):
            message = "Old password incorrect."
        else:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            salt = generate_salt()
            new_hash = hash_password(new, salt)
            c.execute("UPDATE users SET password_hash=?, salt=? WHERE username=?",
                      (new_hash, salt, username))
            conn.commit()
            conn.close()
            message = "Password updated successfully."

    return render_template("change_password.html", message=message)


@app.route("/set_model", methods=["POST"])
def set_model():
    if "username" not in session:
        return redirect(url_for("login"))
    # List of allowed models (you can customize these)
    ALLOWED_MODELS = get_available_models()

    selected_model = request.form.get("last_model")

    if selected_model in ALLOWED_MODELS:
        session["last_model"] = selected_model
        update_user_model(session["username"], selected_model)
    return redirect(url_for("index"))


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

        user_data = verify_user(username, password)

        if user_data:
            user_id , last_model = user_data
            session["username"] = username
            session["user_id"] = user_id
            session["last_model"] = last_model
            session["last_seen"] = datetime.utcnow().isoformat()
            session["allowed_models"] = get_available_models()

            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid credentials.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/register', methods=['GET', 'POST'])
def register():
   if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Validate inputs (add your validation logic here)
        if not username or not password:
           return redirect(url_for('register', error='Username and password are required.'))
        if username_not_taken( username ):
            add_user( username, password )
        else:
            return redirect(url_for('register', error='Username already exists - choose another, please.'))
        if verify_user(  username, password ):
            return redirect(url_for('index'))
        else:
            return redirect( url_for( '/register', error= "A database error occured!" ))
       
   return render_template('register.html')


@app.route("/", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    last_model = session.get("last_model")

    if "chat_history" in session:
        session["chat_history"] = []

    if request.method == "POST":
        prompt = request.form["prompt"]

        add_chat_message(username, "user", prompt, last_model )

        try:

            updated_history = get_chat_history(username)

            result = requests.post("http://localhost:11434/api/chat", json={
                "model": last_model,
                "stream": False,
                "messages": updated_history
            })

            
            if result.status_code != 200:
                # Try to extract error message from Ollama
                error_json = result.json()
                error_msg = error_json.get("error", "Unknown error from Ollama")
                return render_template("index.html", error=error_msg, chat_history=updated_history, allowed_models= session["allowed_models"])

            raw = result.json()["message"]["content"] 

            # Save assistant reply to DB
            add_chat_message(username, "ai", raw, last_model)

            updated_history = get_chat_history(username)

            return render_template("index.html", chat_history=updated_history, allowed_models= session["allowed_models"])

        except Exception as e:
            error_msg = f"Could not connect to Ollama at http://localhost:11434. Is it running? Error:{e}"
            db_history = get_chat_history(username)
            return render_template("index.html", error=error_msg, chat_history=db_history, allowed_models= session["allowed_models"])
    
    history = get_chat_history(username)

    # If last message is from user and unanswered, remove it and pre-fill
    if history and history[-1]["role"] == "user":
        last_prompt = history[-1]["content"]
        delete_last_message(username)  # You need to implement this if not already present
        prefill_prompt = last_prompt
        history = get_chat_history(username)
    
    return render_template("index.html", chat_history=history, allowed_models= session["allowed_models"] )


@app.route('/new_chat', methods=['GET'])
def new_chat():
    if "username" not in session:
        return redirect(url_for("login"))

    data = get_user_id(session["username"])
    if data is None:
        return redirect(url_for("login"))
    user_id, _ = data
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
    
    md_text = get_history_markdown( session['username'] )

    # Send as downloadable markdown file
    return Response(
        md_text,
        mimetype="text/markdown",
        headers={
            "Content-Disposition": "attachment; filename=chat_export.md"
        }
    )
