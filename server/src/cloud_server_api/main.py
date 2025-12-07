import asyncio
import hashlib
import json
import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import socketio
import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..music_gen import QueueManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

musicgen_queue: QueueManager | None = None
music_urls: Dict[str, Dict[str, str]] = {}
music_urls_lock: asyncio.Lock | None = None


# Create SocketIO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=30,
    ping_interval=25,
)


async def send_to_socketio_client(event: str, to: str, **kwargs) -> None:
    """Helper function to send data to a specific client"""
    # Converts {'a': 1, 'b': 2} -> (1, 2)
    # keys are LOST. Client receives: 1, 2
    # payload = tuple(kwargs.values())
    try:
        logging.debug(f"Sending event '{event}' to {to} with payload: {kwargs}")
        await sio.emit(event, data=kwargs, to=to)
        logging.info("Event sent successfully")
    except Exception as e:
        logger.error(f"Failed to send to {to}: {e}")

    # Usage:
    # send_to_socketio_client('my_event', 'sid123', name='Alice', age=30)


def _save_file_sync(
    owner_id: str, music_bytes: bytes, **kwargs
) -> tuple[str, str]:
    """
    INTERNAL WORKER: Runs in a separate thread.
    Blocks CPU (Hashing) and Disk (Writing).
    Returns: (url_hash, filepath)
    """
    # 2. Path Calculation
    dt_formatted = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    # Use owner_id (client_id) in filename to keep things organized
    filename = f"music_{owner_id}_{dt_formatted}.wav"

    kwargs_str = ""
    
    for key, value in kwargs.items():
        kwargs_str += f"{key}:{value},"
    combined_str = filename + kwargs_str
    url_hash = hashlib.sha256(combined_str.encode()).hexdigest()

    output_dir = os.path.join("tmp", "music")
    filename = url_hash
    filepath = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(music_bytes)

    return url_hash, filepath


async def createmusicurl(
    owner_id: str, music_bytes: bytes, **kwargs
) -> str:
    """Create a temporary URL for the generated music file"""
    print("Creating music URL...")
    url_hash, filepath = await asyncio.to_thread(
        _save_file_sync, owner_id, music_bytes, **kwargs
    )
    global music_urls

    async with music_urls_lock:
        if owner_id not in music_urls:
            music_urls[owner_id] = {}
        music_urls[owner_id][url_hash] = filepath
        print(f"Music URL created: {url_hash} -> {filepath} for {owner_id}")
        print(f"Current {owner_id}'s music_urls: {music_urls[owner_id]}")
    return url_hash


async def remove_file_and_entry(owner_id: str, url_hash: str, filepath: str) -> None:
    """Remove the file from disk and delete the entry from music_urls"""
    global music_urls
    async with music_urls_lock:
        if owner_id in music_urls and url_hash in music_urls[owner_id]:
            filepath = music_urls[owner_id][url_hash]
            del music_urls[owner_id][url_hash]
        if not music_urls[owner_id]:
            del music_urls[owner_id]
    if os.path.exists(filepath):
        os.remove(filepath)
        print("File deleted.", filepath)
    else:
        print("File does not exist.", filepath)


async def notify_socketio_client_music_generated(
    event: str,
    sid: str,
    music_bytes: bytes,
    **kwargs,
) -> None:
    url_hash = await createmusicurl(
        owner_id=sid, music_bytes=music_bytes, **kwargs
    )
    await send_to_socketio_client(event=event, to=sid, file_id=url_hash, **kwargs)


# Application startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Define a global exception handler for asyncio
    def handle_task_exception(loop, context):
        msg = context.get("message", "Unhandled exception in asyncio task")
        exc = context.get("exception")
        if exc:
            logger.error(f"{msg}: {exc}", exc_info=exc)
        else:
            logger.error(f"{msg}")

    logger.info("Starting lifespan...")

    shutil.rmtree("tmp", ignore_errors=True)

    # Register the handler
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(handle_task_exception)

    global musicgen_queue
    musicgen_queue = QueueManager(
        sender_callable=notify_socketio_client_music_generated,
        url_creator_callable=createmusicurl,
    )
    global music_urls_lock
    music_urls_lock = asyncio.Lock()
    logger.info("Lifespan startup complete.")
    yield


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

# Mount SocketIO, wrap both applications together and route traffic to them
app.mount("/socket.io", socketio.ASGIApp(sio, app))


@sio.event
async def connect(sid, environ, auth):
    # logger.info(f"Client connected: {sid}, auth: {auth}")
    # await connection_manager.add_connection(sid)
    # client_id = str(auth.get("client_id")) if auth else "unknown"
    logger.info("Client connected with session ID %s (auth: %s)", sid, auth)
    await sio.emit("connected", {"sid": sid}, to=sid)


class EmotionUpdate(BaseModel):
    stage: str
    emotion: str
    metadata: Optional[Dict] = None


@sio.on("emotion_update")
async def handle_emotion_update(sid, data):
    update = EmotionUpdate(**data)
    stage = update.stage
    emotion = update.emotion
    metadata = update.metadata if update.metadata else {}
    dt = datetime.now(timezone.utc)
    # Or a custom timezone offset, e.g., UTC+3
    # tz = timezone(timedelta(hours=3))
    # dt = dt.astimezone(tz)

    # ISO-8601 format with milliseconds
    dt = datetime.now(timezone.utc)
    dt_formatted = dt.isoformat(timespec="milliseconds")
    timestamp = metadata.get("timestamp", dt_formatted)
    logger.info(
        f"Emotion update received at {timestamp}: {stage} {emotion} ({metadata})"
    )

    metadata["timestamp"] = dt_formatted

    await musicgen_queue.add_item(
        sid=sid,
        stage=stage,
        emotion=emotion,
        metadata=metadata,
    )


@sio.on("ping")
async def handle_ping(sid):
    """Handle ping from client for health check"""
    logger.info(f"Ping received from {sid}")
    await sio.emit("pong", data={"message": "pong"}, to=sid)


@app.get("/")
async def serve_index(request: Request):
    """Serve main page"""
    return {"message": "server is running"}


@app.put("/emotion_update")
async def receive_emotion_update(
    payload: EmotionUpdate,
    client_id: str | None = None,
):
    """Receive emotion update via HTTP PUT"""
    # metadata = data.get("metadata", {})
    new_created_client_id = False
    if client_id is None:
        new_created_client_id = True
        client_id = str(uuid.uuid4())
    stage = payload.stage
    emotion = payload.emotion
    metadata = payload.metadata if payload.metadata else {}
    dt = datetime.now(timezone.utc)
    # Or a custom timezone offset, e.g., UTC+3
    # tz = timezone(timedelta(hours=3))
    # dt = dt.astimezone(tz)

    # ISO-8601 format with milliseconds
    dt_formatted = dt.isoformat(timespec="milliseconds")
    timestamp = metadata.get("timestamp", dt_formatted)

    logger.info(
        f"Emotion update received at {timestamp}: {stage} {emotion} ({metadata})"
    )

    metadata["timestamp"] = timestamp

    await musicgen_queue.add_item(
        client_id=client_id,
        stage=stage,
        emotion=emotion,
        metadata=metadata,
    )
    if new_created_client_id:
        return {"status": "queued", "client_id": client_id}
    else:
        return {"status": "queued"}
    # Process the emotion update in the background if needed


@app.get("/get_music")
async def get_music(
    background_tasks: BackgroundTasks, owner_id: str, file_id: str | None = None
):
    """Endpoint to retrieve generated music file"""
    if file_id is None:
        files_list = []
        if owner_id in music_urls:
            async with music_urls_lock:
                files_list = list(music_urls[owner_id].keys())
        return {"available_files": files_list}
    filepath = None
    async with music_urls_lock:
        if owner_id in music_urls and file_id in music_urls[owner_id]:
            filepath = music_urls[owner_id][file_id]
    if filepath and os.path.exists(filepath):
        background_tasks.add_task(remove_file_and_entry, owner_id, file_id, filepath)
        return FileResponse(
            filepath, media_type="audio/wav", filename=os.path.basename(filepath)
        )
    else:
        return {"error": "Music file not found"}, 404


@app.get("/ping")
async def ping():
    """Health check endpoint"""
    return {"message": "pong"}


def main():
    logger.info("Starting multi-client media processing server...")
    # When running as a module (python -m src.cloud_server.main),
    # __package__ will be the package path (e.g. 'src.cloud_server.main').
    # Use a package-qualified import string for uvicorn so the reloader's
    # subprocess imports the correct module and relative imports work.
    if __package__:
        module_path = f"{__package__}.main:app"
    else:
        module_path = "main:app"

    uvicorn.run(module_path, host="0.0.0.0", port=8080, log_level="info", reload=False)


if __name__ == "__main__":
    main()
