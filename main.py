from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from handlers import start, handle_message
from youtube_handler import handle_youtube_callback
from dotenv import load_dotenv
import os
import subprocess

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def _update_ytdlp():
    try:
        result = subprocess.run(
            ['pip', 'install', '-U', '--pre', 'yt-dlp[default]'],
            capture_output=True, text=True, timeout=120
        )
        for line in result.stdout.splitlines():
            if 'Successfully installed' in line:
                print(f"[INFO] yt-dlp actualizado: {line.strip()}")
                return
        print("[INFO] yt-dlp ya está actualizado")
    except Exception as e:
        print(f"[WARN] No se pudo actualizar yt-dlp: {e}")


def main():
    _update_ytdlp()

    if not TELEGRAM_TOKEN:
        raise ValueError("Falta el token de Telegram: TELEGRAM_TOKEN")

    if not OPENAI_API_KEY:
        raise ValueError("Falta la API key de OpenAI: OPENAI_API_KEY")

    # Crear la aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Añadir manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_youtube_callback, pattern='^yt_'))
    
    # Iniciar el bot
    app.run_polling()

if __name__ == "__main__":
    main()