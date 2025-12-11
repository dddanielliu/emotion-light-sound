# Server for 光聲隨心 (emotion-light-sound)

This directory contains the server-side application for the "光聲隨心" project.

## Functionality

The server application is responsible for:
- Receiving emotion data from one or more clients via a Socket.IO connection.
- Managing a queue for music generation requests.
- Using a machine learning model to generate music based on the received emotion.
- Providing an endpoint for clients to download the generated music files.

## Setup and Execution

The server is designed to be run with Docker and Docker Compose, as it relies on a specific environment with GPU access for music generation.

### Prerequisites

- Docker
- Docker Compose
- For GPU acceleration: NVIDIA drivers and the NVIDIA Container Toolkit installed on the host machine.

### Running the Server

To build and run the server, execute the following command from the `server` directory:

```bash
docker-compose up -d
```

This command will:
1. Build the Docker image as defined in the `Dockerfile`.
2. Start a container in detached mode (`-d`).
3. Map port `8080` on the host to port `8080` in the container.
4. Mount the necessary volumes for source code and temporary file storage.

You can check the logs of the running container with:
```bash
docker-compose logs -f
```

To stop the server, run:
```bash
docker-compose down
```