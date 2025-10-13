from pytubefix import YouTube
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

def is_youtube_url(url: str) -> bool:
    """Verifica si la URL es de YouTube"""
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    return bool(re.match(youtube_regex, url))

async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el link de YouTube mostrando botones interactivos"""
    url = update.message.text.strip()
    
    # Guardar la URL en el contexto del usuario
    context.user_data['youtube_url'] = url
    
    # Crear botones interactivos
    keyboard = [
        [
            InlineKeyboardButton("🎵 Solo Audio", callback_data='yt_audio'),
            InlineKeyboardButton("🎬 Audio + Video", callback_data='yt_video')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎯 Detecté un link de YouTube!\n\n"
        "¿Qué querés descargar?",
        reply_markup=reply_markup
    )

async def handle_youtube_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección del usuario (audio o video)"""
    query = update.callback_query
    await query.answer()
    
    # Obtener la URL guardada
    url = context.user_data.get('youtube_url')
    if not url:
        await query.edit_message_text("❌ Error: No se encontró la URL. Por favor, enviá el link de nuevo.")
        return
    
    choice = query.data
    
    # Actualizar el mensaje para mostrar progreso
    if choice == 'yt_audio':
        await query.edit_message_text("🎵 Descargando audio... Por favor esperá.")
        await download_audio(query, context, url)
    elif choice == 'yt_video':
        await query.edit_message_text("🎬 Descargando video... Por favor esperá.")
        await download_video(query, context, url)

async def download_audio(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Descarga solo el audio del video de YouTube"""
    try:
        # Crear directorio de descargas si no existe
        os.makedirs('downloads', exist_ok=True)
        
        # Crear objeto YouTube
        yt = YouTube(url)
        
        # Obtener el stream de audio de mejor calidad
        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        
        if not audio_stream:
            await query.edit_message_text("❌ No se pudo encontrar un stream de audio.")
            return
        
        # Descargar el audio
        audio_file = audio_stream.download(output_path='downloads')
        
        # Enviar el archivo de audio
        with open(audio_file, 'rb') as audio:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio,
                title=yt.title,
                performer=yt.author,
                duration=int(yt.length),
                read_timeout=60,
                write_timeout=60,
                connect_timeout=60
            )
        
        # Intentar actualizar el mensaje, pero no fallar si hay timeout
        try:
            await query.edit_message_text("✅ Audio descargado y enviado correctamente!")
        except Exception as timeout_error:
            print(f"Timeout al editar mensaje (ignorado): {timeout_error}")
        
        # Limpiar archivo
        if os.path.exists(audio_file):
            os.remove(audio_file)
            
    except Exception as e:
        print(f"Error descargando audio: {e}")
        import traceback
        traceback.print_exc()
        # Intentar enviar mensaje de error, pero no fallar si hay timeout
        try:
            await query.edit_message_text(f"❌ Error al descargar el audio. Por favor, intentá de nuevo.")
        except:
            pass

async def download_video(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Descarga el video con audio de YouTube"""
    try:
        # Crear directorio de descargas si no existe
        os.makedirs('downloads', exist_ok=True)
        
        # Crear objeto YouTube
        yt = YouTube(url)
        
        # Obtener el stream de video con audio de mejor calidad (progressive streams)
        # Progressive streams incluyen audio y video juntos
        video_stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        
        if not video_stream:
            await query.edit_message_text("❌ No se pudo encontrar un stream de video.")
            return
        
        # Descargar el video
        video_file = video_stream.download(output_path='downloads')
        
        # Verificar tamaño del archivo
        file_size = os.path.getsize(video_file)
        max_size = 50 * 1024 * 1024  # 50 MB (límite de Telegram para bots)
        
        if file_size > max_size:
            try:
                await query.edit_message_text(
                    f"⚠️ El video es demasiado grande ({file_size / (1024*1024):.1f} MB).\n"
                    f"Telegram tiene un límite de 50 MB para bots.\n"
                    f"Probá descargando solo el audio."
                )
            except:
                pass
        else:
            # Enviar el archivo de video
            with open(video_file, 'rb') as video:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=video,
                    caption=yt.title,
                    duration=int(yt.length),
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60
                )
            
            # Intentar actualizar el mensaje, pero no fallar si hay timeout
            try:
                await query.edit_message_text("✅ Video descargado y enviado correctamente!")
            except Exception as timeout_error:
                print(f"Timeout al editar mensaje (ignorado): {timeout_error}")
        
        # Limpiar archivo
        if os.path.exists(video_file):
            os.remove(video_file)
            
    except Exception as e:
        print(f"Error descargando video: {e}")
        import traceback
        traceback.print_exc()
        # Intentar enviar mensaje de error, pero no fallar si hay timeout
        try:
            await query.edit_message_text(f"❌ Error al descargar el video. Por favor, intentá de nuevo.")
        except:
            pass

