import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from urllib.parse import urlencode, urljoin

import requests
import socketio
import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..opencv_face import face_detection

CLOUD_SERVER_URL = os.getenv("CLOUD_SERVER_URL")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

sio_cloud = socketio.AsyncClient()
sid_cloud = None

@sio_cloud.event
async def connect_cloud():
    logger.info("Connected to Cloud server")

@sio_cloud.event
async def disconnect_cloud():
    logger.info("Disconnected from Cloud server")

@sio_cloud.on("connected")
async def handle_set_sid_cloud(data):
    global sid_cloud
    sid_cloud = data["sid"]
    logger.info("Set sid to %s", sid_cloud)

@sio_cloud.on("music_generated")
async def music_generated(data):
    """
    Handle receiving music from the cloud.
    """
    print(f"Received music {data}")
    # data example:
    # {
    #     'fileurl': 'f92fd34d99718d9b6c51bff9ff96e0a6d36e3718738b4492746b9ce0b51c6693',
    #     'metadata':
    #         {
    #             'timestamp': '2025-11-23T10:44:10.953+00:00',
    #             'emotion_dict': {'pre': 'happy'},
    #             'prompt': 'generate music based on emotion'
    #         }
    # }

    fileurl = data["fileurl"]
    params = {
        "owner_id": sid_cloud,
        "file": fileurl
    }
    url = urljoin(CLOUD_SERVER_URL, "get_music") + '?' + urlencode(params)

    # get the music from server
    music_bytes = requests.get(url).content
    # with open("music.wav", "wb") as f:
    #     f.write(music_bytes)

    # TODO: Play the music in frontend

def save_file(filename, data):
    with open(filename, "wb") as f:
        f.write(data)

async def keep_alive():
    """Background task to keep the connection alive"""
    while True:
        # logger.debug("Sending keep-alive ping to cloud server")
        await sio_cloud.emit("ping")
        await asyncio.sleep(25)

# Application startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting lifespan...")
    
    # Connect to Cloud Server on startup
    try:
        await sio_cloud.connect(CLOUD_SERVER_URL)
        logger.info("Connected to cloud server at %s", CLOUD_SERVER_URL)
        asyncio.create_task(keep_alive())
    except Exception as e:
        logger.error(f"Failed to connect to cloud server: {e}")

    yield

    yield

    # Cleanup on shutdown
    if sio_cloud.connected:
        await sio_cloud.disconnect()

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
