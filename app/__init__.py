from flask import Flask

from app.api import api
from app.pages import pages
from app.runtime import get_app_mode, get_resource_path


def create_app():
    app = Flask(
        __name__,
        template_folder=get_resource_path("app", "templates"),
        static_folder=get_resource_path("app", "static"),
    )
    app.config["APP_MODE"] = get_app_mode()

    blueprints = [
        pages,
        api,
    ]

    for bp in blueprints:
        app.register_blueprint(bp)

    return app
