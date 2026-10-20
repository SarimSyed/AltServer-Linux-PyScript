import io
import json
import tempfile
import unittest
import urllib.error
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import main


class LauncherChecks(unittest.TestCase):
    def test_start_and_quit_do_not_launch_helpers_or_contact_servers(self):
        output = io.StringIO()
        with patch.object(main, "read_devices", return_value=([], "disconnected")), \
                patch("builtins.input", return_value="q"), \
                patch.object(main.subprocess, "Popen") as launch, \
                patch.object(main.urllib.request, "urlopen") as request, redirect_stdout(output):
            main.main()
        self.assertIn("Install AltStore with iLoader", output.getvalue())
        self.assertIn("Goodbye", output.getvalue())
        launch.assert_not_called()
        request.assert_not_called()

    def test_invalid_choice_recovers_and_eof_exits_cleanly(self):
        output = io.StringIO()
        with patch.object(main, "read_devices", return_value=([], "tools")), \
                patch("builtins.input", side_effect=["wrong", EOFError]), redirect_stdout(output):
            main.main()
        self.assertIn("Choose 1, 2, 3, 4, or q", output.getvalue())
        self.assertIn("Goodbye", output.getvalue())

    def test_device_identifiers_and_command_errors_are_not_displayed(self):
        results = [Mock(returncode=0, stdout="private-device-identifier\n"),
                   Mock(returncode=1, stdout="", stderr="private device information")]
        output = io.StringIO()
        with patch.object(main.shutil, "which", return_value="/usr/bin/tool"), \
                patch.object(main, "run_tool", side_effect=results), redirect_stdout(output):
            devices, problem = main.read_devices()
            main.show_menu(devices, problem)
        self.assertIn("Trust needed", output.getvalue())
        self.assertNotIn("private", output.getvalue())
        self.assertFalse(devices[0].trusted)

    def test_pairing_uses_selected_device_and_hides_command_output(self):
        device = main.Device("private-id", "Test iPad", False)
        output = io.StringIO()
        with patch.object(main, "read_devices", return_value=([device], "")), \
                patch.object(main.shutil, "which", return_value="/usr/bin/idevicepair"), \
                patch.object(main, "run_tool", return_value=Mock(returncode=0, stdout="private-id")) as run, \
                redirect_stdout(output):
            main.pair_ipad()
        run.assert_called_once_with(["idevicepair", "-u", "private-id", "pair"])
        self.assertIn("Pairing completed", output.getvalue())
        self.assertNotIn("private-id", output.getvalue())

    def test_install_opens_iloader_without_asking_for_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            ipa = Path(directory) / "AltStore.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("Payload/AltStore.app/Info.plist", "test")
            output = io.StringIO()
            with patch.object(main, "IPA", ipa), \
                    patch.object(main.shutil, "which", return_value="/usr/bin/iloader"), \
                    patch.object(main.subprocess, "Popen") as launch, \
                    patch("builtins.input") as ask, redirect_stdout(output):
                main.install_altstore()
            self.assertEqual(launch.call_args.args[0], ["/usr/bin/iloader"])
            self.assertNotIn("shell", launch.call_args.kwargs)
            self.assertIn(str(ipa), output.getvalue())
            self.assertIn("Import IPA", output.getvalue())
            ask.assert_not_called()

    def test_missing_installer_has_an_actionable_setup_command(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "iloader.rpm"
            package.touch()
            output = io.StringIO()
            with patch.object(main, "ILOADER_RPM", package), \
                    patch.object(main.shutil, "which", return_value=None), \
                    patch.object(main.subprocess, "Popen") as launch, redirect_stdout(output):
                main.install_altstore()
            self.assertIn("sudo dnf install", output.getvalue())
            launch.assert_not_called()

    def test_invalid_ipa_does_not_launch_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            ipa = Path(directory) / "AltStore.ipa"
            ipa.write_text("Not Found")
            with patch.object(main, "IPA", ipa), \
                    patch.object(main.shutil, "which", return_value="/usr/bin/iloader"), \
                    patch.object(main.subprocess, "Popen") as launch, redirect_stdout(io.StringIO()):
                main.install_altstore()
            launch.assert_not_called()

    def test_server_status_handles_outage_and_checks_metadata_only(self):
        url = "https://example.invalid"
        error = urllib.error.HTTPError(url, 502, "Bad Gateway", {}, None)
        with patch.object(main.urllib.request, "urlopen", side_effect=error) as request:
            self.assertEqual(main.server_status(url), "Unavailable (HTTP 502)")
        request.assert_called_once_with(url + "/v3/client_info", timeout=5)
        metadata = io.StringIO(json.dumps({"client_info": "public", "user_agent": "public"}))
        with patch.object(main.urllib.request, "urlopen", return_value=metadata):
            self.assertEqual(main.server_status(url), "Reachable")

    def test_advanced_mode_can_be_cancelled_without_starting_anything(self):
        with patch("builtins.input", return_value="n"), \
                patch.object(main.subprocess, "Popen") as launch, redirect_stdout(io.StringIO()):
            main.advanced_controls()
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
