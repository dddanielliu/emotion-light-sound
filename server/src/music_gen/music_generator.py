import asyncio
import logging
import random
import traceback
from typing import Any, Callable, Dict, Optional

import torch
from pydantic import BaseModel, ValidationError, model_validator
from transformers import pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MusicGenerator:
    def __init__(self):
        self.device = None
        self.synthesiser = None
        self.emotion_prompt = {
            "angry": "E Phrygian, an extremely fast and aggressive rock-like rhythm. Piano hits rapid, low-register clusters. Cello/Viola plays intense, short-bowed bursts. Pounding, repetitive bassline and explosive, heavy percussion, reflecting turmoil.",
            "disgust": "C Phrygian, extremely fast and aggressive rock music. Features sharp, dissonant low-register piano clusters, heavy tremolo strings, and loud, pounding drum and bass rhythms.",
            "fear": "C Locrian, a slow, deeply unsettling and suspenseful atmosphere. Uses sustained, quiet, and highly dissonant piano notes, low-register string drones, and sparse, irregular bass drum hits.",
            "happy": "G Major, a bright and uplifting up-tempo track that gradually builds energy. The piano uses high, staccato chords. Cello/Viola takes a joyful, counter-melody role. Driving electric bass and bright, accented percussion.",
            "sad": "G Major, a bright and uplifting up-tempo track that gradually builds energy. The piano uses high, staccato chords. Cello/Viola takes a joyful, counter-melody role. Driving electric bass and bright, accented percussion.",
            "surprise": "A Minor transitioning to A Major, a dramatic musical event with a sudden, sharp dynamic shift. Begins quietly with sparse, low piano notes and high-tension cello tremolo, then explodes into a loud, fast bass and drum sequence, ending with a sudden, loud strike.",
            "neutral": "F Ionian, a warm and steady mid-tempo ambient piece. The piano plays a simple, repetitive arpeggio pattern. Cello/Viola section provides a smooth, sustained backdrop. Gentle electric bassline and minimal percussion. Suitable for a flowing transition.",
        }
        self._set_device()
        self._load_model_once()

    def _load_model_once(self):
        self.synthesiser = pipeline(
            "text-to-audio", model="facebook/musicgen-small", device=self.device
        )
        logging.info("Model loaded successfully")

    def _set_device(self):
        if torch.cuda.is_available():
            # 1. NVIDIA CUDA GPU
            self.device = (
                "cuda"  # Simplified device string for the first CUDA GPU (cuda:0)
            )
            logging.info(f"Using NVIDIA CUDA GPU: {self.device}")
        elif torch.backends.mps.is_available():
            # 2. Apple MPS (Apple Silicon)
            self.device = "mps"  # PyTorch device string for MPS
            logging.info(f"Using Apple Silicon MPS: {self.device}")
        elif torch.backends.hip.is_available():
            # 3. AMD ROCm GPU
            self.device = "cuda"  # ROCm uses the 'cuda' namespace in PyTorch and 'cuda' is sufficient
            logging.info(f"Using AMD ROCm GPU: {self.device}")
        else:
            # 4. CPU Fallback
            self.device = "cpu"
            logging.info(f"Using CPU: {self.device}")

    def emotion_to_prompt(self, emotion: str) -> str:
        inst = "stainway piano, string, drumset, bass"
        prompt = (
            self.emotion_prompt.get(emotion.lower(), self.emotion_prompt["neutral"])
            + ", "
            + inst
        )
        return prompt

    def generate(self, emotion: str, duration: int = 30) -> bytes:
        prompt = self.emotion_to_prompt(emotion)
        logging.info(prompt)
        logging.info(f"duration = {duration}")

        if not prompt:
            raise ValueError("prompt is empty!")

        if duration < 0:
            raise ValueError("duration must > 0")

        try:
            # 隨機 seed (optional, for variation)
            seed = random.randint(0, 2**32 - 1)
            torch.manual_seed(seed)
            if self.device == "cpu":
                pass  # CPU，不用 cuda 設定 seed
            # MPS 的 seed 設定由 PyTorch 自己管理

            result = self.synthesiser(
                prompt,
                forward_params={"do_sample": True, "max_new_tokens": duration * 50},
            )
            return result

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Error generating music: {e}")

        # """ Simulate generated generation """
        # import time
        # time.sleep(2)  # Simulate time-consuming generation
        # logging.info(f"Finished generating music for prompt: {prompt}")
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
        #     logging.info("fake generation failed:", e)
        #     return b""


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
