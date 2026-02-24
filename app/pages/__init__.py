from flask import Blueprint, render_template


pages = Blueprint('pages', __name__)


@pages.route("/video", methods=["GET"])
def video():
    return render_template("video.html")

@pages.route("/track", methods=["GET"])
def track():
    return render_template("music.html")

@pages.route("/image", methods=["GET"])
def image():
    return render_template("image.html")

@pages.route("/pdf", methods=["GET"])
def pdf():
    return render_template("pdf.html")