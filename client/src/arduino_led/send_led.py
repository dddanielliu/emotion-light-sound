import serial
import time
import random
import serial.tools.list_ports # Import for port listing
import threading # Import for multi-threading

# --- Configuration ---
BAUD_RATE = 115200

# List of emotions to send
EMOTIONS = [
    "angry",
    "fear",
    "neutral",
    "sad",
    "disgust",
    "happy",
    "surprise"
]

# Flag to control the serial reading thread
stop_reading_thread = False

def send_emotion(ser_connection, emotion_to_send):
    """Sends an emotion string over the serial connection."""
    try:
        # Encode the string and add a newline character as expected by Arduino
        ser_connection.write(f"{emotion_to_send}\n".encode('utf-8'))
        print(f"Sent: '{emotion_to_send}'")
    except serial.SerialException as e:
        print(f"Error sending data: {e}")
        # Attempt to re-establish connection or exit
        raise

def read_from_arduino(ser_connection):
    """Continuously reads data from the serial port and prints it."""
    global stop_reading_thread
    while not stop_reading_thread:
        try:
            if ser_connection.in_waiting > 0:
                line = ser_connection.readline().decode('utf-8').strip()
                if line:
                    print(f"Arduino: {line}")
        except serial.SerialException as e:
            print(f"Error reading from serial port: {e}")
            break
        except Exception as e:
            print(f"Unexpected error in reading thread: {e}")
            break
        time.sleep(0.01) # Small delay to prevent busy-waiting

def select_serial_port():
    """Lists available serial ports and prompts the user to select one."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found. Please ensure your Arduino is connected.")
        return None

    print("Available serial ports:")
    candidate_port = None
    for i, port in enumerate(ports):
        print(f"  {i+1}: {port.device} ({port.description})")
        if candidate_port is None and 'Arduino' in port.description:
            candidate_port = port
    
    if candidate_port:
        print(f"Auto selecting arduino port: {candidate_port.device} ({candidate_port.description})")
        return candidate_port.device

    while True:
        try:
            choice = input("Enter the number of the port to use: ")
            index = int(choice) - 1
            if 0 <= index < len(ports):
                return ports[index].device
            else:
                print("Invalid choice. Please enter a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def main():
    """Main function to connect to Arduino and send random emotions."""
    global stop_reading_thread
    ser = None
    reading_thread = None
    try:
        selected_port = select_serial_port()
        if not selected_port:
            return

        print(f"Attempting to connect to Arduino on {selected_port} at {BAUD_RATE} baud...")
        ser = serial.Serial(selected_port, BAUD_RATE, timeout=1)
        time.sleep(2)  # Give the Arduino time to reset after connection

        # Start the reading thread
        reading_thread = threading.Thread(target=read_from_arduino, args=(ser,))
        reading_thread.daemon = True # Allow main program to exit even if thread is still running
        reading_thread.start()

        print("Connection established. Sending random emotions...")
        while True:
            # Choose a random emotion from the list
            random_emotion = random.choice(EMOTIONS)
            send_emotion(ser, random_emotion)

            # Wait for a random duration between 1 and 10 seconds
            random_delay = random.uniform(1, 10)
            print(f"Waiting for {random_delay:.2f} seconds...")
            time.sleep(random_delay)

    except serial.SerialException as e:
        print(f"\nError: Could not open serial port.")
        print(f"Please ensure:")
        print(f"  1. The Arduino is connected to your computer.")
        print(f"  2. The selected port is correct.")
        print(f"  3. The Arduino IDE Serial Monitor is closed (only one program can access the port at a time).")
        print(f"Details: {e}")
    except KeyboardInterrupt:
        print("\nProgram terminated by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        stop_reading_thread = True # Signal the reading thread to stop
        if reading_thread and reading_thread.is_alive():
            reading_thread.join(timeout=1) # Wait for the thread to finish
        if ser and ser.is_open:
            print("Closing serial connection.")
            ser.close()

if __name__ == "__main__":
    main()