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
    Busca um filme e retorna os 3 melhores resultados encontrados pela API,
    com os detalhes já em português.
    """
    try:
        # 1. Limpeza da query e extração do ano
        clean_query = query.replace('&', 'and')
        year_match = re.search(r'\((\d{4})\)', clean_query)
        year = int(year_match.group(1)) if year_match else None
        if year:
            clean_query = re.sub(r'\s*\(\d{4}\)\s*', '', clean_query).strip()
        
        # 2. Busca inicial
        # V--- CORREÇÃO 1: 'raw_response' é um dicionário ---V
        raw_response = search.multi(term=clean_query)
        print(f"[DEBUG TMDb] Resposta crua de search.multi: {raw_response}")
        
        # A lista de resultados está na chave 'results'
        raw_results_list = raw_response.get('results', [])

        # Agora, filtramos os resultados para pegar APENAS filmes
        search_results = []
        # V--- CORREÇÃO 2: Iterar na lista e checar o dict ---V
        for r_dict in raw_results_list:
            if r_dict.get('media_type') == 'movie':
                search_results.append(r_dict)
        # ^--- FIM DAS CORREÇÕES 2 ---^

        if not search_results:
            print(f"Query: '{clean_query}' | Ano: {year} | Resultados (filmes) Encontrados: 0")
            return []
        
        print(f"Query: '{clean_query}' | Ano: {year} | Resultados (filmes) Encontrados: {len(search_results)}")
        
        # 3. Filtro inicial por ano (Pós-filtro)
        filtered_results = []
        if year:
            # V--- CORREÇÃO 3: 'r' é um dict, usar .get() ---V
            for r_dict in search_results:
                release_date = r_dict.get('release_date')
                if release_date and str(year) in str(release_date):
                    filtered_results.append(r_dict)
            # ^--- FIM DA CORREÇÃO 3 ---^
        
        if not filtered_results:
            filtered_results = search_results

        options = []
        # O loop agora pega os 3 primeiros resultados
        # V--- CORREÇÃO 4: 'result_dict' é um dict ---V
        for result_dict in filtered_results[:3]:
            try:
                tmdb_id_to_fetch = result_dict.get('id')
                if not tmdb_id_to_fetch:
                    continue 

                details = movie_search.details(tmdb_id_to_fetch, append_to_response='translations')
                
                # --- LÓGICA DO TÍTULO INTELIGENTE (CORRIGIDA) ---
                title_pt = details.title 
                original_title = details.original_title
                
                english_title = None
                translations_data = details.translations.get('translations', [])
                english_translation = next((t['data']['title'] for t in translations_data if t['iso_639_1'] == 'en' and t['data']['title']), None)
                if english_translation:
                    english_title = english_translation
                
                # V--- INÍCIO DA CORREÇÃO ---V
                
                # O 'title' principal para checagem de automação DEVE ser o title_pt
                main_title_for_check = title_pt 
                
                # Agora, definimos o texto do BOTÃO
                # Por padrão, usamos o título em PT
                button_title_to_use = title_pt 

                # Se o título PT é o original E existe um em inglês...
                if title_pt == original_title and english_title:
                    # ...usamos o título em INGLÊS no botão.
                    button_title_to_use = english_title
                
                # Montamos o texto final do botão
                if button_title_to_use != original_title:
                    final_button_text = f"{button_title_to_use} ({original_title})"
                else:
                    final_button_text = button_title_to_use

                # ^--- FIM DA CORREÇÃO ---^

                year_value = 'N/A'
                try:
                    if details.release_date:
                        year_value = int(details.release_date.split('-')[0])
                except: pass
                
                # V--- CORREÇÃO NO DICT DE RETORNO ---V
                options.append({
                    'tmdb_id': details.id,
                    'title': main_title_for_check,    # <--- Sempre será o 'title_pt'
                    'button_text': final_button_text, # <--- Texto "inteligente" para o botão
                    'year': year_value,
                    'genre': details.genres[0]['name'] if details.genres else 'N/A',
                    'description': details.overview,
                    'poster_url': f"https://image.tmdb.org/t/p/w500{details.poster_path}" if details.poster_path else None
                })
                # ^--- FIM DA CORREÇÃO ---^
                
            except TMDbException as e:
                print(f"Erro da API TMDb ao processar {result_dict.get('id', 'ID_DESCONHECIDO')}: {e}")
                continue
            except Exception as e:
                print(f"Erro ao processar resultado individual: {e}")
                continue
            
        return options
    
    except Exception as e:
        print(f"Erro ao buscar opções no TMDb: {e}")
        return []
    
def search_series_options(query: str) -> list[dict]:
    """Busca por séries no TMDb e retorna uma lista de opções formatadas."""
    print(f"[TMDb API] Buscando séries por: '{query}'")
    search_url = f"{BASE_URL}/search/tv"
    params = {
        'api_key': API_KEY,
        'language': 'pt-BR',
        'query': query
    }
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        options = []
        # Pegamos apenas os 5 primeiros resultados
        for result in data.get('results', [])[:5]:
            year = result.get('first_air_date', '').split('-')[0] if result.get('first_air_date') else 'N/A'
            options.append({
                'tmdb_id': result.get('id'),
                'title': result.get('name'),
                'year': year,
                'poster_url': f"https://image.tmdb.org/t/p/w500{result.get('poster_path')}" if result.get('poster_path') else None,
                # Usado para o botão de confirmação
                'button_text': f"{result.get('name')} ({year})"
            })
        return options
    except Exception as e:
        print(f"❌ Erro na API TMDb (search_series_options): {e}")
        return []

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
    