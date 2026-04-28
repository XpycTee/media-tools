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
    def _get_flag_value_pairs(self, cmd, flag_prefix):
        pairs = []
        for index, value in enumerate(cmd[:-1]):
            if value.startswith(flag_prefix):
                pairs.append([value, cmd[index + 1]])
        return pairs

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

    def test_build_ffmpeg_command_defaults_first_subtitle_when_none_marked(self):
        cmd, output_file = video_merger.build_ffmpeg_command(
            "/media/video.mkv",
            [],
            [
                {"name": "Sub 1", "file": "/media/sub1.srt"},
                {"name": "Sub 2", "file": "/media/sub2.srt"},
            ],
        )

        self.assertEqual(output_file, "/media/muxed_video.mkv")
        disposition_pairs = self._get_flag_value_pairs(cmd, "-disposition:s:")
        self.assertIn(["-disposition:s:0", "default"], disposition_pairs)
        self.assertIn(["-disposition:s:1", "0"], disposition_pairs)

    def test_build_ffmpeg_command_honors_explicit_default_subtitle(self):
        cmd, _ = video_merger.build_ffmpeg_command(
            "/media/video.mkv",
            [],
            [
                {"name": "Sub 1", "file": "/media/sub1.srt"},
                {"name": "Sub 2", "file": "/media/sub2.srt", "default": True},
            ],
        )

        disposition_pairs = self._get_flag_value_pairs(cmd, "-disposition:s:")
        self.assertIn(["-disposition:s:0", "0"], disposition_pairs)
        self.assertIn(["-disposition:s:1", "default"], disposition_pairs)
