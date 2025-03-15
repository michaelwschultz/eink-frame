"""Main script to fetch and display images from a remote server."""

import json
import subprocess
import time
import argparse

import requests
from send_to_display import send_image_to_display

STATE_FILE = "state.json"
START_TIME = time.time()
BACKEND_URL = "https://michaelwschultz--3506d8cafe2211efb693569c3dd06744.web.val.run"


def get_current_state(frame_list):
    """Check if the state file exists and read the last displayed state."""
    try:
        with open(file=STATE_FILE, mode="r", encoding="utf-8") as file:
            data = json.load(file)
            current_frame = data.get(
                "last_displayed", 0
            )  # 0 is a default in case last_displayed is missing
            print(f"Current frame is {frame_list[current_frame]}")
            return current_frame
    except (FileNotFoundError, json.JSONDecodeError):
        print("State file not found or is corrupted. Defaulting to frame 0.")
        return 0  # Default state if file doesn't exist


def set_next_state(frame_list, current_state):
    """Determine the next state based on the current state."""
    # Determine the next state and update the file
    next_state = current_state + 1 if current_state + 1 < len(frame_list) else 0

    with open(file=STATE_FILE, mode="w", encoding="utf-8") as file:
        json.dump({"last_displayed": next_state}, file)

    print(
        f"Transitioning to {frame_list[next_state]}, "
        f"length of states: {len(frame_list)}, "
        f"state + 1: {current_state + 1}"
    )
    return next_state


def display_image(image_type):
    """Simulate displaying the image (replace with actual display code)."""
    print(f"Displaying {image_type} image...")
    subprocess.run(["python", "send_image_to_display.py"], check=True)


def fetch_frame_list():
    """Fetch the list of frame states from the server."""
    url = f"{BACKEND_URL}?generate=list"
    default_frames = ["weather", "hemolog"]

    try:
        response = requests.get(url)

        if response.status_code == 200:
            frame_list: list[str] = response.json()
            print(f"Possible frame states updated {frame_list}")
            return frame_list

        print(f"Failed to fetch list of frames. Status code: {response.status_code}")
        return default_frames

    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"An error occurred: {e}")
        return default_frames


def fetch_image(frame_list, next_state):
    """Fetch the image from the server and save it locally."""
    frame_name = frame_list[next_state]
    url = f"{BACKEND_URL}?frame={frame_name}&generate=image"
    output_path = "images/fetched-image.png"

    try:
        response = requests.get(url)

        if response.status_code == 200:
            with open(output_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
                elapsed_time = time.time() - START_TIME
                print(f"Image saved to {output_path}. Took {elapsed_time:.2f} seconds")
                return
        else:
            print(f"Failed to fetch the image. Status code: {response.status_code}")

    except (requests.RequestException, IOError) as e:
        print(f"An error occurred: {e}")


def main(frame):
    """Main function to control the flow of the script."""
    if frame is not None:
        fetch_image([frame], 0)
    else:
        frame_list = fetch_frame_list()
        current_state = get_current_state(frame_list)
        next_state = set_next_state(frame_list, current_state)
        fetch_image(frame_list, next_state)

    send_image_to_display()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Skip cycle and display any frame by name."
    )
    parser.add_argument(
        "-F",
        "--frame",
        type=str,
        default=None,
        required=False,
        help="Name of the frame to display that matches list.",
    )

    args = parser.parse_args()
    main(args.frame)
