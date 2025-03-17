"""Rotary Encoder and Button Control for Raspberry Pi"""

import time
import subprocess

import RPi.GPIO as GPIO


class RotaryEncoder:
    """Class to handle rotary encoder and button events."""

    def __init__(self):
        # GPIO Pins
        self.clk = 31  # Clock pin
        self.dt = 37  # Data pin
        self.sw = 36  # Switch pin

        # Setup
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.clk, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.dt, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Track last state of CLK
        self.last_clk_state = GPIO.input(self.clk)

        # Add event detection
        GPIO.add_event_detect(
            self.clk, GPIO.BOTH, callback=self.rotary_callback, bouncetime=10
        )
        GPIO.add_event_detect(
            self.sw, GPIO.FALLING, callback=self.button_callback, bouncetime=200
        )

    def rotary_callback(self):
        """Callback function for rotary encoder rotation."""
        clk_state = GPIO.input(self.clk)
        dt_state = GPIO.input(self.dt)

        if clk_state != self.last_clk_state:  # Detect rotation
            if dt_state != clk_state:
                print("Rotated Clockwise")
            else:
                print("Rotated Counterclockwise")

        self.last_clk_state = clk_state

    def button_callback(self):
        """Callback function for button press."""
        subprocess.run(["python", "fetch_and_display_image.py"], check=True)


if __name__ == "__main__":

    def cleanup():
        """Cleanup GPIO settings."""
        GPIO.cleanup()

    try:
        encoder = RotaryEncoder()
        while True:
            time.sleep(0.1)  # Keep the script running
    except KeyboardInterrupt as e:
        print("Exiting...")
        cleanup()
    finally:
        cleanup()
