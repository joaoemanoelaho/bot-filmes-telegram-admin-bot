import requests
import re
import os
import time
import subprocess
import sys
import random

# --- CONFIGURAÇÕES PRINCIPAIS ---
# Coloque o caminho completo para o seu arquivo M3U
M3U_FILE_PATH = "C:\\Users\\filme\\Downloads\\tv_channels_20efbmf6_plus.m3u"
# Pasta onde os filmes baixados serão salvos.
DOWNLOAD_FOLDER = "C:\\converter"
# Arquivo que guardará o histórico de downloads
LOG_FILE = "downloaded.log"

# Cabeçalho para simular um navegador Chrome.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- ATUALIZAÇÃO ---
# Adicione o Referer para simular que a requisição vem do próprio site.
# Este é o passo crucial para corrigir o erro 403 Forbidden.
REFERER_URL = "http://trabalho724.top:8080/"
# --- FIM DA ATUALIZAÇÃO ---

def sanitize_filename(filename):
    """Remove caracteres inválidos de nomes de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def load_downloaded_log():
    """Carrega a lista de filmes já baixados."""
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        downloaded = {line.strip() for line in f}
        print(f"Carregados {len(downloaded)} registros do histórico de downloads.")
        return downloaded

def add_to_downloaded_log(full_title_with_lang: str):
    """Adiciona um filme ao histórico após o download."""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(full_title_with_lang + '\n')

def parse_m3u(file_path: str):
    """Lê um M3U e extrai informações dos filmes."""
    print(f"Lendo e aplicando filtros ao arquivo: {file_path}\n")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    movies = []
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
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

        command = [
            sys.executable, '-m', 'yt_dlp',
            '--output', file_path,
            '--no-playlist', '--retries', '20', '--fragment-retries', '20',
            '--user-agent', HEADERS['User-Agent'],
            
            # --- ATUALIZAÇÃO APLICADA AQUI ---
            # Adicionamos o header 'Referer' ao comando do yt-dlp
            '--add-header', f'Referer: {REFERER_URL}',
            # --- FIM DA ATUALIZAÇÃO ---
            
            url
        ]
        
        # O check=True fará o script parar e mostrar o erro se o yt-dlp falhar.
        subprocess.run(command, check=True)

        print(f"\n✅ Download de '{full_title_with_lang}' concluído com sucesso!")
        add_to_downloaded_log(full_title_with_lang)

    except Exception as e:
        print(f"\n❌ ERRO ao baixar '{full_title_with_lang}': {e}")
        # Se o download falhar, apaga o arquivo parcial para não ocupar espaço.
        if os.path.exists(file_path):
            os.remove(file_path)

def main():
    """Função principal que orquestra o processo de download."""
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
        
    # V--- NOVA LÓGICA AQUI ---V
    # Embaralha a lista de filmes a serem baixados
    random.shuffle(movies_to_download)
    print(f"\nLista de {total_to_download} filmes pendentes foi embaralhada.")
    # ^--- FIM DA NOVA LÓGICA ---^

    print(f"Iniciando o download de {total_to_download} novos filmes (em ordem aleatória)...")
    for movie in movies_to_download:
        download_movie(movie)
        time.sleep(2) # Pequena pausa para não sobrecarregar o servidor
        
    print("\nVerificação concluída. Todos os filmes novos foram baixados.")
    
if __name__ == "__main__":
    main()