import re

from telegram import Update
from telegram.ext import ContextTypes
from openai_client import generate_markdown
from pdf_generator import generate_pdf
from youtube_handler import is_youtube_url, handle_youtube_link
from social_media_handler import (
    is_instagram_url,
    handle_instagram_video,
)

# Historial de mensajes por usuario
historias = {}
URL_REGEX = re.compile(r'(https?://|www\.)\S+', re.IGNORECASE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje_bienvenida = (
        "¡Hola! Soy tu bot multifuncional. Aquí te explico cómo usarme:\n\n"
        "📄 PRESUPUESTOS:\n"
        "1. Enviame un solo mensaje con todos los detalles del presupuesto (fecha, dirección, contacto, trabajos, materiales, costo, etc.).\n"
        "2. Te voy a enviar un PDF con el presupuesto formateado.\n"
        "3. Si querés modificar un presupuesto, respondé al mensaje con el PDF y decime qué cambiar.\n\n"
        "🎬 YOUTUBE:\n"
        "1. Enviame un link de YouTube.\n"
        "2. Elegí si querés descargar solo audio 🎵 o video completo 🎬.\n"
        "3. Te enviaré el archivo correspondiente.\n\n"
        "📱 INSTAGRAM:\n"
        "Enviame un link de Instagram y te mando el video automáticamente.\n\n"
        "Usá /start para ver estas instrucciones de nuevo."
    )
    await update.message.reply_text(mensaje_bienvenida)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mensaje = update.message.text
    
    # Verificar si es un link de YouTube
    if is_youtube_url(mensaje):
        await handle_youtube_link(update, context)
        return

    # Verificar si es un link de Instagram
    if is_instagram_url(mensaje):
        await handle_instagram_video(update, context)
        return

    # Si es otra URL, informar que no está soportada
    if mensaje and URL_REGEX.search(mensaje):
        await update.message.reply_text("⚠️ Solo puedo descargar de YouTube o Instagram.")
        return

    # Inicializar historial para el usuario si no existe
    if user_id not in historias:
        historias[user_id] = []

    # Verificar si es una respuesta a un PDF
    es_respuesta = update.message.reply_to_message is not None and \
                   hasattr(update.message.reply_to_message, 'document') and \
                   update.message.reply_to_message.document is not None and \
                   update.message.reply_to_message.document.mime_type == "application/pdf"

    # Agregar el mensaje al historial
    if es_respuesta:
        historias[user_id].append({"role": "user", "content": f"Modificar el presupuesto anterior: {mensaje}"})
    else:
        historias[user_id].append({"role": "user", "content": mensaje})

    try:
        # Generar JSON con OpenAI
        json_response = generate_markdown(historias[user_id])

        # Generar y enviar el PDF
        pdf_file = generate_pdf(json_response)
        with open(pdf_file, "rb") as file:
            sent_message = await context.bot.send_document(chat_id=update.effective_chat.id, document=file)
        
        # Guardar el contenido Markdown en el historial
        historias[user_id].append({"role": "assistant", "content": json_response["content"]})

    except Exception as e:
        print(e)
        await update.message.reply_text(f"No pude procesar tu solicitud. Por favor, intentá de nuevo.")