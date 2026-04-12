"""WiFi credential manager — stores and retrieves WiFi configurations.

Credentials are saved to wifi_credentials.json in the project directory.
On first run (or if the file is missing), the setup portal is triggered.
"""

import json
import os

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wifi_credentials.json")


def load_credentials():
    """Load saved WiFi credentials from disk.

    Returns:
        dict with 'ssid' and 'password' keys, or None if not configured.
    """
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("ssid"):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def save_credentials(ssid, password):
    """Save WiFi credentials to disk.

    Args:
        ssid: The network name.
        password: The network password.
    """
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump({"ssid": ssid, "password": password}, f)
    print(f"WiFi credentials saved for: {ssid}")


def clear_credentials():
    """Remove saved WiFi credentials."""
    try:
        os.remove(CREDENTIALS_FILE)
        print("WiFi credentials cleared.")
    except FileNotFoundError:
        pass


def needs_setup():
    """Check if WiFi credentials need to be configured.

    Returns:
        True if no valid credentials are saved.
    """
    return load_credentials() is None


if __name__ == "__main__":
    creds = load_credentials()
    if creds:
        print(f"Configured SSID: {creds['ssid']}")
    else:
        print("No WiFi credentials configured. Run wifi_setup.py to configure.")
