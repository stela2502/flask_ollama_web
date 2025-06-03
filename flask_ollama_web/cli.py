#!/usr/bin/env python3

from flask_ollama_web.routes import app
from flask_ollama_web.userdb import init_db
from flask_ollama_web.userdb import init_chats_table
import os

def main():
    init_db()
    init_chats_table()
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=8080, debug=debug_mode)

if __name__ == "__main__":
    main()
