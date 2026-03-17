import os
from pathlib import Path


ALLOWED_EXTENSIONS = {
    "audio": {".mka"},
    "subtitle": {".srt", ".ass", ".vtt"},
}


def normalize_dialog_result(result):
    if not result:
        return []
    if isinstance(result, (str, Path)):
        return [str(result)]
    return [str(item) for item in result if item]


def is_allowed_media_file(path, media_type):
    allowed = ALLOWED_EXTENSIONS.get(media_type, set())
    return Path(path).suffix.lower() in allowed


def build_directory_selection_payload(directory, media_type):
    root = Path(directory)
    files = []

    for current_root, _, filenames in os.walk(root):
        for filename in filenames:
            full_path = Path(current_root) / filename
            if not is_allowed_media_file(full_path, media_type):
                continue
            relative_name = str(full_path.relative_to(root))
            files.append(
                {
                    "path": str(full_path),
                    "display_name": filename,
                    "relative_name": relative_name,
                }
            )

    return {
        "selection_kind": "directory",
        "track_name_hint": root.name,
        "files": files,
    }


def build_file_selection_payload(paths, media_type):
    files = []
    for raw_path in paths:
        full_path = Path(raw_path)
        if not is_allowed_media_file(full_path, media_type):
            continue
        files.append(
            {
                "path": str(full_path),
                "display_name": full_path.name,
                "relative_name": full_path.name,
            }
        )

    return {
        "selection_kind": "file",
        "track_name_hint": None,
        "files": files,
    }


def build_save_target_payload(path, selection_kind):
    if not path:
        return {"selection_kind": selection_kind, "path": None}
    return {"selection_kind": selection_kind, "path": str(Path(path))}


class DesktopBridge:
    def __init__(self, webview_module):
        self._webview = webview_module
        self._window = None

    def attach_window(self, window):
        self._window = window

    def pick_media_source(self, media_type, selection_kind):
        if not self._window:
            return {"error": "Desktop window is not ready", "files": []}

        if media_type not in ALLOWED_EXTENSIONS:
            return {"error": f"Unsupported media type: {media_type}", "files": []}

        if selection_kind == "directory":
            dialog_type = getattr(
                self._webview,
                "FOLDER_DIALOG",
                getattr(self._webview, "DIRECTORY_DIALOG", None),
            )
            if dialog_type is None:
                return {"error": "Folder dialog is not supported by this pywebview build", "files": []}

            result = self._window.create_file_dialog(dialog_type)
            paths = normalize_dialog_result(result)
            if not paths:
                return {"selection_kind": "directory", "track_name_hint": None, "files": []}
            return build_directory_selection_payload(paths[0], media_type)

        if selection_kind == "file":
            file_types = self._build_file_types(media_type)
            result = self._window.create_file_dialog(
                self._webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=file_types,
            )
            paths = normalize_dialog_result(result)
            return build_file_selection_payload(paths, media_type)

        return {"error": f"Unsupported selection kind: {selection_kind}", "files": []}

    def pick_merge_output(self, video_count, suggested_name):
        if not self._window:
            return {"error": "Desktop window is not ready", "path": None}

        if video_count > 1:
            dialog_type = getattr(
                self._webview,
                "FOLDER_DIALOG",
                getattr(self._webview, "DIRECTORY_DIALOG", None),
            )
            if dialog_type is None:
                return {"error": "Folder dialog is not supported by this pywebview build", "path": None}

            result = self._window.create_file_dialog(dialog_type)
            paths = normalize_dialog_result(result)
            return build_save_target_payload(paths[0] if paths else None, "directory")

        save_dialog = getattr(self._webview, "SAVE_DIALOG", None)
        if save_dialog is None:
            return {"error": "Save dialog is not supported by this pywebview build", "path": None}

        result = self._window.create_file_dialog(
            save_dialog,
            save_filename=suggested_name or "muxed_output.mkv",
            file_types=["Matroska video (*.mkv)"],
        )
        paths = normalize_dialog_result(result)
        return build_save_target_payload(paths[0] if paths else None, "file")

    def _build_file_types(self, media_type):
        if media_type == "audio":
            return ["Audio tracks (*.mka)"]
        if media_type == "subtitle":
            return ["Subtitle files (*.srt;*.ass;*.vtt)"]
        return []
