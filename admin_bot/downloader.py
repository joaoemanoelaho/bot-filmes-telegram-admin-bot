import requests
from bs4 import BeautifulSoup
import re
import qbittorrentapi
import time
import os

# --- CONFIGURAÇÕES DO qBITTORRENT ---
# Use os dados que você configurou nas opções do qBittorrent
QBIT_HOST = 'localhost'
QBIT_PORT = 8080
QBIT_USER = 'admin'
QBIT_PASS = 'adminadmin'

# --- PASTA PARA ONDE OS FILMES SERÃO BAIXADOS ---
DOWNLOAD_PATH = "C:\\converter" 

def search_and_download(query: str):
    # --- PARTE 1: O SCRAPER (já fizemos) ---
    formatted_query = query.replace(" ", "+")
    search_url = f"https://www.starckfilmes-v2.com/?s={formatted_query}"
    print(f"Buscando em: {search_url}")

    try:
        response_search = requests.get(search_url)
        response_search.raise_for_status()
        soup_search = BeautifulSoup(response_search.text, 'html.parser')
        
        first_result = soup_search.find('h2', class_='entry-title').find('a')
        if not first_result:
            print("Nenhum resultado encontrado na busca.")
            return

        movie_page_url = first_result['href']
        print(f"Página do filme encontrada: {movie_page_url}")

        response_movie = requests.get(movie_page_url)
        response_movie.raise_for_status()
        soup_movie = BeautifulSoup(response_movie.text, 'html.parser')

        magnet_link = soup_movie.find('div', class_='post-buttons').find('a', class_='check')['href']
        print(f"Magnet Link encontrado!")

    except Exception as e:
        print(f"Ocorreu um erro no scraper: {e}")
        return

    # --- PARTE 2: O DOWNLOADER (NOVO) ---
    print("\nConectando ao qBittorrent...")
    qbt_client = qbittorrentapi.Client(host=QBIT_HOST, port=QBIT_PORT, username=QBIT_USER, password=QBIT_PASS)

    try:
        qbt_client.auth_log_in()
        print("Login no qBittorrent bem-sucedido.")
    except qbittorrentapi.LoginFailed as e:
        print(f"Falha no login do qBittorrent: {e}")
        return

    print("Adicionando torrent para download...")
    # Adiciona o magnet link ao qBittorrent e especifica a pasta para salvar
    if not qbt_client.torrents_add(urls=magnet_link, save_path=DOWNLOAD_PATH):
        print("Erro ao adicionar o magnet link.")
        return

    # Espera um pouco para o torrent ser adicionado e obter os metadados
    time.sleep(5)
    
    # Encontra o torrent que acabamos de adicionar
    torrent = qbt_client.torrents_info(sort='added_on', reverse=True)[0]
    print(f"Iniciando download de: {torrent.name}")

    # Monitora o progresso do download
    while torrent.progress < 1:
        print(f"Baixando: {torrent.progress * 100:.2f}% | Velocidade: {torrent.dlspeed / 1024:.2f} KB/s", end='\r')
        time.sleep(2)
        # Atualiza as informações do torrent
        torrent = qbt_client.torrents_info(torrent_hashes=torrent.hash)[0]

    # --- PARTE 3: O EXPLORADOR DE PASTA (NOVO) ---
    print("\nDownload concluído! Procurando o arquivo de vídeo principal...")

    content_path = os.path.join(torrent.save_path, torrent.name)
    video_file_path = None

    if os.path.isdir(content_path):
        # Se for uma pasta, procuramos o maior arquivo de vídeo dentro dela
        largest_file_size = 0
        for dirpath, _, filenames in os.walk(content_path):
            for filename in filenames:
                # Procuramos por extensões de vídeo comuns
                if filename.lower().endswith(('.mkv', '.mp4', '.avi')):
                    full_path = os.path.join(dirpath, filename)
                    file_size = os.path.getsize(full_path)
                    if file_size > largest_file_size:
                        largest_file_size = file_size
                        video_file_path = full_path
    elif os.path.isfile(content_path) and content_path.lower().endswith(('.mkv', '.mp4', '.avi')):
        # Se o download já for um único arquivo de vídeo
        video_file_path = content_path

    if video_file_path:
        print(f"Arquivo de vídeo principal encontrado: {video_file_path}")
        # AQUI, no próximo passo, chamaremos o FFmpeg para converter o 'video_file_path'
    else:
        print("ERRO: Nenhum arquivo de vídeo principal foi encontrado no download.")

    print("\nDownload concluído! O arquivo está em " + DOWNLOAD_PATH)
    # Aqui, no futuro, chamaremos o FFmpeg para conversão
    
if __name__ == "__main__":
    search_and_download("O Poderoso Chefão")