# Server Source Code

This directory contains the main source code for the server application of the "光聲隨心 (emotion-light-sound)" project.

## Structure

- `__main__.py`: The main entry point for the server application, executed when the Docker container starts. It launches the cloud server API.
- `cloud_server_api/`: A FastAPI and Socket.IO application that handles client connections, emotion updates, and music file distribution.
- `music_gen/`: The core module responsible for queuing emotion-based requests and generating music using a machine learning model.