import asyncio
import logging
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, ValidationError, model_validator
from transformers import pipeline
import torch
import random
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MusicGenerator:
    def __init__(self):
        self.device = None
        self.synthesiser = None
        self.prompt = ""
        self.emotion_prompt = {
            "angry":    "angry, 100 bpm, C key",
            "disgust":  "creepy, C minor key",
            "fear":     "horror movie soundtrack, dark, 100 BPM, C minor key",
            "happy":    "bright major chords, happy type, 128 BPM C Major",
            "sad":      "sad, rain sounds in background, emotional, 120 BPM",
            "surprise": "circus music, 100 BPM, C major chord",
            "neutral":  "soft and gentle, peaceful atmosphere, nature sounds, 90 BPM, C key"
        }
        self._set_device()
        self._load_model_once()
    def _load_model_once(self):
        self.synthesiser = pipeline(
                "text-to-audio",
                model="facebook/musicgen-small",
                device=self.device
            )
        print("Model loaded successfully")

    def _set_device(self):
        if torch.backends.mps.is_available():
            self.device = 0
            print("Using Apple Silicon MPS (or MPS-supported device)")
        else:
            self.device = -1
            print("Using CPU")
        

    def emotion_to_prompt(self, emotion: str):
        style = "only piano"
        self.prompt = self.emotion_prompt.get(emotion.lower(), self.emotion_prompt["neutral"]) +", "+ style
        

    def generate_music(self, prompt: str, duration: int = 30):
        print(prompt)
        print(f"duration = {duration}")

        if not prompt:
            raise ValueError("prompt is empty!")
        self.prompt = prompt

        if duration > 0:
            self.duration = duration
        else:
            raise ValueError("duration must > 0")

        try:
            # 隨機 seed (optional, for variation)
            seed = random.randint(0, 2**32 - 1)
            torch.manual_seed(seed)
            if self.device == "cpu":
                pass  # CPU，不用 cuda 設定 seed
            # MPS 的 seed 設定由 PyTorch 自己管理

            result = self.synthesiser(
                self.prompt,
                forward_params={
                    "do_sample": True,
                    "max_new_tokens": self.duration * 50
                }
            )
            return result

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Error generating music: {e}")

        
        # """ Simulate generated generation """
        # import time
        # time.sleep(2)  # Simulate time-consuming generation
        # print(f"Finished generating music for prompt: {prompt}")
        # import os
        # import random
        # try:
        #     files = os.listdir("test_musics")
        #     if len(files) == 0:
        #         raise Exception("No test music files found")
        #     file = random.choice(files)
        #     # read the file to bytes
        #     with open(os.path.join("test_musics", file), "rb") as f:
        #         music_bytes = f.read()
        #     return music_bytes
        # except Exception as e:
        #     print("fake generation failed:", e)
        #     return b""

class InstanceItem(BaseModel):
    sid: Optional[str] = None
    client_id: Optional[str] = None
    emotion: str                    # 改成 emotion，不是 prompt
    duration: int = 15
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
        emotion: str,
        duration: int = 15,             # ✅ 修正：加逗號，int 放型別註解
        sid: Optional[str] = None,      # ✅ 加逗號
        client_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        item = InstanceItem(
            sid=sid,
            client_id=client_id,
            emotion=emotion,            # ✅ 用 emotion，不是 prompt
            duration=duration,          # ✅ 傳 duration
            metadata=metadata
        )
        await self.queue.put(item)

    async def runner(self):
        """Process items in the queue"""
        while True:
            item = await self.queue.get()
            
            # ✅ 修正：用 item.emotion
            print(f"Processing emotion: {item.emotion}")
            generated_music = await asyncio.to_thread(
                self.music_generator.generate,
                item.emotion,
                item.duration
            )
            
            # ✅ 正確的 metadata 處理
            metadata = (item.metadata or {}).copy()
            metadata.update({
                "emotion": item.emotion,
                "duration": item.duration
            })

            if item.sid:
                logger.info(
                    f"Generated {len(generated_music)} bytes for sid: {item.sid}"
                )
                logger.debug(f"\titem: {item.model_dump()}")
                metadata = item.metadata if item.metadata else {}
                metadata["prompt"] = item.prompt

                asyncio.create_task(
                    self.notify_socketio_client_music_generated(
                        event="music_generated",
                        sid=item.sid,
                        music_bytes=generated_music,
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
                        metadata=metadata,
                    )
                )

            self.queue.task_done()

            print(f"Finished processing item: {item.prompt}")
