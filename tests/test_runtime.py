import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "runtime.py"
SPEC = importlib.util.spec_from_file_location("runtime_module", MODULE_PATH)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runtime)


class RuntimeTests(unittest.TestCase):
    def test_get_start_url_normalizes_path(self):
        self.assertEqual(
            runtime.get_start_url("127.0.0.1", 5000, "video"),
            "http://127.0.0.1:5000/video",
        )

    def test_choose_port_falls_back_when_port_is_taken(self):
        fake_socket = MagicMock()
        fake_socket.bind.side_effect = OSError("busy")
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_socket
        fake_context.__exit__.return_value = False

        with (
            patch.object(runtime.socket, "socket", return_value=fake_context),
            patch.object(runtime, "find_free_port", return_value=55001),
        ):
            next_port = runtime.choose_port("127.0.0.1", 5000)

        self.assertEqual(next_port, 55001)

    def test_choose_port_keeps_requested_port_when_available(self):
        fake_socket = MagicMock()
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_socket
        fake_context.__exit__.return_value = False

        with patch.object(runtime.socket, "socket", return_value=fake_context):
            self.assertEqual(runtime.choose_port("127.0.0.1", 5000), 5000)

    def test_get_resource_path_points_into_repo_in_dev_mode(self):
        path = runtime.get_resource_path("app", "templates")
        self.assertTrue(path.endswith("app/templates"))


if __name__ == "__main__":
    unittest.main()
