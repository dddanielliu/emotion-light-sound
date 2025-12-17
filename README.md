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

### Client Setup

The client runs locally on your machine.

See [client/](client).

### Server Setup

The server can either runs remotely or locally, it is recommened the server to have GPU to accelerate music generation process.

See [server/](server).
