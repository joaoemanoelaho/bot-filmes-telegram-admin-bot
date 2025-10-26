# No seu arquivo tastedive_api.py

import httpx
from config import TASTEDIVE_API_KEY
import unicodedata

API_URL = "https://tastedive.com/api/similar"

def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def get_recommendations(movie_title: str, limit: int = 5) -> list[str] | None:
    """
    Busca recomendações de filmes na API TasteDive, simulando um navegador.
    """
    clean_title = movie_title.replace(":", "")
    normalized_title = remove_accents(clean_title)

    params = {
        "q": normalized_title,
        "type": "movie",
        "info": 0,
        "limit": limit,
        "k": TASTEDIVE_API_KEY
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        with httpx.Client() as client:
            response = client.get(API_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # V--- A CORREÇÃO ESTÁ AQUI (letras minúsculas) ---V
            results = data.get("similar", {}).get("results", [])
            
            if not results:
                return []
                
            return [result["name"] for result in results]
            # ^--- FIM DA CORREÇÃO ---^

    except Exception as e:
        print(f"Erro ao buscar recomendações no TasteDive: {e}")
        return None