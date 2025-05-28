import markdown
from flask import Flask, request, render_template, session, redirect, url_for
import requests
import re
from flask import Response

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Required for session use

@app.route("/", methods=["GET", "POST"])
def index():
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        prompt = request.form["prompt"]
        session["chat_history"].append({"role": "user", "content": prompt})

        try:
            result = requests.post("http://localhost:11434/api/chat", json={
                "model": "llama3",
                "stream": False,
                "messages": session["chat_history"]
            })

            if result.status_code != 200:
                # Try to extract error message from Ollama
                error_json = result.json()
                error_msg = error_json.get("error", "Unknown error from Ollama")
                return render_template("index.html", error=error_msg, chat_history=session["chat_history"])

            raw = result.json()["message"]["content"] 

            reply = markdown.markdown(raw)
            session["chat_history"].append({"role": "assistant", "content": reply, "raw": raw})
            session.modified = True
            return redirect(url_for("index"))
        except Exception as e:
            error_msg = f"Could not connect to Ollama at http://localhost:11434. Is it running? Error:{e}"
            return render_template("index.html", error=error_msg, chat_history=session["chat_history"])

    return render_template("index.html", chat_history=session["chat_history"])


@app.route('/new_chat', methods=['GET'])
def new_chat():
    session["chat_history"] = []  # Clear stored chat
    return redirect(url_for('index'))


@app.route('/export_markdown', methods=['GET'])
def export_markdown():
    chat_history = session.get("chat_history", [])
    
    # Convert chat history to markdown string
    md_lines = []
    for message in chat_history:
        role = message.get("role", "unknown")
        content = message.get("raw") or message.get("content") or ""
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