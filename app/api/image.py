import io

from flask import Blueprint, request, send_file

from app.utils import image_converter


image = Blueprint('image', __name__, url_prefix='/image')


@image.route("/convert", methods=["POST"])
def convert():
    files = request.files.getlist('file')
    target = request.form.get('format', 'jpeg')
    try:
        quality = int(request.form.get('quality', 85))
    except Exception:
        quality = 85

    if not files:
        return "No files uploaded", 400

    try:
        data, content_type, filename = image_converter.convert_images(files, target, quality)
    except Exception as e:
        return f"Conversion error: {e}", 500

    return send_file(io.BytesIO(data), mimetype=content_type, as_attachment=True, download_name=filename)
