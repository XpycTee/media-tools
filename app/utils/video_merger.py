import os
import subprocess
from pathlib import Path

def get_base_folder():
    """Возвращает корневую папку медиа или None, если VIDEO_ROOT не задан."""
    # В десктопном режиме VIDEO_ROOT не требуется, пути абсолютные
    if os.environ.get("APP_MODE", "").strip().lower() == "desktop":
        return None
    raw_value = os.environ.get("VIDEO_ROOT", "").strip()
    if not raw_value:
        raw_value = _read_video_root_from_env_file()
    if not raw_value:
        return None
    return Path(raw_value).expanduser()


def _read_video_root_from_env_file():
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return ""

    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            raw_line = line.strip()
            if not raw_line or raw_line.startswith("#") or "=" not in raw_line:
                continue
            key, value = raw_line.split("=", 1)
            if key.strip() == "VIDEO_ROOT":
                return value.strip().strip("'\"")
    except OSError:
        return ""

    return ""


def is_video_root_configured():
    # В десктопном режиме VIDEO_ROOT не требуется
    if os.environ.get("APP_MODE", "").strip().lower() == "desktop":
        return True
    return get_base_folder() is not None


def find_file(filename):
    """Ищем файл по абсолютному/относительному пути или рекурсивно в BASE_FOLDER.

    Поддерживаем передачи относительных путей (например "subdir/file.mka") из фронтенда.
    Логика поиска:
    1. Если это абсолютный путь и файл существует — вернуть его.
    2. Попробовать соединить BASE_FOLDER + filename и проверить существование.
    3. Иначе искать по basename внутри BASE_FOLDER; если filename содержал поддиректорию,
       вернуть совпадение чей относительный путь заканчивается на переданный filename.
    4. Иначе вернуть первый найденный файл с таким basename.
    """
    import sys
    print(f"[DEBUG find_file] Поиск файла: {filename}", file=sys.stderr)
    base_folder = get_base_folder()
    is_desktop = os.environ.get("APP_MODE", "").strip().lower() == "desktop"
    print(f"[DEBUG find_file] base_folder: {base_folder}, is_desktop: {is_desktop}", file=sys.stderr)

    # Absolute path provided
    if os.path.isabs(filename):
        print(f"[DEBUG find_file] Абсолютный путь: {filename}", file=sys.stderr)
        if os.path.exists(filename):
            print(f"[DEBUG find_file] Файл существует, возвращаем", file=sys.stderr)
            return filename
        # В десктопном режиме можно попробовать найти файл относительно текущей директории
        if is_desktop:
            # Попробуем относительный путь от текущей директории
            candidate = os.path.join(os.getcwd(), filename)
            print(f"[DEBUG find_file] Проверяем кандидата: {candidate}", file=sys.stderr)
            if os.path.exists(candidate):
                print(f"[DEBUG find_file] Кандидат существует, возвращаем", file=sys.stderr)
                return candidate
        # Файл не найден
        print(f"[DEBUG find_file] Абсолютный путь не найден", file=sys.stderr)
        return None

    if base_folder is None:
        # В десктопном режиме используем текущую директорию как базовую
        if is_desktop:
            base_folder = Path.cwd()
        else:
            print(f"[DEBUG find_file] base_folder is None и не десктоп, возвращаем None", file=sys.stderr)
            return None

    base_folder_str = str(base_folder)
    print(f"[DEBUG find_file] base_folder_str: {base_folder_str}", file=sys.stderr)

    # Try joining BASE_FOLDER with provided filename (handles relative paths)
    candidate = os.path.join(base_folder_str, filename)
    print(f"[DEBUG find_file] Кандидат после join: {candidate}", file=sys.stderr)
    if os.path.exists(candidate):
        print(f"[DEBUG find_file] Кандидат существует, возвращаем", file=sys.stderr)
        return candidate

    # Fallback: search by basename and try to prefer matching relative path
    target_basename = os.path.basename(filename)
    matches = []
    print(f"[DEBUG find_file] Ищем по basename: {target_basename}", file=sys.stderr)
    for root, dirs, files in os.walk(base_folder_str):
        if target_basename in files:
            full = os.path.join(root, target_basename)
            rel = os.path.relpath(full, base_folder_str)
            matches.append((rel, full))

    if not matches:
        print(f"[DEBUG find_file] Совпадений не найдено, возвращаем None", file=sys.stderr)
        return None

    print(f"[DEBUG find_file] Найдено совпадений: {len(matches)}", file=sys.stderr)
    # If a path-like filename was provided, try to find a match whose relative path endswith it
    norm_filename = filename.replace('\\', '/').lstrip('./')
    for rel, full in matches:
        if rel.replace('\\', '/').endswith(norm_filename):
            print(f"[DEBUG find_file] Найдено точное совпадение по относительному пути: {full}", file=sys.stderr)
            return full

    # Otherwise return the first match
    print(f"[DEBUG find_file] Возвращаем первое совпадение: {matches[0][1]}", file=sys.stderr)
    return matches[0][1]


def build_ffmpeg_command(video_file, audios, subtitles, output_file=None):
    """
    Создаём команду ffmpeg для объединения видео, аудио и субтитров.
    Оригинальная аудио дорожка (если есть) добавляется последней.
    """
    cmd = ["ffmpeg", "-i", video_file]
    # Добавляем аудио дорожки
    for audio in audios:
        cmd.extend(["-i", audio['file']])
    # Добавляем субтитры
    for sub in subtitles:
        cmd.extend(["-i", sub['file']])

    # Строим map
    map_args = ["-map", "0:v:0"]  # видео из исходного файла
    for i in range(len(audios)):
        map_args.extend(["-map", f"{i+1}:a:0"])  # аудио из каждого входа
    for i in range(len(subtitles)):
        map_args.extend(["-map", f"{len(audios)+1+i}:s:0"])  # субтитры

    # Формируем названия дорожек
    metadata_args = []
    for idx, audio in enumerate(audios):
        metadata_args.extend([f"-metadata:s:a:{idx}", f"title={audio['name']}"])
    for idx, sub in enumerate(subtitles):
        metadata_args.extend([f"-metadata:s:s:{idx}", f"title={sub['name']}"])

    if not output_file:
        dir_name = os.path.dirname(video_file)
        base_name = os.path.basename(video_file)
        output_file = os.path.join(dir_name, f"muxed_{base_name}")
    final_cmd = cmd + map_args + metadata_args + ["-c:v", "copy", "-c:a", "copy", "-c:s", "copy", output_file]
    return final_cmd, output_file


def build_ffmpeg_progress_command(video_file, audios, subtitles, output_file=None):
    """Создаём команду ffmpeg c machine-readable прогрессом в stdout."""
    cmd, output_file = build_ffmpeg_command(video_file, audios, subtitles, output_file=output_file)
    # Global options for progress reporting.
    progress_flags = ["-nostats", "-progress", "pipe:1"]
    cmd = [cmd[0]] + progress_flags + cmd[1:]
    return cmd, output_file


def get_media_duration_ms(file_path):
    """Возвращает длительность медиафайла в миллисекундах через ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None

    value = (proc.stdout or "").strip()
    if not value:
        return None
    try:
        return max(1, int(float(value) * 1000))
    except ValueError:
        return None
