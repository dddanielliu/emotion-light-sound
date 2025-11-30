import os
import random
import traceback
import torch
import numpy as np
from scipy.io import wavfile
from transformers import pipeline
import time

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
        style = "only piano, Jazz"
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

        # finally:
        #     if self.synthesiser:
        #         del self.synthesiser
        #     if self.device == "mps":
        #         torch.mps.empty_cache()
        #     print("Cleaned up resources")
    

"mono"
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

"stereo"
# def store_music(music, filename="song.wav"):
#     output_dir = os.path.join(os.getcwd(), "output")
#     os.makedirs(output_dir, exist_ok=True)

#     audio = music.get("audio")         # shape = (2, N)
#     sr = music.get("sampling_rate")

#     if audio is None or sr is None:
#         raise RuntimeError("Invalid music data")

#     # stereo 轉 int16，要轉置成 (N, 2)
#     audio_int16 = (audio.T * 32767).astype(np.int16)

#     output_path = os.path.join(output_dir, filename)
#     wavfile.write(output_path, rate=sr, data=audio_int16)
#     print(f"Saved music to {output_path}")

#     return output_path



if __name__ == "__main__":
    mg = MusicGenerator()
    # for emotion in mg.emotion_prompt:
    start = time.time()
    emotion = "angry"
    mg.emotion_to_prompt(emotion)
    print("generating...")
    print(f"Emotion = {emotion}")
    music = mg.generate_music(prompt= mg.prompt)
    end = time.time()
    store_music(music, filename=f"{emotion}.wav")
    print(f"生成耗時: {end - start:.2f} 秒")