import re
import unicodedata
from tmdbv3api import TMDb, Movie, Search
from tmdbv3api.exceptions import TMDbException
from config import TMDB_API_KEY 

# Configuração da API
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR' 

movie_search = Movie() # Para usar o .details()
search = Search()      # Instância correta

# Esta função de normalização é para a lógica de reordenação
def normalize_str(s):
    if not s: return ""
    s = s.lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

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
        
        # 2. V--- A CORREÇÃO DE OURO: Usar search.movie() ---V
        
        raw_response = {}
        if year:
            # Busca filmes, com idioma E ano.
            raw_response = search.movie(term=clean_query, language='pt-BR', year=year)
        else:
            # Busca filmes, com idioma, sem ano.
            raw_response = search.movie(term=clean_query, language='pt-BR')
            
        print(f"[DEBUG TMDb] Resposta crua de search.movie: {raw_response}")
        
        # O resultado já é uma lista de dicionários de FILMES.
        # Não precisamos mais filtrar por 'media_type'.
        search_results = raw_response.get('results', [])
        # ^--- FIM DA CORREÇÃO ---^
        
        if not search_results:
            print(f"Query: '{clean_query}' | Ano: {year} | Resultados (filmes) Encontrados: 0")
            return []
        
        print(f"Query: '{clean_query}' | Ano: {year} | Resultados (filmes) Encontrados: {len(search_results)}")
        
        # 3. V--- REMOVIDO FILTRO DE ANO MANUAL ---V
        # A API já filtrou o ano para nós. 'search_results' é a nossa lista final.
        
        # 4. REORDENAÇÃO POR RELEVÂNCIA (Opcional, mas recomendado)
        # Reordena a lista para priorizar matches exatos do título.
        normalized_query = normalize_str(clean_query)
        
        def sort_key(movie_dict):
            title = movie_dict.get('title', '')
            normalized_title = normalize_str(title)
            # Critério 1: Match exato (False=0) vem antes
            is_not_exact_match = (normalized_title != normalized_query)
            # Critério 2: Popularidade
            popularity = -movie_dict.get('popularity', 0)
            return (is_not_exact_match, popularity)

        try:
            final_sorted_list = sorted(search_results, key=sort_key)
            print(f"Reordenado. Top 3 títulos: {[m.get('title', 'N/A') for m in final_sorted_list[:3]]}")
        except Exception as e:
            print(f"Erro ao reordenar: {e}. Usando lista antiga.")
            final_sorted_list = search_results # Fallback
            
        options = []
        # O loop agora pega os 3 primeiros da lista REORDENADA
        for result_dict in final_sorted_list[:3]:
            try:
                tmdb_id_to_fetch = result_dict.get('id')
                if not tmdb_id_to_fetch:
                    continue 

                # Seu código original para buscar 'details' (está perfeito)
                details = movie_search.details(tmdb_id_to_fetch, append_to_response='translations')
                
                # --- LÓGICA DO TÍTULO INTELIGENTE (Mantida) ---
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
                print(f"Erro da API TMDb ao processar {result_dict.get('id', 'ID_DESCONHECIDO')}: {e}")
                continue
            except Exception as e:
                print(f"Erro ao processar resultado individual: {e}")
                continue
            
        return options
    
    except Exception as e:
        print(f"Erro ao buscar opções no TMDb: {e}")
        return []
    