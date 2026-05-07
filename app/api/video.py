import copy
import os
import subprocess
import threading
import uuid

from flask import Blueprint, jsonify, request

from app.utils.video_merger import (
    build_ffmpeg_progress_command,
    find_file,
    get_media_duration_ms,
    is_video_root_configured,
)


video = Blueprint("video", __name__, url_prefix="/video")

_JOBS = {}
_JOBS_LOCK = threading.Lock()


def _format_hms_to_ms(value):
    if not value or ":" not in value:
        return None
    try:
        hh, mm, ss = value.split(":")
        return int((int(hh) * 3600 + int(mm) * 60 + float(ss)) * 1000)
    except (TypeError, ValueError):
        return None


def _extract_out_time_ms(progress_line):
    if "=" not in progress_line:
        return None
    key, raw = progress_line.split("=", 1)
    key = key.strip()
    raw = raw.strip()
    if key == "out_time_ms":
        try:
            return int(raw)
        except ValueError:
            return None
    if key == "out_time":
        return _format_hms_to_ms(raw)
    return None


def _build_initial_state(total):
    return {
        "status": "queued",
        "overall_percent": 0.0,
        "current_file": None,
        "current_file_percent": 0.0,
        "processed": 0,
        "total": total,
        "results": {},
        "error": None,
    }


def _set_job_state(job_id, **updates):
    with _JOBS_LOCK:
        state = _JOBS.get(job_id)
        if not state:
            return
        state.update(updates)


def _get_job_state(job_id):
    with _JOBS_LOCK:
        state = _JOBS.get(job_id)
        return copy.deepcopy(state) if state else None


def _calc_overall_percent(processed, total, current_file_percent):
    if total <= 0:
        return 100.0
    clamped_current = max(0.0, min(100.0, float(current_file_percent)))
    return min(100.0, ((processed + clamped_current / 100.0) / total) * 100.0)


def _run_ffmpeg_with_progress(cmd, duration_ms, progress_cb):
    import sys
    print(f"[DEBUG _run_ffmpeg_with_progress] Запуск команды: {cmd}", file=sys.stderr)
    print(f"[DEBUG _run_ffmpeg_with_progress] Первый элемент (исполняемый файл): {cmd[0] if cmd else 'None'}", file=sys.stderr)
    print(f"[DEBUG _run_ffmpeg_with_progress] Проверяем существование файла: {os.path.exists(cmd[0]) if cmd and cmd[0] else 'N/A'}", file=sys.stderr)
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        print(f"[DEBUG _run_ffmpeg_with_progress] Исключение при запуске subprocess: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"Failed to start ffmpeg: {e}"

    output_lines = []
    for line in proc.stdout:
        output_lines.append(line.rstrip())
        out_time_ms = _extract_out_time_ms(line)
        if out_time_ms is None or not duration_ms:
            continue
        current_percent = min(100.0, (out_time_ms / duration_ms) * 100.0)
        progress_cb(current_percent)

    return_code = proc.wait()
    if return_code == 0:
        return None

    tail = "\n".join(output_lines[-20:]).strip()
    return tail or f"ffmpeg exited with code {return_code}"

def _resolve_output_file(video_path, output_target):
    import sys
    if not isinstance(output_target, dict):
        print(f"[DEBUG _resolve_output_file] output_target не dict: {output_target}", file=sys.stderr)
        return None

    raw_path = output_target.get("path")
    if not raw_path:
        print(f"[DEBUG _resolve_output_file] path отсутствует", file=sys.stderr)
        return None

    selection_kind = output_target.get("selection_kind")
    print(f"[DEBUG _resolve_output_file] raw_path={raw_path}, selection_kind={selection_kind}", file=sys.stderr)
    if selection_kind == "file":
        print(f"[DEBUG _resolve_output_file] возвращаем файл: {raw_path}", file=sys.stderr)
        return raw_path

    if selection_kind == "directory":
        base_name = os.path.basename(video_path)
        result = os.path.join(raw_path, f"muxed_{base_name}")
        print(f"[DEBUG _resolve_output_file] директория, результат: {result}", file=sys.stderr)
        return result

    print(f"[DEBUG _resolve_output_file] неизвестный selection_kind, возвращаем raw_path", file=sys.stderr)
    return raw_path


def _process_single_video(video_key, streams, progress_cb, output_target=None):
    import sys
    import os
    print(f"[DEBUG _process_single_video] Начало обработки видео: video_key={video_key}", file=sys.stderr)
    print(f"[DEBUG _process_single_video] streams={streams}", file=sys.stderr)
    print(f"[DEBUG _process_single_video] output_target={output_target}", file=sys.stderr)
    if not is_video_root_configured():
        print(f"[DEBUG _process_single_video] VIDEO_ROOT не сконфигурирован", file=sys.stderr)
        return "VIDEO_ROOT is not configured. Set VIDEO_ROOT in the environment before using the Video module."

    video_path = find_file(video_key)
    if not video_path:
        # Попробуем найти файл в директории output_target, если это директория
        if output_target and isinstance(output_target, dict):
            output_path = output_target.get("path")
            selection_kind = output_target.get("selection_kind")
            if selection_kind == "directory" and output_path:
                # Предполагаем, что видеофайлы находятся в родительской директории output_path
                parent_dir = os.path.dirname(output_path.rstrip('/'))
                candidate = os.path.join(parent_dir, video_key)
                print(f"[DEBUG _process_single_video] Пробуем кандидата из output_target: {candidate}", file=sys.stderr)
                if os.path.exists(candidate):
                    video_path = candidate
                    print(f"[DEBUG _process_single_video] Видеофайл найден через output_target: {video_path}", file=sys.stderr)
                else:
                    # Может быть, видеофайлы находятся в самой output_path (директории muxed)
                    candidate2 = os.path.join(output_path, video_key)
                    print(f"[DEBUG _process_single_video] Пробуем кандидата в output_path: {candidate2}", file=sys.stderr)
                    if os.path.exists(candidate2):
                        video_path = candidate2
                        print(f"[DEBUG _process_single_video] Видеофайл найден в output_path: {video_path}", file=sys.stderr)
        if not video_path:
            print(f"[DEBUG _process_single_video] Видеофайл не найден: {video_key}", file=sys.stderr)
            return "Video file not found"
    print(f"[DEBUG _process_single_video] Видеофайл найден: {video_path}", file=sys.stderr)

    audio_files = []
    for audio in streams.get("audio", []):
        audio_file_key = audio.get("file", "")
        print(f"[DEBUG _process_single_video] Ищем аудио файл: {audio_file_key}", file=sys.stderr)
        path = find_file(audio_file_key)
        if not path:
            print(f"[DEBUG _process_single_video] Аудио файл не найден: {audio_file_key}", file=sys.stderr)
            return f"Audio file {audio.get('file')} not found"
        print(f"[DEBUG _process_single_video] Аудио файл найден: {path}", file=sys.stderr)
        audio_files.append({"name": audio.get("name", ""), "file": path})

    # Добавляем оригинальную дорожку последней.
    audio_files.append({"name": "Original", "file": video_path})

    subtitle_files = []
    for sub in streams.get("subtitles", []):
        sub_file_key = sub.get("file", "")
        print(f"[DEBUG _process_single_video] Ищем субтитры: {sub_file_key}", file=sys.stderr)
        path = find_file(sub_file_key)
        if not path:
            print(f"[DEBUG _process_single_video] Субтитры не найдены: {sub_file_key}", file=sys.stderr)
            return f"Subtitle file {sub.get('file')} not found"
        print(f"[DEBUG _process_single_video] Субтитры найдены: {path}", file=sys.stderr)
        subtitle_files.append({
            "name": sub.get("name", ""),
            "file": path,
            "default": bool(sub.get("default")),
        })

    import sys
    duration_ms = get_media_duration_ms(video_path)
    print(f"[DEBUG _process_single_video] Длительность видео: {duration_ms} мс", file=sys.stderr)
    output_file = _resolve_output_file(video_path, output_target)
    print(f"[DEBUG _process_single_video] output_file: {output_file}", file=sys.stderr)
    cmd, output_file = build_ffmpeg_progress_command(
        video_path,
        audio_files,
        subtitle_files,
        output_file=output_file,
    )
    print(f"[DEBUG _process_single_video] Команда ffmpeg построена, выходной файл: {output_file}", file=sys.stderr)
    ffmpeg_error = _run_ffmpeg_with_progress(cmd, duration_ms, progress_cb)
    if ffmpeg_error:
        print(f"[DEBUG _process_single_video] Ошибка ffmpeg: {ffmpeg_error}", file=sys.stderr)
        return f"FFmpeg error: {ffmpeg_error}"
    print(f"[DEBUG _process_single_video] Успешно создан: {output_file}", file=sys.stderr)
    return f"Created {output_file}"


def _parse_merge_request(data):
    if not isinstance(data, dict):
        raise ValueError("Invalid payload: expected JSON object")

    if "items" in data:
        items = data.get("items")
        if not isinstance(items, dict):
            raise ValueError("Invalid payload: items must be an object")
        return items, data.get("output")

    return data, None


def _merge_payload(data, progress_hook=None):
    items_payload, output_target = _parse_merge_request(data)

    items = list(items_payload.items())
    total = len(items)
    results = {}
    processed = 0

    for video_key, streams in items:
        streams = streams if isinstance(streams, dict) else {}

        if progress_hook:
            progress_hook(
                current_file=video_key,
                current_file_percent=0.0,
                processed=processed,
                total=total,
                results=results,
            )

        def on_progress(current_percent):
            if not progress_hook:
                return
            progress_hook(
                current_file=video_key,
                current_file_percent=current_percent,
                processed=processed,
                total=total,
                results=results,
            )

        results[video_key] = _process_single_video(
            video_key,
            streams,
            on_progress,
            output_target=output_target,
        )
        processed += 1

        if progress_hook:
            progress_hook(
                current_file=video_key,
                current_file_percent=100.0,
                processed=processed,
                total=total,
                results=results,
            )

    return results


def _run_job(job_id, data):
    try:
        state = _get_job_state(job_id)
        if not state:
            return
        total = state["total"]
        _set_job_state(job_id, status="running")

        def progress_hook(current_file, current_file_percent, processed, total, results):
            _set_job_state(
                job_id,
                current_file=current_file,
                current_file_percent=round(current_file_percent, 2),
                processed=processed,
                total=total,
                overall_percent=round(
                    _calc_overall_percent(processed, total, current_file_percent), 2
                ),
                results=copy.deepcopy(results),
            )

        results = _merge_payload(data, progress_hook)
        _set_job_state(
            job_id,
            status="completed",
            overall_percent=100.0 if total > 0 else 0.0,
            current_file=None,
            current_file_percent=0.0,
            processed=total,
            results=results,
            error=None,
        )
    except Exception as exc:
        _set_job_state(
            job_id,
            status="failed",
            current_file=None,
            current_file_percent=0.0,
            error=str(exc),
        )


@video.route("/merge/start", methods=["POST"])
def merge_start():
    data = request.get_json(silent=True)
    try:
        items, _ = _parse_merge_request(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    job_id = str(uuid.uuid4())
    with _JOBS_LOCK:
        _JOBS[job_id] = _build_initial_state(total=len(items))

    worker = threading.Thread(target=_run_job, args=(job_id, data), daemon=True)
    worker.start()
    return jsonify({"job_id": job_id, "status": "queued"})


@video.route("/merge/status/<job_id>", methods=["GET"])
def merge_status(job_id):
    state = _get_job_state(job_id)
    if not state:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(state)


@video.route("/merge", methods=["POST"])
def merge():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload: expected JSON object"}), 400

    try:
        # Legacy synchronous endpoint for backward compatibility.
        results = _merge_payload(data)
        return jsonify(results)
    except subprocess.SubprocessError as exc:
        return jsonify({"error": f"Subprocess error: {exc}"}), 500
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
