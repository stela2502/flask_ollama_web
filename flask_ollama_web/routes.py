
import markdown
from flask import Flask, request, render_template, session, redirect, url_for
import requests
import re
from flask import Blueprint


app = Flask(__name__)
app.secret_key = "your-secret-key"  # Required for session use

@app.route("/", methods=["GET", "POST"])
def index():
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        prompt = request.form["prompt"]
        session["chat_history"].append({"role": "user", "content": prompt})

        result = requests.post("http://localhost:11434/api/chat", json={
            "model": "llama3",
            "stream": False,
            "messages": session["chat_history"]
        })
        raw = result.json()["message"]["content"] 
        #raw_mod = raw
        #re.sub(r'(?m)^(```.*)$', r'\n\1\n', raw_mod)

        reply = markdown.markdown( raw ) 
        session["chat_history"].append({"role": "assistant", "content": reply, "raw": raw, })
        session.modified = True
        return redirect(url_for("index"))

    return render_template("index.html", chat_history=session["chat_history"])


@app.route('/new_chat', methods=['GET'])
def new_chat():
    session["chat_history"] = [] # Clear stored chat
    return redirect(url_for('index'))   # Redirect to main chat page