from telegram.ext import Application, CommandHandler, MessageHandler, filters
from handlers import start, handle_message
from dotenv import load_dotenv
import os

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("Falta el token de Telegram: TELEGRAM_TOKEN")

    if not OPENAI_API_KEY:
        raise ValueError("Falta la API key de OpenAI: OPENAI_API_KEY")

    # Crear la aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Añadir manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Iniciar el bot
    app.run_polling()

if __name__ == "__main__":
    main()