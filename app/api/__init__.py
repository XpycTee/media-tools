from flask import Blueprint, jsonify, send_file

from app.api.video import video
from app.api.track import track
from app.api.image import image
from app.api.pdf import pdf


api = Blueprint('api', __name__, url_prefix='/api')

blueprints = [
    video,
    track,
    image,
    pdf,
]

for bp in blueprints:
    api.register_blueprint(bp)
