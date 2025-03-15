"""This script listens for a button press on a Raspberry Pi GPIO pin."""

import time
import subprocess

import RPi.GPIO as GPIO

# GPIO Pin for the button
BUTTON_PIN = 36

# Setup GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Enable pull-up resistor


def button_callback():
    """Callback function to be called when the button is pressed."""
    subprocess.run(
        ["python", "fetch_and_display_image.py"], check=True
    )  # Run the external script


# Add event detection for the button press
GPIO.add_event_detect(
    BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=300
)

try:
    while True:
        time.sleep(1)  # Keep the script running

except KeyboardInterrupt:
    GPIO.cleanup()
