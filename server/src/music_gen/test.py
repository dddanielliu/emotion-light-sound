import os
from music_generator import MusicGenerator  


OUTPUT_DIR = "test_musics"
if __name__ == "__main__":
    print("test start\n")
    print("initialize\n")
    gen = MusicGenerator()

    print("emotion2prompt\n")
    emotion = "happy"

    print(emotion+"\n")
    prompt = gen.emotion_to_prompt("happy")


    print("gen music\n")
    music_bytes = gen.generate(prompt)

    output_path = os.path.join(OUTPUT_DIR, f"test_{emotion}.mp3")
    with open(output_path, "wb") as f:
        f.write(music_bytes)
        
    print("done！")
