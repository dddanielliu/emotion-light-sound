import asyncio
import logging
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, ValidationError, model_validator
from transformers import AutoProcessor, MusicgenForConditionalGeneration, pipeline
from io import BytesIO
from scipy.io import wavfile
import torch

processor = AutoProcessor.from_pretrained("facebook/musicgen-small")  
device = torch.device('cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')) # medium 音質最棒
model = MusicgenForConditionalGeneration.from_pretrained(
    "facebook/musicgen-small",
    dtype=torch.float16,      # ✅ 改成 dtype
    device_map="auto",
    low_cpu_mem_usage=True
    )
SAMPLING_RATE = 32000


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MusicGenerator:
    def __init__(self, model, processor, sampling_rate = SAMPLING_RATE):
        self.model = model
        self.processor = processor
        self.sampling_rate = sampling_rate
        self.prompt = ""
        self.emotion = "neutral"
        self.emotion_prompt = {
            "angry":    "aggressive industrial metal, distorted heavy guitars, pounding drums, dark atmosphere, fast tempo 140 BPM, intense energy",
            "disgust":  "creepy dissonant ambient, eerie soundscape, uncomfortable textures, wet squelching synths, minor key horror atmosphere",
            "fear":     "horror movie soundtrack, suspenseful strings, heartbeat kick drum, dark ambient drones, sudden scares, minor key tension",
            "happy":    "upbeat pop dance music, bright major chords, catchy melody, energetic drums, summer vibe, 128 BPM, joyful and fun",
            "sad":      "slow emotional piano ballad, minor key, reverb soaked, melancholic melody, soft strings, rain sounds in background, very emotional",
            "surprise": "playful upbeat electronic, sudden drops, quirky synth leads, cartoonish sound effects, fast tempo changes, energetic and fun",
            "neutral":  "calm ambient chillout, soft pads, gentle arpeggios, peaceful atmosphere, nature sounds, 90 BPM relaxing lo-fi"
        }

    def emotion_to_prompt(self, emotion: str) -> str:
        return self.emotion_prompt.get(emotion.lower(), self.emotion_prompt["neutral"])
        

    def generate(self, emotion: str, duration:int = 15) -> bytes:
        self.prompt = self.emotion_to_prompt(emotion)
        print(f"emotion 2  prompt done")
        print(f"Generating music for prompt: {self.prompt}")
        logger.info(f"Generating {duration}s music → emotion: {emotion}")

        # 完全不用 .to(device)！device_map="auto" 已經處理好
        inputs = processor(
            text=[self.prompt],
            padding=True,
            return_tensors="pt"
        )

        # 1秒 ≈ 50 tokens（medium/large 模型經驗值）
        max_new_tokens = max(256, duration * 50)  # 至少 256 避免太短

        try:
            with torch.no_grad():
                audio_values = self.model.generate(
                    **inputs,
                    do_sample=True,
                    guidance_scale=3.5,      # 3.0~5.0，越高越貼 prompt
                    temperature=0.95,
                    top_k=250,
                    max_new_tokens=max_new_tokens,
                )
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            logger.error("GPU OOM! 建議降低 duration 或換 small 模型")
            raise

        # 取出音訊並正規化（防止爆音）
        audio_np = audio_values[0, 0].cpu().numpy().astype("float32")
        max_val = abs(audio_np).max()
        if max_val > 0:
            audio_np = audio_np / max_val * 0.98  # 留一點頭部空間

        # 轉成 16-bit WAV bytes
        buffer = BytesIO()
        wavfile.write(buffer, self.sampling_rate, (audio_np * 32767).astype("int16"))
        wav_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Generated successfully! {len(wav_bytes)/1024:.1f} KB, {duration}s")
        return wav_bytes


        
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
