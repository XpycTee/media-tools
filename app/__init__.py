from app.api import api
from app.pages import pages

from flask import Flask


def create_app():
    app = Flask(__name__)

    blueprints = [
        pages,
        api,
    ]

    for bp in blueprints:
        app.register_blueprint(bp)

    return app