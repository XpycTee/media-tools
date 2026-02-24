from environs import Env

import os

env = Env()
env.read_env()

# Папка, где ищем видео, аудио и субтитры
BASE_FOLDER = env.path("VIDEO_ROOT")

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
    # Absolute path provided
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename

    # Try joining BASE_FOLDER with provided filename (handles relative paths)
    candidate = os.path.join(BASE_FOLDER, filename)
    if os.path.exists(candidate):
        return candidate

    # Fallback: search by basename and try to prefer matching relative path
    target_basename = os.path.basename(filename)
    matches = []
    for root, dirs, files in os.walk(BASE_FOLDER):
        if target_basename in files:
            full = os.path.join(root, target_basename)
            rel = os.path.relpath(full, BASE_FOLDER)
            matches.append((rel, full))

    if not matches:
        return None

    # If a path-like filename was provided, try to find a match whose relative path endswith it
    norm_filename = filename.replace('\\', '/').lstrip('./')
    for rel, full in matches:
        if rel.replace('\\', '/').endswith(norm_filename):
            return full

    # Otherwise return the first match
    return matches[0][1]


def build_ffmpeg_command(video_file, audios, subtitles):
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

    dir_name = os.path.dirname(video_file)
    base_name = os.path.basename(video_file)
    output_file = os.path.join(dir_name, f"muxed_{base_name}")
    final_cmd = cmd + map_args + metadata_args + ["-c:v", "copy", "-c:a", "copy", "-c:s", "copy", output_file]
    return final_cmd, output_file