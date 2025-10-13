import yt_dlp
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
        # Configuración para descargar audio
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            # Configuraciones para evitar detección de bot
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'age_limit': None,
        }
        
        # Crear directorio de descargas si no existe
        os.makedirs('downloads', exist_ok=True)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Cambiar extensión a mp3
            audio_file = os.path.splitext(filename)[0] + '.mp3'
        
        # Enviar el archivo de audio
        with open(audio_file, 'rb') as audio:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio,
                title=info.get('title', 'Audio'),
                performer=info.get('uploader', 'YouTube'),
                duration=int(info.get('duration', 0)),
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
        # Intentar enviar mensaje de error, pero no fallar si hay timeout
        try:
            await query.edit_message_text(f"❌ Error al descargar el audio. Por favor, intentá de nuevo.")
        except:
            pass

async def download_video(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Descarga el video con audio de YouTube"""
    try:
        # Configuración para descargar video
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            # Configuraciones para evitar detección de bot
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'age_limit': None,
        }
        
        # Crear directorio de descargas si no existe
        os.makedirs('downloads', exist_ok=True)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Asegurar extensión mp4
            if not filename.endswith('.mp4'):
                video_file = os.path.splitext(filename)[0] + '.mp4'
            else:
                video_file = filename
        
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
                    caption=info.get('title', 'Video'),
                    duration=int(info.get('duration', 0)),
                    width=info.get('width'),
                    height=info.get('height'),
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
        # Intentar enviar mensaje de error, pero no fallar si hay timeout
        try:
            await query.edit_message_text(f"❌ Error al descargar el video. Por favor, intentá de nuevo.")
        except:
            pass

