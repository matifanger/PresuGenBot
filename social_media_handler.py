import os
import re
import glob
import requests
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

import yt_dlp

DOWNLOAD_DIR = os.path.abspath('downloads')
MAX_TELEGRAM_FILE_SIZE = 50 * 1024 * 1024

COBALT_API_URL = 'https://dwnld.nichind.dev'
COBALT_API_KEY = 'b05007aa-bb63-4267-a66e-78f8e10bf9bf'

INSTAGRAM_SHORTCODE_REGEX = re.compile(
    r"instagram\.com/(?:reel|reels|p|tv)/(?P<shortcode>[A-Za-z0-9_\-]+)",
    re.IGNORECASE,
)
INSTAGRAM_URL_REGEX = re.compile(r"instagram\.com/([A-Za-z0-9_\-]+)", re.IGNORECASE)


def is_instagram_url(text: Optional[str]) -> bool:
    if not text:
        return False
    return bool(INSTAGRAM_URL_REGEX.search(text.strip()))


def _get_proxy_url():
    return os.getenv('PROXY_FULL') or os.getenv('PROXY_URL') or os.getenv('PROXY') or None


def _extract_instagram_shortcode(url: str) -> Optional[str]:
    match = INSTAGRAM_SHORTCODE_REGEX.search(url)
    if match:
        return match.group("shortcode")
    return None


def _ensure_download_dir():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _clean_instagram_downloads():
    _ensure_download_dir()
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            if file.endswith('.mp4'):
                os.remove(os.path.join(DOWNLOAD_DIR, file))
        except OSError:
            pass


# --- Method 1: yt-dlp ---

def _download_instagram_ytdlp(url: str, shortcode: str) -> str:
    _clean_instagram_downloads()
    output_template = os.path.join(DOWNLOAD_DIR, f'instagram_{shortcode}.%(ext)s')

    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 3,
    }

    proxy = _get_proxy_url()
    if proxy:
        ydl_opts['proxy'] = proxy

    print(f"[INFO] yt-dlp: descargando Instagram {shortcode}...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    expected = os.path.join(DOWNLOAD_DIR, f'instagram_{shortcode}.mp4')
    if os.path.exists(expected) and os.path.getsize(expected) > 0:
        print(f"[INFO] yt-dlp OK: {expected} ({os.path.getsize(expected)} bytes)")
        return expected

    pattern = os.path.join(DOWNLOAD_DIR, f'instagram_{shortcode}.*')
    files = [f for f in glob.glob(pattern) if not f.endswith(('.part', '.ytdl', '.tmp'))]
    if files:
        files.sort(key=os.path.getmtime, reverse=True)
        return files[0]

    raise RuntimeError("yt-dlp: no se encontró el archivo descargado")


# --- Method 2: Cobalt API ---

def _download_instagram_cobalt(url: str, shortcode: str) -> str:
    _clean_instagram_downloads()

    api_url = os.getenv('COBALT_API_URL', COBALT_API_URL)
    api_key = os.getenv('COBALT_API_KEY', COBALT_API_KEY)

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if api_key:
        headers['Authorization'] = f'Api-Key {api_key}'

    print(f"[INFO] Cobalt: descargando Instagram {shortcode}...")
    resp = requests.post(api_url, json={
        'url': url,
        'downloadMode': 'auto',
        'filenameStyle': 'pretty',
    }, headers=headers, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(f'Cobalt error HTTP {resp.status_code}')

    data = resp.json()
    if 'error' in data:
        raise RuntimeError(f'Cobalt: {data["error"].get("code", data["error"])}')

    download_url = data.get('url')
    if not download_url:
        raise RuntimeError('Cobalt: no devolvió URL')

    dl_resp = requests.get(download_url, stream=True, timeout=120)
    if dl_resp.status_code != 200:
        raise RuntimeError(f'Error descargando: HTTP {dl_resp.status_code}')

    file_path = os.path.join(DOWNLOAD_DIR, f'instagram_{shortcode}.mp4')
    total = 0
    with open(file_path, 'wb') as f:
        for chunk in dl_resp.iter_content(chunk_size=256 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)

    if total == 0:
        raise RuntimeError('Cobalt: archivo vacío')

    print(f"[INFO] Cobalt OK: {file_path} ({total} bytes)")
    return file_path


# --- Orchestrator ---

def download_instagram_video(url: str) -> str:
    shortcode = _extract_instagram_shortcode(url)
    if not shortcode:
        raise ValueError("No pude identificar el reel/post de Instagram.")

    # Method 1: yt-dlp
    try:
        return _download_instagram_ytdlp(url, shortcode)
    except Exception as e:
        print(f"[WARN] yt-dlp Instagram falló: {e}")

    # Method 2: Cobalt API
    try:
        return _download_instagram_cobalt(url, shortcode)
    except Exception as e:
        print(f"[WARN] Cobalt Instagram falló: {e}")

    raise RuntimeError("No se pudo descargar el video con ningún método")


async def handle_instagram_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()
    status_message = await update.message.reply_text("📥 Descargando video de Instagram...")
    video_path = None

    try:
        video_path = download_instagram_video(url)
        if not os.path.exists(video_path):
            raise RuntimeError("El archivo descargado no está disponible.")

        file_size = os.path.getsize(video_path)
        if file_size > MAX_TELEGRAM_FILE_SIZE:
            await status_message.edit_text(
                f"⚠️ El video pesa {file_size / (1024*1024):.1f} MB y supera el límite de 50 MB."
            )
            return

        await status_message.edit_text("📤 Enviando video...")
        await _send_video_file(context, update.effective_chat.id, video_path)
        await status_message.edit_text("✅ Video de Instagram enviado correctamente!")

    except Exception as exc:
        await status_message.edit_text(
            "❌ No pude descargar el video de Instagram.\n"
            f"Motivo: {exc}"
        )
    finally:
        _safe_remove(video_path)


async def _send_video_file(context: ContextTypes.DEFAULT_TYPE, chat_id: int, file_path: str):
    with open(file_path, "rb") as video_file:
        await context.bot.send_video(
            chat_id=chat_id,
            video=video_file,
            supports_streaming=True,
            read_timeout=120,
            write_timeout=120,
            connect_timeout=60,
        )


def _safe_remove(path: Optional[str]):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
