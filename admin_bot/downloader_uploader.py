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
MIN_UPLOAD_INTERVAL = 240   # 4 minutos
MAX_UPLOAD_INTERVAL = 480   # 8 minutos

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
    """
    Adiciona um filme ao histórico APÓS O UPLOAD.
    MODIFICADO: Se for 4K, adiciona a versão normal e a 4K.
    """
    try:
        # 1. Remove " 4K", " 4k", etc. de forma segura, mantendo o resto
        # (flags=re.IGNORECASE) ignora se é 4K ou 4k
        non_4k_title = re.sub(r'\s+4K\b', '', full_title_with_lang, flags=re.IGNORECASE).strip()
        # Limpa espaços duplos que a remoção pode ter deixado
        non_4k_title = re.sub(r'\s+', ' ', non_4k_title) 
        
        # 2. Usa um set para garantir que não haja duplicatas
        # Se o título não for 4K, o set terá apenas 1 item.
        # Se for 4K, terá 2 itens (o original e o non_4k_title).
        titles_to_log = {full_title_with_lang, non_4k_title}

        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            for title in titles_to_log:
                f.write(title + '\n')
        
        if len(titles_to_log) > 1:
            log(f"Adicionadas versões (4K e normal) ao log: '{non_4k_title}'", "green")
        else:
            log(f"Adicionado ao log: '{full_title_with_lang}'", "green")

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

def limpar_arquivos_temporarios(pasta_download, log_func=log):
    """
    Procura e remove arquivos temporários de downloads falhados (.part, .ytdl)
    em um diretório específico.
    Usa a função de log do script.
    """
    log_func("--- 🛡️ Iniciando Sistema de Segurança (Limpeza de .part) ---", "yellow")
    
    # Lista de padrões de arquivos temporários para remover
    padroes_para_limpar = ["*.part", "*.ytdl", "*.mp4"]
    arquivos_removidos = 0

    for padrao in padroes_para_limpar:
        # Cria o caminho completo do padrão (ex: /pasta/de/downloads/*.part)
        caminho_padrao = os.path.join(pasta_download, padrao)
        
        try:
            # glob.glob encontra todos os arquivos que correspondem ao padrão
            arquivos_temporarios = glob.glob(caminho_padrao)
        except Exception as e:
            log_func(f"Erro ao buscar arquivos com padrão '{padrao}': {e}", "red")
            continue
        
        if not arquivos_temporarios:
            log_func(f"Nenhum arquivo '{padrao}' encontrado.", "blue")
            continue

        for arquivo in arquivos_temporarios:
            try:
                os.remove(arquivo)
                log_func(f"🧹 Arquivo temporário removido: {arquivo}", "yellow")
                arquivos_removidos += 1
            except OSError as e:
                log_func(f"⚠️ Erro ao tentar remover {arquivo}: {e}", "red")

    if arquivos_removidos > 0:
        log_func(f"--- ✅ Limpeza Concluída: {arquivos_removidos} arquivos removidos ---", "green")
    else:
        log_func("--- 🛡️ Fim da Limpeza (Nada a fazer) ---", "blue")

# =================================================================
# BLOCO DE PROCESSAMENTO DE VÍDEO (do Uploader)
# =================================================================

def get_video_metadata_hachoir(file_path):
    """
    Extrai metadados usando Hachoir (pure Python),
    ideal para ambientes restritos como o Square Cloud.
    VERSÃO 2.1 - Corrigido o TypeError
    """
    log(f"Tentando extrair metadados com Hachoir (v2.1)...", "blue")
    duration, width, height = 0, 0, 0
    try:
        # Hachoir precisa do 'real path'
        real_path = os.path.realpath(file_path)
        
        # --- CORREÇÃO ---
        # Removemos o FileInputStream e passamos o caminho direto.
        # O createParser abre o arquivo sozinho.
        parser = createParser(real_path) 
        # --- FIM DA CORREÇÃO ---
        
        if not parser:
            log(f"Hachoir: Não foi possível criar o parser.", "red")
            return None, None, None

        # Usamos 'with parser' para garantir que ele feche o arquivo
        with parser: 
            metadata = extractMetadata(parser)
        
        if not metadata:
            log(f"Hachoir: Não foi possível extrair metadados.", "red")
            return None, None, None

        # Extrai os dados
        if metadata.has("duration"):
            # Hachoir retorna timedelta, precisamos de segundos
            duration = int(metadata.get("duration").total_seconds())
        if metadata.has("width"):
            width = metadata.get("width")
        if metadata.has("height"):
            height = metadata.get("height")
        
        if duration == 0 or width == 0:
            log(f"Hachoir: Metadados incompletos (d={duration}, w={width}).", "yellow")
            return None, None, None
        
        log(f"Metadados extraídos (Hachoir): {width}x{height}, {duration}s", "green")
        return duration, width, height
        
    except Exception as e:
        log(f"Erro no Hachoir: {repr(e)}", "red")
        import traceback
        log(traceback.format_exc(), "yellow")
        return None, None, None
    
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
            '--max-filesize', '2900M',
            '--no-playlist', 
            '--retries', '20', 
            '--fragment-retries', '20',
            '--no-check-certificates', 
            '--socket-timeout', '120',         # <-- AUMENTADO
            '--http-chunk-size', '10M',      # <-- NOVO
            '--buffer-size', '16K',          # <-- NOVO (ajuda)
            '--no-keep-fragments',           # <-- NOVO (limpeza)
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
            
        # 👇 SEU SISTEMA DE SEGURANÇA ENTRA AQUI 👇
        limpar_arquivos_temporarios(DOWNLOAD_FOLDER, log_func=log)
        # 👆 FIM DA ALTERAÇÃO 👆

    except Exception as e:
        # Este bloco agora vai capturar o erro que estava em branco
        log(f"\n❌ ERRO INESPERADO (TIPO: {type(e)}) ao baixar '{full_title_with_lang}':", "red")
        log(f"   REPR DO ERRO: {repr(e)}", "red")
        import traceback
        log(traceback.format_exc(), "yellow") # Imprime o stack trace completo

        # 👇 SEU SISTEMA DE SEGURANÇA ENTRA AQUI TAMBÉM 👇
        limpar_arquivos_temporarios(DOWNLOAD_FOLDER, log_func=log)
        # 👆 FIM DA ALTERAÇÃO 👆
    
    # Se chegou aqui, falhou. Limpa o arquivo parcial.
    if file_path and os.path.exists(file_path):
        try:
            log(f"Limpando arquivo parcial: {file_path}", "yellow")
            os.remove(file_path)
        except Exception as e:
            log(f"Erro ao limpar arquivo parcial: {e}", "red")
            
    return None # Retorna None em caso de falha

def scan_download_folder():
    """
    NOVO: Verifica a pasta de download por arquivos .mp4 existentes
    e cria um mapa 'titulo' -> 'caminho_completo'.
    """
    log(f"Verificando pasta {DOWNLOAD_FOLDER} por arquivos existentes...", "blue")
    local_files = {}
    if not os.path.isdir(DOWNLOAD_FOLDER):
        log(f"Pasta de download '{DOWNLOAD_FOLDER}' não existe, será criada.", "yellow")
        return {}
    
    try:
        for file in os.listdir(DOWNLOAD_FOLDER):
            if file.endswith(".mp4"):
                # O nome do arquivo sem .mp4 é o 'full_title_with_lang'
                file_name_without_ext = os.path.splitext(file)[0]
                full_path = os.path.join(DOWNLOAD_FOLDER, file)
                local_files[file_name_without_ext] = full_path
    except Exception as e:
        log(f"Erro ao escanear a pasta de download: {e}", "red")
    
    return local_files

async def upload_video(app, full_path, caption_text, cache, sem):
    """
    Versão universal 2.0.
    Usa Hachoir para metadados (pure Python).
    Remove FFMPEG (thumbnails).
    Adiciona logging de erro detalhado.
    MODIFICADO: Removido o sleep; agora ele só retorna True.
    """
    async with sem:
        try:
            file_size_mb = os.path.getsize(full_path) / (1024**2)
            MAX_FILE_SIZE_MB = 2900
            
            if file_size_mb > MAX_FILE_SIZE_MB:
                log(f"⚠️  Arquivo muito grande ({file_size_mb:.0f}MB > {MAX_FILE_SIZE_MB}MB): {caption_text}", "yellow")
                log(f"   Deletando arquivo...", "yellow")
                os.remove(full_path)
                return False

            # --- LÓGICA DE METADADOS 2.0 (USA HACHOIR) ---
            duration, width, height = 0, 0, 0
            try:
                if full_path in cache:
                    duration, width, height = cache[full_path].values()
                    log(f"Metadados cacheados: {duration}s, {width}x{height}", "yellow")
                else:
                    duration, width, height = await asyncio.to_thread(get_video_metadata_hachoir, full_path)
                    if not duration:
                        duration, width, height = 0, 0, 0
                    
                    cache[full_path] = {"duration": duration, "width": width, "height": height}
                    await asyncio.to_thread(save_cache, cache)
            
            except Exception as e:
                log(f"AVISO: Falha ao obter metadados com Hachoir: {e}", "yellow")
                duration, width, height = 0, 0, 0
            # --- FIM DA LÓGICA 2.0 ---

            backoff = 5
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    log(f"🔄 Enviando {caption_text}...", "blue")
                    
                    send_kwargs = {
                        "chat_id": STORAGE_CHANNEL_ID,
                        "video": full_path,
                        "caption": caption_text,
                        "progress": progress_callback
                    }
                    
                    if duration > 0 and width > 0:
                        log(f"Enviando com metadados (Hachoir): {duration}s, {width}x{height}", "blue")
                        send_kwargs["duration"] = duration
                        send_kwargs["width"] = width
                        send_kwargs["height"] = height
                    else:
                        log(f"Enviando SEM metadados (Hachoir falhou ou metadados incompletos)", "yellow")

                    await app.send_video(**send_kwargs)
                    
                    log(f"\n✅ Upload concluído: {caption_text}", "green")
                    os.remove(full_path)
                    
                    # --- LÓGICA DE ESPERA REMOVIDA DAQUI ---
                    
                    return True
                        
                except FloodWait as e:
                    log(f"\n⚠️ FloodWait: Telegram pediu para esperar {e.value}s", "yellow")
                    await asyncio.sleep(e.value + random.uniform(5, 15))
                    retry_count += 1
                
                except (OSError, ConnectionError) as e:
                    retry_count += 1
                    log(f"\n🔌 ERRO DE REDE (Tentativa {retry_count}/{max_retries}):", "red")
                    log(f"   TIPO: {type(e)}", "red")
                    log(f"   ERRO: {repr(e)}", "red") 
                    if retry_count < max_retries:
                        log(f"Reconectando em {backoff}s...", "yellow")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                    else:
                        log(f"❌ Falha após {max_retries} tentativas", "red")
                        break
                
                except Exception as e:
                    retry_count += 1
                    log(f"\n❌ ERRO INESPERADO NO UPLOAD (Tentativa {retry_count}/{max_retries}):", "red")
                    log(f"   TIPO: {type(e)}", "red")
                    log(f"   ERRO: {repr(e)}", "red") 
                    import traceback
                    log(traceback.format_exc(), "yellow") 
                    
                    if retry_count < max_retries:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 120)
                    else:
                        log(f"❌ Falha após {max_retries} tentativas", "red")
                        break
            
            return False # Se saiu do loop, o upload falhou

        except Exception as e:
            log(f"Erro inesperado (fora do loop de retry): {e}", "red")
            return False
        
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

    app = Client(
        SESSION_NAME,
        session_string=SESSION_STRING,
        api_id=API_ID,
        api_hash=API_HASH,
        workers=WORKER_COUNT
    )

    # --- 🛡️ LIMPEZA DE STARTUP 🛡️ ---
    # (Adicionado conforme sua solicitação)
    log("Garantindo que a pasta de download existe...", "blue")
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    log("Verificando pasta de download por arquivos .part órfãos...", "yellow")
    # Usamos to_thread para rodar a função síncrona (que usa os.remove)
    # sem bloquear o loop de eventos do asyncio.
    await asyncio.to_thread(limpar_arquivos_temporarios, DOWNLOAD_FOLDER, log_func=log)
    log("Verificação de limpeza no startup concluída.", "green")
    # --- FIM DA LIMPEZA DE STARTUP ---

    cache = await asyncio.to_thread(load_cache)
    downloaded_set = await asyncio.to_thread(load_downloaded_log)
    local_files_map = await asyncio.to_thread(scan_download_folder)
    if local_files_map:
        log(f"Encontrados {len(local_files_map)} arquivos .mp4 locais que serão priorizados para upload.", "green")

    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    sem = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

    all_movies_in_list = await asyncio.to_thread(parse_m3u, M3U_FILE_PATH)
    if not all_movies_in_list:
        log("Nenhum filme filtrado encontrado na lista M3U.", "red")
        return

    movies_to_process = [
        movie for movie in all_movies_in_list 
        if movie['full_title_with_lang'] not in downloaded_set
    ]
    
    total_to_process = len(movies_to_process)
    if total_to_process == 0:
        log("\nNenhum filme novo para processar. Seu catálogo está em dia!", "green")
        return
    
    random.shuffle(movies_to_process)
    log(f"\nLista de {total_to_process} filmes pendentes foi embaralhada.", "yellow")
    
    async with app:
        me = await app.get_me()
        log(f"✅ Logado como {me.first_name}", "green")
        
        # ... (O bloco que lista os chats e verifica o canal continua igual) ...
        log("=======================================================", "yellow")
        log("Listando os primeiros 100 chats que esta SESSION_STRING conhece:", "yellow")
        try:
            i = 0
            async for dialog in app.get_dialogs(limit=100):
                log(f"   > Título: {dialog.chat.title} | ID: {dialog.chat.id}", "white")
                i += 1
            log(f"Total de {i} chats encontrados (limitado a 100).", "yellow")
        except Exception as e:
            log(f"Erro ao tentar listar os chats: {e}", "red")
        log("=======================================================", "yellow")
        log(f"Verificando (priming) o canal de storage {STORAGE_CHANNEL_ID}...", "blue")
        try:
            await app.get_chat(STORAGE_CHANNEL_ID)
            log("Canal de storage verificado com sucesso.", "green")
        except Exception as e:
            log(f"❌ ERRO CRÍTICO: Não foi possível acessar o canal {STORAGE_CHANNEL_ID}.", "red")
            log(f"   Verifique se o ID está correto no config.py.", "red")
            log(f"   Verifique se a conta '{me.first_name}' é um MEMBRO deste canal/grupo.", "red")
            log(f"   Erro: {e}", "red")
            sys.exit(1)
        # ... (Fim do bloco de verificação) ...
            
        log(f"📁 Pasta de trabalho: {DOWNLOAD_FOLDER}", "white")
        log(f"🚀 Iniciando processo em lotes de {BATCH_SIZE}...", "blue")

        for i in range(0, total_to_process, BATCH_SIZE):
            batch_movies = movies_to_process[i:i + BATCH_SIZE]
            
            log(f"--- Processando Lote {i // BATCH_SIZE + 1} / {total_to_process // BATCH_SIZE + 1} (Tamanho: {BATCH_SIZE}) ---", "green")
            
            for movie in batch_movies:
                title = movie['full_title_with_lang']
                
                caption = re.sub(r'\s+4K\b', '', title, flags=re.IGNORECASE).strip()
                caption = re.sub(r'\s+', ' ', caption) 
                
                log(f"\n--- Processando: {title} ---", "white")
                if title != caption:
                    log(f"--- (Caption do Telegram será: {caption}) ---", "yellow")
                
                current_log = await asyncio.to_thread(load_downloaded_log)
                if title in current_log:
                    log(f"PULANDO (já no log): {title}", "yellow")
                    continue
                
                file_path = None
                
                file_path = local_files_map.get(title) 
                
                if file_path and os.path.exists(file_path):
                    log(f"Arquivo encontrado localmente. Pulando download.", "green")
                    log(f"   -> {file_path}", "green")
                else:
                    if file_path:
                        log(f"Arquivo estava no map, mas não existe mais. Baixando...", "yellow")
                    
                    log(f"Arquivo não encontrado localmente. Iniciando download...", "blue")
                    file_path = await asyncio.to_thread(download_movie_sync, movie)
                
                
                # --- LÓGICA DE PAUSA MOVIDA PARA CÁ ---
                upload_succeeded = False # Flag
                
                if file_path:
                    log(f"--- Iniciando Upload de '{caption}' ---", "blue")
                    
                    # 1. Upload (função não dorme mais)
                    success = await upload_video(app, file_path, caption, cache, sem)
                    
                    if success:
                        upload_succeeded = True # Seta a flag
                        
                        # 2. Log (IMEDIATO)
                        await asyncio.to_thread(add_to_downloaded_log, title)
                        
                        # 3. SLEEP (Agora está no main)
                        wait_time = random.uniform(MIN_UPLOAD_INTERVAL, MAX_UPLOAD_INTERVAL)
                        minutes = wait_time / 60
                        log(f"⏱️  Aguardando {minutes:.1f} minutos até próximo upload...", "yellow")
                        await asyncio.sleep(wait_time)
                        
                    else:
                        log(f"Upload de '{caption}' falhou. O arquivo será mantido para a próxima vez.", "red")
                        local_files_map[title] = file_path
                else:
                    log(f"Download de '{caption}' falhou. Pulando para o próximo.", "red")
                
                # Só faz a pausa CURTA se o upload NÃO aconteceu (falha no down/up)
                if not upload_succeeded:
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
