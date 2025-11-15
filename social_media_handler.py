import logging
import os
import re
from typing import Optional

import requests
from instaloader import Instaloader, Post
from instaloader.exceptions import InstaloaderException
from telegram import Update
from telegram.ext import ContextTypes

DOWNLOAD_DIR = os.path.abspath('downloads')
MAX_TELEGRAM_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (límite bots Telegram)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

INSTAGRAM_SHORTCODE_REGEX = re.compile(
    r"instagram\.com/(?:reel|reels|p|tv)/(?P<shortcode>[A-Za-z0-9_\-]+)",
    re.IGNORECASE,
)
INSTAGRAM_URL_REGEX = re.compile(r"instagram\.com/([A-Za-z0-9_\-]+)", re.IGNORECASE)


def is_instagram_url(text: str) -> bool:
    if not text:
        return False
    return bool(INSTAGRAM_URL_REGEX.search(text.strip()))


async def handle_instagram_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarga y envía videos de Instagram (reels, posts o IGTV)."""
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


def download_instagram_video(url: str) -> str:
    """Obtiene el video de Instagram empleando Instaloader."""
    shortcode = _extract_instagram_shortcode(url)
    if not shortcode:
        raise ValueError("No pude identificar el reel/post de Instagram.")

    _ensure_download_dir()
    loader = _build_instaloader()

    try:
        post = Post.from_shortcode(loader.context, shortcode)
    except InstaloaderException as exc:
        raise RuntimeError(f"No pude acceder al contenido: {exc}") from exc

    video_url = _resolve_instagram_video_url(post)
    if not video_url:
        raise RuntimeError("El enlace no contiene un video descargable.")

    filename = f"instagram_{shortcode}.mp4"
    file_path = os.path.join(DOWNLOAD_DIR, filename)

    try:
        response = requests.get(video_url, stream=True, timeout=120, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if chunk:
                    file.write(chunk)
    except Exception as exc:
        _safe_remove(file_path)
        raise RuntimeError(f"No pude descargar el video: {exc}") from exc

    return file_path


def _extract_instagram_shortcode(url: str) -> Optional[str]:
    match = INSTAGRAM_SHORTCODE_REGEX.search(url)
    if match:
        return match.group("shortcode")
    return None


def _ensure_download_dir():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _build_instaloader() -> Instaloader:
    loader = Instaloader(
        dirname_pattern=DOWNLOAD_DIR,
        download_video_thumbnails=False,
        download_geotags=False,
        save_metadata=False,
        download_comments=False,
        post_metadata_txt_pattern="",
    )
    loader.quiet = True
    logging.getLogger("instaloader").setLevel(logging.WARNING)
    return loader


def _resolve_instagram_video_url(post: Post) -> Optional[str]:
    if post.is_video:
        return post.video_url

    if post.typename == "GraphSidecar":
        for node in post.get_sidecar_nodes():
            if node.is_video:
                return node.video_url

    return None


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

