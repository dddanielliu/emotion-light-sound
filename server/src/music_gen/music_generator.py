import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, ValidationError, model_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MusicGenerator:
    def __init__(self):
        """Initialize the music generator model here"""
        self.model = None

    def generate(self, prompt: str) -> bytes:
        # Generate music based on the prompt
        print(f"Generating music for prompt: {prompt}")


        """ Simulate generated generation """
        import time
        time.sleep(2)  # Simulate time-consuming generation
        print(f"Finished generating music for prompt: {prompt}")
        import os
        import random
        try:
            files = os.listdir("test_musics")
            if len(files) == 0:
                raise Exception("No test music files found")
            file = random.choice(files)
            # read the file to bytes
            with open(os.path.join("test_musics", file), "rb") as f:
                music_bytes = f.read()
            return music_bytes
        except Exception as e:
            print("fake generation failed:", e)
            return b""

        return b""  # Placeholder for generated music bytes


class InstanceItem(BaseModel):
    sid: Optional[str] = None
    client_id: Optional[str] = None
    stage: str
    emotion: str
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    def check_sid_or_client_id(cls, values):
        sid = values.get("sid") or None
        client_id = values.get("client_id") or None
        if not sid and not client_id:
            raise ValidationError('Either "sid" or "client_id" must be provided.')
        return values


class QueueManager:
    def __init__(
        self,
        sender_callable: Callable,
        url_creator_callable: Callable,
    ) -> None:
        self.music_generator = MusicGenerator()
        self.queue: asyncio.Queue[InstanceItem] = asyncio.Queue()

        self.notify_socketio_client_music_generated = sender_callable
        self.create_url = url_creator_callable

        self._runner_task = asyncio.create_task(self.runner())

    async def add_item(
        self,
        sid: Optional[str] = None,
        client_id: Optional[str] = None,
        stage: str = None,
        emotion: str = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        item = InstanceItem(
            sid=sid,
            client_id=client_id,
            stage=stage,
            emotion=emotion,
            metadata=metadata,
        )
        await self.queue.put(item)

    async def runner(self):
        """Process items in the queue"""
        while True:
            item = await self.queue.get()
            print(f"Processing emotion: {item.model_dump()}")
            # Even though we use async, this ensures only one generation at a time
            generated_music = await asyncio.to_thread(
                self.music_generator.generate, item.emotion
            )
            if item.sid:
                logger.info(
                    f"Generated {len(generated_music)} bytes for sid: {item.sid}"
                )
                logger.debug(f"\titem: {item.model_dump()}")
                metadata = item.metadata if item.metadata else {}

                asyncio.create_task(
                    self.notify_socketio_client_music_generated(
                        event="music_generated",
                        sid=item.sid,
                        music_bytes=generated_music,
                        stage=item.stage,
                        emotion=item.emotion,
                        metadata=metadata,
                    )
                )

            if item.client_id:
                logger.info(
                    f"Generated {len(generated_music)} bytes for client_id: {item.client_id}"
                )
                logger.debug(f"\titem: {item.model_dump()}")
                asyncio.create_task(
                    self.create_url(
                        owner_id=item.client_id,
                        music_bytes=generated_music,
                        stage=item.stage,
                        emotion=item.emotion,
                        metadata=item.metadata,
                    )
                )

            self.queue.task_done()

            print(f"Finished processing item: {item.model_dump()}")
