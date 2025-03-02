##
##display for 7.5 inch R/B/W 3 color eink to display better quality
##
##
from PIL import Image
from PIL import ImageDraw
import time
import os
import random
from waveshare_epd import epd7in5b_V2
import numpy
import sys

EPD_WIDTH = 800
EPD_HEIGHT = 480

# Define the picture directory
PIC_DIR = '/home/pi/display-images/images/'

def main():
    epd = epd7in5b_V2.EPD()
    epd.init()

    localimg = random.choice(os.listdir(PIC_DIR))

    # pass argument to override photo selection
    if len(sys.argv) == 2:
      localimg = sys.argv[1]

    print(localimg)

    # Crop photo to the correct size or thie image wont be sent to the display
    photo = Image.open(PIC_DIR+localimg).crop((0, 0, EPD_WIDTH, EPD_HEIGHT))

    # Create a new image with RGBA mode to strip out the red channel
    red_channel = Image.new("RGB", photo.size)
    pixels = photo.load()
    new_pixels = red_channel.load()

    # Loop through every pixel to determine the red pixels and remove the ones that aren't
    for i in range(photo.size[0]):
      for j in range(photo.size[1]):
        r, g, b = pixels[i, j]
        # Check if red is the dominant color
        if (r-g >= 80) and (r-b >= 80):
            # Keep the red pixel as is, make it fully opaque in the new image
            new_pixels[i, j] = (0, g, b)
        else:
            # Make non-red pixels transparent or set to a background color
            # For transparency, set the alpha to 0
            new_pixels[i, j] = (255, 255, 255)  # This makes non-red areas white "transparent"


    # (OPTIONAL) convert to bw
    # photo = photo.convert('1', dither=Image.FLOYDSTEINBERG)
    frame_black = epd.getbuffer(photo)
    frame_red = epd.getbuffer(red_channel)

    epd.display(frame_black, frame_red)
    epd.sleep()
    # time.sleep(3600)  # change the image every hour ,I quote this line as added the script in crontab

    exit()
    main()

if __name__ == '__main__':
    main()
