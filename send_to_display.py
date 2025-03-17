"""This script is used to send an image to a Waveshare 7.5 inch E-Ink display."""

## Image to R/B/W 3 color eink to display, though black and white works fine

import sys
import time

from PIL import Image
from waveshare_epd import epd7in5b_V2


EPD_WIDTH = 800  # pixels
EPD_HEIGHT = 480  # pixels
RED_THRESHOLD = 60

# Define the picture directory
LOCAL_IMG = "/images/fetched-image.png"


def load_image():
    """Load the image and process it for red, white, and black display"""
    # Crop image to the correct size or thie image wont be sent to the display
    image = Image.open(LOCAL_IMG).crop((0, 0, EPD_WIDTH, EPD_HEIGHT))

    # Create a new image with RGBA mode to strip out the red channel
    red_channel = Image.new("RGB", image.size)
    pixels = image.load()
    new_pixels = red_channel.load()

    # Loop through every pixel to determine the red pixels and remove the ones that aren't
    # NOTE: There is a epd function to do this but I had trouble with it working consistently
    for i in range(image.size[0]):
        for j in range(image.size[1]):
            r, g, b = pixels[i, j]
            # Check if red is the dominant color
            if (r - g >= RED_THRESHOLD) and (r - b >= RED_THRESHOLD):
                # Keep the red pixel as is, make it fully opaque in the new image
                new_pixels[i, j] = (0, g, b)
            else:
                # Make non-red pixels transparent or set to a background color
                # For transparency, set the alpha to 0
                new_pixels[i, j] = (
                    255,
                    255,
                    255,
                )  # This makes non-red areas white "transparent"

    return image, red_channel


def send_image_to_display():
    """Send the image to the E-Ink display."""
    start_time = time.time()
    print("Initializing EPD...")
    epd = epd7in5b_V2.EPD()
    epd.init()
    # epd.Clear() # clear the display if needed

    # Load the image and separate black and red channels
    black_channel, red_channel = load_image()

    frame_black = epd.getbuffer(black_channel)
    frame_red = epd.getbuffer(red_channel)

    try:
        print("Sending image to display...")
        epd.display(frame_black, frame_red)
        epd.sleep()

        elapsed_time = time.time() - start_time
        print(f"Image sent to display. Took {elapsed_time:.2f} seconds")
    except IOError as e:
        print(f"Sending image to display failed: {e}")
        epd.sleep()
        epd.Dev_exit()
    except KeyboardInterrupt:
        print("Ctrl + C: Exiting...")
        epd.sleep()
        epd.Dev_exit()
        sys.exit()


if __name__ == "__main__":
    send_image_to_display()
