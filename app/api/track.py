import os
import subprocess
import tempfile

from flask import Blueprint, request, send_file


track = Blueprint('track', __name__, url_prefix='/track')


@track.route("/compile", methods=["POST"])
def compile():
    # Получаем файлы и данные формы
    audio = request.files.get("audio")
    cover = request.files.get("cover")
    title = request.form.get("title", "track")
    artist = request.form.get("artist", "unknown")
    album = request.form.get("album", "")
    genre = request.form.get("genre", "")
    comment = request.form.get("comment", "")
    year = request.form.get("year", "")

    if not audio:
        return "Audio file is required", 400

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio_input.mp3")
        audio.save(audio_path)

        output_filename = f"{title} - {artist}.mp3"
        output_path = os.path.join(tmpdir, output_filename)

        cmd = ["ffmpeg", "-y", "-i", audio_path]

        if cover:
            cover_path = os.path.join(tmpdir, "cover.jpg")
            cover.save(cover_path)
            cmd.extend(["-i", cover_path, "-map", "0", "-map", "1"])
        else:
            cmd.extend(["-map", "0"])

        cmd.extend(["-c", "copy", "-id3v2_version", "3"])

        # Добавляем метаданные
        if title:
            cmd.extend(["-metadata", f"title={title}"])
        if artist:
            cmd.extend(["-metadata", f"artist={artist}"])
        if album:
            cmd.extend(["-metadata", f"album={album}"])
        if genre:
            cmd.extend(["-metadata", f"genre={genre}"])
        if comment:
            cmd.extend(["-metadata", f"comment={comment}"])
        if year:
            cmd.extend(["-metadata", f"year={year}"])

        if cover:
            cmd.extend([
                "-metadata:s:v", "title=Cover",
                "-metadata:s:v", "comment=Cover (front)"
            ])

        cmd.append(output_path)

        # Выполняем ffmpeg
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            return f"FFmpeg error: {e}", 500

        # Отправляем результат клиенту
        return send_file(output_path, as_attachment=True, download_name=output_filename)
