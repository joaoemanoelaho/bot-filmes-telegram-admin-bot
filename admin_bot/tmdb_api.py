import re
from tmdbv3api import TMDb, Movie
from tmdbv3api.exceptions import TMDbException # Vamos manter isso, o import estava certo
from config import TMDB_API_KEY 

# Configuração da API
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR' # <-- Continua correto, afeta o 'details'

movie_search = Movie() # <-- Vamos manter para usar o .details()

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
        # V--- A CORREÇÃO ESTÁ AQUI ---V
        # Paramos de usar 'movie_search.search()' (que é bugado)
        # Usamos 'tmdb.search()' (multi-search) que ACEITA o idioma.
        
        # Primeiro, tentamos buscar com o ano, se ele existir
        raw_results = []
        if year:
            raw_results = tmdb.search(query=clean_query, language='pt-BR', year=year)
        
        # Se não achou com ano (ou não tinha ano), busca sem o ano
        if not raw_results:
             raw_results = tmdb.search(query=clean_query, language='pt-BR')

        # Agora, filtramos os resultados para pegar APENAS filmes
        search_results = []
        for r in raw_results:
            # Usamos 'isinstance(r, Movie)' para garantir que é um objeto de filme
            if isinstance(r, Movie):
                search_results.append(r)
        # ^--- FIM DA CORREÇÃO ---^

        if not search_results:
            print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: 0")
            return []
        
        print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: {len(search_results)}")
        
        # 3. Filtro de ano (agora redundante, mas vamos manter para garantir)
        filtered_results = []
        if year:
            for r in search_results:
                release_date = getattr(r, 'release_date', None)
                if release_date and str(year) in str(release_date):
                    filtered_results.append(r)
        
        if not filtered_results:
            filtered_results = search_results

        options = []
        # O loop agora pega os 3 primeiros resultados
        for result in filtered_results[:3]:
            try:
                # 'details' vai respeitar o tmdb.language = 'pt-BR' global
                details = movie_search.details(result.id, append_to_response='translations')
                
                # --- LÓGICA DO TÍTULO INTELIGENTE ---
                title_pt = details.title 
                original_title = details.original_title
                
                english_title = None
                translations_data = details.translations.get('translations', [])
                english_translation = next((t['data']['title'] for t in translations_data if t['iso_639_1'] == 'en' and t['data']['title']), None)
                if english_translation:
                    english_title = english_translation
                
                display_title = title_pt
                
                # Sua lógica: se o título PT for igual ao original (ex: Tropa de Elite)
                # E existir um título em inglês, use o de inglês.
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
                print(f"Erro da API TMDb ao processar {getattr(result, 'id', 'ID_DESCONHECIDO')}: {e}")
                continue
            except Exception as e:
                print(f"Erro ao processar resultado individual: {e}")
                continue
            
        return options
    
    except Exception as e:
        print(f"Erro ao buscar opções no TMDb: {e}")
        return []
    