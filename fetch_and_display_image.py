import json
import requests
import time
from send_to_display import send_image_to_display

STATE_FILE = "state.json"

# Must list all frames here
FRAME_STATES = ["weather", "hemolog"]

START_TIME = time.time()

def get_current_state():
    # Read the last displayed state from the file.
    try:
        with open(STATE_FILE, "r") as file:
            data = json.load(file)
            return data.get("last_displayed", 0) # 0 is a default incase last_displayed is missing
    except (FileNotFoundError, json.JSONDecodeError):
        return 0  # Default state if file doesn't exist

def set_next_state(current_state):
    # Determine the next state and update the file
    next_state = current_state + 1 if current_state + 1 < len(FRAME_STATES) else 0

    with open(STATE_FILE, "w") as file:
        json.dump({"last_displayed": next_state}, file)

    return next_state

def display_image(image_type):
    # Simulate displaying the image (replace with actual display code).
    print(f"Displaying {image_type} image...")
    subprocess.run(["python", "send_image_to_display.py"])  # Replace with actual display script


def fetch_image(next_state):
    url = f"https://michaelwschultz-generateframeimage.web.val.run?frame={FRAME_STATES[next_state]}&generate=image"
    output_path = "images/fetched-image.png"

    try:
        response = requests.get(url, stream=True)  # Use stream=True to handle large files

        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
                elapsed_time = time.time() - START_TIME
                print(f"Image saved to {output_path}. Took {elapsed_time:.2f} seconds")
        else:
            print(f"Failed to fetch the image. Status code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")


def main():
    current_state = get_current_state()
    next_state = set_next_state(current_state)
    fetch_image(next_state)
    send_image_to_display()


if __name__ == "__main__":
    main()
