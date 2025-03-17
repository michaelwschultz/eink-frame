"""Optional: This script listens for a rotary dial press on a Raspberry Pi GPIO pin."""

# ignoring several pylint warnings that aren't correct or not worth fixing
# pylint: disable=E1101

import time
import subprocess

from RPi import GPIO  # pylint: disable=E0401

# GPIO Pins
CLK = 31  # Clock pin
DT = 37  # Data pin
SW = 36  # Switch pin

# Setup
GPIO.setmode(GPIO.BOARD)
GPIO.setup(CLK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(DT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Track last state of CLK
last_clk_state = GPIO.input(CLK)


def rotary_callback(*_):
    """Callback function to be called when the rotary dial is pressed. (optional)"""
    # pylint: disable=W0603
    global last_clk_state
    clk_state = GPIO.input(CLK)
    dt_state = GPIO.input(DT)

    if clk_state != last_clk_state:  # Detect rotation
        if dt_state != clk_state:
            print("Rotated Clockwise")
        else:
            print("Rotated Counterclockwise")

    last_clk_state = clk_state


def button_callback():
    """Callback function called when roatary dial is pressed."""
    subprocess.run(["python", "fetch_and_display_image.py"], check=True)


# Add event detection
GPIO.add_event_detect(CLK, GPIO.BOTH, callback=rotary_callback, bouncetime=10)
GPIO.add_event_detect(SW, GPIO.FALLING, callback=button_callback, bouncetime=200)

try:
    while True:
        time.sleep(0.1)  # Keep the script running

except KeyboardInterrupt:
    print("\nExiting...")
    GPIO.cleanup()
