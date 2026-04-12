"""WiFi setup portal — creates an access point and serves a mobile-friendly
config page so you can update WiFi credentials from your phone.

Usage:
    python wifi_setup.py              # Start the setup portal
    python wifi_setup.py --connect    # Just try connecting with saved credentials

When the Pi can't reach the internet, run this script. It:
1. Creates a temporary WiFi access point (AP mode)
2. Starts a tiny HTTP server with a captive-portal-style setup page
3. Connects your phone to the AP, fill in SSID + password
4. The Pi connects to your real network and shuts down the AP
"""

import base64
import json
import os
import signal
import socket
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

from wifi_config import load_credentials, save_credentials, needs_setup

# Access point config
AP_SSID = "eink-frame-setup"
AP_PASSWORD = ""  # Open network for easy phone access (short-lived)
AP_INTERFACE = "wlan0"
AP_IP = "10.0.0.1"
HTTP_PORT = 80

# How long to wait for a connection test (seconds)
CONNECT_TEST_TIMEOUT = 15
CONNECT_TEST_URL = "https://www.google.com/generate_204"


# ── HTML page (embedded so no external files needed) ──────────────────────

SETUP_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>eink-frame WiFi Setup</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #eee;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .card {
    background: #16213e;
    border-radius: 16px;
    padding: 32px;
    max-width: 400px;
    width: 100%;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  h1 {
    font-size: 1.4rem;
    margin-bottom: 8px;
    color: #e94560;
  }
  p.subtitle { color: #999; margin-bottom: 24px; font-size: 0.9rem; }
  label { display: block; margin-bottom: 6px; font-size: 0.85rem; color: #aaa; }
  input {
    width: 100%;
    padding: 12px 14px;
    margin-bottom: 18px;
    border: 1px solid #333;
    border-radius: 8px;
    background: #0f3460;
    color: #eee;
    font-size: 1rem;
    outline: none;
    transition: border-color 0.2s;
  }
  input:focus { border-color: #e94560; }
  button {
    width: 100%;
    padding: 14px;
    background: #e94560;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }
  button:hover { background: #c73652; }
  button:disabled { background: #555; cursor: not-allowed; }
  .status {
    margin-top: 18px;
    padding: 12px;
    border-radius: 8px;
    font-size: 0.9rem;
    display: none;
  }
  .status.success { display: block; background: #1b4332; color: #52b788; }
  .status.error { display: block; background: #3d0c11; color: #e5383b; }
  .status.info { display: block; background: #0f3460; color: #90caf9; }
</style>
</head>
<body>
<div class="card">
  <h1>📶 eink-frame WiFi Setup</h1>
  <p class="subtitle">Connect your display to a new WiFi network</p>
  <form id="wifi-form">
    <label for="ssid">Network Name (SSID)</label>
    <input type="text" id="ssid" name="ssid" placeholder="MyWiFiNetwork" required
           autocapitalize="off" autocorrect="off" autocomplete="off">
    <label for="password">Password</label>
    <input type="password" id="password" name="password" placeholder="WiFi password">
    <button type="submit" id="submit-btn">Connect</button>
  </form>
  <div id="status" class="status"></div>
</div>
<script>
document.getElementById('wifi-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('submit-btn');
  const status = document.getElementById('status');
  const ssid = document.getElementById('ssid').value.trim();
  const password = document.getElementById('password').value;

  btn.disabled = true;
  btn.textContent = 'Connecting...';
  status.className = 'status info';
  status.textContent = 'Saving credentials and connecting to ' + ssid + '...';

  try {
    const resp = await fetch('/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'ssid=' + encodeURIComponent(ssid) + '&password=' + encodeURIComponent(password)
    });
    const data = await resp.json();

    if (data.success) {
      status.className = 'status success';
      status.textContent = '✓ Connected to ' + ssid + '! The setup AP will shut down shortly.';
    } else {
      status.className = 'status error';
      status.textContent = '✗ ' + (data.error || 'Connection failed. Check your credentials and try again.');
      btn.disabled = false;
      btn.textContent = 'Try Again';
    }
  } catch (err) {
    status.className = 'status success';
    status.textContent = '✓ Credentials saved! The AP is shutting down — reconnect to your home WiFi.';
  }
});
</script>
</body>
</html>"""


# ── HTTP server ───────────────────────────────────────────────────────────

class SetupHandler(BaseHTTPRequestHandler):
    """Serves the WiFi setup page and handles credential submission."""

    def do_GET(self):
        if self.path in ("/", "/index.html", "/generate_204", "/hotspot-detect.html",
                         "/kindle-wifi/wifistub.html", "/fwlink", "/connect"):
            self._serve_setup_page()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/connect":
            self._handle_connect()
        else:
            self.send_error(404)

    def _serve_setup_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(SETUP_PAGE_HTML.encode("utf-8"))

    def _handle_connect(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        params = parse_qs(body)

        ssid = params.get("ssid", [""])[0].strip()
        password = params.get("password", [""])[0]

        if not ssid:
            self._json_response(400, {"success": False, "error": "SSID is required"})
            return

        # Save credentials
        save_credentials(ssid, password)

        # Try connecting to the new network
        connected = _connect_to_wifi(ssid, password)

        if connected:
            self._json_response(200, {"success": True, "ssid": ssid})
            # Shut down the AP and server after a short delay
            _schedule_shutdown(2)
        else:
            self._json_response(200, {
                "success": False,
                "error": "Could not connect. Check SSID and password."
            })

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        # Quiet logging — only print errors
        if args and args[0].startswith("POST"):
            print(f"  Setup server: {args[0]}")


# ── AP management ─────────────────────────────────────────────────────────

def _run(cmd, check=False):
    """Run a shell command, returning the result."""
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)


def start_access_point():
    """Start a WiFi access point so a phone can connect."""
    print(f"Starting access point: {AP_SSID}")

    # Install hostapd/dnsmasq if missing (quietly)
    _run("which hostapd || sudo apt-get install -y hostapd >/dev/null 2>&1")
    _run("which dnsmasq || sudo apt-get install -y dnsmasq >/dev/null 2>&1")

    # Stop existing services that might conflict
    _run("sudo systemctl stop dnsmasq 2>/dev/null")
    _run("sudo systemctl stop hostapd 2>/dev/null")
    _run("sudo killall wpa_supplicant 2>/dev/null")

    # Configure the AP interface
    _run(f"sudo ifconfig {AP_INTERFACE} down 2>/dev/null")
    _run(f"sudo ifconfig {AP_INTERFACE} {AP_IP}/24 up")

    # Configure dnsmasq for DHCP
    dnsmasq_conf = f"""
interface={AP_INTERFACE}
dhcp-range=10.0.0.10,10.0.0.100,255.255.255.0,1h
address=/#/{AP_IP}
"""
    with open("/tmp/eink_dnsmasq.conf", "w") as f:
        f.write(dnsmasq_conf)
    _run("sudo dnsmasq -C /tmp/eink_dnsmasq.conf")

    # Configure hostapd
    hostapd_conf = f"""
interface={AP_INTERFACE}
driver=nl80211
ssid={AP_SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
"""
    with open("/tmp/eink_hostapd.conf", "w") as f:
        f.write(hostapd_conf)
    _run("sudo hostapd -B /tmp/eink_hostapd.conf")

    # Enable IP forwarding
    _run("sudo sh -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'")

    print(f"Access point '{AP_SSID}' is running. Connect from your phone.")


def stop_access_point():
    """Shut down the access point and clean up."""
    print("Shutting down access point...")
    _run("sudo killall hostapd 2>/dev/null")
    _run("sudo killall dnsmasq 2>/dev/null")
    _run("sudo rm /tmp/eink_dnsmasq.conf /tmp/eink_hostapd.conf 2>/dev/null")
    _run("sudo sh -c 'echo 0 > /proc/sys/net/ipv4/ip_forward'")
    _run(f"sudo ifconfig {AP_INTERFACE} down 2>/dev/null")
    print("Access point stopped.")


# ── WiFi connection ────────────────────────────────────────────────────────

def _connect_to_wifi(ssid, password):
    """Attempt to connect to a WiFi network using nmcli or wpa_supplicant."""
    print(f"Attempting to connect to: {ssid}")

    # Try nmcli first (modern Raspberry Pi OS)
    if _has_nmcli():
        return _connect_nmcli(ssid, password)

    # Fall back to wpa_supplicant
    return _connect_wpa_supplicant(ssid, password)


def _has_nmcli():
    result = _run("which nmcli")
    return result.returncode == 0


def _connect_nmcli(ssid, password):
    """Connect using NetworkManager (nmcli)."""
    # Remove existing connection if it exists
    _run(f"sudo nmcli con delete '{ssid}' 2>/dev/null")

    if password:
        result = _run(f"sudo nmcli dev wifi connect '{ssid}' password '{password}' ifname {AP_INTERFACE}")
    else:
        result = _run(f"sudo nmcli dev wifi connect '{ssid}' ifname {AP_INTERFACE}")

    if result.returncode == 0:
        # Verify with a quick connectivity check
        time.sleep(3)
        return _test_connectivity()
    return False


def _connect_wpa_supplicant(ssid, password):
    """Connect using wpa_supplicant (legacy Pi OS)."""
    # Kill the AP first (we need wlan0 back)
    stop_access_point()

    # Generate wpa_supplicant config
    if password:
        # Use wpa_passphrase to generate the psk
        psk_result = _run(f"wpa_passphrase '{ssid}' '{password}'")
        wpa_conf = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

{psk_result.stdout}
"""
    else:
        wpa_conf = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={{
    ssid="{ssid}"
    key_mgmt=NONE
}}
"""

    conf_path = "/tmp/eink_wpa.conf"
    with open(conf_path, "w") as f:
        f.write(wpa_conf)

    # Stop any existing wpa_supplicant and restart with our config
    _run("sudo killall wpa_supplicant 2>/dev/null")
    time.sleep(1)
    _run(f"sudo wpa_supplicant -B -i {AP_INTERFACE} -c {conf_path}")
    time.sleep(5)

    # Get a DHCP lease
    _run(f"sudo dhclient {AP_INTERFACE} 2>/dev/null")

    # Test connectivity
    return _test_connectivity()


def _test_connectivity():
    """Check if we can reach the internet."""
    try:
        result = _run(f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout {CONNECT_TEST_TIMEOUT} {CONNECT_TEST_URL}")
        return result.stdout.strip() in ("200", "204")
    except Exception:
        return False


def _schedule_shutdown(delay_seconds):
    """Schedule the AP and server to shut down after a delay."""
    def _shutdown():
        time.sleep(delay_seconds)
        stop_access_point()
        os._exit(0)

    import threading
    t = threading.Thread(target=_shutdown, daemon=True)
    t.start()


# ── Main entry points ──────────────────────────────────────────────────────

def run_setup_portal():
    """Start the AP + web server for WiFi configuration."""
    print("=" * 50)
    print("  eink-frame WiFi Setup Portal")
    print("=" * 50)
    print()

    # Start the access point
    start_access_point()
    print()

    # Start the HTTP server
    server = HTTPServer((AP_IP, HTTP_PORT), SetupHandler)
    print(f"Setup page running at http://{AP_IP}")
    print(f"Connect to '{AP_SSID}' from your phone to configure WiFi.")
    print("Press Ctrl+C to cancel.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCancelling setup...")
    finally:
        stop_access_point()
        server.server_close()


def connect_with_saved_credentials():
    """Try to connect using saved credentials. Returns True if connected."""
    creds = load_credentials()
    if not creds:
        return False

    ssid = creds["ssid"]
    password = creds.get("password", "")

    print(f"Connecting to saved network: {ssid}")
    connected = _connect_to_wifi(ssid, password)

    if connected:
        print(f"✓ Connected to {ssid}")
    else:
        print(f"✗ Could not connect to {ssid}")

    return connected


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="eink-frame WiFi setup")
    parser.add_argument("--connect", action="store_true",
                        help="Try connecting with saved credentials (no AP)")
    args = parser.parse_args()

    if args.connect:
        success = connect_with_saved_credentials()
        sys.exit(0 if success else 1)
    else:
        run_setup_portal()
