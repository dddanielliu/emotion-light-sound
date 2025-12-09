import logging
import random
import threading
import time

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ArduinoLEDController:
    def __init__(self):
        self.ser = None
        self.reading_thread = None
        self.stop_reading_thread = False
        self.BAUD_RATE = 115200
        self.EMOTIONS = [
            "angry",
            "fear",
            "neutral",
            "sad",
            "disgust",
            "happy",
            "surprise",
        ]

    def _select_serial_port(self):
        """Automatically selects an Arduino serial port."""
        ports = serial.tools.list_ports.comports()
        if not ports:
            logger.warning(
                "No serial ports found. Please ensure your Arduino is connected."
            )
            return None

        for port in ports:
            # Look for common Arduino descriptions
            if (
                "Arduino" in port.description
                or "USB-SERIAL CH340" in port.description
                or "ttyACM" in port.device
            ):
                logger.info(
                    f"Auto-selected Arduino port: {port.device} ({port.description})"
                )
                return port.device

        logger.warning(
            "No Arduino-like serial port found automatically. Please check connection."
        )
        return None

    def list_available_ports(self):
        """Lists all available serial ports."""
        ports = serial.tools.list_ports.comports()
        if not ports:
            return []

        available_ports_info = []
        for port in ports:
            available_ports_info.append(
                {"device": port.device, "description": port.description}
            )
        return available_ports_info

    def initialize_connection(self):
        """Establishes serial connection and starts reading thread."""
        if self.ser and self.ser.is_open:
            logger.info("Serial connection already open.")
            return True

        selected_port = self._select_serial_port()
        if not selected_port:
            logger.error("Failed to initialize: No serial port selected.")
            available_ports = self.list_available_ports()
            if available_ports:
                logger.info("Available serial ports:")
                for p in available_ports:
                    logger.info(f"  - {p['device']} ({p['description']})")
            else:
                logger.info("No serial ports found at all.")
            return False

        try:
            logger.info(
                f"Attempting to connect to Arduino on {selected_port} at {self.BAUD_RATE} baud..."
            )
            self.ser = serial.Serial(selected_port, self.BAUD_RATE, timeout=1)
            time.sleep(2)  # Give Arduino time to reset

            self.stop_reading_thread = False
            self.reading_thread = threading.Thread(target=self._read_from_arduino)
            self.reading_thread.daemon = True
            self.reading_thread.start()
            logger.info(
                "Arduino serial connection established and reading thread started."
            )
            return True
        except serial.SerialException as e:
            logger.error(f"Could not open serial port {selected_port}: {e}")
            logger.error("Please ensure:")
            logger.error("  1. The Arduino is connected to your computer.")
            logger.error("  2. The selected port is correct.")
            logger.error("  3. The Arduino IDE Serial Monitor is closed.")
            self.ser = None
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during connection: {e}")
            self.ser = None
            return False

    def _read_from_arduino(self):
        """Continuously reads data from the serial port."""
        while not self.stop_reading_thread:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8").strip()
                    if line:
                        logger.debug(f"Arduino: {line}")
            except serial.SerialException as e:
                logger.error(f"Error reading from serial port: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error in Arduino reading thread: {e}")
                break
            time.sleep(0.01)

    def update_led(self, emotion: str):
        """Sends an emotion string over the serial connection to update LED."""
        if not self.ser or not self.ser.is_open:
            logger.warning("Serial connection not established. Cannot send emotion.")
            return

        if emotion not in self.EMOTIONS:
            logger.warning(
                f"Invalid emotion '{emotion}'. Must be one of {self.EMOTIONS}"
            )
            return

        try:
            self.ser.write(f"{emotion}\n".encode("utf-8"))
            logger.info(f"Sent emotion to Arduino: '{emotion}'")
        except serial.SerialException as e:
            logger.error(f"Error sending data to Arduino: {e}")
            # Consider attempting to re-initialize connection here if critical
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending emotion: {e}")

    def close_connection(self):
        """Stops the reading thread and closes the serial connection."""
        self.stop_reading_thread = True
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=1)
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("Arduino serial connection closed.")
        self.ser = None
        self.reading_thread = None
