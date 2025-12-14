# Client Source Code

This directory contains the main source code for the client application of the "光聲隨心 (emotion-light-sound)" project.

## Structure

- `__main__.py`: The main entry point for the client application, executed when you run `python -m src`. It initializes and starts the client web server.
- `client_web_server/`: A FastAPI and Socket.IO application that serves the frontend and manages communication.
- `opencv_face/`: Handles face detection and emotion recognition from the webcam feed.
- `arduino_led/`: Manages communication with the Arduino to control the LED lights.
