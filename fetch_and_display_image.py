import requests
import time
from send_to_display import send_image_to_display

def fetch_image():
    start_time = time.time()
    url = "https://michaelwschultz-generateframeimage.web.val.run?frame=weather&generate=image"
    output_path = "images/fetched-image.png"

    try:
        response = requests.get(url, stream=True)  # Use stream=True to handle large files

        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
                elapsed_time = time.time() - start_time
                print(f"Image saved to {output_path}. Took {elapsed_time:.2f} seconds")
        else:
            print(f"Failed to fetch the image. Status code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_image()
    send_image_to_display()
