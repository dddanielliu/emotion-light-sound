# 光聲隨心 (emotion-light-sound)

This project is a real-time interactive system that translates human emotion into an ambient experience of light and sound.

## Architecture

The project consists of two main components:

1.  **Client**: A local application that captures video from a webcam, detects the user's emotion using OpenCV, controls an Arduino-based LED strip, and communicates with the server.
2.  **Server**: A backend service running in Docker that receives emotion data, generates music using a deep learning model, and sends it back to the client.

## Getting Started

### Prerequisites

-   Docker
-   Docker Compose
-   Python 3.12+
-   An Arduino board
-   A webcam

### Server Setup

The server runs inside a Docker container.

```bash
cd server
docker-compose up -d
```

The server will be running on `http://localhost:8080`.

### Client Setup

The client runs locally on your machine.

1.  **Navigate to the client directory:**
    ```bash
    cd client
    ```

2.  **Install dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    # Using Python's built-in venv
    python -m venv .venv
    source .venv/bin/activate
    
    # Install dependencies using uv (or pip)
    pip install uv
    uv pip install -e .
    ```

3.  **Configure Environment:**
    Create a `.env` file from the example and ensure `CLOUD_SERVER_URL` points to your server's address.
    ```bash
    cp .env.example .env
    # Edit .env and set CLOUD_SERVER_URL=http://localhost:8080
    ```

4.  **Run the client:**
    The client is launched via its `src` module.
    ```bash
    python -m src
    ```
    Open your web browser to `http://localhost:8000` to start the experience.