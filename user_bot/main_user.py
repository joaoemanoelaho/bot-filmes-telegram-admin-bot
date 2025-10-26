# Salve como: user_bot/main_user.py

import logging
from telegram.ext import Application
import handlers_user as handlers # <-- Importa o arquivo correto
from config import USER_BOT_TOKEN # <-- Use um novo token do config.py

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def main() -> None:
    application = Application.builder().token(USER_BOT_TOKEN).build()

    application.add_handler(handlers.start_handler)
    application.add_handler(handlers.button_click_handler)
    application.add_handler(handlers.inline_search_handler)
    application.add_handler(handlers.watch_handler)
    application.add_handler(handlers.text_handler)
    application.add_handler(handlers.cancel_command_handler)
    application.add_handler(handlers.help_command_handler)
    application.add_handler(handlers.request_command_handler)

    print("Bot de USUÁRIO iniciado e rodando!")
    application.run_polling()

if __name__ == "__main__":
    main()