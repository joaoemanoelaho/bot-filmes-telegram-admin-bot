import sys
import os
import time
import asyncio

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import logging
from telegram.ext import Application
import handlers_admin as handlers
from config import ADMIN_BOT_TOKEN
from telegram.error import NetworkError, Conflict

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

async def main() -> None:
    """Inicia o bot com retry automático"""
    retry_count = 0
    max_retries = 5
    
    while True:
        try:
            application = Application.builder().token(ADMIN_BOT_TOKEN).build()

            application.add_handler(handlers.start_handler)
            application.add_handler(handlers.button_click_handler)
            application.add_handler(handlers.get_id_command_handler)
            application.add_handler(handlers.admin_video_handler)
            application.add_handler(handlers.get_chat_id_command_handler)
            application.add_handler(handlers.channel_video_handler)

            print("✅ Bot de ADMIN iniciado e rodando (polling)!")
            retry_count = 0
            await application.run_polling(allowed_updates=["message", "channel_post"])
            
        except Conflict:
            print("❌ Conflito: outro bot já está rodando. Aguardando...")
            await asyncio.sleep(10)
            
        except NetworkError as e:
            retry_count += 1
            if retry_count >= max_retries:
                print(f"❌ Muitas tentativas falhadas. Reiniciando em 30s...")
                await asyncio.sleep(30)
                retry_count = 0
            else:
                print(f"⚠️ Erro de rede ({retry_count}/{max_retries}): {e}. Tentando em 5s...")
                await asyncio.sleep(5)
                
        except Exception as e:
            print(f"❌ Erro inesperado: {e}. Reiniciando em 10s...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())