import asyncio
import os
import subprocess
import json
import time
import random
from pyrogram import Client
from pyrogram.errors import FloodWait
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import API_ID, API_HASH, STORAGE_CHANNEL_ID

# ========================
# CONFIGURAÇÕES GERAIS
# ========================
SESSION_NAME = "minha_conta_de_upload"
MONITOR_FOLDER = "C:/converter"
SLEEP_TIME = 30
WORKER_COUNT = 16
MAX_CONCURRENT_UPLOADS = 1

MIN_UPLOAD_INTERVAL = 300      # 5 minutos
MAX_UPLOAD_INTERVAL = 600      # 10 minutos

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFPROBE_PATH = os.path.join(BASE_DIR, "ffprobe.exe")
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")
THUMBNAIL_PATH = os.path.join(MONITOR_FOLDER, "thumb.jpg")
CACHE_FILE = os.path.join(BASE_DIR, "metadata_cache.json")

# ========================
# FUNÇÕES AUXILIARES
# ========================

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def log(msg, color="white"):
    colors = {
        "green": "\033[92m", "yellow": "\033[93m",
        "red": "\033[91m", "blue": "\033[94m", "white": "\033[0m"
    }
    print(colors.get(color, "\033[0m") + msg + "\033[0m")

# ========================
# PROCESSAMENTO DE VÍDEO
# ========================

def get_video_metadata(file_path):
    """Extrai metadados usando FFprobe."""
    if not os.path.exists(FFPROBE_PATH):
        log(f"ERRO: ffprobe.exe não encontrado em {FFPROBE_PATH}", "red")
        return None, None, None

    try:
        command = [
            FFPROBE_PATH, "-v", "quiet", "-print_format", "json", "-show_streams", file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
        )

        if not video_stream:
            log("Stream de vídeo não encontrado.", "red")
            return None, None, None

        duration = int(float(video_stream.get("duration", 0)))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        if duration == 0 or width == 0:
            return None, None, None

        log(f"Metadados extraídos: {width}x{height}, {duration}s", "green")
        return duration, width, height
    except Exception as e:
        log(f"Erro no FFprobe: {e}", "red")
        return None, None, None

def create_thumbnail(file_path, duration):
    """Cria thumbnail com FFmpeg."""
    if not os.path.exists(FFMPEG_PATH):
        log(f"ERRO: ffmpeg.exe não encontrado em {FFMPEG_PATH}", "red")
        return None

    try:
        thumb_time = min(5, int(duration * 0.1))
        command = [
            FFMPEG_PATH, "-i", file_path, "-ss", str(thumb_time),
            "-vframes", "1", THUMBNAIL_PATH, "-y"
        ]
        subprocess.run(command, capture_output=True, check=True)
        if os.path.exists(THUMBNAIL_PATH):
            log("Thumbnail criado com sucesso.", "blue")
            return THUMBNAIL_PATH
    except Exception as e:
        log(f"Erro no FFmpeg: {e}", "red")
    return None

# ========================
# UPLOAD
# ========================

def progress_callback(current, total):
    """Callback de progresso (síncrono)."""
    pct = (current / total) * 100
    print(f"Progresso: {pct:.2f}%", end="\r")

async def upload_video(app, full_path, caption_text, cache, sem):
    async with sem:
        try:
            file_size_mb = os.path.getsize(full_path) / (1024**2)
            MAX_FILE_SIZE_MB = 3900  # Limite seguro do Telegram
            
            if file_size_mb > MAX_FILE_SIZE_MB:
                log(f"⚠️  Arquivo muito grande ({file_size_mb:.0f}MB > {MAX_FILE_SIZE_MB}MB): {caption_text}", "yellow")
                log(f"   Deletando arquivo...", "yellow")
                os.remove(full_path)
                return
            
            if full_path in cache:
                duration, width, height = cache[full_path].values()
                log(f"Metadados cacheados: {duration}s, {width}x{height}", "yellow")
            else:
                duration, width, height = await asyncio.to_thread(get_video_metadata, full_path)
                if not duration:
                    duration, width, height = 0, 0, 0
                cache[full_path] = {"duration": duration, "width": width, "height": height}
                save_cache(cache)

            thumb = None
            if duration > 0:
                thumb = await asyncio.to_thread(create_thumbnail, full_path, duration)

            backoff = 5
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    log(f"🔄 Enviando {caption_text}...", "blue")
                    
                    await app.send_video(
                        chat_id=STORAGE_CHANNEL_ID,
                        video=full_path,
                        caption=caption_text,
                        progress=progress_callback,
                        duration=duration,
                        width=width,
                        height=height,
                        thumb=thumb
                    )
                    
                    log(f"\n✅ Upload concluído: {caption_text}", "green")
                    os.remove(full_path)
                    if thumb and os.path.exists(thumb):
                        os.remove(thumb)

                    wait_time = random.uniform(MIN_UPLOAD_INTERVAL, MAX_UPLOAD_INTERVAL)
                    minutes = wait_time / 60
                    log(f"⏱️  Aguardando {minutes:.1f} minutos até próximo upload...", "yellow")
                    await asyncio.sleep(wait_time)
                    break
                    
                except FloodWait as e:
                    log(f"\n⚠️ FloodWait: Telegram pediu para esperar {e.value}s", "yellow")
                    log(f"   Respeitando limite do Telegram...", "yellow")
                    await asyncio.sleep(e.value + random.uniform(5, 15))  # Adiciona buffer aleatório
                    retry_count += 1
                    
                except (OSError, ConnectionError) as e:
                    if "10065" in str(e):
                        retry_count += 1
                        log(f"\n🔌 Erro de conexão (tentativa {retry_count}/{max_retries})", "yellow")
                        if retry_count < max_retries:
                            log(f"Reconectando em {backoff}s...", "yellow")
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 2, 60)
                        else:
                            log(f"❌ Falha após {max_retries} tentativas", "red")
                            break
                    else:
                        raise
                        
                except Exception as e:
                    log(f"❌ Erro no upload ({caption_text}): {e}", "red")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 120)
                    
        except Exception as e:
            log(f"Erro inesperado: {e}", "red")
            
# ========================
# MAIN LOOP
# ========================

async def main():
    log("Iniciando cliente Pyrogram...", "blue")
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, workers=WORKER_COUNT)

    cache = load_cache()
    sem = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

    async with app:
        me = await app.get_me()
        log(f"✅ Logado como {me.first_name}", "green")
        log(f"📁 Monitorando: {MONITOR_FOLDER}", "white")
        log(f"🚀 Modo prioridade total (1 upload por vez).", "yellow")

        while True:
            try:
                all_files = [
                    f for f in os.listdir(MONITOR_FOLDER)
                    if f.lower().endswith(('.mp4', '.mkv', '.avi'))
                ]
            except FileNotFoundError:
                log(f"ERRO: Pasta {MONITOR_FOLDER} não encontrada.", "red")
                break

            if all_files:
                all_files.sort()
                for file_name in all_files:
                    full_path = os.path.join(MONITOR_FOLDER, file_name)
                    caption_text = os.path.splitext(file_name)[0]
                    log(f"Iniciando upload: {file_name}", "blue")
                    await upload_video(app, full_path, caption_text, cache, sem)

            await asyncio.sleep(SLEEP_TIME)

# ========================
# ENTRY POINT
# ========================
if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())