import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import altserver as main


class RepairChecks(unittest.TestCase):
    def test_remote_anisette_is_used_by_children_without_starting_podman(self):
        url = "https://example.invalid/anisette"
        response = Mock()
        response.json.return_value = {
            "X-Apple-I-MD": "test-otp",
            "X-Apple-I-MD-M": "test-machine",
            "X-MMe-Client-Info": "test-client",
        }
        with patch.dict(os.environ), patch.object(main.requests, "get", return_value=response) as get, \
                patch.object(main.os, "makedirs") as mkdir, \
                patch.object(main.subprocess, "run") as run, \
                patch.object(main.subprocess, "Popen") as popen:
            helper = main.AnisetteServer(url=url)
            daemon = main.AltServerDaemon()
            self.assertEqual(popen.call_args.kwargs["env"]["ALTSERVER_ANISETTE_SERVER"], url)
            installer = main.InstallationManager()
            installer.selectedDevice = main.iDevice("test", "test-udid")
            installer.account = "test@example.invalid"
            installer.password = "test-password"
            installer.filePath = "/tmp/test.ipa"
            installer.run()
            self.assertEqual(run.call_args.kwargs["env"]["ALTSERVER_ANISETTE_SERVER"], url)
            run.reset_mock()
            helper.kill()
            daemon.kill()
            get.assert_called_once_with(url, timeout=10)
            response.raise_for_status.assert_called_once()
            mkdir.assert_not_called()
            run.assert_not_called()

    def test_remote_anisette_rejects_metadata_instead_of_signing_headers(self):
        response = Mock()
        response.json.return_value = {"client_info": "test-client", "user_agent": "test-agent"}
        with patch.dict(os.environ), patch.object(main.requests, "get", return_value=response), \
                patch.object(main.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "legacy signing headers"):
                main.AnisetteServer(url="https://example.invalid")
            run.assert_not_called()

    def test_remote_anisette_rejects_invalid_url_before_network_request(self):
        with patch.object(main.requests, "get") as get:
            for url in ("file:///tmp/data", "https://user:password@example.invalid", "not-a-url"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    main.AnisetteServer(url=url)
            get.assert_not_called()

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
