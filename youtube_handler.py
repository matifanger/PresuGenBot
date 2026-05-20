import os
import re
import glob
import time
import requests as http_requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import Optional

import yt_dlp

DOWNLOAD_DIR = os.path.abspath('downloads')

COBALT_API_URL = 'https://dwnld.nichind.dev'
COBALT_API_KEY = 'b05007aa-bb63-4267-a66e-78f8e10bf9bf'

PIPED_INSTANCES = [
    'https://pipedapi.kavin.rocks',
    'https://pipedapi.leptons.xyz',
    'https://pipedapi.nosebs.ru',
    'https://pipedapi-libre.kavin.rocks',
    'https://pipedapi.adminforge.de',
    'https://api.piped.yt',
    'https://pipedapi.drgns.space',
    'https://pipedapi.owo.si',
    'https://pipedapi.ducks.party',
    'https://piped-api.codespace.cz',
    'https://pipedapi.reallyaweso.me',
    'https://api.piped.private.coffee',
    'https://pipedapi.darkness.services',
    'https://pipedapi.orangenet.cc',
]

SKIP_FALLBACK_KEYWORDS = [
    'private video', 'video unavailable', 'not available',
    'this video has been removed', 'copyright',
]


def _extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r'(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})',
        r'([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def is_youtube_url(url: Optional[str]) -> bool:
    if not url:
        return False
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    return bool(re.match(youtube_regex, url))


async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data['youtube_url'] = url

    keyboard = [
        [
            InlineKeyboardButton("🎵 Solo Audio (MP3)", callback_data='yt_audio'),
            InlineKeyboardButton("🎬 Video (MP4)", callback_data='yt_video')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎯 Detecté un link de YouTube!\n\n"
        "¿Qué querés descargar?",
        reply_markup=reply_markup
    )


async def handle_youtube_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data

    if choice == 'yt_cancel':
        await query.edit_message_text("❌ Descarga cancelada.")
        return

    url = context.user_data.get('youtube_url')
    if not url:
        await query.edit_message_text("❌ Error: No se encontró la URL. Por favor, enviá el link de nuevo.")
        return

    if choice == 'yt_audio':
        await query.edit_message_text("🎵 Procesando audio... Por favor esperá (puede tardar 30-60 seg).")
        await download_audio(query, context, url)
    elif choice == 'yt_video':
        await query.edit_message_text("🎬 Procesando video... Por favor esperá (puede tardar 30-60 seg).")
        await download_video(query, context, url)


def _get_proxy_url():
    return os.getenv('PROXY_FULL') or os.getenv('PROXY_URL') or os.getenv('PROXY') or None


def _clean_download_dir():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, file))
        except OSError:
            pass


def _should_skip_fallback(error_msg: str) -> bool:
    error_lower = error_msg.lower()
    return any(kw in error_lower for kw in SKIP_FALLBACK_KEYWORDS)


def _check_pot_server(url: str) -> bool:
    try:
        r = http_requests.get(f"{url}/ping", timeout=5)
        return r.status_code == 200
    except Exception:
        try:
            r = http_requests.get(url, timeout=5)
            return r.status_code < 500
        except Exception:
            return False


# --- Method 1: yt-dlp (with PO token if available) ---

def _download_with_ytdlp(video_url: str, format_type: str = 'mp3') -> dict:
    _clean_download_dir()
    output_template = os.path.join(DOWNLOAD_DIR, '%(title).80s.%(ext)s')

    ydl_opts = {
        'outtmpl': output_template,
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 3,
        'quiet': True,
        'no_warnings': True,
    }

    proxy = _get_proxy_url()
    if proxy:
        ydl_opts['proxy'] = proxy

    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    if os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file

    ydl_opts.setdefault('extractor_args', {})
    ydl_opts['extractor_args']['youtube'] = {
        'player_client': ['web', 'mweb', 'android'],
    }

    pot_url = os.getenv('POT_PROVIDER_URL')
    if pot_url:
        pot_ok = _check_pot_server(pot_url)
        print(f"[INFO] PO Token server ({pot_url}): {'OK' if pot_ok else 'UNREACHABLE'}")
        if pot_ok:
            ydl_opts['extractor_args']['youtubepot-bgutilhttp'] = {
                'base_url': [pot_url],
            }
        else:
            print("[WARN] PO Token server no responde, yt-dlp sin PO tokens")
    else:
        print("[INFO] POT_PROVIDER_URL no configurada, yt-dlp sin PO tokens")

    if format_type == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = (
            'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/'
            'bestvideo[ext=mp4]+bestaudio[ext=m4a]/'
            'best[ext=mp4]/best'
        )
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        print(f"[INFO] yt-dlp: descargando {format_type.upper()}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(video_url, download=True)

        ext = 'mp3' if format_type == 'mp3' else 'mp4'
        files = glob.glob(os.path.join(DOWNLOAD_DIR, f'*.{ext}'))
        if not files:
            files = [f for f in glob.glob(os.path.join(DOWNLOAD_DIR, '*'))
                     if not f.endswith(('.part', '.ytdl', '.tmp'))]

        if not files:
            return {'success': False, 'error': 'No se encontró el archivo descargado'}

        files.sort(key=os.path.getmtime, reverse=True)
        downloaded = files[0]

        if os.path.getsize(downloaded) == 0:
            return {'success': False, 'error': 'El archivo descargado está vacío'}

        print(f"[INFO] yt-dlp OK: {downloaded} ({os.path.getsize(downloaded)} bytes)")
        return {'success': True, 'file_path': downloaded}

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        print(f"[WARN] yt-dlp falló: {error_msg[:200]}")
        return {'success': False, 'error': error_msg}
    except Exception as e:
        print(f"[WARN] yt-dlp error: {e}")
        return {'success': False, 'error': str(e)}


# --- Method 2: Cobalt API ---

def _download_with_cobalt(video_url: str, format_type: str = 'mp3') -> dict:
    _clean_download_dir()

    api_url = os.getenv('COBALT_API_URL', COBALT_API_URL)
    api_key = os.getenv('COBALT_API_KEY', COBALT_API_KEY)

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if api_key:
        headers['Authorization'] = f'Api-Key {api_key}'

    if format_type == 'mp3':
        payload = {
            'url': video_url,
            'downloadMode': 'audio',
            'audioFormat': 'mp3',
            'filenameStyle': 'pretty',
        }
    else:
        payload = {
            'url': video_url,
            'downloadMode': 'auto',
            'videoQuality': '720',
            'youtubeVideoCodec': 'h264',
            'filenameStyle': 'pretty',
        }

    try:
        print(f"[INFO] Cobalt API: descargando {format_type.upper()}...")
        resp = http_requests.post(api_url, json=payload, headers=headers, timeout=30)

        if resp.status_code != 200:
            return {'success': False, 'error': f'Cobalt API error HTTP {resp.status_code}'}

        data = resp.json()

        if 'error' in data:
            error_code = data['error'].get('code', str(data['error']))
            return {'success': False, 'error': f'Cobalt: {error_code}'}

        tunnel_url = data.get('url')
        filename = data.get('filename', f'download.{format_type}')

        if not tunnel_url:
            return {'success': False, 'error': 'Cobalt no devolvió URL de descarga'}

        print(f"[INFO] Cobalt: descargando archivo '{filename}'...")
        dl_resp = http_requests.get(tunnel_url, stream=True, timeout=300)

        if dl_resp.status_code != 200:
            return {'success': False, 'error': f'Error descargando archivo: HTTP {dl_resp.status_code}'}

        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        file_path = os.path.join(DOWNLOAD_DIR, safe_filename)

        total = 0
        with open(file_path, 'wb') as f:
            for chunk in dl_resp.iter_content(chunk_size=256 * 1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)

        if total == 0:
            return {'success': False, 'error': 'Cobalt: archivo descargado vacío'}

        print(f"[INFO] Cobalt OK: {file_path} ({total} bytes)")
        return {'success': True, 'file_path': file_path}

    except http_requests.Timeout:
        return {'success': False, 'error': 'Cobalt: timeout en la descarga'}
    except Exception as e:
        print(f"[WARN] Cobalt error: {e}")
        return {'success': False, 'error': f'Cobalt: {str(e)[:200]}'}


# --- Method 3: Piped API (uses NewPipeExtractor, different from yt-dlp) ---

def _download_with_piped(video_url: str, format_type: str = 'mp3') -> dict:
    _clean_download_dir()

    video_id = _extract_video_id(video_url)
    if not video_id:
        return {'success': False, 'error': 'Piped: no se pudo extraer el video ID'}

    instances = list(PIPED_INSTANCES)
    custom_instance = os.getenv('PIPED_API_URL')
    if custom_instance:
        instances.insert(0, custom_instance.rstrip('/'))

    last_error = ''
    for instance in instances:
        try:
            api_url = f"{instance}/streams/{video_id}"
            print(f"[INFO] Piped ({instance}): obteniendo streams...")
            resp = http_requests.get(api_url, timeout=15)

            if resp.status_code != 200:
                last_error = f'Piped {instance}: HTTP {resp.status_code}'
                print(f"[WARN] {last_error}")
                continue

            data = resp.json()

            if 'error' in data:
                last_error = f"Piped: {data['error']}"
                print(f"[WARN] {last_error}")
                continue

            stream_url = None
            filename = data.get('title', 'download') or 'download'
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)[:80]

            if format_type == 'mp3':
                streams = data.get('audioStreams', [])
                best = None
                for s in streams:
                    if s.get('format') == 'M4A' or s.get('mimeType', '').startswith('audio/'):
                        if best is None or s.get('bitrate', 0) > best.get('bitrate', 0):
                            best = s
                if not best and streams:
                    best = max(streams, key=lambda s: s.get('bitrate', 0))
                if best:
                    stream_url = best.get('url')
                    ext = 'mp3'
                    filename = f"{filename}.{ext}"
            else:
                streams = data.get('videoStreams', [])
                best = None
                for s in streams:
                    if s.get('videoOnly', False):
                        continue
                    q = int(re.sub(r'\D', '', s.get('quality', '0')) or 0)
                    if q <= 720 and (best is None or q > int(re.sub(r'\D', '', best.get('quality', '0')) or 0)):
                        best = s
                if not best:
                    for s in streams:
                        if not s.get('videoOnly', False):
                            best = s
                            break
                if best:
                    stream_url = best.get('url')
                    ext = 'mp4'
                    filename = f"{filename}.{ext}"

            if not stream_url:
                last_error = f'Piped {instance}: no streams disponibles'
                print(f"[WARN] {last_error}")
                continue

            print(f"[INFO] Piped: descargando stream de {instance}...")
            dl_resp = http_requests.get(stream_url, stream=True, timeout=300, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            })

            if dl_resp.status_code != 200:
                last_error = f'Piped stream download: HTTP {dl_resp.status_code}'
                print(f"[WARN] {last_error}")
                continue

            file_path = os.path.join(DOWNLOAD_DIR, filename)
            total = 0
            with open(file_path, 'wb') as f:
                for chunk in dl_resp.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)

            if total == 0:
                last_error = f'Piped {instance}: archivo vacío'
                print(f"[WARN] {last_error}")
                continue

            if format_type == 'mp3' and not file_path.endswith('.mp3'):
                import subprocess
                mp3_path = os.path.splitext(file_path)[0] + '.mp3'
                try:
                    subprocess.run(
                        ['ffmpeg', '-i', file_path, '-vn', '-ab', '192k', '-y', mp3_path],
                        capture_output=True, timeout=120
                    )
                    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                        os.remove(file_path)
                        file_path = mp3_path
                except Exception as e:
                    print(f"[WARN] ffmpeg conversion failed: {e}")

            print(f"[INFO] Piped OK: {file_path} ({total} bytes)")
            return {'success': True, 'file_path': file_path}

        except http_requests.Timeout:
            last_error = f'Piped {instance}: timeout'
            print(f"[WARN] {last_error}")
            continue
        except Exception as e:
            last_error = f'Piped {instance}: {str(e)[:100]}'
            print(f"[WARN] {last_error}")
            continue

    return {'success': False, 'error': last_error or 'Piped: todas las instancias fallaron'}


# --- Orchestrator: tries all methods in order ---

def download_youtube(video_url: str, format_type: str = 'mp3') -> dict:
    # Method 1: yt-dlp (with PO token if available)
    result = _download_with_ytdlp(video_url, format_type)
    if result['success']:
        return result

    ytdlp_error = result.get('error', '')

    if _should_skip_fallback(ytdlp_error):
        return {'success': False, 'error': ytdlp_error[:200]}

    # Method 2: Cobalt API
    print("[INFO] yt-dlp falló, intentando Cobalt API como fallback...")
    cobalt_result = _download_with_cobalt(video_url, format_type)
    if cobalt_result['success']:
        return cobalt_result

    cobalt_error = cobalt_result.get('error', '')
    print(f"[WARN] Cobalt también falló: {cobalt_error}")

    # Method 3: Piped API (uses totally different extractor)
    print("[INFO] Cobalt falló, intentando Piped API como último fallback...")
    piped_result = _download_with_piped(video_url, format_type)
    if piped_result['success']:
        return piped_result

    piped_error = piped_result.get('error', '')
    print(f"[WARN] Piped también falló: {piped_error}")

    return {
        'success': False,
        'error': f"Todos los métodos fallaron. yt-dlp: {ytdlp_error[:80]}"
    }


async def download_audio(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    try:
        result = download_youtube(url, 'mp3')

        if not result['success']:
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Reintentar", callback_data='yt_audio'),
                    InlineKeyboardButton("❌ Cancelar", callback_data='yt_cancel')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"❌ {result['error']}\n\n¿Querés reintentar?",
                reply_markup=reply_markup
            )
            return

        audio_file = result['file_path']

        if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
            await query.edit_message_text("❌ El archivo descargado está vacío")
            return

        file_size = os.path.getsize(audio_file)
        if file_size > 50 * 1024 * 1024:
            await query.edit_message_text(
                f"⚠️ El audio es demasiado grande ({file_size / (1024*1024):.1f} MB).\n"
                f"Telegram tiene un límite de 50 MB para bots."
            )
            os.remove(audio_file)
            return

        await query.edit_message_text("📤 Enviando audio...")

        with open(audio_file, 'rb') as audio:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio,
                read_timeout=60,
                write_timeout=60,
                connect_timeout=60
            )

        try:
            await query.edit_message_text("✅ Audio enviado correctamente!")
        except Exception:
            pass

        if os.path.exists(audio_file):
            os.remove(audio_file)

    except Exception as e:
        print(f"[ERROR] download_audio: {e}")
        try:
            await query.edit_message_text("❌ Error al procesar el audio.")
        except Exception:
            pass


async def download_video(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    try:
        result = download_youtube(url, 'mp4')

        if not result['success']:
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Reintentar", callback_data='yt_video'),
                    InlineKeyboardButton("❌ Cancelar", callback_data='yt_cancel')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"❌ {result['error']}\n\n¿Querés reintentar?",
                reply_markup=reply_markup
            )
            return

        video_file = result['file_path']

        if not os.path.exists(video_file) or os.path.getsize(video_file) == 0:
            await query.edit_message_text("❌ El archivo descargado está vacío")
            return

        file_size = os.path.getsize(video_file)
        if file_size > 50 * 1024 * 1024:
            await query.edit_message_text(
                f"⚠️ El video es demasiado grande ({file_size / (1024*1024):.1f} MB).\n"
                f"Telegram tiene un límite de 50 MB para bots.\n"
                f"Probá descargando solo el audio."
            )
            os.remove(video_file)
            return

        await query.edit_message_text("📤 Enviando video...")

        with open(video_file, 'rb') as video:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=video,
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60
            )

        try:
            await query.edit_message_text("✅ Video enviado correctamente!")
        except Exception:
            pass

        if os.path.exists(video_file):
            os.remove(video_file)

    except Exception as e:
        print(f"[ERROR] download_video: {e}")
        try:
            await query.edit_message_text("❌ Error al procesar el video.")
        except Exception:
            pass
