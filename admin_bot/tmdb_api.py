import re
from tmdbv3api import TMDb, Movie
from config import TMDB_API_KEY

# Configuração da API
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR' # <-- Isso está CORRETO. Ele traduzirá os 'details'

movie_search = Movie()

def search_movie_options(query: str) -> list:
    """
    Busca um filme e retorna os 3 melhores resultados encontrados pela API,
    sem nenhum filtro de idioma, para o usuário escolher.
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
        # Forçamos a busca a ser em 'en-US' para encontrar títulos originais.
        search_results = movie_search.search(clean_query, language='en-US')
        # ^--- FIM DA CORREÇÃO ---^

        if not search_results:
             print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: 0")
             return [] # Retorna vazio se a busca falhar
        
        print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: {len(search_results)}")
        
        # 3. Filtro inicial por ano (flexível)
        filtered_results = []
        if year:
            # Tenta encontrar com o ano exato primeiro
            for r in search_results:
                release_date = getattr(r, 'release_date', None)
                if release_date and str(year) in str(release_date):
                    filtered_results.append(r)
        
        # Se não achou com o ano exato OU se nenhum ano foi dado, usa os resultados principais
        if not filtered_results:
            filtered_results = search_results

        options = []
        # O loop agora pega os 3 primeiros resultados
        for result in filtered_results[:3]:
            try:
                if isinstance(result, str):
                    continue
                
                # 'details' vai respeitar o tmdb.language = 'pt-BR' global
                details = movie_search.details(result.id, append_to_response='translations')
                
                # --- LÓGICA DO TÍTULO INTELIGENTE ---
                title_pt = details.title # Virá em PT-BR
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
                    'title': display_title, # Título em PT-BR
                    'button_text': final_button_text, # Título para o botão
                    'year': year_value,
                    'genre': details.genres[0]['name'] if details.genres else 'N/A',
                    'description': details.overview,
                    'poster_url': f"https://image.tmdb.org/t/p/w500{details.poster_path}" if details.poster_path else None
                })
            except Exception as e:
                print(f"Erro ao processar resultado individual: {e}")
                continue
            
        return options
    
    except Exception as e:
        print(f"Erro ao buscar opções no TMDb: {e}")
        return []