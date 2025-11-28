from music_generator import MusicGenerator, model, processor, SAMPLING_RATE
from scipy.io import wavfile

OUTPUT_FILE = "test_output.wav"

def main():
    print("🚀 初始化 MusicGenerator...")
    gen = MusicGenerator(model, processor, sampling_rate=SAMPLING_RATE)

    print("🎯 開始生成音樂，情緒: happy, 時長: 8秒")
    music_bytes = gen.generate("happy", duration=8)

    print(f"💾 儲存音樂到 {OUTPUT_FILE} ...")
    with open(OUTPUT_FILE, "wb") as f:
        f.write(music_bytes)

    print(f"✅ 測試完成！請播放 {OUTPUT_FILE} 確認音樂是否正確生成。")

if __name__ == "__main__":
    main()
