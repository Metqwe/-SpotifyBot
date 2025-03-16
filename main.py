import os
import subprocess
import requests
import json
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from database import init_db, add_track, get_track, get_all_tracks

load_dotenv()

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Ініціалізуємо базу перед запуском бота
init_db()

# Додаємо кнопку "Старт"
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Старт")]
    ],
    resize_keyboard=True
)

def add_cover_to_mp3(mp3_path, cover_url):
    try:
        audio = MP3(mp3_path, ID3=ID3)
        response = requests.get(cover_url)
        response.raise_for_status()
        
        audio.tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # 3 = Cover (front)
                desc="Cover",
                data=response.content  # Завантажуємо картинку
            )
        )
        audio.save()
    except error as e:
        print("Помилка при додаванні обкладинки:", e)
    except requests.exceptions.RequestException as e:
        print("Помилка при завантаженні зображення:", e)

def get_spotify_cover(url):
    """ Отримуємо URL обкладинки через spotdl metadata """
    try:
        command = ["spotdl", "meta", url, "--json"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        return metadata.get("cover_url", None)
    except Exception as e:
        print(f"Помилка отримання обкладинки: {e}")
        return None

@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("Вітаю! Надішли мені посилання на трек із Spotify, і я конвертую його в MP3!".encode("utf-8").decode("utf-8"), reply_markup=start_keyboard)

@dp.message(Command("tracks"))
async def list_tracks(message: Message):
    tracks = get_all_tracks()
    if not tracks:
        await message.answer("📂 У базі поки що немає треків.")
        return
    
    track_list = "\n".join([f"🎵 {track[0]} - {track[1]}" for track in tracks])
    await message.answer(f"📂 **Збережені треки:**\n{track_list}", parse_mode="Markdown")

@dp.message()
async def handle_spotify_link(message: Message):
    url = message.text.strip()
    if "open.spotify.com/track" not in url:
        await message.answer("❌ Надішли коректне посилання на трек зі Spotify.")
        return
    
    track_id = url.split("/track/")[-1].split("?")[0]
    existing_track = get_track(track_id)
    
    if existing_track:
        await message.answer("⏳ Хвилинку, зараз відправлю!")
        audio = FSInputFile(existing_track)
        await message.answer_audio(audio=audio)
        return
    
    await message.answer("🎵 Завантажую трек... Зачекай кілька секунд!".encode("utf-8").decode("utf-8"))
    
    try:
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)
        command = ["spotdl", url, "--output", output_dir]
        subprocess.run(command, check=True)

        for file in os.listdir(output_dir):
            if file.endswith(".mp3"):
                file_path = f"{output_dir}/{file}"
                track_name = file.replace(".mp3", "").replace("_", " ")
                cover_url = get_spotify_cover(url)  # Отримуємо правильну обкладинку
                
                if cover_url:
                    add_cover_to_mp3(file_path, cover_url)  # Додаємо обкладинку
                
                add_track(track_id, file_path)
                
                await message.answer_audio(
                    audio=FSInputFile(file_path),
                    title=track_name,
                    performer="Spotify",
                    caption="[@spotifyconvert_bot](https://t.me/spotifyconvert_bot)",
                    parse_mode="Markdown"
                )
                break
    except Exception as e:
        await message.answer(f"❌ Сталася помилка: {str(e)}".encode("utf-8").decode("utf-8"))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
