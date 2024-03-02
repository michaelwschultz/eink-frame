##
##display for 7.5 inch R/B/W 3 color eink to display better quality, need to use my convert script to convert picture to 3 colors 800x480 or 880x528
##
##
from PIL import Image
from PIL import ImageDraw
import time
import os
import random
from waveshare_epd import epd7in5b_V2
import numpy
#from waveshare_epd import epd7in5b_HD  #unquote this line if you are using higher version 7in5b_HD

EPD_WIDTH = 800
EPD_HEIGHT = 480

#unquote the below 2 lines if you are using higher version 7in5b_HD
#EPD_WIDTH = 880
#EPD_HEIGHT = 528

#def choose_random_loading_image(path):
#    images=os.listdir(path)
#    loading_image=random.randint(0,len(images)-1)
#   return path+images[loading_image]
# define the picture directory
picdir = '/home/pi/photos/'

def main():
    epd = epd7in5b_V2.EPD()
    epd.init()

    localimg = random.choice(os.listdir(picdir))
    print(localimg)
    photo = Image.open(picdir+localimg).crop((0, 0, EPD_WIDTH, EPD_HEIGHT))

    # Create a new image with RGBA mode to strip out the red channel
    red_channel = Image.new("RGB", photo.size)
    pixels = photo.load()
    new_pixels = red_channel.load()

    # loop through every pixel to determine the red pixels and remove the ones that aren't
    for i in range(photo.size[0]):
      for j in range(photo.size[1]):
        r, g, b = pixels[i, j]
        # Check if red is the dominant color
        if (r-g >= 80) and (r-b >= 80):
            # Keep the red pixel as is, make it fully opaque in the new image
            new_pixels[i, j] = (r, g, b)
        else:
            # Make non-red pixels transparent or set to a background color
            # For transparency, set the alpha to 0
            new_pixels[i, j] = (255, 255, 255)  # This makes non-red areas white "transparent"


    frame_black = epd.getbuffer(photo)
    frame_red = epd.getbuffer(red_channel)

    epd.display(frame_black, frame_red)
    # time.sleep(3600)  # change the image every hour ,I quote this line as added the script in crontab
    exit()
    main()

if __name__ == '__main__':
    main()
