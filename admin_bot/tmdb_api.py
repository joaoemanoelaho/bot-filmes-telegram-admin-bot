import re
from tmdbv3api import TMDb, Movie, Search
from tmdbv3api.exceptions import TMDbException
from config import TMDB_API_KEY 

# Configuração da API (ISSO AQUI GARANTE O PT-BR)
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
        # V--- CORREÇÃO APLICADA AQUI ---V
        # A busca é feita SEMPRE com o clean_query. O 'year' será usado
        # APENAS no filtro pós-busca, que já está implementado logo abaixo.
        raw_results = search.multi(term=clean_query)
        # ^--- FIM DA CORREÇÃO ---^

        print(f"[DEBUG TMDb] Resposta crua de search.multi: {raw_results}")

        # Agora, filtramos os resultados para pegar APENAS filmes
        search_results = []
        for r in raw_results:
            if isinstance(r, Movie):
                search_results.append(r)

        if not search_results:
            print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: 0")
            return []
        
        print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: {len(search_results)}")
        
        # 3. Filtro inicial por ano (Pós-filtro)
        # ESTA LÓGICA AGORA VAI FUNCIONAR CORRETAMENTE
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
    