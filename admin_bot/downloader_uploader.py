import re
import os
import time
import subprocess
import sys
import random
import json
import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait

# --- CONFIGURAÇÃO INICIAL ---
# Garante que o config.py seja encontrado (copiado dos seus scripts)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    # IMPORTANTE: Seu config.py agora precisa ter TUDO
    from config import (
        M3U_FILE_PATH, DOWNLOAD_FOLDER, LOG_FILE, REFERER_URL, 
        USER_AGENT, PROXY_URL, API_ID, API_HASH, STORAGE_CHANNEL_ID, SESSION_STRING
    )
except ImportError:
    print("ERRO: Não foi possível encontrar o arquivo 'config.py'.")
    print("Certifique-se que 'config.py' está no mesmo diretório e contém:")
    print("M3U_FILE_PATH, DOWNLOAD_FOLDER, LOG_FILE, REFERER_URL, USER_AGENT, PROXY_URL, API_ID, API_HASH, STORAGE_CHANNEL_ID")
    sys.exit(1)

# --- NOVAS CONFIGURAÇÕES DO SCRIPT ---
BATCH_SIZE = 2  # O TAMANHO DO LOTE QUE VOCÊ PEDIU
SESSION_NAME = "minha_conta_de_upload"
WORKER_COUNT = 16 # Do seu script de upload
MAX_CONCURRENT_UPLOADS = 1 # Do seu script de upload
MIN_UPLOAD_INTERVAL = 300   # 5 minutos
MAX_UPLOAD_INTERVAL = 600   # 10 minutos

# --- CAMINHOS PARA FFmpeg/FFprobe ---
# (Copiado do seu script de upload)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFPROBE_PATH = os.path.join(BASE_DIR, "ffprobe.exe")
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")
# Caminho da thumbnail agora usa o DOWNLOAD_FOLDER
THUMBNAIL_PATH = os.path.join(DOWNLOAD_FOLDER, "thumb.jpg")
CACHE_FILE = os.path.join(BASE_DIR, "metadata_cache.json")

# =================================================================
# FUNÇÃO DE LOG (do seu Uploader)
# =================================================================

def log(msg, color="white"):
    """Função de log colorida."""
    colors = {
        "green": "\033[92m", "yellow": "\033[93m",
        "red": "\033[91m", "blue": "\033[94m", "white": "\033[0m"
    }
    print(colors.get(color, "\033[0m") + str(msg) + "\033[0m")

# =================================================================
# FUNÇÕES AUXILIARES (Combinadas de ambos os scripts)
# =================================================================

def sanitize_filename(filename):
    """Remove caracteres inválidos de nomes de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def load_cache():
    """Carrega cache de metadados do uploader."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    """Salva cache de metadados do uploader."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def load_downloaded_log():
    """Carrega a lista de filmes já processados (do downloader)."""
    if not os.path.exists(LOG_FILE):
        return set()
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            downloaded = {line.strip() for line in f}
            log(f"Carregados {len(downloaded)} registros do histórico de downloads.", "blue")
            return downloaded
    except Exception as e:
        log(f"Erro ao carregar o log '{LOG_FILE}': {e}. Começando com um histórico vazio.", "red")
        return set()

def add_to_downloaded_log(full_title_with_lang: str):
    """Adiciona um filme ao histórico APÓS O UPLOAD."""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(full_title_with_lang + '\n')
    except Exception as e:
        log(f"Erro ao salvar no log '{LOG_FILE}': {e}", "red")

def parse_m3u(file_path: str):
    """Lê um M3U e extrai informações dos filmes (do downloader)."""
    log(f"Lendo e aplicando filtros ao arquivo: {file_path}\n", "blue")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        log(f"ERRO: Arquivo M3U não encontrado em: {file_path}", "red")
        log("Verifique se o nome/caminho está correto no seu arquivo 'config.py'.", "red")
        return []
    except Exception as e:
        log(f"Erro ao ler o arquivo M3U: {e}", "red")
        return []

    movies = []
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            try:
                group_match = re.search(r'group-title="([^"]+)"', line, re.IGNORECASE)
                if group_match and "filmes" in group_match.group(1).lower():
                    title_match = re.search(r'tvg-name="([^"]+)"', line)
                    original_title = title_match.group(1).strip() if title_match else line.split(',')[-1].strip()
                    
                    if re.search(r'\(\d{4}\)', original_title):
                        url = lines[i+1].strip()
                        
                        language = "Dublado"
                        if any(word in original_title.upper() for word in ["LEGENDADO", " LEG"]):
                            language = "Legendado"
                        
                        clean_title = re.sub(r'\s+(DUBLADO|LEGENDADO|DUB|LEG|DUAL)\b', '', original_title, flags=re.IGNORECASE).strip()
                        clean_title = re.sub(r'\s+', ' ', clean_title)
                        
                        lang_tag = "[DUB]" if language == "Dublado" else "[LEG]"
                        full_title_with_lang = f"{clean_title} {lang_tag}"
                        
                        movies.append({
                            'full_title_with_lang': full_title_with_lang,
                            'url': url
                        })
            except Exception as e:
                log(f"Pequeno erro ao processar a linha: {line}. Detalhes: {e}", "yellow")
    
    log(f"Encontrados {len(movies)} filmes que batem com os critérios.", "green")
    return movies

# =================================================================
# BLOCO DE PROCESSAMENTO DE VÍDEO (do Uploader)
# =================================================================

def get_video_metadata(file_path):
    """Extrai metadados usando FFprobe (síncrono)."""
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
        if duration == 0 or width == 0: return None, None, None
        return duration, width, height
    except Exception as e:
        log(f"Erro no FFprobe: {e}", "red")
        return None, None, None

def create_thumbnail(file_path, duration):
    """Cria thumbnail com FFmpeg (síncrono)."""
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
            return THUMBNAIL_PATH
    except Exception as e:
        log(f"Erro no FFmpeg: {e}", "red")
    return None

def progress_callback(current, total):
    """Callback de progresso (síncrono)."""
    pct = (current / total) * 100
    print(f"Progresso: {pct:.2f}%", end="\r")

# =================================================================
# FUNÇÕES PRINCIPAIS (DOWNLOADER E UPLOADER REFATORADOS)
# =================================================================

def download_movie_sync(movie_info: dict) -> str:
    """
    Baixa um único filme usando yt-dlp (FUNÇÃO SÍNCRONA).
    Será executada em uma thread separada para não bloquear o asyncio.
    Retorna o caminho do arquivo em sucesso, ou None em falha.
    """
    full_title_with_lang = movie_info['full_title_with_lang']
    url = movie_info['url']
    
    log(f"\n+++ Iniciando download de: '{full_title_with_lang}' via yt-dlp +++", "blue")
    file_path = ""
    try:
        safe_filename = sanitize_filename(full_title_with_lang) + ".mp4"
        file_path = os.path.join(DOWNLOAD_FOLDER, safe_filename)
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        command = [
            sys.executable, '-m', 'yt_dlp',
            '--output', file_path,
            '--no-playlist', 
            '--retries', '20', 
            '--fragment-retries', '20',
            '--no-check-certificates', 
            '--socket-timeout', '30',
            '--user-agent', USER_AGENT,
            '--add-header', f'Referer: {REFERER_URL}',
            '--add-header', f'Origin: {REFERER_URL}',
        ]
        if PROXY_URL:
            log("+++ Usando Proxy para esta requisição +++", "yellow")
            command.extend(['--proxy', PROXY_URL])
            
        command.append(url)
        
        # --- MUDANÇA CRÍTICA: Voltamos para o subprocess.run() síncrono ---
        # A função inteira rodará em uma thread, então isso não bloqueará o loop principal.
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        log(f"\n✅ Download de '{full_title_with_lang}' concluído com sucesso!", "green")
        return file_path # Retorna o caminho do arquivo para o upload

    except subprocess.CalledProcessError as e:
        log(f"\n❌ ERRO DO YT-DLP ao baixar '{full_title_with_lang}': O comando falhou com o código {e.returncode}", "red")
        try:
            # e.stderr já será uma string se capture_output=True e text=True
            log(f"Saída do erro: {e.stderr}", "red")
        except:
            log(f"Saída do erro (não foi possível decodificar): {e.stderr}", "red")
            
    except Exception as e:
        # Este bloco agora vai capturar o erro que estava em branco
        log(f"\n❌ ERRO INESPERADO (TIPO: {type(e)}) ao baixar '{full_title_with_lang}':", "red")
        log(f"   REPR DO ERRO: {repr(e)}", "red")
        import traceback
        log(traceback.format_exc(), "yellow") # Imprime o stack trace completo
    
    # Se chegou aqui, falhou. Limpa o arquivo parcial.
    if file_path and os.path.exists(file_path):
        try:
            log(f"Limpando arquivo parcial: {file_path}", "yellow")
            os.remove(file_path)
        except Exception as e:
            log(f"Erro ao limpar arquivo parcial: {e}", "red")
            
    return None # Retorna None em caso de falha

async def upload_video(app, full_path, caption_text, cache, sem):
    """
    Função de upload MODIFICADA para Square Cloud.
    Remove o uso de ffprobe/ffmpeg para evitar 'Permission denied'.
    """
    async with sem:
        try:
            file_size_mb = os.path.getsize(full_path) / (1024**2)
            MAX_FILE_SIZE_MB = 3900 
            
            if file_size_mb > MAX_FILE_SIZE_MB:
                log(f"⚠️  Arquivo muito grande ({file_size_mb:.0f}MB > {MAX_FILE_SIZE_MB}MB): {caption_text}", "yellow")
                log(f"   Deletando arquivo...", "yellow")
                os.remove(full_path)
                return False # Falha no upload

            # --- BLOCO FFPROBE/FFMPEG REMOVIDO ---
            # Não tentamos mais pegar metadados ou criar thumbnails,
            # pois não temos permissão para rodar .exe no Square Cloud.
            # O Pyrogram vai tentar adivinhar isso sozinho.
            # 
            # (Todo o bloco que chamava get_video_metadata e create_thumbnail foi removido)
            # --- FIM DA REMOÇÃO ---

            backoff = 5
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    log(f"🔄 Enviando {caption_text}...", "blue")
                    
                    # --- MUDANÇA CRÍTICA ---
                    # Removemos duration, width, height, e thumb.
                    # O Pyrogram vai detectar isso automaticamente.
                    await app.send_video(
                        chat_id=STORAGE_CHANNEL_ID,
                        video=full_path,
                        caption=caption_text,
                        progress=progress_callback
                    )
                    # --- FIM DA MUDANÇA ---
                    
                    log(f"\n✅ Upload concluído: {caption_text}", "green")
                    os.remove(full_path) # Deleta o vídeo
                    
                    # (A lógica de deletar o thumb também foi removida, 
                    # pois ele não é mais criado)

                    wait_time = random.uniform(MIN_UPLOAD_INTERVAL, MAX_UPLOAD_INTERVAL)
                    minutes = wait_time / 60
                    log(f"⏱️  Aguardando {minutes:.1f} minutos até próximo upload...", "yellow")
                    await asyncio.sleep(wait_time)
                    return True # Sucesso no upload
                    
                except FloodWait as e:
                    log(f"\n⚠️ FloodWait: Telegram pediu para esperar {e.value}s", "yellow")
                    await asyncio.sleep(e.value + random.uniform(5, 15))
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
            
            return False # Falha no upload

        except Exception as e:
            log(f"Erro inesperado em upload_video: {e}", "red")
            return False # Falha no upload
        
# =================================================================
# FUNÇÃO PRINCIPAL (O ORQUESTRADOR)
# =================================================================

async def main():
    log("Iniciando cliente Pyrogram...", "blue")

    if not SESSION_STRING:
        log("ERRO: A variável de ambiente PYROGRAM_SESSION_STRING não foi definida no Square Cloud.", "red")
        log("Por favor, gere a string localmente e adicione-a ao painel do seu app.", "red")
        sys.exit(1)

    log("Iniciando cliente Pyrogram a partir da String de Sessão...", "blue")

    # Inicia o cliente usando a string, em vez do nome da sessão
    app = Client(
        SESSION_NAME,  # Pode manter o nome, não afeta
        session_string=SESSION_STRING,
        api_id=API_ID,
        api_hash=API_HASH,
        workers=WORKER_COUNT
    )

    # Carrega o cache e o log usando asyncio.to_thread para não bloquear
    cache = await asyncio.to_thread(load_cache)
    downloaded_set = await asyncio.to_thread(load_downloaded_log)
    
    # Garante que a pasta de download exista
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    sem = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

    # Carrega a lista de filmes (também em thread)
    all_movies_in_list = await asyncio.to_thread(parse_m3u, M3U_FILE_PATH)
    if not all_movies_in_list:
        log("Nenhum filme filtrado encontrado na lista M3U.", "red")
        return

    # Filtra filmes que já estão no log
    movies_to_download = [
        movie for movie in all_movies_in_list 
        if movie['full_title_with_lang'] not in downloaded_set
    ]
    
    total_to_download = len(movies_to_download)
    if total_to_download == 0:
        log("\nNenhum filme novo para baixar. Seu catálogo está em dia!", "green")
        return
    
    # Embaralha a lista (do seu script de download)
    random.shuffle(movies_to_download)
    log(f"\nLista de {total_to_download} filmes pendentes foi embaralhada.", "yellow")
    
    async with app:
        me = await app.get_me()
        log(f"✅ Logado como {me.first_name}", "green")
        log(f"📁 Pasta de trabalho: {DOWNLOAD_FOLDER}", "white")
        log(f"🚀 Iniciando processo em lotes de {BATCH_SIZE}...", "blue")

        # --- ESTE É O NOVO LOOP DE LOTE QUE VOCÊ DESCREVEU ---
        for i in range(0, total_to_download, BATCH_SIZE):
            # Pega um lote de filmes da lista
            batch_movies = movies_to_download[i:i + BATCH_SIZE]
            
            log(f"--- Processando Lote {i // BATCH_SIZE + 1} / {total_to_download // BATCH_SIZE + 1} (Tamanho: {BATCH_SIZE}) ---", "green")
            
            # --- LOOP MODIFICADO: Baixa 1, Envia 1 ---
            for movie in batch_movies:
                log(f"\n--- Processando: {movie['full_title_with_lang']} ---", "white")
                
                # Checa de novo caso o log tenha sido atualizado
                if movie['full_title_with_lang'] in await asyncio.to_thread(load_downloaded_log):
                    log(f"PULANDO (já no log): {movie['full_title_with_lang']}", "yellow")
                    continue
                
                # 1. FASE DE DOWNLOAD
                file_path = await asyncio.to_thread(download_movie_sync, movie)
                
                # 2. FASE DE UPLOAD (IMEDIATA)
                if file_path:
                    log(f"--- Iniciando Upload de '{movie['full_title_with_lang']}' ---", "blue")
                    caption = movie['full_title_with_lang']
                    
                    # Tenta fazer o upload
                    success = await upload_video(app, file_path, caption, cache, sem)
                    
                    if success:
                        log(f"Marcando '{caption}' como concluído no log.", "green")
                        await asyncio.to_thread(add_to_downloaded_log, caption)
                    else:
                        log(f"Upload de '{caption}' falhou. Ele NÃO será marcado no log...", "red")
                
                # Pausa aleatória (do seu downloader) entre cada FILME
                sleep_time = random.randint(2, 5)
                log(f"Pausa curta ({sleep_time}s) antes do próximo item do lote...", "yellow")
                await asyncio.sleep(sleep_time) 
            
            log(f"\n--- Fim do Lote {i // BATCH_SIZE + 1} ---", "green")
    
    log("\nVerificação concluída. Todos os lotes foram processados.", "green")

# ========================
# ENTRY POINT
# ========================
if __name__ == "__main__":
    if os.name == 'nt': # Necessário para asyncio no Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
