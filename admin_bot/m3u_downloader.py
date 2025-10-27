import re
import os
import time
import subprocess
import sys
import random

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from config import M3U_FILE_PATH, DOWNLOAD_FOLDER, LOG_FILE, REFERER_URL, USER_AGENT, PROXY_URL
except ImportError:
    print("ERRO: Não foi possível encontrar o arquivo 'config_downloader.py'.")
    print("Por favor, crie o arquivo com as variáveis M3U_FILE_PATH, DOWNLOAD_FOLDER, etc.")
    sys.exit(1) # Para o script se a configuração não existir

# Cabeçalho para simular um navegador Chrome.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
# --- FIM DAS CONFIGURAÇÕES ---

def sanitize_filename(filename):
    """Remove caracteres inválidos de nomes de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def load_downloaded_log():
    """Carrega a lista de filmes já baixados."""
    if not os.path.exists(LOG_FILE):
        return set()
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            downloaded = {line.strip() for line in f}
            print(f"Carregados {len(downloaded)} registros do histórico de downloads.")
            return downloaded
    except Exception as e:
        print(f"Erro ao carregar o log '{LOG_FILE}': {e}. Começando com um histórico vazio.")
        return set()

def add_to_downloaded_log(full_title_with_lang: str):
    """Adiciona um filme ao histórico após o download."""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(full_title_with_lang + '\n')
    except Exception as e:
        print(f"Erro ao salvar no log '{LOG_FILE}': {e}")

def parse_m3u(file_path: str):
    """Lê um M3U e extrai informações dos filmes."""
    print(f"Lendo e aplicando filtros ao arquivo: {file_path}\n")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"ERRO: Arquivo M3U não encontrado em: {file_path}")
        print("Verifique se o nome/caminho está correto no seu arquivo 'config_downloader.py'.")
        return []
    except Exception as e:
        print(f"Erro ao ler o arquivo M3U: {e}")
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
                print(f"Pequeno erro ao processar a linha: {line}. Detalhes: {e}")
    
    print(f"Encontrados {len(movies)} filmes que batem com os critérios.")
    return movies

def download_movie(movie_info: dict):
    """Baixa um único filme usando yt-dlp com os headers corretos."""
    full_title_with_lang = movie_info['full_title_with_lang']
    url = movie_info['url']
    
    print(f"\n+++ Iniciando download de: '{full_title_with_lang}' via yt-dlp +++")
    file_path = ""
    try:
        safe_filename = sanitize_filename(full_title_with_lang) + ".mp4"
        file_path = os.path.join(DOWNLOAD_FOLDER, safe_filename)
        
        # Garante que a pasta de download exista (baseado no config)
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
            print("+++ Usando Proxy para esta requisição +++")
            command.extend(['--proxy', PROXY_URL])
        # --- FIM DA MUDANÇA ---
            
        command.append(url)
        
        subprocess.run(command, check=True)

        print(f"\n✅ Download de '{full_title_with_lang}' concluído com sucesso!")
        add_to_downloaded_log(full_title_with_lang)

    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERRO DO YT-DLP ao baixar '{full_title_with_lang}': O comando falhou com o código {e.returncode}")
        if e.stderr:
            try:
                print(f"Saída do erro: {e.stderr.decode('utf-8')}")
            except:
                 print(f"Saída do erro (não decodificado): {e.stderr}")
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO ao baixar '{full_title_with_lang}': {e}")
    finally:
        if file_path and os.path.exists(file_path):
            if full_title_with_lang not in load_downloaded_log():
                try:
                    print(f"Limpando arquivo parcial: {file_path}")
                    os.remove(file_path)
                except Exception as e:
                    print(f"Erro ao limpar arquivo parcial: {e}")


def main():
    """Função principal que orquestra o processo de download."""
    
    print("--- Configurações Carregadas ---")
    print(f"Pasta de Download: {DOWNLOAD_FOLDER}")
    print(f"Arquivo M3U: {M3U_FILE_PATH}")
    print(f"Arquivo de Log: {LOG_FILE}")
    print("---------------------------------")
    
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    downloaded_set = load_downloaded_log()
    all_movies_in_list = parse_m3u(M3U_FILE_PATH)
    if not all_movies_in_list:
        print("Nenhum filme filtrado encontrado na lista M3U.")
        return

    movies_to_download = [
        movie for movie in all_movies_in_list 
        if movie['full_title_with_lang'] not in downloaded_set
    ]
    
    total_to_download = len(movies_to_download)
    if total_to_download == 0:
        print("\nNenhum filme novo para baixar. Seu catálogo está em dia!")
        return
        
    random.shuffle(movies_to_download)
    print(f"\nLista de {total_to_download} filmes pendentes foi embaralhada.")

    print(f"Iniciando o download de {total_to_download} novos filmes (em ordem aleatória)...")
    for i, movie in enumerate(movies_to_download):
        print(f"\n--- Processando {i+1} de {total_to_download} ---")
        download_movie(movie)
        
        sleep_time = random.randint(2, 5)
        print(f"Pausando por {sleep_time} segundos...")
        time.sleep(sleep_time) 
        
    print("\nVerificação concluída. Todos os filmes novos foram baixados.")
    
if __name__ == "__main__":
    main()