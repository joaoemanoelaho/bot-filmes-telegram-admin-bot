import re
from tmdbv3api import TMDb, Movie
from config import TMDB_API_KEY

# Configuração da API
tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = 'pt-BR' # O idioma aqui continua sendo 'pt-BR' para que os detalhes venham em português QUANDO disponíveis

movie_search = Movie()

def search_movie_options(query: str) -> list:
    """
    Busca um filme e retorna os 3 melhores resultados encontrados pela API,
    sem nenhum filtro de idioma, para o usuário escolher.
    """
    try:
        # 1. Limpeza da query e extração do ano (seu código original)
        clean_query = query.replace('&', 'and')
        year_match = re.search(r'\((\d{4})\)', clean_query)
        year = int(year_match.group(1)) if year_match else None
        if year:
            clean_query = re.sub(r'\s*\(\d{4}\)\s*', '', clean_query).strip()
        
        # 2. Busca inicial
        search_results = movie_search.search(clean_query)
        
        # 3. Filtro inicial por ano
        filtered_results = [r for r in search_results if str(year) in r.release_date] if year else search_results

        options = []
        # O loop agora pega os 3 primeiros resultados que a API retornou, sem validação extra
        for result in filtered_results[:3]:
            details = movie_search.details(result.id, append_to_response='translations')
            
            # --- LÓGICA DO TÍTULO INTELIGENTE ---
            
            # 1. Pega os títulos base
            title_pt = details.title  # Este é o título em PT-BR ou o fallback para o original
            original_title = details.original_title
            
            # 2. Busca pelo título em Inglês na lista de traduções
            english_title = None
            translations_data = details.translations.get('translations', [])
            english_translation = next((t['data']['title'] for t in translations_data if t['iso_639_1'] == 'en' and t['data']['title']), None)
            if english_translation:
                english_title = english_translation

            # 3. Decide qual título exibir
            display_title = title_pt # Começa com o padrão (PT ou Original)
            
            # Se o título em PT for igual ao original (ou seja, não há tradução PT)
            # E se existir um título em Inglês, use o Inglês pois é mais legível.
            if title_pt == original_title and english_title:
                display_title = english_title
            
            # 4. Monta o texto final para o botão
            # Se o título de exibição for diferente do original, mostre o original para contexto.
            if display_title != original_title:
                final_button_text = f"{display_title} ({original_title})"
            else:
                final_button_text = display_title # Se forem iguais, não precisa repetir

            # --- FIM DA LÓGICA ---

            options.append({
                'tmdb_id': details.id,
                'title': display_title, # O título principal para salvar no DB
                'button_text': final_button_text, # O texto para exibir no botão
                'year': int(details.release_date.split('-')[0]) if details.release_date else 'N/A',
                'genre': details.genres[0]['name'] if details.genres else 'N/A',
                'description': details.overview,
                'poster_url': f"https://image.tmdb.org/t/p/w500{details.poster_path}" if details.poster_path else None
            })
            
        return options
    
    except Exception as e:
        print(f"Erro ao buscar opções no TMDb: {e}")
        return []