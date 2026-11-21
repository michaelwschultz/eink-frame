"""Main script to fetch and display images from a remote server."""

import argparse
from contextlib import contextmanager
import json
import os
import re
import subprocess
import sys
import time

try:
    import fcntl
except ImportError:  # Windows local dev
    fcntl = None

import requests
from wifi_setup import connect_with_saved_credentials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = "state.json"
IMAGES_DIR = "images"
OUTPUT_PATH = os.path.join(IMAGES_DIR, "fetched-image.png")
LOCK_FILE = "/tmp/eink-frame.lock"
BACKEND_URL = os.environ.get("EINK_BACKEND_URL", "https://eink.schultz.co").rstrip("/")
FRAME_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@contextmanager
def display_lock():
    """Acquire an exclusive cross-process lock around SPI display updates."""
    if fcntl is None:
        yield
        return

    with open(LOCK_FILE, mode="w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def is_valid_frame_name(frame_name):
    """Return True if frame_name is a safe, non-empty frame identifier."""
    return isinstance(frame_name, str) and bool(FRAME_NAME_RE.match(frame_name))


def read_state():
    """Read raw state from STATE_FILE, returning defaults if missing or invalid."""
    try:
        with open(file=STATE_FILE, mode="r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                return {
                    "last_displayed": data.get("last_displayed", 0),
                    "last_frame": data.get("last_frame"),
                }
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        print("State file not found or is corrupted. Defaulting to frame 0.")
    return {"last_displayed": 0, "last_frame": None}


def save_state(index, frame_name):
    """Persist the current frame index and name to STATE_FILE."""
    with open(file=STATE_FILE, mode="w", encoding="utf-8") as file:
        json.dump({"last_displayed": index, "last_frame": frame_name}, file)


def get_current_state(frame_list):
    """Resolve the current frame index within frame_list from STATE_FILE."""
    if not frame_list:
        return 0

    state = read_state()
    last_frame = state.get("last_frame")
    if last_frame in frame_list:
        current_index = frame_list.index(last_frame)
    else:
        raw_index = state.get("last_displayed", 0)
        if not isinstance(raw_index, int) or raw_index < 0:
            raw_index = 0
        current_index = raw_index % len(frame_list)

    print(f"Current frame is {frame_list[current_index]}")
    return current_index


def set_next_state(frame_list, current_state, step=1):
    """Advance (or rewind) the state by step, persist it, and return the new index."""
    next_state = (current_state + step) % len(frame_list)
    frame_name = frame_list[next_state]
    save_state(next_state, frame_name)

    print(
        f"Transitioning to {frame_name}, "
        f"length of states: {len(frame_list)}, "
        f"index: {next_state}"
    )
    return next_state


def set_named_state(frame_list, frame_name):
    """Persist a specific frame name, syncing its index if present in frame_list."""
    if frame_name in frame_list:
        index = frame_list.index(frame_name)
    else:
        index = get_current_state(frame_list) if frame_list else 0
    save_state(index, frame_name)
    print(f"Setting frame to {frame_name} (index: {index})")
    return index


def fetch_frame_list():
    """Fetch the list of frame states from the server."""
    url = f"{BACKEND_URL}/api/frames"
    default_frames = ["weather", "hemolog"]

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            frame_list: list[str] = response.json()
            if isinstance(frame_list, list) and frame_list:
                print(f"Possible frame states updated {frame_list}")
                return frame_list

        print(f"Failed to fetch list of frames. Status code: {response.status_code}")
        return default_frames

    except (requests.RequestException, json.JSONDecodeError) as err:
        print(f"An error occurred: {err}")
        return default_frames


def fetch_image_by_name(frame_name):
    """Fetch a single frame image by name and save it locally. Returns True on success."""
    if not is_valid_frame_name(frame_name):
        print(f"Invalid frame name: {frame_name!r}")
        return False

    url = f"{BACKEND_URL}/img/{frame_name}.png"
    start_time = time.time()

    try:
        response = requests.get(url, timeout=20)

        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if content_type and not content_type.startswith("image/"):
                print(f"Unexpected content type for {frame_name}: {content_type}")
                return False

            os.makedirs(IMAGES_DIR, exist_ok=True)
            with open(OUTPUT_PATH, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            elapsed_time = time.time() - start_time
            print(f"Image saved to {OUTPUT_PATH}. Took {elapsed_time:.2f} seconds")
            return True

        print(f"Failed to fetch the image. Status code: {response.status_code}")
        return False

    except (requests.RequestException, OSError) as err:
        print(f"An error occurred: {err}")
        return False


def fetch_image(frame_list, next_state):
    """Fetch the image from the server and save it locally."""
    return fetch_image_by_name(frame_list[next_state])


def run_send_to_display():
    """Run send_to_display.py in a subprocess so GPIO pins are released after each refresh."""
    script_path = os.path.join(BASE_DIR, "send_to_display.py")
    subprocess.run([sys.executable, script_path], cwd=BASE_DIR, check=True)


def display_frame(frame_name):
    """Fetch frame_name and push it to the e-ink display under the SPI lock."""
    with display_lock():
        if not fetch_image_by_name(frame_name):
            return False
        run_send_to_display()
        return True


def main(frame=None, step=1):
    """Main function to control the flow of the script."""
    connect_with_saved_credentials()
    frame_list = fetch_frame_list()

    if frame is not None:
        if not is_valid_frame_name(frame):
            print(f"Invalid frame name: {frame!r}")
            return False
        set_named_state(frame_list, frame)
        target_frame = frame
    else:
        current_state = get_current_state(frame_list)
        next_state = set_next_state(frame_list, current_state, step=step)
        target_frame = frame_list[next_state]

    return display_frame(target_frame)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch and display the next, previous, or a specific frame."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-F",
        "--frame",
        type=str,
        default=None,
        help="Name of the frame to display.",
    )
    group.add_argument(
        "--next",
        action="store_true",
        help="Advance to the next frame in the list (default).",
    )
    group.add_argument(
        "--prev",
        action="store_true",
        help="Go back to the previous frame in the list.",
    )

    args = parser.parse_args()
    main(frame=args.frame, step=-1 if args.prev else 1)
