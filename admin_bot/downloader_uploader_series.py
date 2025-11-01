#
# NOME DO ARQUIVO: downloader_uploader_series.py
#
import re
import os
import time
import subprocess
import sys
import random
import json
import asyncio
import glob
from pyrogram import Client
from pyrogram.errors import FloodWait
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

# --- CONFIGURAÇÃO INICIAL ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from config import (
        M3U_FILE_PATH, DOWNLOAD_FOLDER, REFERER_URL, USER_AGENT, 
        PROXY_URL, API_ID, API_HASH, SESSION_STRING,
        # --- MUDANÇA AQUI: Carregando as novas configs ---
        STORAGE_CHANNEL_ID_SERIES, LOG_FILE_SERIES
    )
except ImportError:
    print("ERRO: Não foi possível encontrar o 'config.py'.")
    print("Certifique-se que 'config.py' contém as novas variáveis:")
    print("STORAGE_CHANNEL_ID_SERIES e LOG_FILE_SERIES")
    sys.exit(1)

# --- CONFIGURAÇÕES DO SCRIPT ---
BATCH_SIZE = 2
SESSION_NAME = "minha_conta_de_upload"
WORKER_COUNT = 16
MAX_CONCURRENT_UPLOADS = 1
MIN_UPLOAD_INTERVAL = 240   # 4 minutos
MAX_UPLOAD_INTERVAL = 480   # 8 minutos

# Caminhos (sem mudança)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFPROBE_PATH = os.path.join(BASE_DIR, "ffprobe.exe")
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")
THUMBNAIL_PATH = os.path.join(DOWNLOAD_FOLDER, "thumb.jpg")
CACHE_FILE = os.path.join(BASE_DIR, "metadata_cache.json")

# =================================================================
# FUNÇÃO DE LOG (Sem mudança)
# =================================================================
def log(msg, color="white"):
    colors = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m", "blue": "\033[94m", "white": "\033[0m"}
    print(colors.get(color, "\033[0m") + str(msg) + "\033[0m")

# =================================================================
# FUNÇÕES AUXILIARES (Pequenas mudanças)
# =================================================================

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def load_cache(): # (Sem mudança)
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache): # (Sem mudança)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def load_downloaded_log():
    """ --- MUDANÇA AQUI: Lendo o log de séries --- """
    if not os.path.exists(LOG_FILE_SERIES):
        return set()
    try:
        with open(LOG_FILE_SERIES, 'r', encoding='utf-8') as f:
            downloaded = {line.strip() for line in f}
            log(f"Carregados {len(downloaded)} registros do histórico de SÉRIES.", "blue")
            return downloaded
    except Exception as e:
        log(f"Erro ao carregar o log '{LOG_FILE_SERIES}': {e}. Começando com um histórico vazio.", "red")
        return set()

def add_to_downloaded_log(full_title_for_log: str):
    """ --- MUDANÇA AQUI: Escrevendo no log de séries --- """
    try:
        with open(LOG_FILE_SERIES, 'a', encoding='utf-8') as f:
            f.write(full_title_for_log + '\n')
        log(f"Adicionado ao log de séries: '{full_title_for_log}'", "green")
    except Exception as e:
        log(f"Erro ao salvar no log '{LOG_FILE_SERIES}': {e}", "red")

#
# =================================================================
# 🎯 O NOVO CÉREBRO: O PARSER DE SÉRIES 🎯
# =================================================================
#
def parse_m3u_series(file_path: str) -> list[dict]:
    """
    Lê o M3U e extrai informações de SÉRIES.
    Usa Regex para SXX EXX e assume [DUB].
    """
    log(f"Lendo e filtrando SÉRIES do arquivo: {file_path}\n", "blue")
    
    # Regex para extrair: (Grupo 1: Título) S(Grupo 2: Temporada) E(Grupo 3: Episódio)
    # Ex: "Bob Esponja (1999-2010) S03 E16"
    SERIES_REGEX = re.compile(r"(.*?) S(\d+) E(\d+)", re.IGNORECASE)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        log(f"ERRO: Arquivo M3U não encontrado em: {file_path}", "red")
        return []
    except Exception as e:
        log(f"Erro ao ler o arquivo M3U: {e}", "red")
        return []

    episodes = []
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            try:
                # 1. Filtro de Grupo: Só queremos o que começa com "SERIES |"
                group_match = re.search(r'group-title="([^"]+)"', line, re.IGNORECASE)
                if not group_match or not group_match.group(1).startswith("SERIES |"):
                    continue # Pula (ex: "FILMES", "CANAIS")

                # 2. Extração do Título: Pega o "tvg-name"
                title_match = re.search(r'tvg-name="([^"]+)"', line)
                if not title_match:
                    continue
                
                original_title = title_match.group(1).strip()
                url = lines[i+1].strip()
                
                # 3. Aplicação do Regex
                match = SERIES_REGEX.search(original_title)
                if not match:
                    log(f"PULANDO (Formato SXX EXX não encontrado): {original_title}", "yellow")
                    continue
                    
                # 4. Coleta dos Dados
                series_title = match.group(1).strip() # Ex: "Bob Esponja (1999-2010)"
                season_number = int(match.group(2))   # Ex: 3
                episode_number = int(match.group(3))  # Ex: 16
                audio_type = "DUB"                    # Nossa Assunção!
                
                # 5. Formatação Padrão (VITAL para o Bot Indexador)
                # Usamos :02d para formatar '1' como '01'
                standard_name = f"{series_title} S{season_number:02d} E{episode_number:02d} [{audio_type}]"
                
                episodes.append({
                    'series_title': series_title,
                    'season_number': season_number,
                    'episode_number': episode_number,
                    'audio_type': audio_type,
                    'full_title_for_log': standard_name, # Para o log (ex: "Serie S01 E01 [DUB]")
                    'caption_filename': standard_name,   # Para o nome do arquivo e caption
                    'url': url
                })
            except Exception as e:
                log(f"Pequeno erro ao processar a linha: {line}. Detalhes: {e}", "yellow")
    
    log(f"Encontrados {len(episodes)} episódios de séries que batem com os critérios.", "green")
    return episodes

# =================================================================
# BLOCO DE PROCESSAMENTO DE VÍDEO (Sem mudança)
# =================================================================
# (As funções get_video_metadata_hachoir e progress_callback 
# são idênticas às do downloader_uploader.py)

def get_video_metadata_hachoir(file_path):
    log(f"Tentando extrair metadados com Hachoir...", "blue")
    duration, width, height = 0, 0, 0
    try:
        real_path = os.path.realpath(file_path)
        parser = createParser(real_path) 
        if not parser:
            log(f"Hachoir: Não foi possível criar o parser.", "red")
            return None, None, None
        with parser: 
            metadata = extractMetadata(parser)
        if not metadata:
            log(f"Hachoir: Não foi possível extrair metadados.", "red")
            return None, None, None
        if metadata.has("duration"):
            duration = int(metadata.get("duration").total_seconds())
        if metadata.has("width"):
            width = metadata.get("width")
        if metadata.has("height"):
            height = metadata.get("height")
        if duration == 0 or width == 0:
            log(f"Hachoir: Metadados incompletos.", "yellow")
            return None, None, None
        log(f"Metadados extraídos (Hachoir): {width}x{height}, {duration}s", "green")
        return duration, width, height
    except Exception as e:
        log(f"Erro no Hachoir: {repr(e)}", "red")
        return None, None, None
    
def progress_callback(current, total):
    print(f"Progresso: {(current / total) * 100:.2f}%", end="\r")

# =================================================================
# FUNÇÕES PRINCIPAIS (DOWNLOADER E UPLOADER REFATORADOS)
# =================================================================

def download_episode_sync(episode_info: dict) -> str:
    """
    Baixa um único episódio usando yt-dlp (SÍNCRONO).
    """
    caption_filename = episode_info['caption_filename']
    url = episode_info['url']
    
    log(f"\n+++ Iniciando download de: '{caption_filename}' via yt-dlp +++", "blue")
    file_path = ""
    try:
        # --- MUDANÇA AQUI: O nome do arquivo JÁ VEM PADRONIZADO ---
        safe_filename = sanitize_filename(caption_filename) + ".mp4"
        file_path = os.path.join(DOWNLOAD_FOLDER, safe_filename)
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        command = [
            sys.executable, '-m', 'yt_dlp',
            '--output', file_path,
            '--no-playlist', 
            '--retries', '20', 
            '--fragment-retries', '20',
            '--no-check-certificates', 
            '--socket-timeout', '120',
            '--http-chunk-size', '10M',
            '--buffer-size', '16K',
            '--no-keep-fragments',
            '--user-agent', USER_AGENT,
            '--add-header', f'Referer: {REFERER_URL}',
            '--add-header', f'Origin: {REFERER_URL}',
        ]
        if PROXY_URL:
            log("+++ Usando Proxy para esta requisição +++", "yellow")
            command.extend(['--proxy', PROXY_URL])
            
        command.append(url)
        
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        log(f"\n✅ Download de '{caption_filename}' concluído com sucesso!", "green")
        return file_path # Retorna o caminho do arquivo para o upload

    except subprocess.CalledProcessError as e:
        log(f"\n❌ ERRO DO YT-DLP ao baixar '{caption_filename}': {e.returncode}", "red")
        log(f"Saída do erro: {e.stderr}", "red")
        limpar_arquivos_temporarios(DOWNLOAD_FOLDER, log_func=log) # Sistema de segurança
    except Exception as e:
        log(f"\n❌ ERRO INESPERADO (TIPO: {type(e)}) ao baixar '{caption_filename}':", "red")
        log(f"   REPR DO ERRO: {repr(e)}", "red")
        limpar_arquivos_temporarios(DOWNLOAD_FOLDER, log_func=log) # Sistema de segurança
    
    # Se chegou aqui, falhou. Limpa o arquivo parcial.
    if file_path and os.path.exists(file_path):
        try:
            log(f"Limpando arquivo parcial: {file_path}", "yellow")
            os.remove(file_path)
        except Exception as e:
            log(f"Erro ao limpar arquivo parcial: {e}", "red")
            
    return None # Retorna None em caso de falha

def scan_download_folder(): # (Sem mudança)
    log(f"Verificando pasta {DOWNLOAD_FOLDER} por arquivos existentes...", "blue")
    local_files = {}
    if not os.path.isdir(DOWNLOAD_FOLDER):
        log(f"Pasta de download '{DOWNLOAD_FOLDER}' não existe, será criada.", "yellow")
        return {}
    try:
        for file in os.listdir(DOWNLOAD_FOLDER):
            if file.endswith(".mp4"):
                file_name_without_ext = os.path.splitext(file)[0]
                full_path = os.path.join(DOWNLOAD_FOLDER, file)
                local_files[file_name_without_ext] = full_path
    except Exception as e:
        log(f"Erro ao escanear a pasta de download: {e}", "red")
    return local_files

async def upload_video(app, full_path, caption_text, cache, sem):
    """
    (Esta função é idêntica à do downloader_uploader.py)
    """
    async with sem:
        try:
            file_size_mb = os.path.getsize(full_path) / (1024**2)
            MAX_FILE_SIZE_MB = 2900
            
            if file_size_mb > MAX_FILE_SIZE_MB:
                log(f"⚠️  Arquivo muito grande ({file_size_mb:.0f}MB): {caption_text}", "yellow")
                os.remove(full_path)
                return False

            duration, width, height = 0, 0, 0
            try:
                if full_path in cache:
                    duration, width, height = cache[full_path].values()
                else:
                    duration, width, height = await asyncio.to_thread(get_video_metadata_hachoir, full_path)
                    if not duration: duration, width, height = 0, 0, 0
                    cache[full_path] = {"duration": duration, "width": width, "height": height}
                    await asyncio.to_thread(save_cache, cache)
            except Exception as e:
                log(f"AVISO: Falha ao obter metadados com Hachoir: {e}", "yellow")
                duration, width, height = 0, 0, 0

            backoff = 5
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    log(f"🔄 Enviando {caption_text}...", "blue")
                    
                    send_kwargs = {
                        # --- MUDANÇA AQUI: Enviando para o canal de SÉRIES ---
                        "chat_id": STORAGE_CHANNEL_ID_SERIES, 
                        "video": full_path,
                        "caption": caption_text,
                        "progress": progress_callback
                    }
                    
                    if duration > 0 and width > 0:
                        send_kwargs["duration"] = duration
                        send_kwargs["width"] = width
                        send_kwargs["height"] = height
                    
                    await app.send_video(**send_kwargs)
                    
                    log(f"\n✅ Upload concluído: {caption_text}", "green")
                    os.remove(full_path)
                    return True
                        
                except FloodWait as e:
                    log(f"\n⚠️ FloodWait: Esperando {e.value}s", "yellow")
                    await asyncio.sleep(e.value + random.uniform(5, 15))
                    retry_count += 1
                
                except (OSError, ConnectionError) as e:
                    retry_count += 1
                    log(f"\n🔌 ERRO DE REDE (Tentativa {retry_count}/{max_retries}): {repr(e)}", "red")
                    if retry_count < max_retries:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                    else:
                        break
                
                except Exception as e:
                    retry_count += 1
                    log(f"\n❌ ERRO INESPERADO NO UPLOAD (Tentativa {retry_count}/{max_retries}):", "red")
                    log(f"   TIPO: {type(e)}", "red") 
                    if retry_count < max_retries:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 120)
                    else:
                        break
            return False 
        except Exception as e:
            log(f"Erro inesperado (fora do loop de retry): {e}", "red")
            return False

# Função de limpeza (será usada no downloader_episode_sync)
def limpar_arquivos_temporarios(pasta_download, log_func=log):
    log_func("--- 🛡️ Limpeza de .part ---", "yellow")
    padroes_para_limpar = ["*.part", "*.ytdl", "*.mp4"]
    arquivos_removidos = 0
    for padrao in padroes_para_limpar:
        caminho_padrao = os.path.join(pasta_download, padrao)
        try:
            arquivos_temporarios = glob.glob(caminho_padrao)
        except Exception as e:
            log_func(f"Erro ao buscar arquivos '{padrao}': {e}", "red")
            continue
        for arquivo in arquivos_temporarios:
            try:
                os.remove(arquivo)
                log_func(f"🧹 Arquivo temporário removido: {arquivo}", "yellow")
                arquivos_removidos += 1
            except OSError as e:
                log_func(f"⚠️ Erro ao tentar remover {arquivo}: {e}", "red")
    if arquivos_removidos > 0:
        log_func(f"--- ✅ Limpeza Concluída: {arquivos_removidos} arquivos ---", "green")
    else:
        log_func("--- 🛡️ Fim da Limpeza (Nada a fazer) ---", "blue")

# =================================================================
# FUNÇÃO PRINCIPAL (O ORQUESTRADOR)
# =================================================================

async def main():
    log("Iniciando cliente Pyrogram...", "blue")
    if not SESSION_STRING:
        log("ERRO: PYROGRAM_SESSION_STRING não definida.", "red")
        sys.exit(1)

    app = Client(
        SESSION_NAME,
        session_string=SESSION_STRING,
        api_id=API_ID,
        api_hash=API_HASH,
        workers=WORKER_COUNT
    )

    # Limpeza de Startup
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    await asyncio.to_thread(limpar_arquivos_temporarios, DOWNLOAD_FOLDER, log_func=log)
    
    cache = await asyncio.to_thread(load_cache)
    
    # --- MUDANÇA AQUI: Carregando log e parser de SÉRIES ---
    downloaded_set = await asyncio.to_thread(load_downloaded_log)
    local_files_map = await asyncio.to_thread(scan_download_folder)
    
    sem = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

    all_episodes_in_list = await asyncio.to_thread(parse_m3u_series, M3U_FILE_PATH)
    # --- FIM DA MUDANÇA ---
    
    if not all_episodes_in_list:
        log("Nenhum EPISÓDIO DE SÉRIE encontrado na lista M3U.", "red")
        return

    episodes_to_process = [
        episode for episode in all_episodes_in_list 
        if episode['full_title_for_log'] not in downloaded_set
    ]
    
    total_to_process = len(episodes_to_process)
    if total_to_process == 0:
        log("\nNenhum episódio novo para processar. Catálogo de séries em dia!", "green")
        return
    
    random.shuffle(episodes_to_process)
    log(f"\nLista de {total_to_process} episódios pendentes foi embaralhada.", "yellow")
    
    async with app:
        me = await app.get_me()
        log(f"✅ Logado como {me.first_name}", "green")
        
        # --- MUDANÇA AQUI: Verificando o canal de SÉRIES ---
        log(f"Verificando o canal de storage de SÉRIES {STORAGE_CHANNEL_ID_SERIES}...", "blue")
        try:
            await app.get_chat(STORAGE_CHANNEL_ID_SERIES)
            log("Canal de SÉRIES verificado com sucesso.", "green")
        except Exception as e:
            log(f"❌ ERRO CRÍTICO: Não foi possível acessar o canal {STORAGE_CHANNEL_ID_SERIES}.", "red")
            sys.exit(1)
            
        log(f"📁 Pasta de trabalho: {DOWNLOAD_FOLDER}", "white")
        log(f"🚀 Iniciando processo de SÉRIES em lotes de {BATCH_SIZE}...", "blue")

        for i in range(0, total_to_process, BATCH_SIZE):
            batch_episodes = episodes_to_process[i:i + BATCH_SIZE]
            
            log(f"--- Processando Lote de Séries {i // BATCH_SIZE + 1} / {total_to_process // BATCH_SIZE + 1} ---", "green")
            
            for episode in batch_episodes:
                title_for_log = episode['full_title_for_log']
                caption = episode['caption_filename'] # Nossos nomes padronizados
                
                log(f"\n--- Processando: {caption} ---", "white")
                
                current_log = await asyncio.to_thread(load_downloaded_log)
                if title_for_log in current_log:
                    log(f"PULANDO (já no log): {caption}", "yellow")
                    continue
                
                file_path = local_files_map.get(caption) 
                
                if file_path and os.path.exists(file_path):
                    log(f"Episódio encontrado localmente. Pulando download.", "green")
                else:
                    log(f"Episódio não encontrado. Iniciando download...", "blue")
                    file_path = await asyncio.to_thread(download_episode_sync, episode)
                
                
                upload_succeeded = False
                
                if file_path:
                    log(f"--- Iniciando Upload de '{caption}' ---", "blue")
                    
                    success = await upload_video(app, file_path, caption, cache, sem)
                    
                    if success:
                        upload_succeeded = True
                        await asyncio.to_thread(add_to_downloaded_log, title_for_log)
                        wait_time = random.uniform(MIN_UPLOAD_INTERVAL, MAX_UPLOAD_INTERVAL)
                        log(f"⏱️  Aguardando {wait_time/60:.1f} minutos até próximo upload...", "yellow")
                        await asyncio.sleep(wait_time)
                    else:
                        log(f"Upload de '{caption}' falhou. Será mantido para a próxima vez.", "red")
                        local_files_map[title_for_log] = file_path
                else:
                    log(f"Download de '{caption}' falhou. Pulando.", "red")
                
                if not upload_succeeded:
                    sleep_time = random.randint(2, 5)
                    log(f"Pausa curta ({sleep_time}s) antes do próximo item...", "yellow")
                    await asyncio.sleep(sleep_time) 
            
            log(f"\n--- Fim do Lote de Séries {i // BATCH_SIZE + 1} ---", "green")
    
    log("\nVerificação de séries concluída. Todos os lotes foram processados.", "green")

# ========================
# ENTRY POINT
# ========================
if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
    