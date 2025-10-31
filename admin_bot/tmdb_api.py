import re
import unicodedata
from tmdbv3api import TMDb, Movie, Search # Search não é mais usado, mas não quebra
from tmdbv3api.exceptions import TMDbException
from config import TMDB_API_KEY 

# Configuração da API
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR' 

movie_search = Movie() # Para usar o .details() e .search()

def normalize_str(s):
    """Remove acentos, põe em minúsculas e remove espaços extras."""
    if not s:
        return ""
    s = s.lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def search_movie_options(query: str) -> list:
    """
    Busca um filme, reordena por relevância, e filtra os 3 melhores
    usando os 'details' para validar o ano.
    """
    try:
        # 1. Limpeza da query e extração do ano
        clean_query = query.replace('&', 'and')
        year_match = re.search(r'\((\d{4})\)', clean_query)
        year_from_query = int(year_match.group(1)) if year_match else None
        if year_from_query:
            clean_query = re.sub(r'\s*\(\d{4}\)\s*', '', clean_query).strip()
        
        # 2. Busca inicial
        search_results = movie_search.search(clean_query)

        if not search_results:
            print(f"Query: '{clean_query}' | Ano: {year_from_query} | Resultados Encontrados: 0")
            return []
        
        print(f"Query: '{clean_query}' | Ano: {year_from_query} | Resultados Encontrados: {len(search_results)}")
        
        # 3. V--- REMOVIDO FILTRO DE ANO MANUAL ---V
        # Não podemos confiar no 'release_date' da lista de busca.
        # Vamos filtrar DEPOIS de pegar os 'details'.

        # 4. REORDENAÇÃO POR RELEVÂNCIA
        normalized_query = normalize_str(clean_query)
        
        def sort_key(movie):
            title = getattr(movie, 'title', '')
            normalized_title = normalize_str(title)
            is_not_exact_match = (normalized_title != normalized_query)
            popularity = -getattr(movie, 'popularity', 0)
            return (is_not_exact_match, popularity)

        try:
            final_sorted_list = sorted(search_results, key=sort_key)
            print(f"Reordenado. Top 5 Títulos (pré-details): {[getattr(m, 'title', 'N/A') for m in final_sorted_list[:5]]}")
        except Exception as e:
            print(f"Erro ao reordenar: {e}. Usando lista antiga.")
            final_sorted_list = search_results
        
        options = []
        # 5. V--- NOVO LOOP DE FILTRAGEM ---V
        # Iteramos nos 5 melhores resultados reordenados
        for result_movie in final_sorted_list[:5]:
            try:
                if not isinstance(result_movie, Movie):
                    continue
                
                details = movie_search.details(result_movie.id, append_to_response='translations')
                
                # V--- FILTRO DE ANO NOVO (usando details) ---V
                year_value = 0
                if details.release_date:
                    try:
                        year_value = int(details.release_date.split('-')[0])
                    except: pass # Deixa year_value como 0
                
                # Se o usuário especificou um ano (ex: 2023) E
                # o ano do filme (ex: 2007) for diferente, PULE este filme.
                if year_from_query and year_value != year_from_query:
                    print(f"FILTRADO: '{details.title}' (Ano {year_value}) não bate com o ano da query ({year_from_query})")
                    continue
                # ^--- FIM DO FILTRO DE ANO ---^

                # --- LÓGICA DO TÍTULO INTELIGENTE (Sua lógica, está perfeita) ---
                title_pt = details.title 
                original_title = details.original_title
                
                english_title = None
                translations_data = details.translations.get('translations', [])
                english_translation = next((t['data']['title'] for t in translations_data if t['iso_639_1'] == 'en' and t['data']['title']), None)
                if english_translation:
                    english_title = english_translation
                
                main_title_for_check = title_pt 
                button_title_to_use = title_pt 

                if title_pt == original_title and english_title:
                    button_title_to_use = english_title
                
                if button_title_to_use != original_title:
                    final_button_text = f"{button_title_to_use} ({original_title})"
                else:
                    final_button_text = button_title_to_use
                
                options.append({
                    'tmdb_id': details.id,
                    'title': main_title_for_check,    
                    'button_text': final_button_text, 
                    'year': year_value if year_value != 0 else 'N/A',
                    'genre': details.genres[0]['name'] if details.genres else 'N/A',
                    'description': details.overview,
                    'poster_url': f"https://image.tmdb.org/t/p/w500{details.poster_path}" if details.poster_path else None
                })
                
                # Se já temos 3 opções, não precisamos buscar mais
                if len(options) >= 3:
                    break
                    
            except TMDbException as e:
                print(f"Erro da API TMDb ao processar {getattr(result_movie, 'id', 'ID_DESCONHECIDO')}: {e}")
                continue
            except Exception as e:
                print(f"Erro ao processar resultado individual: {e}")
                continue
            
        return options
    
    except Exception as e:
        print(f"Erro ao buscar opções no TMDb: {e}")
        return []
    