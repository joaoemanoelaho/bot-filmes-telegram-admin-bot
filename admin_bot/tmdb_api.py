import re
import unicodedata 
from tmdbv3api import TMDb, Movie, Search
from tmdbv3api.exceptions import TMDbException
from config import TMDB_API_KEY 

# Configuração da API
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR' 

movie_search = Movie()

def normalize_str(s):
    """Remove acentos, põe em minúsculas e remove espaços extras."""
    if not s:
        return ""
    s = s.lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def search_movie_options(query: str) -> list:
    """
    Busca um filme, reordena por relevância e retorna os 3 melhores.
    """
    try:
        # 1. Limpeza da query e extração do ano
        clean_query = query.replace('&', 'and')
        year_match = re.search(r'\((\d{4})\)', clean_query)
        year = int(year_match.group(1)) if year_match else None
        if year:
            clean_query = re.sub(r'\s*\(\d{4}\)\s*', '', clean_query).strip()
        
        # 2. Busca inicial
        search_results = movie_search.search(clean_query)

        if not search_results:
            print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: 0")
            return []
        
        print(f"Query: '{clean_query}' | Ano: {year} | Resultados Encontrados: {len(search_results)}")
        
        # 3. Filtro inicial por ano
        year_filtered_results = []
        if year:
            for r in search_results:
                if not isinstance(r, Movie): 
                    continue
                
                # V--- A CORREÇÃO DEFINITIVA ESTÁ AQUI ---V
                # Pega a release_date. Se for None, usa ""
                release_date_str = getattr(r, 'release_date', '') 
                
                # Checa se a string "2023-10-18" começa com "2023"
                if release_date_str.startswith(str(year)):
                    year_filtered_results.append(r)
                # ^--- FIM DA CORREÇÃO ---^
        
        # Esta linha de fallback agora só será usada se NENHUM filme de 2023
        # for encontrado, o que é o comportamento correto.
        if not year_filtered_results:
            year_filtered_results = search_results

        # 4. REORDENAÇÃO POR RELEVÂNCIA (Esta lógica estava correta)
        normalized_query = normalize_str(clean_query)
        
        def sort_key(movie):
            title = getattr(movie, 'title', '')
            normalized_title = normalize_str(title)
            is_not_exact_match = (normalized_title != normalized_query)
            popularity = -getattr(movie, 'popularity', 0)
            return (is_not_exact_match, popularity)

        try:
            final_sorted_list = sorted(year_filtered_results, key=sort_key)
            print(f"Reordenado. Top 3 títulos: {[getattr(m, 'title', 'N/A') for m in final_sorted_list[:3]]}")
        except Exception as e:
            print(f"Erro ao reordenar: {e}. Usando lista antiga.")
            final_sorted_list = year_filtered_results
        
        options = []
        # O loop agora pega os 3 primeiros da lista REORDENADA
        for result_movie in final_sorted_list[:3]:
            try:
                if not isinstance(result_movie, Movie):
                    continue
                
                details = movie_search.details(result_movie.id, append_to_response='translations')
                
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

                year_value = 'N/A'
                try:
                    if details.release_date:
                        year_value = int(details.release_date.split('-')[0])
                except: pass

                options.append({
                    'tmdb_id': details.id,
                    'title': main_title_for_check,    
                    'button_text': final_button_text, 
                    'year': year_value,
                    'genre': details.genres[0]['name'] if details.genres else 'N/A',
                    'description': details.overview,
                    'poster_url': f"https://image.tmdb.org/t/p/w500{details.poster_path}" if details.poster_path else None
                })
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
    