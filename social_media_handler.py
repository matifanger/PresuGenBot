import logging
import os
import re
import time
from typing import Optional

import requests
from telegram import Update
from telegram.ext import ContextTypes
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse

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


def is_instagram_url(text: Optional[str]) -> bool:
    if not text:
        return False
    return bool(INSTAGRAM_URL_REGEX.search(text.strip()))


def _parse_proxy_from_env():
    """Lee PROXY_FULL del entorno y devuelve un dict con partes o None si no hay proxy."""
    proxy_full = os.getenv('PROXY_FULL') or os.getenv('PROXY_URL') or os.getenv('PROXY')
    if not proxy_full:
        return None

    try:
        parsed = urlparse(proxy_full)
        protocol = parsed.scheme or 'http'
        username = parsed.username or ''
        password = parsed.password or ''
        server = parsed.hostname or ''
        port = parsed.port or 80

        full = f"{protocol}://{username}:{password}@{server}:{port}"

        return {
            'server': server,
            'port': port,
            'username': username,
            'password': password,
            'protocol': protocol,
            'full': full,
        }
    except Exception:
        return None


def _create_instagram_driver(download_path=None, use_wire=True):
    """Crea un driver de Chrome para Instagram."""
    try:
        if download_path:
            os.makedirs(download_path, exist_ok=True)
            download_path = os.path.abspath(download_path)
        else:
            download_path = os.path.abspath('downloads')
            os.makedirs(download_path, exist_ok=True)
        
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        proxy_cfg = _parse_proxy_from_env()
        
        # Siempre usar seleniumwire para capturar requests
        from seleniumwire import webdriver as wire_webdriver
        
        seleniumwire_options = {}
        
        if proxy_cfg and proxy_cfg.get('server'):
            chrome_options.add_argument(f"--proxy-server={proxy_cfg['protocol']}://{proxy_cfg['server']}:{proxy_cfg['port']}")
            seleniumwire_options = {
                'proxy': {
                    'http': proxy_cfg['full'],
                    'https': proxy_cfg['full'],
                },
            }
            masked = f"{proxy_cfg['protocol']}://{proxy_cfg['username']}:****@{proxy_cfg['server']}:{proxy_cfg['port']}"
            print(f"[DEBUG] Instagram driver con proxy: {masked}")
        
        service = Service(ChromeDriverManager().install())
        
        if seleniumwire_options:
            driver = wire_webdriver.Chrome(service=service, options=chrome_options, seleniumwire_options=seleniumwire_options)
        else:
            driver = wire_webdriver.Chrome(service=service, options=chrome_options)
        
        try:
            driver.set_page_load_timeout(300)
            driver.set_script_timeout(300)
        except Exception:
            pass

        print(f"[DEBUG] Instagram driver creado: {download_path}")
        return driver
        
    except Exception as e:
        print(f"[ERROR] No se pudo crear el driver: {e}")
        return None


def _wait_for_instagram_download(download_dir, timeout=180):
    """Espera a que termine la descarga en el directorio."""
    print(f"[DEBUG] Esperando descarga en: {download_dir}")
    
    for seconds in range(timeout):
        files = os.listdir(download_dir)
        
        downloading = any(f.endswith(('.crdownload', '.tmp', '.part')) for f in files)
        
        if downloading:
            if seconds % 10 == 0:
                print(f"[DEBUG] Descarga en progreso... ({seconds}s/{timeout}s)")
        elif files:
            non_temp_files = [f for f in files if not f.endswith(('.crdownload', '.tmp', '.part'))]
            if non_temp_files:
                non_temp_files.sort(
                    key=lambda x: os.path.getmtime(os.path.join(download_dir, x)),
                    reverse=True
                )
                latest_file = os.path.join(download_dir, non_temp_files[0])
                if os.path.getsize(latest_file) > 0:
                    print(f"[DEBUG] Descarga completada: {non_temp_files[0]}")
                    return latest_file
        
        time.sleep(1)
    
    print("[ERROR] Timeout esperando descarga")
    return None


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
    """Descarga video de Instagram usando Selenium + yt-dlp con cookies."""
    import subprocess
    import tempfile
    import json
    
    shortcode = _extract_instagram_shortcode(url)
    if not shortcode:
        raise ValueError("No pude identificar el reel/post de Instagram.")

    _ensure_download_dir()
    
    download_dir = DOWNLOAD_DIR
    driver = None
    
    try:
        print(f"[INFO] Descargando reel {shortcode} con Selenium + yt-dlp...")
        
        # Limpiar directorio
        if os.path.exists(download_dir):
            for file in os.listdir(download_dir):
                try:
                    if file.endswith('.mp4'):
                        os.remove(os.path.join(download_dir, file))
                except:
                    pass
        
        # Crear driver para obtener cookies
        driver = _create_instagram_driver(download_dir)
        if not driver:
            raise RuntimeError("No se pudo iniciar el navegador")
        
        print(f"[DEBUG] Navegando a {url} para obtener cookies...")
        driver.get(url)
        time.sleep(5)
        
        # Exportar cookies a archivo temporal
        cookies_file = None
        try:
            cookies = driver.get_cookies()
            if cookies:
                # Crear archivo de cookies en formato Netscape
                cookies_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                cookies_file.write("# Netscape HTTP Cookie File\n")
                cookies_file.write("# This file was generated by PresuGenBot\n\n")
                
                for cookie in cookies:
                    domain = cookie.get('domain', '')
                    flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                    path = cookie.get('path', '/')
                    secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                    expiration = str(int(cookie.get('expiration', 0)))
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    
                    cookies_file.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}\n")
                
                cookies_file.close()
                print(f"[DEBUG] Cookies exportadas a: {cookies_file.name}")
        except Exception as e:
            print(f"[WARN] Error exportando cookies: {e}")
        
        driver.quit()
        driver = None
        
        # Ahora descargar con yt-dlp usando las cookies
        output_template = os.path.join(download_dir, 'instagram_%(id)s.%(ext)s')
        
        cmd = [
            'yt-dlp',
            '-f', 'best[ext=mp4]/best',
            '-o', output_template,
            '--no-warnings',
            '--no-check-certificate',
        ]
        
        if cookies_file:
            cmd.extend(['--cookies', cookies_file.name])
        
        cmd.append(url)
        
        print(f"[DEBUG] Ejecutando yt-dlp con cookies...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        print(f"[DEBUG] yt-dlp stdout: {result.stdout}")
        if result.stderr:
            print(f"[DEBUG] yt-dlp stderr: {result.stderr}")
        
        # Limpiar archivo de cookies
        if cookies_file:
            try:
                os.unlink(cookies_file.name)
            except:
                pass
        
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp falló: {result.stderr}")
        
        # Buscar el archivo descargado
        expected_file = os.path.join(download_dir, f'instagram_{shortcode}.mp4')
        
        if os.path.exists(expected_file):
            file_size = os.path.getsize(expected_file)
            print(f"[DEBUG] Video descargado: {expected_file} ({file_size} bytes)")
            return expected_file
        
        # Buscar cualquier archivo mp4 nuevo
        mp4_files = [f for f in os.listdir(download_dir) if f.endswith('.mp4')]
        if mp4_files:
            latest = os.path.join(download_dir, mp4_files[0])
            print(f"[DEBUG] Video encontrado: {latest}")
            return latest
        
        raise RuntimeError("No se encontró el video descargado")
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Timeout descargando video")
    except Exception as e:
        print(f"[ERROR] Error descargando video: {e}")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"Error descargando video: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def _extract_instagram_shortcode(url: str) -> Optional[str]:
    match = INSTAGRAM_SHORTCODE_REGEX.search(url)
    if match:
        return match.group("shortcode")
    return None


def _ensure_download_dir():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


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
