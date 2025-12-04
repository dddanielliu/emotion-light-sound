import os
import time

import numpy as np
from scipy.io import wavfile

from .music_generator import MusicGenerator


# 音樂儲存位置
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
    # for emotion in mg.emotion_prompt:
    for i in range(2):
        start = time.time()
        emotion = "angry"
        music = mg.generate(emotion=emotion, duration=5)
        end = time.time()
        store_music(music, filename=f"{emotion}.wav")
        print(f"生成耗時: {end - start:.2f} 秒")
