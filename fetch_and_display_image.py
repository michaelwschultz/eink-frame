import json
import requests
import time
import argparse
from send_to_display import send_image_to_display

STATE_FILE = "state.json"
START_TIME = time.time()

def get_current_state(frame_list):
    # Read the last displayed state from the file.
    try:
        with open(STATE_FILE, "r") as file:
            data = json.load(file)
            current_frame = data.get("last_displayed", 0) # 0 is a default incase last_displayed is missing
            print(f"Current frame is {frame_list[current_frame]}")
            return current_frame
    except (FileNotFoundError, json.JSONDecodeError):
        return 0  # Default state if file doesn't exist

def set_next_state(frame_list, current_state):
    # Determine the next state and update the file
    next_state = current_state + 1 if current_state + 1 < len(frame_list) else 0

    with open(STATE_FILE, "w") as file:
        json.dump({"last_displayed": next_state}, file)

    print(f"Trasitioning to {frame_list[next_state]}, length of states: {len(frame_list)}, state + 1: {current_state + 1}")
    return next_state

def display_image(image_type):
    # Simulate displaying the image (replace with actual display code).
    print(f"Displaying {image_type} image...")
    subprocess.run(["python", "send_image_to_display.py"])  # Replace with actual display script


def fetch_frame_list():
    url = "https://michaelwschultz-generateframeimage.web.val.run?generate=list"

    print("fetching frame list")
    try:
        response = requests.get(url)

        if response.status_code == 200:
            print(f"Possible frame states updated {response.json()}")
            return response.json()
        else:
            print(f"Failed to fetch list of frames. Status code: {response.status_code}")
            return ["weather", "hemolog"]

    except Exception as e:
        print(f"An error occurred: {e}")



def fetch_image(frame_list, next_state):
    url = f"https://michaelwschultz-generateframeimage.web.val.run?frame={frame_list[next_state]}&generate=image"
    output_path = "images/fetched-image.png"

    try:
        response = requests.get(url, stream=True)  # Use stream=True to handle large files

        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
                elapsed_time = time.time() - START_TIME
                print(f"Image saved to {output_path}. Took {elapsed_time:.2f} seconds")
                return
        else:
            print(f"Failed to fetch the image. Status code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")


def main(frame):
    if frame is not None:
        fetch_image([frame], 0)
    else:
        frame_list = fetch_frame_list()
        current_state = get_current_state(frame_list)
        next_state = set_next_state(frame_list, current_state)
        fetch_image(frame_list, next_state)

    send_image_to_display()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skip cycle and display any frame by name.")
    parser.add_argument("-F", "--frame", type=str, default=None, required=False, help="Name of the frame to display that matches list.")

    args = parser.parse_args()
    main(args.frame)
