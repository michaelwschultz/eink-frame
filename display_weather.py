import requests
from send_to_display import send_image_to_display

def fetch_weather_image():
    url = "https://michaelwschultz-generateframeimage.web.val.run?generate=image"
    output_path = "images/current-weather.png"

    try:
        response = requests.get(url, stream=True)  # Use stream=True to handle large files

        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"Image saved to {output_path}")
        else:
            print(f"Failed to fetch the image. Status code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_weather_image()
    send_image_to_display()
