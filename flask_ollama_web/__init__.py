from flask import Flask

def create_app():
    app = Flask(__name__)
    with app.app_context():
        import flask_ollama_web.routes  # this registers routes on app
    return app

app = create_app()