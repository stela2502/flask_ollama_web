#!/usr/bin/env python3

from flask_ollama_web.routes import app
from flask_ollama_web.userdb import init_db
from flask_ollama_web.userdb import init_chats_table

def main():
    init_db()
    init_chats_table()
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
