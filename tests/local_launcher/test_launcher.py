import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "launcher", ROOT / "deployment/local/run.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def args(self, mode="bundled"):
        from argparse import Namespace

        return Namespace(
            mode=mode,
            state=Path("/tmp/launcher-tests"),
            hub_port=8099,
            helios_ui_port=8100,
            helios_api_port=8101,
            helios_ui_origin=None,
            helios_api_origin=None,
        )

    def test_owned_checks_start_and_command_identity(self):
        with patch.object(
            launcher, "command_identity", return_value="different-process"
        ):
            self.assertFalse(launcher.owned(dict(pid=123, identity="original-process")))
        with patch.object(
            launcher, "command_identity", return_value="original-process"
        ):
            self.assertTrue(launcher.owned(dict(pid=123, identity="original-process")))

    def test_stop_terminates_owned_child_and_preserves_foreign_child(self):
        owned_child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"]
        )
        foreign_child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"]
        )
        try:
            record = dict(
                pid=owned_child.pid, identity=launcher.command_identity(owned_child.pid)
            )
            foreign = dict(pid=foreign_child.pid, identity="previous owner")
            launcher.stop_records(dict(processes=[record, foreign]))
            self.assertIsNotNone(owned_child.poll())
            self.assertIsNone(foreign_child.poll())
        finally:
            for child in (owned_child, foreign_child):
                if child.poll() is None:
                    child.terminate()
                child.wait()

    def test_stop_does_not_signal_unowned_pid(self):
        with patch.object(launcher, "owned", return_value=False), patch.object(
            launcher.os, "kill"
        ) as kill:
            launcher.stop_records(dict(processes=[dict(pid=123, identity="old")]))
            kill.assert_not_called()

    def test_occupied_port_is_rejected(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen()
            with self.assertRaisesRegex(RuntimeError, "occupied"):
                launcher.require_free(sock.getsockname()[1])

    def test_lock_mismatch_is_rejected(self):
        with patch.object(
            launcher.subprocess,
            "check_output",
            side_effect=[str(ROOT / "external/helios"), "", "wrong\n"],
        ):
            with self.assertRaisesRegex(RuntimeError, "lock mismatch"):
                launcher.validate_lock()

    def test_dirty_checkout_is_rejected(self):
        with patch.object(
            launcher.subprocess,
            "check_output",
            side_effect=[str(ROOT / "external/helios"), " M tracked.py"],
        ):
            with self.assertRaisesRegex(RuntimeError, "tracked changes"):
                launcher.validate_lock()

    def test_missing_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "deployment").mkdir()
            (root / "deployment/provider-lock.json").write_text(
                (ROOT / "deployment/provider-lock.json").read_text()
            )
            with self.assertRaisesRegex(RuntimeError, "checkout missing"):
                launcher.validate_lock(root)

    def test_modes_do_not_silently_start_bundled_provider(self):
        for mode in ("external", "builtin_only"):
            with patch.object(
                launcher,
                "validate_lock",
                side_effect=AssertionError("provider touched"),
            ):
                self.assertEqual(
                    [s[0] for s in launcher.plan(self.args(mode))], ["hub"]
                )
        self.assertEqual(
            [s[0] for s in launcher.plan(self.args())],
            ["hub", "helios-api", "helios-ui"],
        )

    def test_external_requires_explicit_origins(self):
        with self.assertRaisesRegex(RuntimeError, "requires"):
            launcher.register(self.args("external"))

    def test_child_environment_and_paths_are_separate(self):
        with patch.dict(
            launcher.os.environ, {"PYTHONPATH": "/wrong", "HELIOS_ROOT": "/wrong"}
        ):
            specs = launcher.plan(self.args())
        self.assertNotIn("PYTHONPATH", specs[1][4])
        self.assertEqual(specs[1][4]["HELIOS_ROOT"], "/tmp/launcher-tests/helios")
        self.assertEqual(specs[2][4]["HELIOS_API_URL"], "http://127.0.0.1:8101")
        self.assertEqual(specs[1][4]["HELIOS_UI_ORIGINS"], "http://127.0.0.1:8100")
        self.assertNotEqual(specs[0][2], specs[1][2])

    def test_existing_registry_origins_are_preserved(self):
        sys.path.insert(0, str(ROOT))
        from semantic_hub.providers.registry import Registry

        with tempfile.TemporaryDirectory() as temp:
            args = self.args("external")
            args.state = Path(temp)
            registry = Registry(args.state / "hub", local=True)
            registry.save_provider(
                "helios-local",
                "Local Helios",
                "https://old-ui.example",
                "https://old-api.example",
            )
            args.helios_ui_origin, args.helios_api_origin = (
                "https://new-ui.example",
                "https://new-api.example",
            )
            with self.assertRaises(ValueError):
                launcher.register(args)
            self.assertEqual(
                registry.provider("helios-local")["ui_origin"], "https://old-ui.example"
            )


if __name__ == "__main__":
    unittest.main()
