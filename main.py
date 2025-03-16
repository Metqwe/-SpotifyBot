import os
import subprocess
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from database import init_db, add_track, get_track, get_all_tracks
import shutil

# Перед завантаженням:
output_dir = "downloads"
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir, exist_ok=True)


load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

init_db()

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚀 Старт")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("👋 Вітаю! Надішли мені посилання на трек із Spotify, і я конвертую його в MP3!", reply_markup=start_keyboard)

@dp.message(Command("tracks"))
async def list_tracks(message: Message):
    tracks = get_all_tracks()
    if not tracks:
        await message.answer("📂 У базі поки що немає треків.")
        return
    track_list = "\n".join([f"🎵 {track[0]}" for track in tracks])
    await message.answer(f"📂 **Збережені треки:**\n{track_list}", parse_mode="Markdown")

@dp.message()
async def handle_spotify_link(message: Message):
    url = message.text.strip()
    if "open.spotify.com/track" not in url:
        await message.answer("❌ Надішли коректне посилання на трек зі Spotify.")
        return

    track_id = url.split("/track/")[-1].split("?")[0]
    print(f"Track ID: {track_id}")  # DEBUG

    existing_track = get_track(track_id)
    if existing_track:
        await message.answer("⏳ Трек вже є, надсилаю!")
        audio = FSInputFile(existing_track)
        await message.answer_audio(audio=audio)
        return

    await message.answer("🎵 Завантажую трек... Зачекай кілька секунд!")

    try:
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)
        command = ["spotdl", url, "--output", output_dir]
        subprocess.run(command, check=True)

        for file in os.listdir(output_dir):
            if file.endswith(".mp3"):
                file_path = f"{output_dir}/{file}"
                add_track(track_id, file_path)

                await message.answer_audio(
                    audio=FSInputFile(file_path),
                    title=file.replace(".mp3", ""),
                    performer="Spotify",
                    caption="[@spotifyconvert_bot](https://t.me/spotifyconvert_bot)",
                    parse_mode="Markdown"
                )
                return
    except Exception as e:
        await message.answer(f"❌ Помилка: {str(e)}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

