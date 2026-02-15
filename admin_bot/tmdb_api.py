import re
import requests
from tmdbv3api import TMDb, Movie, Search
from tmdbv3api.exceptions import TMDbException
from config import TMDB_API_KEY, BASE_URL, API_KEY

# Configuração da API
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR' 

movie_search = Movie() # Para usar o .details()
search = Search()      # Instância correta

def search_movie_options(query: str) -> list:
    """
    Busca um filme e retorna os resultados.
    Se o ano for detectado, usa filtro de ano na API para precisão total.
    """
    movie_search = Movie() 
    search = Search()

    try:
        # 1. Limpeza da query e extração do ano
        clean_query = query.replace('&', 'and')
        year_match = re.search(r'\((\d{4})\)', clean_query)
        year = int(year_match.group(1)) if year_match else None
        
        if year:
            clean_query = re.sub(r'\s*\(\d{4}\)\s*', '', clean_query).strip()

        # 2. BUSCA INTELIGENTE
        if year:
            print(f"[DEBUG] Buscando '{clean_query}' filtrando pelo ano {year}...")
            # search.movies permite passar o ano, forçando o TMDb a filtrar na fonte.
            # Isso garante que 'Rebelião (2015)' apareça, mesmo que seja impopular.
            raw_results_list = search.movies(term=clean_query, year=year)
        else:
            print(f"[DEBUG] Busca ampla por '{clean_query}'...")
            # Sem ano, usa multi-search (filmes, séries, etc)
            raw_response = search.multi(term=clean_query)
            raw_results_list = raw_response.get('results', [])

        # 3. Processamento dos Resultados
        # Se veio do search.movies, já são objetos. Se veio do multi, são dicts.
        # Vamos normalizar tudo para lista de objetos ou dicts.
        
        processed_options = []
        
        # Iteramos sobre os resultados (pegando no máximo 5 para não demorar)
        for result in raw_results_list:
            
            # Normalização: se for objeto, converte para dict ou acessa atributos
            # A lib tmdbv3api retorna objetos (result.id) no search.movies
            # e dicts (result['id']) no search.multi. Vamos tratar ambos.
            
            try:
                # Tenta acessar como objeto
                r_media_type = getattr(result, 'media_type', 'movie') # search.movies só traz movie
                r_id = getattr(result, 'id', None)
                r_release_date = getattr(result, 'release_date', '')
            except AttributeError:
                # Se falhar, tenta como dict
                r_media_type = result.get('media_type', 'movie')
                r_id = result.get('id')
                r_release_date = result.get('release_date', '')

            # Filtra apenas filmes
            if r_media_type != 'movie':
                continue

            # Filtro de Ano (Reforço): Se o ano foi pedido, garante que bate
            if year and r_release_date:
                if str(year) not in str(r_release_date):
                    continue

            # Busca detalhes completos (para tradução e botões)
            try:
                details = movie_search.details(r_id, append_to_response='translations')
                
                # Dados Principais
                title_pt = getattr(details, 'title', 'Sem Título')
                original_title = getattr(details, 'original_title', '')
                
                # Tenta achar título em Inglês nas traduções
                english_title = None
                translations = getattr(details, 'translations', {}).get('translations', [])
                for t in translations:
                    if t.get('iso_639_1') == 'en':
                        english_title = t.get('data', {}).get('title')
                        break
                
                # Lógica do Botão
                button_text = title_pt
                if title_pt == original_title and english_title:
                    button_text = english_title
                
                if button_text != original_title:
                    final_button_text = f"{button_text} ({original_title})"
                else:
                    final_button_text = button_text

                # Data e Poster
                r_year = 'N/A'
                if getattr(details, 'release_date', None):
                    r_year = details.release_date.split('-')[0]
                
                poster = getattr(details, 'poster_path', None)
                poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None
                
                overview = getattr(details, 'overview', '')
                genre = 'N/A'
                if getattr(details, 'genres', None) and len(details.genres) > 0:
                    genre = details.genres[0]['name']

                processed_options.append({
                    'tmdb_id': r_id,
                    'title': title_pt,
                    'button_text': final_button_text,
                    'year': r_year,
                    'genre': genre,
                    'description': overview,
                    'poster_url': poster_url
                })
                
                # Se já achamos 3 bons candidatos, paramos
                if len(processed_options) >= 3:
                    break

            except Exception as e:
                print(f"Erro ao processar detalhes do ID {r_id}: {e}")
                continue

        return processed_options

    except Exception as e:
        print(f"Erro geral na busca: {e}")
        return []
    
#
# --- INÍCIO DA ATUALIZAÇÃO ---
#
def search_series_options(query: str, year: str = None) -> list[dict]:
    """
    Busca por séries no TMDb e retorna uma lista de opções formatadas.
    (VERSÃO ATUALIZADA: Aceita ano e retorna 10 resultados)
    """
    print(f"[TMDb API] Buscando séries por: '{query}' (Ano: {year})")
    search_url = f"{BASE_URL}/search/tv"
    params = {
        'api_key': API_KEY,
        'language': 'pt-BR',
        'query': query
    }
    
    # Adiciona o filtro de ano se ele foi fornecido
    if year:
        try:
            params['first_air_date_year'] = int(year)
        except ValueError:
            print(f"⚠️ Aviso: Ano inválido '{year}' recebido, ignorando filtro de ano.")

    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        options = []
        # Pegamos os 10 primeiros resultados (limite aumentado)
        for result in data.get('results', [])[:10]:
            year_result = result.get('first_air_date', '').split('-')[0] if result.get('first_air_date') else 'N/A'
            options.append({
                'tmdb_id': result.get('id'),
                'title': result.get('name'),
                'year': year_result,
                'poster_url': f"https://image.tmdb.org/t/p/w500{result.get('poster_path')}" if result.get('poster_path') else None,
                # Usado para o botão de confirmação
                'button_text': f"{result.get('name')} ({year_result})"
            })
        return options
    except Exception as e:
        print(f"❌ Erro na API TMDb (search_series_options): {e}")
        return []
#
# --- FIM DA ATUALIZAÇÃO ---
#

def get_series_details(tmdb_id: int) -> dict | None:
    """Busca os detalhes completos de UMA série no TMDb."""
    print(f"[TMDb API] Buscando detalhes da série ID: {tmdb_id}")
    detail_url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {
        'api_key': API_KEY,
        'language': 'pt-BR'
    }
    try:
        response = requests.get(detail_url, params=params)
        response.raise_for_status()
        result = response.json()
        
        # Formata os dados para salvar no nosso banco 'series'
        return {
            'tmdb_id': result.get('id'),
            'title': result.get('name'),
            'description': result.get('overview'),
            'poster_url': f"https://image.tmdb.org/t/p/w500{result.get('poster_path')}" if result.get('poster_path') else None,
            'year': result.get('first_air_date', '').split('-')[0] if result.get('first_air_date') else 'N/A',
            'genre': ", ".join([g['name'] for g in result.get('genres', [])])
        }
    except Exception as e:
        print(f"❌ Erro na API TMDb (get_series_details): {e}")
        return None

def get_episode_details(tmdb_id: int, season_number: int, episode_number: int) -> dict | None:
    """Busca os detalhes de UM episódio (ex: Título)."""
    print(f"[TMDb API] Buscando Ep: S{season_number} E{episode_number} da Série ID: {tmdb_id}")
    detail_url = f"{BASE_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}"
    params = {
        'api_key': API_KEY,
        'language': 'pt-BR'
    }
    try:
        response = requests.get(detail_url, params=params)
        response.raise_for_status()
        result = response.json()
        
        # Formata os dados para salvar no nosso banco 'episodes'
        return {
            'title': result.get('name', f'Episódio {episode_number}'),
            'episode_number': result.get('episode_number')
        }
    except Exception as e:
        # Se o episódio não existir no TMDb (ex: "Episódio 25" de um anime),
        # apenas retornamos um título genérico.
        print(f"⚠️ Aviso na API TMDb (get_episode_details): {e}. Usando título genérico.")
        return {
            'title': f'Episódio {episode_number}',
            'episode_number': episode_number
        }
    