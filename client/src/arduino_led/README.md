# Arduino LED Controller

This component manages the communication between the Python client and an Arduino board to control LED lights for the "光聲隨心 (emotion-light-sound)" project.

## Functionality

- `send_led.py`: A Python script that sends commands (e.g., color codes) over a serial connection to the Arduino.
- `arduino_led.ino`: The sketch to be uploaded to the Arduino board. It listens for incoming serial data and sets the LED colors accordingly.

## Setup

1.  Connect your Arduino board to the computer.
2.  Open the `arduino_led.ino` file in the Arduino IDE.
3.  Select the correct board and port.
4.  Upload the sketch to your Arduino.
5.  The Python client (`send_led.py`) will automatically try to connect to the correct serial port when it starts.