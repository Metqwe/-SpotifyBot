import os
import subprocess
import shutil
import asyncio
import atexit  # 🧹 Для видалення тимчасових файлів
import json  # 📖 Для читання метаданих SpotDL
from datetime import datetime  # 🗓 Для історії обробок

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dotenv import load_dotenv
from database import init_db, add_track, get_track, delete_track
import sqlite3

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

init_db()
output_dir = "downloads"
os.makedirs(output_dir, exist_ok=True)

last_file_path = {}
temp_files = []  # 📂 Тимчасові файли для видалення
history_db = []  # 🧾 Локальна історія (опціонально — можна замінити на базу)

# 🧼 Видалення тимчасових файлів при завершенні

def remove_temp_files():
    for file in temp_files:
        if os.path.exists(file):
            os.remove(file)
atexit.register(remove_temp_files)

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚀 Старт")]],
    resize_keyboard=True
)

@router.message(Command("start"))
async def start(message: Message):
    name = message.from_user.first_name or "друже"
    await message.answer(
        f"Привіт👋, <b>{name}</b>!\nНадішли посилання на трек зі Spotify, я його скачаю й запропоную обробку!",
        reply_markup=start_keyboard
    )

@router.message(F.text == "🚀 Старт")
async def handle_start_button(message: Message):
    await start(message)

@router.message(Command("reset"))
async def reset_track(message: Message):
    url = message.text.strip().split()
    if len(url) < 2 or "open.spotify.com/track" not in url[1]:
        await message.answer("⚠️ Надішли команду так: /reset <твоє_посилання_на_трек>")
        return
    track_id = url[1].split("/track/")[-1].split("?")[0]
    delete_track(track_id)
    await message.answer("🗑 Трек видалено з бази. Можеш надіслати його знову.")

@router.message(Command("history"))
async def show_history(message: Message):
    user_id = message.from_user.id
    items = [entry for entry in history_db if entry["user_id"] == user_id]

    if not items:
        await message.answer("📭 Історія пуста. Оброби хоч один трек!")
        return

    for item in items:
        name = item["name"]
        effect = item["effect"]
        path = item["path"]
        date = item["date"]
        await message.answer_document(
            document=FSInputFile(path),
            caption=f"🎧 <b>{name}</b>\n🎚 Ефект: <i>{effect}</i>\n🗓 {date}"
        )

@router.message(F.text.startswith("http"))
async def handle_link(message: Message):
    url = message.text.strip()

    if "open.spotify.com/track" not in url:
        await message.answer("⚠️ Надішли посилання на <b>трек</b>, а не плейлист чи артиста.")
        return

    await message.answer("🎵 Завантажую трек...")
    track_id = url.split("/track/")[-1].split("?")[0]
    existing_path = get_track(track_id)

    if existing_path:
        if os.path.exists(existing_path):
            last_file_path[message.from_user.id] = existing_path
            await send_audio_with_options(message.chat.id, existing_path)
        else:
            await message.answer("❌ Трек вже є в базі, але файл видалено. Скинь інший або завантаж заново.")
        return

    spotdl_path = os.path.join(os.getcwd(), "venv", "Scripts", "spotdl.exe")

    try:
        subprocess.run([spotdl_path, url, "--output", output_dir], check=True)
        # 📖 Пошук назви з JSON метаданих
        metadata_path = os.path.join(output_dir, ".spotdl", "cache", "spotify", f"{track_id}.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                title = metadata.get("name")
                print(f"✅ Назва треку: {title}")

        mp3_files = sorted(
            [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".mp3")],
            key=os.path.getmtime,
            reverse=True
        )
        if mp3_files:
            file_path = mp3_files[0]
            if os.path.getsize(file_path) < 1024:  # Перевірка на зіпсований файл
                await message.answer("❌ Помилка: файл зіпсовано або порожній.")
                return

            if not get_track(track_id):
                add_track(track_id, file_path)
            last_file_path[message.from_user.id] = file_path
            await send_audio_with_options(message.chat.id, file_path)

    except subprocess.CalledProcessError as e:
        await message.answer(f"❌ Помилка: {e}")
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

def get_version_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оригінал", callback_data="original")],
        [InlineKeyboardButton(text="Speed Up", callback_data="speedup")],
        [InlineKeyboardButton(text="Slowed", callback_data="slowed")],
        [InlineKeyboardButton(text="🎚Власний ефект", callback_data="custom")],
    ])

async def send_audio_with_options(chat_id, file_path):
    await bot.send_message(chat_id, "🎵 Вибери версію треку:", reply_markup=get_version_keyboard())
    last_file_path[chat_id] = file_path

@router.callback_query(F.data.in_(["original", "speedup", "slowed", "custom"]))
async def handle_audio_version(callback: CallbackQuery):
    version = callback.data
    user_id = callback.from_user.id

    if user_id not in last_file_path:
        await callback.message.answer("❗️ Трек не знайдено. Скинь ще раз.")
        return

    original_path = last_file_path[user_id]
    base, ext = os.path.splitext(original_path)
    modified_path = f"{base}_{version}.mp3"

    if version == "original":
        await callback.message.answer_audio(audio=FSInputFile(original_path), caption="🎷 Оригінал")
        return

    if version == "custom":
        await callback.message.answer(
            "✍️ Введи свою команду для ffmpeg (тільки -af частину або спрощену команду):\n"
            "<b>🔧 Приклади:</b>\n"
            "• <code>+10 бас</code> — потужний кач без шуму\n"
            "• <code>-5 швидкість</code> — повільніше\n"
            "• <code>+7 гучність</code> — гучніше\n"
            "• <code>+15 нічкор</code> — підіймає пітч (швидко)\n"
            "<i>Можна вводити кілька ефектів через кому. Максимум: бас ±20, нічкор ±20, гучність ±20, швидкість ±50.</i>",
            parse_mode="HTML"
        )
        return

    try:
        if version == "speedup":
            cmd = f'ffmpeg -y -i "{original_path}" -af "asetrate=44100*1.122462,aresample=44100,acompressor" -vn "{modified_path}"'
        elif version == "slowed":
            cmd = f'ffmpeg -y -i "{original_path}" -af "asetrate=44100*0.85,aresample=44100,acompressor" -vn "{modified_path}"'

        subprocess.run(cmd, shell=True, check=True)
        await callback.message.answer_audio(audio=FSInputFile(modified_path), caption=f"🎶 Версія: {version.capitalize()}")

    except Exception as e:
        await callback.message.answer(f"❌ FFmpeg error: {e}")

@router.message()
async def handle_custom_input(message: Message):
    user_id = message.from_user.id
    if user_id not in last_file_path:
        return

    text = message.text.strip()
    original_path = last_file_path[user_id]
    base, ext = os.path.splitext(original_path)
    modified_path = f"{base}_custom.mp3"

    try:
        filters = []
        if "," in text or any(x in text for x in ["бас", "швидкість", "нічкор", "гучність"]):
            parts = [x.strip() for x in text.split(",")]
            for part in parts:
                if "бас" in part:
                    value = int(part.replace("бас", "").strip())
                    value = max(-20, min(20, value))
                    filters.append(f"equalizer=f=90:width_type=h:width=100:g={value}")
                elif "швидкість" in part:
                    value = int(part.replace("швидкість", "").strip())
                    value = max(-50, min(50, value))
                    factor = 1 + (value / 100)
                    filters.append(f"asetrate=44100*{factor},aresample=44100")
                elif "нічкор" in part:
                    value = int(part.replace("нічкор", "").strip())
                    value = max(-20, min(20, value))
                    factor = 1 + (value / 100)
                    filters.append(f"asetrate=44100*{factor},aresample=44100,atempo=1.07")
                elif "гучність" in part:
                    value = int(part.replace("гучність", "").strip())
                    value = max(-20, min(20, value))
                    filters.append(f"volume={value}dB")

            filters.append("acompressor")
            ffmpeg_filter = ",".join(filters)
        else:
            await message.answer("⚠️ Команда не розпізнана. Приклад: +10 бас")
            return

        cmd = f'ffmpeg -y -i "{original_path}" -af "{ffmpeg_filter}" -vn "{modified_path}"'
        subprocess.run(cmd, shell=True, check=True)
        await message.answer_audio(audio=FSInputFile(modified_path), caption="🎛 Власна обробка успішна")

    except Exception as e:
        await message.answer(f"❌ Помилка обробки: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())