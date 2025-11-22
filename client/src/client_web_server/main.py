import asyncio
import io
import logging
import os
import time
from contextlib import asynccontextmanager

import socketio
import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from opencv_face import face_detection

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Application startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting lifespan...")
    yield

# Create SocketIO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=30,
    ping_interval=25,
)

# Create FastAPI application
app = FastAPI(
    title="Multi-client Media Processing Server",
    description="WebSocket server supporting real-time media processing",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static file service (frontend files)
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
print("Frontend path:", frontend_path)
if os.path.exists(frontend_path):
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_path,"js")), name="js")

# Mount SocketIO, wrap both applications together and route traffic to them
app.mount("/socket.io", socketio.ASGIApp(sio, app))


@sio.event
async def connect(sid, environ, auth):
    # logger.info(f"Client connected: {sid}, auth: {auth}")
    # await connection_manager.add_connection(sid)
    client_id = str(auth.get("client_id"))
    logger.info("Client %s connected with session ID %s (auth: %s)", client_id, sid, auth)


@sio.on("video_frame")
async def handle_video_frame(sid, metadata, blob):
    # client_id = metadata["client_id"]
    # print(client_id)
    timestamp = metadata.get("timestamp")
    width = metadata["width"]
    height = metadata["height"]

    # blob is raw bytes

    # img = Image.open(io.BytesIO(blob)).convert("RGB")
    # save PNG
    # filename = f"frames/{client_id}_{int(timestamp * 1000)}.png"
    # print(
    #     f"Image Received ({width}, {height}) original: {metadata.get('originalWidth')}x{metadata.get('originalHeight')}"
    # )
    # img.save(filename, format="PNG")

    # processed_image = face_detection.detect_faces(blob)
    loop = asyncio.get_running_loop()
    processed_image, emotion = await loop.run_in_executor(
        None, face_detection.detect_faces, blob
    )
    reply_event = "processed_video_frame"
    reply_metadata = {
        # "client_id": client_id,
        "sid": sid,
        "timestamp_received": time.time(),
        "original_timestamp": timestamp,
        "width": width,
        "height": height,
        "emotion": emotion
    }
    await sio.emit(reply_event, data=(reply_metadata, processed_image), to=sid)


@app.get("/")
async def serve_index(request: Request):
    """Serve main page"""
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "server is running"}

# @app.get("/js/{js_file}")
# async def serve_js(js_file: str):
#     """Serve main page"""
#     logger.debug(f"frontend_path: {frontend_path}")
#     js_path = os.path.join(frontend_path, "js", js_file)
#     if os.path.exists(js_path):
#         return FileResponse(js_path)
#     return {"message": "server is running"}



@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Server is running normally"}


def main():
    logger.info("Starting multi-client media processing server...")
    # When running as a module (python -m src.model.stream_server.main),
    # __package__ will be the package path (e.g. 'src.model.stream_server').
    # Use a package-qualified import string for uvicorn so the reloader's
    # subprocess imports the correct module and relative imports work.
    if __package__:
        module_path = f"{__package__}.main:app"
    else:
        module_path = "main:app"

    uvicorn.run(module_path, host="0.0.0.0", port=8000, log_level="info", reload=False)

if __name__ == "__main__":
    main()
