import os
import yt_dlp
import requests
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # use env variable for safety
GOFILE_API_URL = "https://api.gofile.io"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

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

# --- Download media with yt-dlp ---
def download_media(url: str, audio_only: bool = False) -> str:
    ydl_opts = {
        "outtmpl": "%(title).80s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
    }
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
    await callback.message.edit_text("⏳ Downloading... please wait")

    try:
        file_path = download_media(url, audio_only=(action == "audio"))

        # Upload to GoFile
        link = upload_to_gofile(file_path)

        await callback.message.edit_text(
            f"✅ Done!\n🔗 Download link:\n{link}"
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {e}")

# --- run ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
