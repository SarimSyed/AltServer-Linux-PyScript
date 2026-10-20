# AltStore installation on this Fedora machine

This is a local launcher with a repaired copy of [powenn/AltServer-Linux-PyScript](https://github.com/powenn/AltServer-Linux-PyScript), using [AltServer-Linux](https://github.com/NyaMisty/AltServer-Linux). The original files in Downloads are unchanged.

## Start here

To run AltServer from any directory, install the command once from this checkout:

```bash
mkdir -p "$HOME/.local/bin"
ln -s "$(pwd)/altserver" "$HOME/.local/bin/altserver"
```

On Fedora, `~/.local/bin` is normally already on your PATH. Then run:

```bash
altserver
```

This starts the repaired AltServer and its local Anisette helper in USB mode.
Keep the terminal open while using it. Enter `p` to list devices, `i` to install,
`w` for Wi-Fi mode, `t` for USB mode, or `e` to exit. The checkout must stay in
place because the command links to it. Run as your normal user.

To use jkcoxson's remote Anisette server instead of the local helper:

```bash
altserver --anisette-server https://mac-ani.jkcoxson.com
```

Exit the running script with `e` before restarting with this option. A successful
start prints `Using remote Anisette server:` with the chosen URL. Remote mode
starts no local container and does not require Podman. The option is per run;
plain `altserver` continues to use the local helper.

Use the server's base URL, not `/v3/client_info`. This older AltServer expects a
legacy JSON response containing signing headers; a v3-only server or metadata
URL is incompatible. Endpoint format validation does not verify Apple sign-in.
Keep credentials, verification codes, and Anisette header values out of logs
shared with others.

For the guided iLoader menu instead:

```bash
cd /home/sarim/Documents/ChatGPT/altstore
python3 main.py
```

The menu shows the iPad connection, installed iLoader, and AltStore IPA status:

1. **Install AltStore with iLoader** opens the installer and shows the IPA path and next steps. Enter account credentials in iLoader.
2. **Check connection / pair iPad** checks trust, guides pairing, and explains missing tools or a stopped USB service. Multiple devices use numbered selection.
3. **Troubleshoot sign-in** checks the preset Anisette services and explains common errors. It sends no account details and does not change your server settings or saved sign-in state.
4. **Advanced AltServer controls** opens the older script when explicitly selected. This is where the existing USB/Wi-Fi server controls live.

Press **q**, **Ctrl+C**, or **Ctrl+D** to exit. The normal menu starts no background services and needs only Python's standard library. It reads USB device status through the installed iDevice utilities.

For a desktop shortcut, open `AltStore.desktop` in the file manager. KDE may ask you to allow launching the file once. The shortcut opens this menu in a terminal.

The guided menu displays device names and short status messages. Detailed legacy AltServer output remains in advanced mode.

## Current sign-in failure: use iLoader

USB detection and local Anisette generation work, but this AltServer v0.0.5 build returned HTTP 503 at Apple's sign-in endpoint. The script repair does not establish compatibility with Apple's current authentication protocol.

[iLoader v2.3.9](https://github.com/nab138/iloader/releases/tag/v2.3.9), released October 16, 2026, specifically addresses the current HTTP 503 failure and supports importing any IPA. Its official Fedora package has been downloaded to `resource/iloader-2.3.9-x86_64.rpm`.

Exit the Python script with `e` after dismissing any AltServer error prompt, then install and launch iLoader:

```bash
sudo dnf install /home/sarim/Documents/ChatGPT/altstore/resource/iloader-2.3.9-x86_64.rpm
iloader
```

Keep the iPad connected and unlocked. Sign in locally, choose **Import IPA**, and select `/home/sarim/Documents/ChatGPT/altstore/resource/AltStore.ipa`. Apple sign-in succeeded during this setup using **StikStore (secondary)**; keep the setting that works for your account. App installation and refresh still need verification.

The older AltServer also displayed an authentication date five hours ahead of the helper's UTC date. Its child processes now use `TZ=UTC`; this addresses that separate timestamp mismatch, not the current Apple authentication compatibility issue.

The downloaded RPM's SHA-256 is `5727713cb95d7f632bc5562640289ee355783879b365504e5909206fa19a826a`.

## Original script setup over USB

1. Exit the old script in Downloads.
2. Install the Fedora dependencies and restore the USB service:

   ```bash
   sudo dnf install libimobiledevice-utils avahi-compat-libdns_sd-devel
   sudo systemctl restart usbmuxd
   ```

3. Connect the iPad with a data cable, unlock it, and tap **Trust**. If needed, run `idevicepair pair` and accept the prompt on the iPad.
4. Launch the repaired copy as your normal user:

   ```bash
   cd /home/sarim/Documents/ChatGPT/altstore
   python3 altserver.py
   ```

5. Enter `p` to list connected devices, then `i` to install. Select the device index, enter your Apple account and password locally, and answer `y` to install AltStore. Enter `e` when finished.

The menu accepts single letters. Its `p` command lists devices; it does not pair them.

## Local repairs

- Start in USB mode; request administrative privileges only when switching to Wi-Fi mode.
- Download and unpack the current netmuxd release archive, and reject HTTP errors and invalid executable downloads.
- Use a local Podman container for Anisette because the downloaded native helper crashes with Fedora's OpenSSL. The project container also needed `libplist-2.0-4`; `Containerfile` adds it to the tested base image.
- Keep Anisette reachable only at `127.0.0.1:6969`. Its private configuration is in `provision-config/`, excluded from Git. Do not share that directory.
- Pass installation arguments directly to AltServer and handle Ctrl+C/EOF without the original closed-input failure.
- Disable automatic self-updates so they do not overwrite this repair.

The helper image has already been built locally. To rebuild it:

```bash
podman build -t localhost/altstore-anisette:fedora -f Containerfile .
```

The helper uses [Provision](https://github.com/Dadoum/Provision), whose authors recommend a secondary Apple account. Enter account credentials only in your own terminal.

## Checks

```bash
python3 -m unittest -q test_launcher.py test_repair.py
```

The local authentication helper was verified to return signing headers without displaying their values. Actual installation requires the connected, paired iPad and local account sign-in. Wi-Fi installation and refresh have not been verified.
