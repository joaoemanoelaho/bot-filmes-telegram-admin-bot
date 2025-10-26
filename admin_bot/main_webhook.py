import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes
import handlers_admin as handlers
from config import ADMIN_BOT_TOKEN
import asyncio

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

app = Flask(__name__)
application = None
bot = Bot(token=ADMIN_BOT_TOKEN)

@app.route("/webhook/admin", methods=["POST"])
async def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return "ok", 200

@app.before_first_request
async def startup():
    global application
    application = Application.builder().token(ADMIN_BOT_TOKEN).build()
    
    application.add_handler(handlers.start_handler)
    application.add_handler(handlers.button_click_handler)
    application.add_handler(handlers.get_id_command_handler)
    application.add_handler(handlers.admin_video_handler)
    application.add_handler(handlers.get_chat_id_command_handler)
    application.add_handler(handlers.channel_video_handler)
    
    await application.initialize()
    print("Bot ADMIN webhook iniciado!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)