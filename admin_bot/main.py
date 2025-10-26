import sys
import os
import asyncio

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import logging
from telegram.ext import Application
import handlers_admin as handlers
from config import ADMIN_BOT_TOKEN

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def main() -> None:
    application = Application.builder().token(ADMIN_BOT_TOKEN).build()

    application.add_handler(handlers.start_handler)
    application.add_handler(handlers.button_click_handler)
    application.add_handler(handlers.get_id_command_handler)
    application.add_handler(handlers.admin_video_handler)
    application.add_handler(handlers.get_chat_id_command_handler)
    application.add_handler(handlers.channel_video_handler)

    print("Bot de ADMIN iniciado e rodando!")
    
    try:
        application.run_polling()
    except Exception as e:
        print(f"❌ Erro: {e}. Reiniciando em 10 segundos...")
        asyncio.sleep(10)
        main()

if __name__ == "__main__":
    main()