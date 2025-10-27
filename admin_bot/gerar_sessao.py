from pyrogram import Client
import sys
import os

# --- Adicionado para encontrar o config.py ---
# Garante que o script possa importar o 'config.py' da mesma pasta
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from config import API_ID, API_HASH
except ImportError:
    print("ERRO: Não foi possível encontrar o arquivo 'config.py'.")
    print("Certifique-se que 'config.py' está no mesmo diretório e contém API_ID e API_HASH.")
    sys.exit(1)
# --- Fim da adição ---
print("--- Gerador de String de Sessão Pyrogram ---")
print(f"API_ID e API_HASH carregados com sucesso do config.py!")

# --- MUDANÇA IMPORTANTE AQUI ---
# Trocamos ":memory:" pelo parâmetro explícito 'in_memory=True'
# Damos um nome qualquer, pois ele não será salvo no disco.
print("\nIniciando cliente em modo 'in-memory'...")
with Client(
    name="gerador_de_sessao", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    in_memory=True  # Esta é a correção
) as app:
# --- FIM DA MUDANÇA ---
    
    print("Login interativo necessário:")
    
    # O app.export_session_string() vai automaticamente pedir 
    # seu telefone, código e senha 2FA aqui no terminal.
    # Responda a todas as perguntas.
    
    session_string = app.export_session_string()
    
    print("\n=======================================================")
    print("LOGIN BEM SUCEDIDO!")
    print("Sua String de Sessão está abaixo. Copie TUDO:")
    print("=======================================================\n")
    print(session_string)
    print("\n=======================================================")
    print("Guarde esta string! Ela é sua 'senha' para o Square Cloud.")
    print("=======================================================")