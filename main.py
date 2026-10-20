"""A local launcher for installing AltStore and checking an iPad."""

import json
import shlex
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IPA = ROOT / "resource" / "AltStore.ipa"
ILOADER_RPM = ROOT / "resource" / "iloader-2.3.9-x86_64.rpm"
SERVERS = {
    "Jkcoxson (Mac)": "https://mac-ani.jkcoxson.com",
    "Jkcoxson (Windows)": "https://ani.jkcoxson.com",
    "StikStore (secondary)": "https://ani2.stikstore.app",
}


@dataclass
class Device:
    identifier: str
    name: str
    trusted: bool


def run_tool(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, timeout=10)


def read_devices():
    if not all(shutil.which(tool) for tool in ("idevice_id", "ideviceinfo")):
        return [], "tools"
    try:
        result = run_tool(["idevice_id", "-l"])
        if result.returncode:
            return [], "service"
        devices = []
        for identifier in result.stdout.splitlines():
            if not identifier.strip():
                continue
            info = run_tool(["ideviceinfo", "-u", identifier, "-k", "DeviceName"])
            name = "".join(c for c in info.stdout.strip() if c.isprintable())[:80]
            devices.append(Device(identifier, name if info.returncode == 0 and name
                                  else "iPad awaiting trust", info.returncode == 0))
        return devices, "" if devices else "disconnected"
    except (OSError, subprocess.SubprocessError):
        return [], "unavailable"


def connection_help(problem):
    if problem == "tools":
        print("Install the iPad connection tools, then return here:")
        print("  sudo dnf install libimobiledevice-utils usbmuxd")
    elif problem == "service":
        print("The USB connection service is unavailable. In another terminal, run:")
        print("  sudo systemctl restart usbmuxd")
    elif problem == "unavailable":
        print("The connection check did not finish. Reconnect the USB cable and try again.")
    else:
        print("Connect your iPad with a data cable, unlock it, and tap Trust if asked.")


def show_menu(devices, problem):
    print("\nAltStore for Linux")
    print("Install apps and check your iPad connection.\n")
    if devices:
        for device in devices:
            state = "Connected" if device.trusted else "Trust needed; choose option 2"
            name = device.name if len(device.name) <= 38 else device.name[:37] + "…"
            print(f"  iPad       {name} — {state}")
    else:
        state = {"tools": "Connection tools needed", "service": "USB service unavailable",
                 "unavailable": "Connection check unavailable"}.get(problem, "Not connected")
        print(f"  iPad       {state}")
    print("  iLoader    " + ("Installed" if shutil.which("iloader") else "Setup needed"))
    print("  AltStore   " + ("IPA ready" if IPA.is_file() and zipfile.is_zipfile(IPA)
                              else "IPA file needed"))
    print("\n  1  Install AltStore with iLoader")
    print("  2  Check connection / pair iPad")
    print("  3  Troubleshoot sign-in")
    print("  4  Advanced AltServer controls")
    print("  q  Quit\n")


def install_altstore():
    executable = shutil.which("iloader")
    if not executable:
        print("Install iLoader first:")
        if ILOADER_RPM.is_file():
            print(f"  sudo dnf install {shlex.quote(str(ILOADER_RPM))}")
        else:
            print("  Download the Fedora RPM from https://github.com/nab138/iloader/releases")
        return
    if not IPA.is_file() or not zipfile.is_zipfile(IPA):
        print("A valid AltStore IPA is needed before installation.")
        print(f"Place AltStore.ipa in: {IPA.parent}")
        print("Official download: https://altstore.io")
        return
    print("\nContinue in iLoader:")
    print("  1. Keep the iPad connected and unlocked.")
    print("  2. Select your iPad, sign in if needed, and choose Import IPA.")
    print("  3. Press Ctrl+L in the file picker and paste this path:\n")
    print(f"     {IPA}\n")
    print("Keep the Anisette server that worked for your account.")
    print("Account details and verification codes are entered only in iLoader.")
    subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    print("\nAfter installation: open AltStore on your iPad. If asked, trust your developer")
    print("profile in Settings → General → VPN & Device Management, and enable")
    print("Developer Mode in Settings → Privacy & Security.")


def pair_ipad():
    devices, problem = read_devices()
    if not devices:
        connection_help(problem)
        return
    if not shutil.which("idevicepair"):
        connection_help("tools")
        return
    selected = devices[0]
    if len(devices) > 1:
        for index, device in enumerate(devices, 1):
            print(f"  {index}  {device.name}")
        answer = input("Choose a device number, or q to go back: ").strip()
        if answer.lower() == "q":
            return
        if not answer.isdecimal() or not 1 <= int(answer) <= len(devices):
            print("Choose one of the device numbers shown.")
            return
        selected = devices[int(answer) - 1]
    if selected.trusted:
        print(f"{selected.name} is connected and trusted. Choose option 1 to install AltStore.")
        return
    print("Keep your iPad unlocked and accept the Trust prompt on its screen.")
    result = run_tool(["idevicepair", "-u", selected.identifier, "pair"])
    if result.returncode == 0:
        print("Pairing completed. Choose option 1 to install AltStore.")
    else:
        print("Pairing is still pending. Tap Trust on the iPad, then choose option 2 again.")


def server_status(address):
    try:
        with urllib.request.urlopen(address + "/v3/client_info", timeout=5) as response:
            data = json.load(response)
        if isinstance(data, dict) and data.get("client_info") and data.get("user_agent"):
            return "Reachable"
        return "Unexpected response"
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        return f"Unavailable (HTTP {code})"
    except (OSError, ValueError):
        return "Could not connect"


def troubleshoot_sign_in():
    print("\nChecking Anisette services (no account details are sent)...", flush=True)
    for name, address in SERVERS.items():
        print(f"  {name}: {server_status(address)}", flush=True)
    print("\nReachable means the helper answered; Apple sign-in can still fail.")
    print("  Helper 502/503: choose a reachable server in iLoader → Settings.")
    print("  Apple -80045: Apple rejected the sign-in. This code alone does not explain why.")
    print("  Apple 503 after a code: the follow-up sign-in failed. Keep the server that")
    print("    reached verification, restart iLoader, and retry once. If it repeats, pause.")
    print("  Your password and verification codes belong in iLoader, never in error reports.")


def advanced_controls():
    print("\nAdvanced mode starts the older AltServer and its local authentication helper.")
    print("Use option 1 in this menu for the iLoader installation flow.")
    if input("Start advanced mode? [y/N]: ").strip().lower() not in ("y", "yes"):
        return
    try:
        import altserver
        altserver.main()
    except ModuleNotFoundError:
        print("Advanced mode needs Python Requests: sudo dnf install python3-requests")
    except SystemExit as error:
        if isinstance(error.code, str):
            print(error.code)
        print("Advanced mode ended. Returning to the main menu.")


def main():
    actions = {
        "1": install_altstore, "i": install_altstore, "install": install_altstore,
        "2": pair_ipad, "p": pair_ipad, "pair": pair_ipad,
        "3": troubleshoot_sign_in, "d": troubleshoot_sign_in,
        "4": advanced_controls, "a": advanced_controls,
    }
    try:
        while True:
            devices, problem = read_devices()
            show_menu(devices, problem)
            choice = input("Choose 1–4, or q to quit: ").strip().lower()
            if choice in ("q", "e", "exit", "quit"):
                break
            if choice in ("", "h", "help", "r", "refresh"):
                continue
            action = actions.get(choice)
            if not action:
                print("Choose 1, 2, 3, 4, or q. You can also use i to install or p to pair.")
                continue
            try:
                action()
            except (OSError, subprocess.SubprocessError, RuntimeError):
                print("That action could not finish. Check its required tools and try again.")
            input("\nPress Enter to return to the menu: ")
    except (EOFError, KeyboardInterrupt):
        pass
    print("\nGoodbye.")


if __name__ == "__main__":
    main()
