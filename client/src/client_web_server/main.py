import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from urllib.parse import urlencode, urljoin

import requests
import socketio
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..opencv_face import face_detection

# Load environment variables from .env file
load_dotenv()

CLOUD_SERVER_URL = os.getenv("CLOUD_SERVER_URL")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Get cloud server URL from environment
CLOUD_SERVER_URL = os.getenv("CLOUD_SERVER_URL")
print("CLOUD_SERVER_URL:", CLOUD_SERVER_URL)


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
    #     'file_id': 'f92fd34d99718d9b6c51bff9ff96e0a6d36e3718738b4492746b9ce0b51c6693',
    #     'stage': 'pre', # or 'post'
    #     'emotion': 'happy',
    #     'metadata': {
    #         'timestamp': '2025-11-23T10:44:10.953+00:00',
    #         ...
    #     }
    # }

    file_id = data["file_id"]
    params = {
        "owner_id": sid_cloud,
        "file_id": file_id
    }
    url = urljoin(CLOUD_SERVER_URL, "get_music") + '?' + urlencode(params)

    # get the music from server
    # music_bytes = requests.get(url).content
    # with open("music.wav", "wb") as f:
    #     f.write(music_bytes)

    # Add URL to data so frontend can play it
    data["url"] = url

    # Forward the music event to the frontend (browser)
    # We emit to all connected clients since we don't track which browser corresponds to which cloud session easily here
    # Ideally, we would map local sid to cloud sid, but for now broadcast is fine for single user
    # print(f"Forwarding music to frontend: {file_id}")
    await sio.emit("music_generated", data)

def save_file(filename, data):
    with open(filename, "wb") as f:
        f.write(data)

async def keep_alive():
    """Background task to keep the connection alive"""
    while True:
        # logger.debug("Sending keep-alive ping to cloud server")
        await sio_cloud.emit("ping")
        await asyncio.sleep(25)

async def send_emotion_update(emotion_dict, metadata):
    """
    Send emotion update to cloud server.
    
    Args:
        emotion_dict: dict with "pre" or "post" key and emotion value
        metadata: dict with "confidence" key
    """
    try:
        if sio_cloud.connected and sid_cloud:
            await sio_cloud.emit(
                "emotion_update",
                {
                    "emotion_dict": emotion_dict,
                    "metadata": metadata,
                },
            )
            emotion_type = "pre" if "pre" in emotion_dict else "post"
            emotion_value = emotion_dict.get("pre") or emotion_dict.get("post")
            logger.info(f"✉️  Sent emotion_update [{emotion_type}]: {emotion_value} (confidence: {metadata.get('confidence', 0):.2f})")
            print(f"✉️  Sent emotion_update [{emotion_type}]: {emotion_value} (confidence: {metadata.get('confidence', 0):.2f})")
        else:
            logger.debug(f"⚠️  Cloud server not connected (connected={sio_cloud.connected}, sid={sid_cloud}), skipping emotion update")
    except Exception as e:
        logger.error(f"Error sending emotion update: {e}")

# Application startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting lifespan...")
    
    # Check if CLOUD_SERVER_URL is set
    if CLOUD_SERVER_URL:
        logger.info(f"CLOUD_SERVER_URL is set to: {CLOUD_SERVER_URL}")
        # Connect to Cloud Server on startup
        try:
            logger.info(f"Attempting to connect to cloud server at {CLOUD_SERVER_URL}...")
            await sio_cloud.connect(CLOUD_SERVER_URL)
            logger.info("✅ Connected to cloud server successfully!")
            asyncio.create_task(keep_alive())
            
            # Register emotion update callback with the main event loop
            loop = asyncio.get_running_loop()
            face_detection.set_emotion_update_callback(send_emotion_update, loop)
            logger.info("✅ Registered emotion update callback")
        except Exception as e:
            logger.error(f"❌ Failed to connect to cloud server: {e}")
            logger.error(f"Emotion updates will NOT be sent to cloud server")
    else:
        logger.warning("⚠️  CLOUD_SERVER_URL not set, skipping cloud server connection")
        logger.warning("Set CLOUD_SERVER_URL environment variable to enable cloud features")

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
    # When running as a module (python -m src.client_web_server.main),
    # __package__ will be the package path (e.g. 'src.client_web_server').
    # Use a package-qualified import string for uvicorn so the reloader's
    # subprocess imports the correct module and relative imports work.
    if __package__:
        module_path = f"{__package__}.main:app"
    else:
        module_path = "main:app"

    uvicorn.run(module_path, host="0.0.0.0", port=8000, log_level="info", reload=False)

if __name__ == "__main__":
    main()
