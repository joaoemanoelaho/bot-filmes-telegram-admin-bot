from telethon.sync import TelegramClient
from config import API_ID, API_HASH, STORAGE_CHANNEL_ID
import os
import time

# --- CONFIGURAÇÕES ---
# O nome do arquivo da sessão que criamos no primeiro login.
SESSION_NAME = "minha_conta_de_upload"
# A pasta que o robô vai vigiar.
# Lembre-se de usar duas barras invertidas "\\" no Windows.
MONITOR_FOLDER = "C:\\converter"
# O ID do canal para onde os vídeos serão enviados (do seu config.py).
TARGET_CHANNEL_ID = STORAGE_CHANNEL_ID
# Tempo de espera em segundos entre cada verificação da pasta.
SLEEP_TIME = 10 

def main():
    """Função principal do robô de automação."""
    print("Iniciando o cliente de automação...")
    
    with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        me = client.get_me()
        print(f"Login bem-sucedido como: {me.first_name}")
        print(f"Vigiando a pasta: {MONITOR_FOLDER}")
        print(f"Enviando para o canal/grupo com ID: {TARGET_CHANNEL_ID}")
        print("-" * 30)

        # Loop infinito para vigiar a pasta
        while True:
            print(f"Verificando a pasta em busca de novos vídeos... (próxima verificação em {SLEEP_TIME}s)")
            
            # Pega todos os arquivos na pasta
            try:
                all_files = os.listdir(MONITOR_FOLDER)
            except FileNotFoundError:
                print(f"ERRO: A pasta '{MONITOR_FOLDER}' não foi encontrada. Verifique o caminho e crie a pasta se necessário.")
                break # Encerra o script se a pasta não existe

            # Filtra apenas os arquivos .mp4
            video_files = [f for f in all_files if f.lower().endswith('.mp4')]

            if video_files:
                # Pega o primeiro vídeo da lista para processar
                file_to_upload = video_files[0]
                full_path = os.path.join(MONITOR_FOLDER, file_to_upload)
                
                # Extrai a legenda a partir do nome do arquivo (remove a extensão .mp4)
                caption_text = os.path.splitext(file_to_upload)[0]

                print(f"\n--- NOVO VÍDEO ENCONTRADO! ---")
                print(f"Arquivo: {file_to_upload}")
                print(f"Legenda: {caption_text}")

                try:
                    print("Iniciando o upload para o Telegram...")
                    client.send_file(
                        TARGET_CHANNEL_ID,
                        full_path,
                        caption=caption_text,
                        part_size_kb=512, # Usando o tamanho máximo de chunk para performance
                        workers=4, # V--- TENTANDO USAR 4 "TRABALHADORES" EM PARALELO ---V
                        progress_callback=lambda sent, total: print(f"Enviado: {sent * 100 / total:.2f}%", end='\r')
                    )
                    print("\nUpload concluído com sucesso!")
                
                except Exception as e:
                    print(f"\nERRO DURANTE O UPLOAD: {e}")
                    print("O arquivo não será apagado. Tentando novamente no próximo ciclo.")
                
                else: # Este bloco só executa se o 'try' for bem-sucedido
                    print(f"Apagando arquivo local: {full_path}")
                    os.remove(full_path)
                    print("Arquivo local apagado.")
                
                print("-" * 30)

            # Espera um tempo antes de verificar a pasta novamente
            time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()