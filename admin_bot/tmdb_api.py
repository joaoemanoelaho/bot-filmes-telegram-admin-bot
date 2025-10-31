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
        # V--- CORREÇÃO 1: Passar 'year' e 'language' para a API ---V
        raw_response = {}
        
        # Tenta buscar com o ano primeiro, se ele existir
        if year:
            raw_response = search.multi(
                term=clean_query, 
                language='pt-BR', 
                year=year # <-- FORÇA A API A FILTRAR POR ANO
            )
            print(f"[DEBUG TMDb] Resposta crua (com ano {year}): {raw_response}")

        # Se a busca com ano não retornar NADA, ou se não havia ano,
        # tente a busca sem o ano.
        if not year or not raw_response.get('results'):
            if year: # Só para logar que a primeira tentativa falhou
                 print(f"[DEBUG TMDb] Busca com ano {year} falhou. Tentando sem ano...")
            
            raw_response = search.multi(term=clean_query, language='pt-BR')
            print(f"[DEBUG TMDb] Resposta crua (sem ano): {raw_response}")
        # ^--- FIM DA CORREÇÃO 1 e 2 ---^
            
        raw_results_list = raw_response.get('results', [])

        # Agora, filtramos os resultados para pegar APENAS filmes
        search_results = []
        for r_dict in raw_results_list:
            if r_dict.get('media_type') == 'movie':
                search_results.append(r_dict)

        if not search_results:
            print(f"Query: '{clean_query}' | Ano: {year} | Resultados (filmes) Encontrados: 0")
            return []
        
        print(f"Query: '{clean_query}' | Ano: {year} | Resultados (filmes) Encontrados: {len(search_results)}")
        
        # V--- CORREÇÃO 3: Remover filtro de ano manual ---V
        # A API já fez o filtro de ano por nós (se o ano foi fornecido).
        # Se não filtramos por ano na API, queremos todos os resultados.
        # Portanto, nosso resultado filtrado é simplesmente o 'search_results'.
        filtered_results = search_results
        # ^--- FIM DA CORREÇÃO 3 ---^

        options = []
        # O loop agora pega os 3 primeiros resultados
        for result_dict in filtered_results[:3]:
            try:
                tmdb_id_to_fetch = result_dict.get('id')
                if not tmdb_id_to_fetch:
                    continue 

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
                    'title': main_title_for_check,    # <--- Sempre será o 'title_pt'
                    'button_text': final_button_text, # <--- Texto "inteligente" para o botão
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
    