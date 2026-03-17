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
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

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
    if not isinstance(output_target, dict):
        return None

    raw_path = output_target.get("path")
    if not raw_path:
        return None

    selection_kind = output_target.get("selection_kind")
    if selection_kind == "file":
        return raw_path

    if selection_kind == "directory":
        base_name = os.path.basename(video_path)
        return os.path.join(raw_path, f"muxed_{base_name}")

    return raw_path


def _process_single_video(video_key, streams, progress_cb, output_target=None):
    if not is_video_root_configured():
        return "VIDEO_ROOT is not configured. Set VIDEO_ROOT in the environment before using the Video module."

    video_path = find_file(video_key)
    if not video_path:
        return "Video file not found"

    audio_files = []
    for audio in streams.get("audio", []):
        path = find_file(audio.get("file", ""))
        if not path:
            return f"Audio file {audio.get('file')} not found"
        audio_files.append({"name": audio.get("name", ""), "file": path})

    # Добавляем оригинальную дорожку последней.
    audio_files.append({"name": "Original", "file": video_path})

    subtitle_files = []
    for sub in streams.get("subtitles", []):
        path = find_file(sub.get("file", ""))
        if not path:
            return f"Subtitle file {sub.get('file')} not found"
        subtitle_files.append({"name": sub.get("name", ""), "file": path})

    duration_ms = get_media_duration_ms(video_path)
    output_file = _resolve_output_file(video_path, output_target)
    cmd, output_file = build_ffmpeg_progress_command(
        video_path,
        audio_files,
        subtitle_files,
        output_file=output_file,
    )
    ffmpeg_error = _run_ffmpeg_with_progress(cmd, duration_ms, progress_cb)
    if ffmpeg_error:
        return f"FFmpeg error: {ffmpeg_error}"
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
