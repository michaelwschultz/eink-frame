import time
import subprocess

import RPi.GPIO as GPIO

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


def rotary_callback(channel):
    global last_clk_state
    clk_state = GPIO.input(CLK)
    dt_state = GPIO.input(DT)

    if clk_state != last_clk_state:  # Detect rotation
        if dt_state != clk_state:
            print("Rotated Clockwise")
        else:
            print("Rotated Counterclockwise")

    last_clk_state = clk_state


def button_callback(channel):
    subprocess.run(["python", "fetch_and_display_image.py"])


# Add event detection
GPIO.add_event_detect(CLK, GPIO.BOTH, callback=rotary_callback, bouncetime=10)
GPIO.add_event_detect(SW, GPIO.FALLING, callback=button_callback, bouncetime=200)

try:
    while True:
        time.sleep(0.1)  # Keep the script running

except KeyboardInterrupt:
    print("\nExiting...")
    GPIO.cleanup()
