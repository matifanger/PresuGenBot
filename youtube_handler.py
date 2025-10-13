import os
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from urllib.parse import urlparse

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
    """Maneja la selección del usuario (audio o video)"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    # Manejar cancelación
    if choice == 'yt_cancel':
        await query.edit_message_text("❌ Descarga cancelada.")
        return
    
    # Obtener la URL guardada
    url = context.user_data.get('youtube_url')
    if not url:
        await query.edit_message_text("❌ Error: No se encontró la URL. Por favor, enviá el link de nuevo.")
        return
    
    # Actualizar el mensaje para mostrar progreso
    if choice == 'yt_audio':
        await query.edit_message_text("🎵 Procesando audio... Por favor esperá (puede tardar 30-60 seg).")
        await download_audio(query, context, url)
    elif choice == 'yt_video':
        await query.edit_message_text("🎬 Procesando video... Por favor esperá (puede tardar 30-60 seg).")
        await download_video(query, context, url)

def _parse_proxy_from_env():
    """Lee PROXY_FULL del entorno y devuelve un dict con partes o None si no hay proxy.

    Espera formato: protocol://username:password@server:port
    """
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

        # Reconstruir la URL completa sin escapados raros
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

def create_driver(download_path=None):
    """Crea un driver de Chrome para scraping con descargas configuradas"""
    try:
        # Configurar directorio de descargas
        if download_path:
            os.makedirs(download_path, exist_ok=True)
            download_path = os.path.abspath(download_path)
        else:
            download_path = os.path.abspath('downloads')
            os.makedirs(download_path, exist_ok=True)
        
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # Descomentar para modo headless
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configurar descargas automáticas sin prompts
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Proxy (opcional)
        proxy_cfg = _parse_proxy_from_env()
        if proxy_cfg and proxy_cfg.get('server'):
            try:
                # Usar selenium-wire para soporte de proxy con auth
                from seleniumwire import webdriver as wire_webdriver

                # Añadir flag --proxy-server para Chrome
                chrome_options.add_argument(f"--proxy-server={proxy_cfg['protocol']}://{proxy_cfg['server']}:{proxy_cfg['port']}")

                seleniumwire_options = {
                    'proxy': {
                        'http': proxy_cfg['full'],
                        'https': proxy_cfg['full'],
                    },
                }

                service = Service(ChromeDriverManager().install())
                driver = wire_webdriver.Chrome(service=service, options=chrome_options, seleniumwire_options=seleniumwire_options)

                # Log sin contraseña
                masked = f"{proxy_cfg['protocol']}://{proxy_cfg['username']}:****@{proxy_cfg['server']}:{proxy_cfg['port']}"
                print(f"[DEBUG] Driver con proxy configurado: {masked}")
            except Exception as e:
                print(f"[WARN] No se pudo inicializar con proxy, usando sin proxy: {e}")
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"[DEBUG] Driver creado con carpeta de descargas: {download_path}")
        return driver
        
    except Exception as e:
        print(f"[ERROR] No se pudo crear el driver: {e}")
        return None

def wait_for_download_complete(download_dir, timeout=360):
    """Espera a que termine la descarga en el directorio"""
    print(f"[DEBUG] Esperando descarga en: {download_dir}")
    
    for seconds in range(timeout):
        files = os.listdir(download_dir)
        
        # Verificar si hay archivos descargándose (.crdownload o .tmp)
        downloading = any(f.endswith(('.crdownload', '.tmp')) for f in files)
        
        if downloading:
            if seconds % 5 == 0:
                print(f"[DEBUG] Descarga en progreso... ({seconds}s/{timeout}s)")
        elif files:
            # No hay descargas en progreso y hay archivos
            non_temp_files = [f for f in files if not f.endswith(('.crdownload', '.tmp'))]
            if non_temp_files:
                # Ordenar por tiempo de modificación (más reciente primero)
                non_temp_files.sort(
                    key=lambda x: os.path.getmtime(os.path.join(download_dir, x)),
                    reverse=True
                )
                latest_file = os.path.join(download_dir, non_temp_files[0])
                print(f"[DEBUG] Descarga completada: {non_temp_files[0]}")
                return latest_file
        
        time.sleep(1)
    
    print("[ERROR] Timeout esperando descarga")
    return None

def download_with_selenium(video_url: str, format_type: str = 'mp3') -> dict:
    """
    Descarga el archivo usando Selenium para scrapear y2mate.nu
    format_type: 'mp3' para audio, 'mp4' para video
    Retorna el path del archivo descargado
    """
    driver = None
    download_dir = os.path.abspath('downloads')
    
    try:
        print(f"[INFO] Iniciando descarga de {format_type.upper()} desde y2mate.nu...")
        
        # Limpiar directorio de descargas
        if os.path.exists(download_dir):
            for file in os.listdir(download_dir):
                try:
                    os.remove(os.path.join(download_dir, file))
                    print(f"[DEBUG] Archivo anterior eliminado: {file}")
                except:
                    pass
        
        driver = create_driver(download_dir)
        if not driver:
            return {'success': False, 'error': 'No se pudo iniciar el navegador'}
        
        # Navegar a y2mate.nu
        print("[DEBUG] Navegando a y2mate.nu...")
        driver.get('https://y2mate.nu/4Fiq/')
        time.sleep(3)
        
        # Paso 1: Encontrar el input y pegar la URL
        print("[DEBUG] Buscando campo de input...")
        try:
            url_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'input'))
            )
            print("[DEBUG] Ingresando URL...")
            url_input.clear()
            url_input.send_keys(video_url)
            time.sleep(1)
        except Exception as e:
            print(f"[ERROR] No se encontró el input: {e}")
            return {'success': False, 'error': 'No se encontró el campo de entrada'}
        
        # Paso 2: Si queremos MP4, hacer clic en botón id="f" (toggle mp3/mp4)
        if format_type == 'mp4':
            print("[DEBUG] Cambiando a modo MP4...")
            try:
                format_button = driver.find_element(By.ID, 'f')
                driver.execute_script("arguments[0].click();", format_button)
                time.sleep(1)
                print("[DEBUG] Modo cambiado a MP4")
            except Exception as e:
                print(f"[DEBUG] Error cambiando a MP4: {e}")
        else:
            print("[DEBUG] Usando modo MP3 (default)")
        
        # Paso 3: Hacer clic en el botón Convert (type="submit")
        print("[DEBUG] Buscando botón Convert...")
        try:
            convert_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button[type="submit"]'))
            )
            print("[DEBUG] Haciendo clic en Convert...")
            driver.execute_script("arguments[0].click();", convert_button)
            time.sleep(3)
        except Exception as e:
            print(f"[ERROR] No se encontró el botón Convert: {e}")
            return {'success': False, 'error': 'No se encontró el botón Convert'}
        
        # Paso 4: Esperar a que aparezca el botón Download o un error
        print("[DEBUG] Esperando botón Download...")
        download_button = None
        
        for attempt in range(60):
            try:
                # Buscar mensajes de error
                try:
                    error_elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ERROR', 'error'), 'error')]")
                    for error_elem in error_elements:
                        error_text = error_elem.text.strip()
                        if error_text and len(error_text) > 5:  # Evitar textos muy cortos
                            print(f"[ERROR] Mensaje de error detectado: {error_text}")
                            return {'success': False, 'error': f'Error del sitio: {error_text}'}
                except:
                    pass
                
                # Buscar botón Download
                buttons = driver.find_elements(By.CSS_SELECTOR, 'button[type="button"]')
                for button in buttons:
                    if 'download' in button.text.lower():
                        download_button = button
                        print(f"[DEBUG] Botón Download encontrado! (intento {attempt + 1})")
                        break
                
                if download_button:
                    break
                
                if attempt % 5 == 0 and attempt > 0:
                    print(f"[DEBUG] Esperando Download... ({attempt}s/60s)")
                
                time.sleep(1)
            except:
                time.sleep(1)
        
        if not download_button:
            print("[ERROR] Timeout esperando botón Download")
            # Intentar capturar cualquier mensaje de error antes de fallar
            try:
                error_elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ERROR', 'error'), 'error')]")
                if error_elements:
                    error_text = error_elements[0].text.strip()
                    return {'success': False, 'error': f'Error: {error_text}'}
            except:
                pass
            return {'success': False, 'error': 'No apareció el botón Download'}
        
        # Paso 5: Hacer clic en Download e iniciar descarga
        print("[DEBUG] Haciendo clic en Download...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", download_button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", download_button)
        
        print("[DEBUG] Click ejecutado, esperando inicio de descarga...")
        time.sleep(3)
        
        # Paso 6: Esperar a que termine la descarga
        downloaded_file = wait_for_download_complete(download_dir, timeout=360)
        
        if not downloaded_file or not os.path.exists(downloaded_file):
            return {'success': False, 'error': 'La descarga no se completó'}
        
        print(f"[DEBUG] Descarga exitosa: {downloaded_file}")
        
        return {
            'success': True,
            'file_path': downloaded_file
        }
        
    except Exception as e:
        print(f"[ERROR] Error en descarga: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': f'Error inesperado: {str(e)}'}
    
    finally:
        if driver:
            try:
                driver.quit()
                print("[DEBUG] Driver cerrado")
            except:
                pass

async def download_audio(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Descarga solo el audio del video de YouTube"""
    try:
        os.makedirs('downloads', exist_ok=True)
        
        # Descargar con Selenium
        result = download_with_selenium(url, 'mp3')
        
        if not result['success']:
            # Mostrar error con opciones de reintento
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
        
        # Verificar archivo
        if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
            await query.edit_message_text("❌ El archivo descargado está vacío")
            return
        
        # Enviar el archivo
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
        except:
            pass
        
        # Limpiar archivo
        if os.path.exists(audio_file):
            os.remove(audio_file)
            
    except Exception as e:
        print(f"[ERROR] Error en download_audio: {e}")
        import traceback
        traceback.print_exc()
        try:
            await query.edit_message_text("❌ Error al procesar el audio.")
        except:
            pass

async def download_video(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Descarga el video con audio de YouTube"""
    try:
        os.makedirs('downloads', exist_ok=True)
        
        # Descargar con Selenium
        result = download_with_selenium(url, 'mp4')
        
        if not result['success']:
            # Mostrar error con opciones de reintento
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
        
        # Verificar archivo
        if not os.path.exists(video_file) or os.path.getsize(video_file) == 0:
            await query.edit_message_text("❌ El archivo descargado está vacío")
            return
        
        # Verificar tamaño
        file_size = os.path.getsize(video_file)
        max_size = 50 * 1024 * 1024  # 50 MB límite Telegram
        
        if file_size > max_size:
            await query.edit_message_text(
                f"⚠️ El video es demasiado grande ({file_size / (1024*1024):.1f} MB).\n"
                f"Telegram tiene un límite de 50 MB para bots.\n"
                f"Probá descargando solo el audio."
            )
            if os.path.exists(video_file):
                os.remove(video_file)
            return
        
        # Enviar el archivo
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
        except:
            pass
        
        # Limpiar archivo
        if os.path.exists(video_file):
            os.remove(video_file)
            
    except Exception as e:
        print(f"[ERROR] Error en download_video: {e}")
        import traceback
        traceback.print_exc()
        try:
            await query.edit_message_text("❌ Error al procesar el video.")
        except:
            pass
