from flask import Flask

def create_app():
    app = Flask(__name__)
    with app.app_context():
        import yourpackage.routes  # this registers routes on app
    return app
