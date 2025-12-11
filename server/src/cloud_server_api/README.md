# Cloud Server API

This component is the core of the server for the "光聲隨心 (emotion-light-sound)" project. It's a FastAPI application that handles all client communication.

## Functionality

- **FastAPI Backend**: Provides HTTP endpoints for health checks and retrieving generated music.
- **Socket.IO Server**: Manages real-time, bidirectional communication with clients.

## Socket.IO Events

-   **`connect`**: A client connects to the server.
-   **`disconnect`**: A client disconnects.
-   **`emotion_update`**: Receives emotion data from a client. This is the primary trigger for the music generation process.
    -   Payload: `{ "stage": "pre" | "post", "emotion": "happy" | "sad" | ..., "metadata": {...} }`
-   **`music_generated`**: Sent back to the client after music has been generated, providing a `file_id` that the client can use to download the audio.
    -   Payload: `{ "file_id": "...", "stage": "...", "emotion": "...", ... }`
-   **`ping` / `pong`**: Used to keep the connection alive.

## HTTP Endpoints

-   `GET /`: A simple endpoint to confirm the server is running.
-   `GET /ping`: Health check endpoint.
-   `GET /get_music`: Endpoint for clients to download the generated music file using a `file_id` and `owner_id`.
