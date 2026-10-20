import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import altserver as main


class RepairChecks(unittest.TestCase):
    def test_failed_download_preserves_existing_file(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("404")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "AltServer"
            path.write_bytes(b"existing")
            with patch.object(main.requests, "get", return_value=response):
                with self.assertRaises(requests.HTTPError):
                    main.DownloadResource("https://example.invalid", str(path))
            self.assertEqual(path.read_bytes(), b"existing")

    def test_netmuxd_archive_extracts_only_executable(self):
        data = b"\x7fELFtest"
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode="w:gz") as archive:
            member = tarfile.TarInfo("../../netmuxd")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        response = Mock(content=archive_bytes.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "netmuxd")
            with patch.object(main, "NETMUXD_PATH", path), patch.object(
                main.requests, "get", return_value=response
            ):
                main.DownloadResource("https://example.invalid", path)
            self.assertEqual(Path(path).read_bytes(), data)

    def test_invalid_resource_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "AltServer")
            with patch.object(main.requests, "get", return_value=Mock(content=b"Not Found")):
                with self.assertRaises(ValueError):
                    main.DownloadResource("https://example.invalid", path)
            self.assertFalse(Path(path).exists())

    def test_interrupt_exits_device_selection(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with self.assertRaises(SystemExit):
                main.InstallationManager().selectDevice([])

    def test_unavailable_usbmuxd_does_not_become_a_fake_device(self):
        result = Mock(returncode=255, stdout="", stderr="Unable to retrieve device list")
        with patch.object(main.subprocess, "run", return_value=result):
            self.assertEqual(main.DeviceManager().getDevices(), [])

    def test_password_and_ipa_path_are_literal_arguments(self):
        installer = main.InstallationManager()
        installer.selectedDevice = main.iDevice("test", "test-udid")
        installer.account = "test@example.invalid"
        installer.password = "test'$(false)"
        installer.filePath = "/tmp/example app.ipa"
        with patch.object(main.subprocess, "run") as run:
            installer.run()
        self.assertEqual(run.call_args.args[0][-3:],
                         ["-p", installer.password, installer.filePath])
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs["env"]["TZ"], "UTC")


if __name__ == "__main__":
    unittest.main()
