import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "desktop_bridge.py"
SPEC = importlib.util.spec_from_file_location("desktop_bridge_module", MODULE_PATH)
desktop_bridge = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(desktop_bridge)


class DesktopBridgeTests(unittest.TestCase):
    def test_normalize_dialog_result_handles_scalar_string(self):
        self.assertEqual(
            desktop_bridge.normalize_dialog_result("/tmp/example.mka"),
            ["/tmp/example.mka"],
        )

    def test_is_allowed_media_file_checks_extension(self):
        self.assertTrue(desktop_bridge.is_allowed_media_file("/tmp/example.mka", "audio"))
        self.assertFalse(desktop_bridge.is_allowed_media_file("/tmp/example.mp3", "audio"))

    def test_build_file_selection_payload_filters_unexpected_extensions(self):
        payload = desktop_bridge.build_file_selection_payload(
            ["/tmp/one.mka", "/tmp/two.txt"],
            "audio",
        )
        self.assertEqual(payload["selection_kind"], "file")
        self.assertEqual(payload["track_name_hint"], None)
        self.assertEqual(
            payload["files"],
            [
                {
                    "path": "/tmp/one.mka",
                    "display_name": "one.mka",
                    "relative_name": "one.mka",
                }
            ],
        )

    def test_build_directory_selection_payload_uses_folder_name_as_hint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "English Dub"
            root.mkdir()
            (root / "01.mka").write_bytes(b"")
            (root / "ignore.txt").write_text("x", encoding="utf-8")

            payload = desktop_bridge.build_directory_selection_payload(root, "audio")

        self.assertEqual(payload["selection_kind"], "directory")
        self.assertEqual(payload["track_name_hint"], "English Dub")
        self.assertEqual(len(payload["files"]), 1)
        self.assertEqual(payload["files"][0]["display_name"], "01.mka")

    def test_build_save_target_payload_normalizes_path(self):
        payload = desktop_bridge.build_save_target_payload("/tmp/output.mkv", "file")
        self.assertEqual(payload, {"selection_kind": "file", "path": "/tmp/output.mkv"})

    def test_pick_merge_output_uses_save_dialog_for_single_video(self):
        webview_module = type("WebViewStub", (), {"SAVE_DIALOG": "save"})
        window = mock.Mock()
        window.create_file_dialog.return_value = "/tmp/output.mkv"
        bridge = desktop_bridge.DesktopBridge(webview_module)
        bridge.attach_window(window)

        payload = bridge.pick_merge_output(1, "muxed_video.mkv")

        self.assertEqual(payload, {"selection_kind": "file", "path": "/tmp/output.mkv"})
        window.create_file_dialog.assert_called_once_with(
            "save",
            save_filename="muxed_video.mkv",
            file_types=["Matroska video (*.mkv)"],
        )

    def test_pick_merge_output_uses_directory_dialog_for_multiple_videos(self):
        webview_module = type("WebViewStub", (), {"FOLDER_DIALOG": "folder"})
        window = mock.Mock()
        window.create_file_dialog.return_value = "/tmp/exports"
        bridge = desktop_bridge.DesktopBridge(webview_module)
        bridge.attach_window(window)

        payload = bridge.pick_merge_output(3, "ignored.mkv")

        self.assertEqual(payload, {"selection_kind": "directory", "path": "/tmp/exports"})
        window.create_file_dialog.assert_called_once_with("folder")


if __name__ == "__main__":
    unittest.main()
