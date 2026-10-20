import os
import argparse
import json
import shutil
import getpass
import datetime
import platform
import requests
import subprocess
import io
import tarfile
import time
from ctypes import CDLL
from urllib.parse import urlsplit


# Developer settings
GITHUB_API_TOKEN = ""
headers = {'Authorization': 'token ' + GITHUB_API_TOKEN}
CUSTOM_HEADERS_ENABLED = False
DEBUGGING = False
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# ANISETTE-SERVER
ANISETTE_HOST = "127.0.0.1"
ANISETTE_PORT = 6969

# ARCH
ARCH = platform.machine()
if ARCH == "armv7l":
    ARCH = "armv7"
NETMUXD_AVAILABLE_ARCHS = ("x86_64", "aarch64", "armv7")
NETMUXD_IS_AVAILABLE = ARCH in NETMUXD_AVAILABLE_ARCHS
Netmuxd_is_on = False  # Use USB for the initial installation.


# DIRECTORY
CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
RESOURCE_DIRECTORY = os.path.join(CURRENT_DIRECTORY, "resource")

# VERSIONS
"""
Versions will be fetch with FetchVersion()
"""
Latest_AltServer_Version = ""
Latest_AltStore_Version = ""
Latest_Netmuxd_Version = ""
Latest_Anisette_Server_Version = ""
Latest_Script_Version = ""

# PATH AND URL
"""
URL value default is "" , value will be update with FetchVersion()
"""
VERSION_JSON_PATH = os.path.join(CURRENT_DIRECTORY, "version.json")

ALTSERVER_PATH = os.path.join(RESOURCE_DIRECTORY, "AltServer")
Altserver_URL = ""

ALTSTORE_PATH = os.path.join(RESOURCE_DIRECTORY, "AltStore.ipa")
AltStore_URL = ""

NETMUXD_PATH = os.path.join(RESOURCE_DIRECTORY, "netmuxd")
Netmuxd_URL = ""

ANISETTE_SERVER_PATH = os.path.join(RESOURCE_DIRECTORY, "anisette-server")
Anisette_Server_URL = ""

SCRIPT_PATH = os.path.join(CURRENT_DIRECTORY, "main.py")
SCRIPT_URL = "https://raw.githubusercontent.com/powenn/AltServer-Linux-PyScript/rewrite/main.py"

# UPDATABLE BOOLS
"""
Default is false , value will be update with CheckUpdate()
"""
AltServer_Is_Updatable = False
AltStore_Is_Updatable = False
Nermuxd_Is_Updatable = False
Anisette_Server_Is_Updatable = False
Script_Is_Updatable = False


Version_Fetched = False


def getAnswer(text):
    try:
        return input(text)
    except (KeyboardInterrupt, EOFError):
        print("\nExiting")
        raise SystemExit(0)


def DebugPrint(msg):
    now = datetime.datetime.now().strftime(TIME_FORMAT)
    if DEBUGGING:
        print(f"[DEBUG] {now}\n== {msg} ==")


def FetchVersion() -> dict:
    print("Fetching version ...")

    global Latest_AltServer_Version, Latest_AltStore_Version, Latest_Anisette_Server_Version, Latest_Netmuxd_Version, Latest_Script_Version

    AltStore_Response = requests.get(
        "https://cdn.altstore.io/file/altstore/apps.json").json()["apps"][0]["versions"][0]
    Latest_AltStore_Version = AltStore_Response["version"]

    Latest_AltServer_Version = requests.get(
        "https://api.github.com/repos/NyaMisty/AltServer-Linux/releases/latest", headers=headers if CUSTOM_HEADERS_ENABLED else "").json()["tag_name"]
    Latest_Netmuxd_Version = requests.get(
        "https://api.github.com/repos/jkcoxson/netmuxd/releases/latest", headers=headers if CUSTOM_HEADERS_ENABLED else "").json()["tag_name"]
    Latest_Anisette_Server_Version = requests.get(
        "https://api.github.com/repos/Dadoum/Provision/releases/latest", headers=headers if CUSTOM_HEADERS_ENABLED else "").json()["tag_name"]
    Latest_Script_Version = requests.get(
        "https://api.github.com/repos/powenn/AltServer-Linux-PyScript/releases/latest", headers=headers if CUSTOM_HEADERS_ENABLED else "").json()["tag_name"]

    global Altserver_URL, AltStore_URL, Netmuxd_URL, Anisette_Server_URL, Version_Fetched

    Altserver_URL = f"https://github.com/NyaMisty/AltServer-Linux/releases/download/{Latest_AltServer_Version}/AltServer-{ARCH}"
    Netmuxd_URL = f"https://github.com/jkcoxson/netmuxd/releases/download/{Latest_Netmuxd_Version}/netmuxd-{ARCH}-unknown-linux-gnu.tar.gz"
    Anisette_Server_URL = f"https://github.com/Dadoum/Provision/releases/download/{Latest_Anisette_Server_Version}/anisette-server-{ARCH}"
    AltStore_URL = AltStore_Response["downloadURL"]

    Version_Fetched = True

    print("Done")
    json_data = {"AltServer": Latest_AltServer_Version, "AltStore": Latest_AltStore_Version, "Netmuxd": Latest_Netmuxd_Version,
                 "Anisette-Server": Latest_Anisette_Server_Version, "Script": Latest_Script_Version}
    DebugPrint(json_data)
    return json_data


def DownloadResource(url, path):
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    data = response.content
    if path == NETMUXD_PATH:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = [m for m in archive.getmembers()
                       if m.isfile() and os.path.basename(m.name) == "netmuxd"]
            if len(members) != 1:
                raise ValueError("Release archive must contain one netmuxd executable")
            data = archive.extractfile(members[0]).read()
    expected = b"PK" if path == ALTSTORE_PATH else b"\x7fELF"
    if not data.startswith(expected):
        raise ValueError(f"Download is not a valid resource: {os.path.basename(path)}")
    temporary = path + ".part"
    with open(temporary, "wb") as output:
        output.write(data)
    os.replace(temporary, path)


def CheckResource():
    resource_list = os.listdir(RESOURCE_DIRECTORY) if os.path.exists(
        RESOURCE_DIRECTORY) else []
    Resource_Missed = not all(resource in resource_list for resource in [
                              'AltServer', 'anisette-server', 'AltStore.ipa', 'netmuxd'])
    latest_version_json = {}

    DebugPrint(f"RESOURCE_MISSED : {Resource_Missed}")

    if not os.path.exists(VERSION_JSON_PATH):
        print("version.json not exists")
        latest_version_json: dict = FetchVersion()
        DebugPrint(latest_version_json)
        with open(VERSION_JSON_PATH, "w") as outfile:
            json.dump(latest_version_json, outfile)
        # Remove all executable binaries to get new binaries
        if os.path.exists(RESOURCE_DIRECTORY):
            shutil.rmtree(RESOURCE_DIRECTORY)

    if Resource_Missed and not Version_Fetched:
        latest_version_json: dict = FetchVersion()

    global current_version_json
    current_version_json = json.load(open(VERSION_JSON_PATH))
    # Resource dir
    if not os.path.exists(RESOURCE_DIRECTORY):
        print("Creating 'resource' directory")
        os.mkdir(RESOURCE_DIRECTORY)
    # AltServer
    if not os.path.exists(ALTSERVER_PATH):
        print(f"Downloading Altserver {Latest_AltServer_Version}")
        DebugPrint(Altserver_URL)
        DownloadResource(Altserver_URL, ALTSERVER_PATH)
        current_version_json["AltServer"] = Latest_AltServer_Version
    # AltStore
    if not os.path.exists(ALTSTORE_PATH):
        print(f"Downloading AltStore ipa {Latest_AltStore_Version}")
        DebugPrint(AltStore_URL)
        DownloadResource(AltStore_URL, ALTSTORE_PATH)
        current_version_json["AltStore"] = Latest_AltStore_Version
    # Netmuxd
    if not os.path.exists(NETMUXD_PATH) and NETMUXD_IS_AVAILABLE:
        print(f"Downloading netmuxd {Latest_Netmuxd_Version}")
        DebugPrint(Netmuxd_URL)
        DownloadResource(Netmuxd_URL, NETMUXD_PATH)
        current_version_json["Netmuxd"] = Latest_Netmuxd_Version
    # Anisette-Server
    if not os.path.exists(ANISETTE_SERVER_PATH):
        print(f"Downloading anisette-server {Latest_Anisette_Server_Version}")
        DebugPrint(Anisette_Server_URL)
        DownloadResource(Anisette_Server_URL, ANISETTE_SERVER_PATH)
        current_version_json["Anisette-Server"] = Latest_Anisette_Server_Version

    # Write updated json data into version.json
    with open(VERSION_JSON_PATH, "w") as outfile:
        json.dump(current_version_json, outfile)

    if not os.access(ALTSERVER_PATH, os.X_OK):
        print("Setting AltServer exec permission")
        os.chmod(ALTSERVER_PATH, 0o755)
    if os.path.exists(NETMUXD_PATH) and not os.access(NETMUXD_PATH, os.X_OK):
        print("Setting netmuxd exec permission")
        os.chmod(NETMUXD_PATH, 0o755)
    if not os.access(ANISETTE_SERVER_PATH, os.X_OK):
        print("Setting anisette-server permission")
        os.chmod(ANISETTE_SERVER_PATH, 0o755)

    DebugPrint(subprocess.getoutput(f"ls -al {RESOURCE_DIRECTORY}"))


def CheckNetworkConnection() -> bool:
    try:
        requests.get('http://google.com')
        return True
    except:
        return False


def CheckUpdate() -> bool:
    if not Version_Fetched:
        FetchVersion()
    with open(VERSION_JSON_PATH, 'r') as openfile:
        json_data = json.load(openfile)

    Current_Script_Version = json_data["Script"]
    Current_AltServer_Version = json_data["AltServer"]
    Current_AltStore_Version = json_data["AltStore"]
    Current_Netmuxd_Version = json_data["Netmuxd"]
    Current_Anisette_Server_Version = json_data["Anisette-Server"]

    global Script_Is_Updatable, AltServer_Is_Updatable, AltStore_Is_Updatable, Nermuxd_Is_Updatable, Anisette_Server_Is_Updatable
    # script
    if Latest_Script_Version != Current_Script_Version:
        Script_Is_Updatable = True
        print(
            f"Script is updatable , current ver : {Current_Script_Version} , latest ver : {Latest_Script_Version}")
    # altserver
    if Latest_AltServer_Version != Current_AltServer_Version:
        AltServer_Is_Updatable = True
        print(
            f"AltServer is updatable , current ver : {Current_AltServer_Version} , latest ver : {Latest_AltServer_Version}")
    # altstore
    if Latest_AltStore_Version != Current_AltStore_Version:
        AltStore_Is_Updatable = True
        print(
            f"AltStrore is updatable , current ver : {Current_AltStore_Version} , latest ver : {Latest_AltStore_Version}")
    # netmuxd
    if Latest_Netmuxd_Version != Current_Netmuxd_Version:
        Nermuxd_Is_Updatable = True
        print(
            f"Netmuxd is updatable , current ver : {Current_Netmuxd_Version} , latest ver : {Latest_Netmuxd_Version}")
    # anisette server
    if Latest_Anisette_Server_Version != Current_Anisette_Server_Version:
        Anisette_Server_Is_Updatable = True
        print(
            f"Anisette-Server is updatable , current ver : {Current_Anisette_Server_Version} , latest ver : {Latest_Anisette_Server_Version}")

    return AltServer_Is_Updatable or AltStore_Is_Updatable or Nermuxd_Is_Updatable or Anisette_Server_Is_Updatable or Script_Is_Updatable


def RemoveOutdatedResource():
    if AltServer_Is_Updatable:
        os.remove(ALTSERVER_PATH)
    if AltStore_Is_Updatable:
        os.remove(ALTSTORE_PATH)
    if Anisette_Server_Is_Updatable:
        os.remove(ANISETTE_SERVER_PATH)
    if Nermuxd_Is_Updatable:
        os.remove(NETMUXD_PATH)


def Update():
    if CheckUpdate():
        answer = getAnswer("Update available, Update now ? (y/n) : ").lower()
        if answer == 'y':
            # Remove outdated resource
            print("Removing outdated resource ...")
            RemoveOutdatedResource()
            # Update script
            if Script_Is_Updatable:
                print(
                    f"Downloading the lastest script [{Latest_Script_Version}] ...")
                response = requests.get(
                    "https://raw.githubusercontent.com/powenn/AltServer-Linux-PyScript/rewrite/main.py")
                open(SCRIPT_PATH, "wb").write(response.content)
                current_version_json["Script"] = Latest_Script_Version
                with open(VERSION_JSON_PATH, "w") as outfile:
                    json.dump(current_version_json, outfile)

            print("\n\nUpdate done\nYou can find update log in https://github.com/powenn/AltServer-Linux-PyScript/releases\nScript requires restart to apply updates\nUse `e` option to exit the script\n\n")
    else:
        print("All resources and script are up to dated :)")


class AnisetteServer:
    # The upstream native helper requires an older OpenSSL than Fedora provides.
    image = "localhost/altstore-anisette:fedora"

    def __init__(self, host=ANISETTE_HOST, port=ANISETTE_PORT, url=None):
        self.local = url is None
        if not self.local:
            parsed = urlsplit(url)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.query or parsed.fragment):
                raise ValueError("Use an HTTP(S) Anisette URL without credentials, query, or fragment")
            self.url = url
            try:
                response = requests.get(self.url, timeout=10)
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError):
                raise RuntimeError("Cannot read the remote Anisette endpoint; check its URL and availability") from None
            required = ("X-Apple-I-MD", "X-Apple-I-MD-M", "X-MMe-Client-Info")
            if not isinstance(data, dict) or not all(isinstance(data.get(key), str) and data[key] for key in required):
                raise RuntimeError("Remote endpoint must return legacy signing headers, not v3 metadata")
            os.environ["ALTSERVER_ANISETTE_SERVER"] = self.url
            print(f"Using remote Anisette server: {self.url}")
            return
        self.url = f"http://{host}:{port}"
        os.environ["ALTSERVER_ANISETTE_SERVER"] = self.url
        config = os.path.join(CURRENT_DIRECTORY, "provision-config")
        os.makedirs(config, mode=0o700, exist_ok=True)
        subprocess.run([
            "podman", "run", "--detach", "--replace", "--name", "altstore-anisette",
            "--userns", "keep-id", "--publish", f"{host}:{port}:6969",
            "--volume", f"{config}:/home/Chester/.config/Provision:Z", self.image,
        ], check=True, stdout=subprocess.DEVNULL)
        print("Waiting for local Anisette helper...")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                response = requests.get(self.url, timeout=5)
                response.raise_for_status()
                data = response.json()
                if all(data.get(key) for key in ("X-Apple-I-MD", "X-Apple-I-MD-M")):
                    print("Local Anisette helper ready")
                    return
            except (requests.RequestException, ValueError):
                pass
            time.sleep(1)
        raise RuntimeError("Local Anisette helper did not become ready; inspect podman logs altstore-anisette locally")

    def kill(self):
        if self.local:
            subprocess.run(["podman", "stop", "--time", "1", "altstore-anisette"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class AltServerDaemon:
    def __init__(self):
        self.start()

    def start(self):
        self.altserver = subprocess.Popen([ALTSERVER_PATH], env={**os.environ, "TZ": "UTC"})

    def kill(self):
        self.altserver.terminate()
        self.altserver.wait(timeout=10)

    def restart(self):
        self.kill()
        self.start()


class Netmuxd:
    def __init__(self):
        if Netmuxd_is_on:
            if subprocess.getoutput("echo $(pidof usbmuxd)") != "":
                print(subprocess.getoutput("sudo kill -9 $(pidof usbmuxd)"))
            self.start()

    def start(self):
        self.netmuxd = subprocess.Popen(f"sudo -b {NETMUXD_PATH}", shell=True)

    def kill(self):
        print(subprocess.getoutput("sudo killall netmuxd"))

    def switchWiFi(self):
        global Netmuxd_is_on
        Netmuxd_is_on = True
        DebugPrint(f"NETMUXD : {Netmuxd_is_on}")
        print(subprocess.getoutput("sudo kill -9 $(pidof usbmuxd)"))
        self.kill()
        self.start()

    def switchTether(self):
        global Netmuxd_is_on
        Netmuxd_is_on = False
        DebugPrint(f"NETMUXD : {Netmuxd_is_on}")
        print(subprocess.getoutput("sudo usbmuxd"))
        self.kill()


def getSUDO():
    subprocess.run(["sudo", "-v"], check=True)


class iDevice:
    def __init__(self, name, UDID):
        self.name = name
        self.UDID = UDID


class DeviceManager:
    def __init__(self, devices=[]):
        self.devices = devices

    def getDevices(self) -> list[iDevice]:
        DebugPrint(f"NETMUXD : {Netmuxd_is_on}")
        self.devices = []
        command = ["idevice_id", "-n" if Netmuxd_is_on else "-l"]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            print("Cannot contact usbmuxd. Run: sudo systemctl restart usbmuxd")
            return self.devices
        udids = result.stdout.splitlines()
        if not udids:
            print("No devices found. Connect and unlock your iPad, then tap Trust.")
        for udid in udids:
            command = ["ideviceinfo", "-u", udid, "-k", "DeviceName"]
            if Netmuxd_is_on:
                command.append("-n")
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                print("Device not trusted. Run idevicepair pair, then tap Trust on the iPad.")
                continue
            self.devices.append(iDevice(name=result.stdout.strip(), UDID=udid))
        return self.devices


class InstallationManager:
    def __init__(self):
        pass

    def selectDevice(self, devices: list[iDevice]):
        for i in range(len(devices)):
            print(f"[{i}] : {devices[i].name} , {devices[i].UDID}")
        try:
            index = int(
                getAnswer("Enter the index of the device for installation : "))
            self.selectedDevice = devices[index]
        except (ValueError, IndexError):
            print("Invalid index")
            self.selectedDevice = None

    def getAccount(self):
        ac = getAnswer("Enter your Apple ID : ")
        self.account = ac

    def getPassword(self):
        pd = getpass.getpass("Enter password of the Apple ID : ")
        self.password = pd

    def selectFile(self):
        answer = getAnswer(
            "Do you want to install AltStore ? (y/n) [n for select your own iPA] : ").lower()
        if answer == 'n':
            filePath = getAnswer("Enter the absolute path of the file : ")
            if filePath != "":
                self.filePath = filePath
            else:
                self.filePath = None
                print("No file path entered")
        else:
            self.filePath = ALTSTORE_PATH

    def run(self):
        subprocess.run(
            [ALTSERVER_PATH, "-u", self.selectedDevice.UDID, "-a", self.account,
             "-p", self.password, self.filePath], env={**os.environ, "TZ": "UTC"})

def main(anisette_url=None):
    tools = ["idevice_id", "ideviceinfo", "idevicepair"]
    if anisette_url is None:
        tools.append("podman")
    missing = [name for name in tools
               if not shutil.which(name)]
    if missing:
        raise SystemExit("Missing tools: " + ", ".join(missing) +
                         "\nRun: sudo dnf install libimobiledevice-utils avahi-compat-libdns_sd-devel podman")
    try:
        CDLL("libdns_sd.so")
    except OSError:
        raise SystemExit("Run: sudo dnf install avahi-compat-libdns_sd-devel")
    CheckResource()
    anisetteserver = AnisetteServer(url=anisette_url)
    netmuxd = Netmuxd()
    altserverdaemon = AltServerDaemon()
    device_manager = DeviceManager()
    installaion_manager = InstallationManager()
    print(HELP_MSG)
    try:
        while True:
            option = getAnswer("Enter OPTION to continue : ").lower()

            if option == 'i':
                devices = device_manager.getDevices()
                if len(devices) == 0:
                    continue
                installaion_manager.selectDevice(devices=devices)
                if installaion_manager.selectedDevice == None:
                    continue
                installaion_manager.getAccount()
                installaion_manager.getPassword()
                installaion_manager.selectFile()
                if installaion_manager.filePath == None:
                    continue
                installaion_manager.run()

            elif option == 'w':
                if NETMUXD_IS_AVAILABLE:
                    if not Netmuxd_is_on:
                        getSUDO()
                        netmuxd.switchWiFi()
                        altserverdaemon.restart()
                else:
                    print(f"Netmuxd is not support arch : {ARCH}")

            elif option == 't':
                if Netmuxd_is_on:
                    netmuxd.switchTether()
                    altserverdaemon.restart()

            elif option == 'e':
                break

            elif option == 'h':
                print(HELP_MSG)

            elif option == 'p':
                devices = device_manager.getDevices()
                for d in devices:
                    print(f"{d.name} , {d.UDID}")

            elif option == 'u':
                print("Automatic updates disabled to preserve this Fedora repair.")

            else:
                print("Invalid option")
    finally:
        altserverdaemon.kill()
        anisetteserver.kill()
        if Netmuxd_is_on:
            netmuxd.kill()



HELP_MSG = """
#####################################
#  Welcome to the AltServer script  #
#####################################

ScriptUsage: [OPTION]

OPTIONS
    i, --Install AltStore or ipa files
        Install AltStore or ipa files to your device
    w, --Switch to wifi Daemode mode (USB is the default)
        Switch and restart to wifi Daemode mode to refresh apps or AltStore
    t, --Switch to usb tethered Daemode mode
        Switch and restart to usb tethered Daemode mode to refresh apps or AltStore
    e, --Exit
        Exit script
    h, --Help
        Show this message
    p, --Pair
        Show connected devices
    u, --Update
        Updates disabled for this repaired copy

For more information:
https://github.com/powenn/AltServer-Linux-PyScript

"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the repaired AltServer on Linux")
    parser.add_argument("--anisette-server", metavar="URL",
                        help="Use a remote legacy Anisette JSON endpoint instead of the local Podman helper")
    args = parser.parse_args()
    DebugPrint("Script Start")
    DebugPrint(
        f"RUNNING AT {CURRENT_DIRECTORY} , RESOURCE_DIR : {RESOURCE_DIRECTORY}")
    DebugPrint(f"ARCH : {ARCH} , NETMUXD_AVAILABLE : {NETMUXD_IS_AVAILABLE}")
    try:
        main(anisette_url=args.anisette_server)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
