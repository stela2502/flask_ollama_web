from flask_ollama_web.routes import app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
