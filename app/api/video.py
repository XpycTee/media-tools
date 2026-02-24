import subprocess

from flask import Blueprint, jsonify, request

from app.utils.video_merger import build_ffmpeg_command, find_file


video = Blueprint('video', __name__, url_prefix='/video')


@video.route("/merge", methods=["POST"])
def merge():
    data = request.get_json()
    results = {}
    
    for video, streams in data.items():
        video_path = find_file(video)
        if not video_path:
            results[video] = "Video file not found"
            continue

        # Ищем аудио
        audio_files = []
        for audio in streams.get("audio", []):
            path = find_file(audio["file"])
            if not path:
                results[video] = f"Audio file {audio['file']} not found"
                break
            audio_files.append({"name": audio["name"], "file": path})
        else:
            # Добавляем оригинальное аудио в конец (если она существует)
            # Предположим, оригинал — это первая дорожка видео
            audio_files.append({"name": "Original", "file": video_path})
            
            # Ищем субтитры
            subtitle_files = []
            for sub in streams.get("subtitles", []):
                path = find_file(sub["file"])
                if not path:
                    results[video] = f"Subtitle file {sub['file']} not found"
                    break
                subtitle_files.append({"name": sub["name"], "file": path})
            else:
                cmd, output_file = build_ffmpeg_command(video_path, audio_files, subtitle_files)
                try:
                    subprocess.run(cmd, check=True)
                    results[video] = f"Created {output_file}"
                except subprocess.CalledProcessError as e:
                    results[video] = f"FFmpeg error: {e}"

    return jsonify(results)
