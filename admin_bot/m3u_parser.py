import re
import os

# --- CONFIGURAÇÕES ---
M3U_FILE_PATH = "C:\\Users\\filme\\Downloads\\tv_channels_20efbmf6_plus.m3u"

def parse_m3u(file_path: str):
    """
    Lê um arquivo M3U e extrai apenas os filmes (VOD),
    assumindo 'Dublado' como padrão.
    """
    print(f"Lendo e aplicando filtros avançados ao arquivo: {file_path}\n")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"ERRO: O arquivo '{file_path}' não foi encontrado.")
        return

    movies = []
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            group_match = re.search(r'group-title="([^"]+)"', line, re.IGNORECASE)
            
            if group_match and "filmes" in group_match.group(1).lower():
                title_match = re.search(r'tvg-name="([^"]+)"', line)
                title = title_match.group(1).strip() if title_match else line.split(',')[-1].strip()
                
                if re.search(r'\(\d{4}\)', title):
                    url = lines[i+1].strip()
                    
                    # --- LÓGICA DE IDIOMA ATUALIZADA ---
                    # 1. Assume que o filme é Dublado por padrão.
                    language = "Dublado"
                    # 2. Se encontrar 'LEG', muda para Legendado.
                    if any(word in title.upper() for word in ["LEGENDADO", " LEG"]):
                        language = "Legendado"
                    # --- FIM DA ATUALIZAÇÃO ---
                    
                    movies.append({'title': title, 'url': url, 'language': language})

    print(f"Encontrados {len(movies)} filmes (VOD) na lista.\n")
    print("--- Exibindo os 20 primeiros resultados ---\n")
    for movie in movies[:20]:
        print(f"Título: {movie['title']}")
        print(f"Idioma: {movie['language']}")
        print(f"URL: {movie['url']}\n")

if __name__ == "__main__":
    parse_m3u(M3U_FILE_PATH)