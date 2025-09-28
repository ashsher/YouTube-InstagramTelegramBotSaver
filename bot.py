import os
import yt_dlp
import requests
import asyncio
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
import sys

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # set in env
GOFILE_API_URL = "https://api.gofile.io"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# === FFMPEG PATH ===
if sys.platform.startswith("win"):  # Windows local testing
    FFMPEG_PATH = r"D:\coding\python\projects\YouTube&InstagramVideoSaverTGBot\bin\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"
else:  # Linux / Render deployment
    # assumes ffmpeg is in your project folder: bin/ffmpeg
    FFMPEG_PATH = os.path.join(os.getcwd(), "bin", "ffmpeg")

# --- Upload file to GoFile ---
def upload_to_gofile(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            response = requests.post(f"{GOFILE_API_URL}/uploadFile", files={"file": f})
        result = response.json()
        if result["status"] == "ok":
            return result["data"]["downloadPage"]
        else:
            return "❌ Upload to GoFile failed."
    except Exception as e:
        return f"❌ Upload error: {e}"

# --- Download media with yt-dlp + progress ---
def download_media(url: str, audio_only: bool, progress_callback=None) -> str:
    ydl_opts = {
        "outtmpl": "%(title).80s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "ffmpeg_location": FFMPEG_PATH
    }

    if progress_callback:
        ydl_opts["progress_hooks"] = [progress_callback]

    if audio_only:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        })
    else:
        ydl_opts.update({"format": "best"})

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# --- /start ---
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("👋 Send me a YouTube or Instagram link and pick audio or video.")

# --- handle links ---
@dp.message(F.text.startswith("http"))
async def handle_link(message: Message):
    url = message.text.strip()
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎥 Video", callback_data=f"video|{url}")],
        [types.InlineKeyboardButton(text="🎵 Audio", callback_data=f"audio|{url}")]
    ])
    await message.answer("Choose format:", reply_markup=keyboard)

# --- handle button clicks ---
@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    action, url = callback.data.split("|")
    status_msg = await callback.message.answer("⏳ Starting download...")

    # Remove ANSI codes
    def clean_ansi(text: str) -> str:
        return re.sub(r'\x1b\[[0-9;]*m', '', text)

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = clean_ansi(d.get('_percent_str', '').strip())
            eta = d.get('eta', '?')
            speed = clean_ansi(d.get('_speed_str', '').strip())
            asyncio.create_task(
                bot.edit_message_text(
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id,
                    text=f"⬇️ Downloading...\nProgress: {percent}\nETA: {eta}s\nSpeed: {speed}"
                )
            )

    try:
        file_path = download_media(url, audio_only=(action == "audio"), progress_callback=progress_hook)

        # Upload to GoFile
        await bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="📤 Uploading to GoFile..."
        )
        link = upload_to_gofile(file_path)

        await bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"✅ Done!\n🔗 Download link:\n{link}"
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        await bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ Error: {e}"
        )

# --- run ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
