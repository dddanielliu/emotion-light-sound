import os
import random
import traceback

import torch
import numpy as np
from scipy.io import wavfile
from transformers import pipeline

class MusicGenerator:
    def __init__(self):
        self.prompt = ""
        self.duration = 30

    def generate_music(self, prompt: str, duration: int = 30):
        if not prompt:
            raise ValueError("prompt is empty!")
        self.prompt = prompt

        if duration > 0:
            self.duration = duration
        else:
            raise ValueError("duration must > 0")

        # 判斷 device：macOS MPS 或 CPU
        if torch.backends.mps.is_available():
            device = "mps"
            print("Using Apple Silicon MPS (or MPS-supported device)")
            pipeline_device = 0  # MPS 利用 device=0 表示第一個可用設備
        else:
            device = "cpu"
            print("Using CPU")
            pipeline_device = -1

        synthesiser = None
        try:
            synthesiser = pipeline(
                "text-to-audio",
                model="facebook/musicgen-small",
                device=pipeline_device
            )
            print("Model loaded successfully")

            # 隨機 seed (optional, for variation)
            seed = random.randint(0, 2**32 - 1)
            torch.manual_seed(seed)
            if device == "cpu":
                pass  # CPU，不用 cuda 設定 seed
            # MPS 的 seed 設定由 PyTorch 自己管理

            result = synthesiser(
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

        finally:
            if synthesiser:
                del synthesiser
            if device == "mps":
                torch.mps.empty_cache()
            print("Cleaned up resources")


def store_music(music, filename="song.wav"):
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)

    audio = music.get("audio")
    sr = music.get("sampling_rate")
    if audio is None or sr is None:
        raise RuntimeError("Invalid music data")

    audio_int16 = (audio * 32767).astype(np.int16)
    output_path = os.path.join(output_dir, filename)
    wavfile.write(output_path, rate=sr, data=audio_int16)
    print(f"Saved music to {output_path}")
    return output_path


if __name__ == "__main__":
    mg = MusicGenerator()
    music = mg.generate_music(
        prompt="peaceful ambient chillout, soft pads, gentle arpeggios, relaxing atmosphere",
        duration=30
    )
    store_music(music, filename="my_music.wav")
