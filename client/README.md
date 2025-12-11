# Client for 光聲隨心 (emotion-light-sound)

This directory contains the client-side application for the "光聲隨心" project.

## Functionality

The client application is responsible for:
- Capturing video from a webcam.
- Performing real-time facial emotion detection.
- Serving a local web interface for the user.
- Controlling an Arduino for LED light feedback.
- Communicating with the main server to send emotion data and receive generated music.

## Setup and Execution

### 1. Installation

Ensure you are in the `client` directory. It is recommended to use a virtual environment.

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
# Assumes you have uv installed (`pip install uv`)
uv pip install -e .
```

### 2. Configuration

Copy the environment variable template and configure it.

```bash
cp .env.example .env
```

Edit the `.env` file to set the `CLOUD_SERVER_URL`, which should point to the address of the running backend server (e.g., `http://localhost:8080`).

### 3. Running the Client

To start the client application, run the `src` module from within the `client` directory:

```bash
python -m src
```

After running the command, open your web browser and navigate to `http://localhost:8000` to begin the interactive experience.