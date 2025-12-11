import asyncio
import io
import logging
import random
import traceback
from typing import Any, Callable, Dict, Optional

import torch
from pydantic import BaseModel, ValidationError, model_validator
from scipy.io import wavfile
from transformers import pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MusicGenerator:
    def __init__(self):
        self.device = None
        self.synthesiser = None
        self.emotion_prompt = {
        "happy": "Uplifting EDM, Progressive House, major key, bright synthesizer leads, energetic beat, euphoria, danceable, optimistic, catchy melody",
        "sad": "Emotional EDM,no drums ,sad piano melody, orchestral string section, cinematic atmosphere, slow electronic beat, deep synthesizer bass, melancholic, sentimental, touching",
        "angry": "Epic Orchestral EDM, Epic cinematic score, deep brass, aggressive strings, dark choir, building tension, minimal percussion, overwhelming",
        "fear": "Dark Ambient Soundscape, horror atmosphere, environmental sounds, eerie wind, distant metallic echoes, creepy synth texture, suspenseful, psychological, unsettling, cold",
        "disgust": "Glitchy electronic music, Acid Techno, squelchy synth, distorted texture, weird rhythm, uncomfortable, dissonant, odd, unpleasant, experimental",
        "surprise": "Cinematic EDM, circus music, fast, chaotic, calliope, brass band, playful, comedic shock.",
        "neutral": "Lo-fi, peaceful steady beat, smooth synthesizer, relaxing, neutral atmosphere, background music, chill, rhythmic, flow, minimal"
        }

        self._set_device()
        self._load_model_once()

    def _load_model_once(self):
        self.synthesiser = pipeline(
            "text-to-audio", model="facebook/musicgen-small", device=self.device
        )
        logger.info("Model loaded successfully")

    def _set_device(self):
        if torch.cuda.is_available():
            # 1. NVIDIA CUDA GPU
            self.device = (
                "cuda"  # Simplified device string for the first CUDA GPU (cuda:0)
            )
            logger.info(f"Using NVIDIA CUDA GPU: {self.device}")
        elif torch.backends.mps.is_available():
            # 2. Apple MPS (Apple Silicon)
            self.device = "mps"  # PyTorch device string for MPS
            logger.info(f"Using Apple Silicon MPS: {self.device}")
        elif torch.backends.hip.is_available():
            # 3. AMD ROCm GPU
            self.device = "cuda"  # ROCm uses the 'cuda' namespace in PyTorch and 'cuda' is sufficient
            logger.info(f"Using AMD ROCm GPU: {self.device}")
        else:
            # 4. CPU Fallback
            self.device = "cpu"
            logger.info(f"Using CPU: {self.device}")

    def emotion_to_prompt(self, emotion: str) -> str:
        tonic = "C key"
        prompt = (
            self.emotion_prompt.get(emotion.lower(), self.emotion_prompt["neutral"])
            +", "
            +tonic
        )
        return prompt

    def generate(self, emotion: str, duration: int = 10) -> bytes:
        prompt = self.emotion_to_prompt(emotion)
        logger.info(prompt)
        logger.info(f"duration = {duration}")

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
            # Extract audio data and sampling rate
            audio_data = result["audio"]
            sampling_rate = result["sampling_rate"]

            # Convert to WAV bytes
            buffer = io.BytesIO()
            wavfile.write(buffer, rate=sampling_rate, data=audio_data)
            wav_bytes = buffer.getvalue()
            return wav_bytes

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Error generating music: {e}")

        # """ Simulate generated generation """
        # import time
        # time.sleep(2)  # Simulate time-consuming generation
        # logger.info(f"Finished generating music for prompt: {prompt}")
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
        #     logger.info("fake generation failed:", e)
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

        self.notify_socketio_client_music_generated = sender_callable
        self.create_url = url_creator_callable

        self._latest_post_item: Optional[InstanceItem] = None
        self._latest_pre_item: Optional[InstanceItem] = None
        self._queue_lock: asyncio.Lock = asyncio.Lock()
        self._new_item_event: asyncio.Event = asyncio.Event()
        self.last_post_item: Optional[InstanceItem] = None

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

        async with self._queue_lock:
            if item.stage == "post":
                self._latest_post_item = item
            elif item.stage == "pre":
                self._latest_pre_item = item
            else:
                logger.warning(f"Received item with unknown stage: {item.stage}")
            self._new_item_event.set()  # Signal the runner that there's a new item

    async def runner(self):
        """Process items based on priority: latest 'post', then latest 'pre', then last 'post' run."""
        while True:
            await self._new_item_event.wait()  # Wait for event to be set

            item_to_process: Optional[InstanceItem] = None
            async with self._queue_lock:
                self._new_item_event.clear()  # Clear the event as we are about to process

                if self._latest_post_item:
                    item_to_process = self._latest_post_item
                    self._latest_post_item = None  # Remove the processed item
                elif self._latest_pre_item:
                    item_to_process = self._latest_pre_item
                    self._latest_pre_item = None  # Remove the processed item
                elif self.last_post_item:
                    logger.info(
                        "No new 'post' or 'pre' items. Running last 'post' item again."
                    )
                    item_to_process = self.last_post_item
                    self._new_item_event.set()  # Set event to trigger loop again for fallback
                else:
                    logger.debug("No items to process. Waiting for new items.")

            if item_to_process:
                logger.info(f"Processing emotion: {item_to_process.model_dump()}")
                generated_music = await asyncio.to_thread(
                    self.music_generator.generate, item_to_process.emotion
                )

                if item_to_process.stage == "post":
                    self.last_post_item = item_to_process

                self._new_item_event.set()  # Set event to trigger loop again

                if item_to_process.sid:
                    logger.info(
                        f"Generated {len(generated_music)} bytes for sid: {item_to_process.sid}"
                    )
                    logger.debug(f"\titem: {item_to_process.model_dump()}")
                    metadata = (
                        item_to_process.metadata if item_to_process.metadata else {}
                    )

                    asyncio.create_task(
                        self.notify_socketio_client_music_generated(
                            event="music_generated",
                            sid=item_to_process.sid,
                            music_bytes=generated_music,
                            stage=item_to_process.stage,
                            emotion=item_to_process.emotion,
                            metadata=metadata,
                        )
                    )

                if item_to_process.client_id:
                    logger.info(
                        f"Generated {len(generated_music)} bytes for client_id: {item_to_process.client_id}"
                    )
                    logger.debug(f"\titem: {item_to_process.model_dump()}")
                    asyncio.create_task(
                        self.create_url(
                            owner_id=item_to_process.client_id,
                            music_bytes=generated_music,
                            stage=item_to_process.stage,
                            emotion=item_to_process.emotion,
                            metadata=item_to_process.metadata,
                        )
                    )

                logger.info(f"Finished processing item: {item_to_process.model_dump()}")
