import asyncio
import socketio
import logging
import os
from urllib.parse import urljoin, urlencode
import requests
import datetime

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
    #     'file_id': 'f92fd34d99718d9b6c51bff9ff96e0a6d36e3718738b4492746b9ce0b51c6693',
    #     'metadata':
    #         {
    #             'timestamp': '2025-11-23T10:44:10.953+00:00',
    #             'emotion_dict': {'pre': 'happy'},
    #             'prompt': 'generate music based on emotion'
    #         }
    # }

    file_id = data["file_id"]
    params = {
        "owner_id": sid_cloud,
        "file_id": file_id
    }
    url = urljoin(CLOUD_SERVER_URL, "get_music") + '?' + urlencode(params)

    # get the music from server
    music_bytes = requests.get(url).content


    timestamp = data.get("metadata", {}).get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    with open(f"music_{timestamp}.wav", "wb") as f:
        f.write(music_bytes)

    # TODO: Play the music in frontend



async def send_update():
    emodict = {"pre": "happy"}
    metadata = {"confidence": 0.95}

    await sio_cloud.emit(
        "emotion_update",
        {
            "emotion_dict": emodict,
            "metadata": metadata,
        },
    )
    logging.info("Sent emotion_update")

async def send_updates_loop():
    for i in range(5):
        await send_update()
        logging.info("Sent update %d/5", i + 1)
        await asyncio.sleep(2)


async def main():
    await sio_cloud.connect(CLOUD_SERVER_URL)
    # start the update loop
    asyncio.create_task(send_updates_loop())
    # keep running
    await sio_cloud.wait()


asyncio.run(main())
