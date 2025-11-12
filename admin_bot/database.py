#
# Arquivo para gerenciar toda a interação com o banco de dados Supabase.
#

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from datetime import datetime, timedelta # Para manipulação de datas
import admin_bot.tmdb_api as tmdb_api

# Tenta criar a conexão com o Supabase.
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Conexão com o Supabase estabelecida com sucesso!")
except Exception as e:
    print(f"Erro ao conectar com o Supabase: {e}")
    supabase = None

def get_or_create_user(user_id: int, first_name: str) -> dict | None:
    """
    Verifica se um usuário existe no DB pelo seu ID.
    Se não existir, cria um novo registro.
    Retorna os dados do usuário.
    """
    if not supabase:
        print("Conexão com Supabase não disponível.")
        return None

    # Tenta buscar o usuário na tabela 'users'
    response = supabase.table('users').select('*').eq('user_id', user_id).execute()
    
    # Se a lista 'data' da resposta estiver vazia, o usuário não existe
    if not response.data:
        print(f"Usuário {user_id} não encontrado. Criando novo registro.")
        try:
            insert_response = supabase.table('users').insert({
                'user_id': user_id,
                'first_name': first_name
                # 'is_vip' já tem 'false' como padrão no banco de dados
            }).execute()
            
            if insert_response.data:
                return insert_response.data[0]
        except Exception as e:
            print(f"Erro ao inserir novo usuário: {e}")
            return None
    
    # Se o usuário já existe, retorna os dados dele
    print(f"Usuário {user_id} encontrado no banco de dados.")
    return response.data[0]

#
def get_user_details(user_id: int):
    """Busca todos os detalhes de um usuário."""
    if not supabase: return None
    try:
        return supabase.table('users').select('*').eq('user_id', user_id).single().execute().data
    except Exception as e:
        print(f"Erro ao buscar detalhes do usuário: {e}")
        return None
    
def set_user_active_payment_id(user_id: int, payment_id: str):
    """Salva o ID do pagamento ativo para um usuário."""
    if not supabase: return
    try:
        supabase.table('users').update({'active_payment_id': payment_id}).eq('user_id', user_id).execute()
    except Exception as e:
        print(f"Erro ao salvar active_payment_id: {e}")

def clear_user_active_payment_id(user_id: int):
    """Limpa o ID do pagamento ativo de um usuário."""
    if not supabase: return
    try:
        supabase.table('users').update({'active_payment_id': None}).eq('user_id', user_id).execute()
    except Exception as e:
        print(f"Erro ao limpar active_payment_id: {e}")
#

def search_movies(query: str) -> list:
    """
    Busca filmes no banco de dados cujo título corresponde à query.
    A busca é case-insensitive (não diferencia maiúsculas de minúsculas).
    """
    if not supabase or not query:
        return []

    try:
        # <<< MUDANÇA AQUI: Adicionamos 'poster_url' na seleção >>>
        select_query = 'movie_id, title, description, poster_url, year, genre'
        response = supabase.table('movies').select(select_query).ilike('title', f'%{query}%').limit(10).execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar filmes: {e}")
        return []

def get_movie_by_id(movie_id: int) -> dict | None:
    """Busca um filme específico no banco de dados pelo seu ID."""
    if not supabase:
        return None
    try:
        response = supabase.table('movies').select('*').eq('movie_id', movie_id).single().execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar filme por ID: {e}")
        return None

def is_user_vip(user_id: int) -> bool:
    """Verifica se o usuário é VIP. Retorna True ou False."""
    if not supabase:
        return False
    try:
        response = supabase.table('users').select('is_vip').eq('user_id', user_id).single().execute()
        if response.data:
            return response.data['is_vip']
        return False
    except Exception as e:
        print(f"Erro ao verificar status VIP: {e}")
        return False
    
def add_movie(movie_data: dict) -> bool:
    """
    Adiciona um novo filme ao banco de dados.
    'movie_data' deve ser um dicionário com todas as colunas da tabela 'movies'.
    Retorna True se foi bem-sucedido, False caso contrário.
    """
    if not supabase:
        return False
    
    try:
        supabase.table('movies').insert(movie_data).execute()
        print(f"Filme '{movie_data['title']}' adicionado ao banco de dados.")
        return True
    except Exception as e:
        print(f"Erro ao adicionar filme no Supabase: {e}")
        return False
    
def add_request(user_id: int, title: str) -> bool:
    """Adiciona um novo pedido de filme/série ao banco de dados."""
    if not supabase:
        return False
    
    try:
        supabase.table('requests').insert({
            'user_id': user_id,
            'requested_title': title
        }).execute()
        print(f"Pedido '{title}' do usuário {user_id} salvo no banco de dados.")
        return True
    except Exception as e:
        print(f"Erro ao salvar pedido no Supabase: {e}")
        return False
    
def log_movie_view(movie_id: int, user_id: int):
    """Registra um evento de visualização na tabela view_history."""
    if not supabase:
        return
    try:
        supabase.table('view_history').insert({
            'movie_id': movie_id,
            'user_id': user_id
        }).execute()
        print(f"Registrada visualização para o filme ID {movie_id} pelo usuário {user_id}")
    except Exception as e:
        print(f"Erro ao registrar visualização: {e}")

def get_trending(period_days: int = 0) -> list:
    """
    Busca os filmes mais vistos em um determinado período.
    period_days = 7 para semanal, 30 para mensal, 0 para geral.
    """
    if not supabase:
        return []
    try:
        # Chama a função que criamos diretamente no banco de dados
        response = supabase.rpc('get_trending_movies', {'period_days': period_days}).execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar trending: {e}")
        return []
    
def set_user_as_vip(user_id: int, duration_days: int = 30) -> bool:
    """Atualiza o status de um usuário para VIP."""
    if not supabase:
        return False
    
    # Calcula a data de expiração
    expiration_date = datetime.utcnow() + timedelta(days=duration_days)
    
    try:
        supabase.table('users').update({
            'is_vip': True,
            'vip_until': expiration_date.isoformat()
        }).eq('user_id', user_id).execute()
        print(f"Usuário {user_id} agora é VIP por {duration_days} dias.")
        return True
    except Exception as e:
        print(f"Erro ao atualizar usuário para VIP: {e}")
        return False
    
def is_user_vip(user_id: int) -> bool:
    """
    Verifica se o usuário é VIP E se a assinatura não expirou.
    Se a assinatura expirou, remove o status VIP automaticamente.
    """
    if not supabase:
        return False
    try:
        response = supabase.table('users').select('is_vip, vip_until').eq('user_id', user_id).single().execute()
        user_data = response.data
        
        if not user_data or not user_data.get('is_vip'):
            return False

        vip_until_str = user_data.get('vip_until')
        if not vip_until_str:
            # Se por algum motivo não houver data de expiração, remove o VIP para segurança
            clear_user_active_payment_id(user_id) # Usamos clear_user... para setar is_vip=False
            return False

        # Converte a data do banco para um objeto de data comparável
        vip_expiration_date = datetime.fromisoformat(vip_until_str.replace('Z', '+00:00'))

        # Compara com a data e hora atuais
        if datetime.now(vip_expiration_date.tzinfo) < vip_expiration_date:
            # A data de expiração ainda está no futuro, então o usuário é VIP.
            return True
        else:
            # A assinatura expirou!
            print(f"Assinatura VIP do usuário {user_id} expirou. Removendo acesso.")
            # Remove o status VIP do usuário
            supabase.table('users').update({'is_vip': False, 'vip_until': None}).eq('user_id', user_id).execute()
            return False

    except Exception as e:
        print(f"Erro ao verificar status VIP: {e}")
        return False
    
def find_movie_by_title_and_year(title: str, year: int) -> dict | None:
    """Procura por um filme no banco de dados pelo título e ano."""
    if not supabase:
        return None
    try:
        response = supabase.table('movies').select('*').eq('title', title).eq('year', year).single().execute()
        return response.data
    except Exception:
        # A exceção acontece se o 'single()' não encontrar nada, o que é normal.
        return None

def update_movie_file_id(movie_id: int, file_id: str, unique_id: str, audio_type: str):
    """Atualiza o file_id E o unique_id de um filme existente."""
    if not supabase:
        return False
    
    # Define os nomes das colunas com base no tipo de áudio
    file_id_column = 'dubbed_file_id' if audio_type.upper() == 'DUB' else 'subtitled_file_id'
    unique_id_column = 'dubbed_unique_id' if audio_type.upper() == 'DUB' else 'subtitled_unique_id'
    
    try:
        # Cria o dicionário de dados para atualizar
        data_to_update = {
            file_id_column: file_id,
            unique_id_column: unique_id
        }
        
        supabase.table('movies').update(data_to_update).eq('movie_id', movie_id).execute()
        print(f"Atualizado {file_id_column} e {unique_id_column} para o filme ID: {movie_id}")
        return True
    except Exception as e:
        print(f"Erro ao atualizar file_id e unique_id: {e}")
        return False
    
def filter_existing_titles(titles: list[str]) -> list[str]:
    """
    Recebe uma lista de títulos de filmes e retorna uma sub-lista 
    contendo apenas os títulos que já existem no banco de dados.
    """
    if not titles:
        return []
    try:
        # Usamos o operador 'in' para buscar todos os títulos de uma vez só,
        # o que é muito mais eficiente do que fazer um loop de buscas.
        response = supabase.table('movies').select('title').in_('title', titles).execute()
        
        # Extrai apenas os títulos da resposta do Supabase
        existing_titles = [movie['title'] for movie in response.data]
        
        return existing_titles
    except Exception as e:
        print(f"Erro ao filtrar títulos existentes no Supabase: {e}")
        return []

def get_or_create_series(tmdb_id: int) -> dict | None:
    """
    Verifica se a série existe no banco de dados pelo tmdb_id.
    Se não existir, busca no TMDb e cria um novo registro.
    Retorna os dados da série do NOSSO banco.
    """
    if not supabase:
        print("Conexão com Supabase não disponível.")
        return None

    # 1. Tenta buscar a série no banco
    response = supabase.table('series').select('*').eq('tmdb_id', tmdb_id).execute()
    
    if response.data:
        print(f"[DB] Série encontrada no banco: {response.data[0]['title']}")
        return response.data[0]

    # 2. Se não encontrou, busca no TMDb
    print(f"[DB] Série {tmdb_id} não encontrada. Buscando no TMDb...")
    series_details = tmdb_api.get_series_details(tmdb_id)
    
    if not series_details:
        print(f"❌ [DB] Falha ao buscar detalhes da série {tmdb_id} no TMDb.")
        return None
        
    # 3. Salva no banco de dados
    try:
        insert_response = supabase.table('series').insert(series_details).execute()
        if insert_response.data:
            print(f"✅ [DB] Série '{series_details['title']}' adicionada ao banco.")
            return insert_response.data[0]
    except Exception as e:
        print(f"❌ [DB] Erro ao inserir nova série no Supabase: {e}")
        return None
    
    return None

def get_or_create_season(series_id: int, season_number: int) -> dict | None:
    """
    Verifica se a temporada existe para uma série.
    Se não existir, cria um novo registro.
    Retorna os dados da temporada.
    """
    if not supabase: return None

    # 1. Tenta buscar a temporada
    response = supabase.table('seasons') \
        .select('*') \
        .eq('series_id', series_id) \
        .eq('season_number', season_number) \
        .execute()
        
    if response.data:
        print(f"[DB] Temporada {season_number} encontrada para a série ID {series_id}.")
        return response.data[0]
        
    # 2. Se não encontrou, cria
    print(f"[DB] Criando registro da Temporada {season_number} para a série ID {series_id}.")
    try:
        insert_data = {
            'series_id': series_id,
            'season_number': season_number,
            'name': f'Temporada {season_number}' # Nome genérico
        }
        insert_response = supabase.table('seasons').insert(insert_data).execute()
        if insert_response.data:
            return insert_response.data[0]
    except Exception as e:
        print(f"❌ [DB] Erro ao inserir nova temporada no Supabase: {e}")
        return None

def find_episode(season_id: int, episode_number: int) -> dict | None:
    """Procura por um episódio específico no banco de dados."""
    if not supabase: return None
    try:
        response = supabase.table('episodes') \
            .select('*') \
            .eq('season_id', season_id) \
            .eq('episode_number', episode_number) \
            .single() \
            .execute()
        return response.data
    except Exception:
        return None # Normal se não encontrar

def add_or_update_episode(season_id: int, tmdb_id: int, season_number: int, episode_number: int, audio_type: str, file_id: str, unique_id: str) -> bool:
    """
    Adiciona ou atualiza um episódio no banco de dados.
    Busca o título do episódio no TMDb.
    AGORA SALVA O unique_id.
    """
    if not supabase: return False

    # 1. Verifica se o episódio já existe
    existing_episode = find_episode(season_id, episode_number)
    
    file_id_column = 'dubbed_file_id' if audio_type.upper() == 'DUB' else 'subtitled_file_id'
    unique_id_column = 'dubbed_unique_id' if audio_type.upper() == 'DUB' else 'subtitled_unique_id'

    try:
        if existing_episode:
            # 2.A. Se existe, ATUALIZA o file_id e unique_id
            print(f"[DB] Atualizando episódio S{season_number} E{episode_number} (ID: {existing_episode['episode_id']})")
            
            data_to_update = {
                file_id_column: file_id,
                unique_id_column: unique_id
            }
            
            supabase.table('episodes') \
                .update(data_to_update) \
                .eq('episode_id', existing_episode['episode_id']) \
                .execute()
            return True
        else:
            # 2.B. Se não existe, busca detalhes no TMDb e CRIA
            print(f"[DB] Adicionando novo episódio S{season_number} E{episode_number}")
            
            ep_details = tmdb_api.get_episode_details(tmdb_id, season_number, episode_number)
            if not ep_details:
                ep_details = {'title': f'Episódio {episode_number}'}
                
            insert_data = {
                'season_id': season_id,
                'episode_number': episode_number,
                'title': ep_details['title'],
                file_id_column: file_id,
                unique_id_column: unique_id
            }
            
            supabase.table('episodes').insert(insert_data).execute()
            print(f"✅ [DB] Episódio '{ep_details['title']}' S{season_number} E{episode_number} adicionado.")
            return True
            
    except Exception as e:
        print(f"❌ [DB] Erro ao salvar episódio no Supabase: {e}")
        return False
    