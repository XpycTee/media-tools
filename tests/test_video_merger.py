import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "utils" / "video_merger.py"
SPEC = importlib.util.spec_from_file_location("video_merger_module", MODULE_PATH)
video_merger = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(video_merger)


class VideoMergerTests(unittest.TestCase):
    def test_find_file_returns_none_for_relative_path_without_video_root(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIDEO_ROOT", None)
            self.assertIsNone(video_merger.find_file("clip.mkv"))

    def test_find_file_keeps_absolute_path_without_video_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "clip.mkv"
            file_path.write_bytes(b"video")

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VIDEO_ROOT", None)
                self.assertEqual(video_merger.find_file(str(file_path)), str(file_path))

    def test_is_video_root_configured_reflects_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"VIDEO_ROOT": temp_dir}, clear=False):
                self.assertTrue(video_merger.is_video_root_configured())

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VIDEO_ROOT", None)
                with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                    self.assertFalse(video_merger.is_video_root_configured())
