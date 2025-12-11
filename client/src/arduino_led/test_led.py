#!/usr/bin/env python3
"""Simple test script to randomly send the 7 emotions to the Arduino LED.

Usage:
  python test_led.py [--delay SECONDS]

The script will try to initialize the serial connection. If it fails, it
will simulate sends by printing the emotions instead.
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time

from .send_led import ArduinoLEDController


def main(delay: float) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    controller = ArduinoLEDController()

    # Shuffle and send all available emotions (there are 7 in the controller.EMOTIONS)
    emotions = random.sample(controller.EMOTIONS, k=len(controller.EMOTIONS))

    if controller.initialize_connection():
        logging.info("Serial connection established — sending emotions to Arduino.")
        try:
            for emotion in emotions:
                controller.update_led(emotion)
                time.sleep(delay)
        finally:
            controller.close_connection()
            logging.info("Finished sending emotions and closed connection.")
    else:
        logging.warning("Could not open serial connection. Simulating sends instead.")
        for emotion in emotions:
            print(f"[SIMULATED SEND] {emotion}")
            time.sleep(max(0.05, delay))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send 7 random emotions to Arduino LED")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between sends (default: 1.0)")
    args = parser.parse_args()
    main(args.delay)
