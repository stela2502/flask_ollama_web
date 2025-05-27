
import markdown
from flask import Flask, request, render_template, session, redirect, url_for
import requests

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
        reply = markdown.markdown( result.json()["message"]["content"] ) 
        session["chat_history"].append({"role": "assistant", "content": reply})
        session.modified = True
        return redirect(url_for("index"))

    return render_template("index.html", chat_history=session["chat_history"])
