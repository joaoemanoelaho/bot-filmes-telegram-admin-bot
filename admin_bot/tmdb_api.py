import re
from tmdbv3api import TMDb, Movie, Search
from tmdbv3api.exceptions import TMDbException
from config import TMDB_API_KEY 

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
                    continue # Pula se o dict não tiver um ID

                # 'details' VAI ser um objeto, pois vem de movie_search.details()
                details = movie_search.details(tmdb_id_to_fetch, append_to_response='translations')
                # ^--- FIM DA CORREÇÃO 4 ---^
                
                # --- LÓGICA DO TÍTULO INTELIGENTE ---
                title_pt = details.title 
                original_title = details.original_title
                
                english_title = None
                translations_data = details.translations.get('translations', [])
                english_translation = next((t['data']['title'] for t in translations_data if t['iso_639_1'] == 'en' and t['data']['title']), None)
                if english_translation:
                    english_title = english_translation
                
                display_title = title_pt
                
                if title_pt == original_title and english_title:
                    display_title = english_title
                
                if display_title != original_title:
                    final_button_text = f"{display_title} ({original_title})"
                else:
                    final_button_text = display_title

                year_value = 'N/A'
                try:
                    if details.release_date:
                        year_value = int(details.release_date.split('-')[0])
                except: pass

                options.append({
                    'tmdb_id': details.id,
                    'title': display_title,
                    'button_text': final_button_text,
                    'year': year_value,
                    'genre': details.genres[0]['name'] if details.genres else 'N/A',
                    'description': details.overview,
                    'poster_url': f"https://image.tmdb.org/t/p/w500{details.poster_path}" if details.poster_path else None
                })
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
    