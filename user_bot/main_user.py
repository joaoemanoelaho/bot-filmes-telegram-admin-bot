import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import logging
import asyncio
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response
from telegram import Update, Bot
from telegram.ext import Application
import handlers_user as handlers
from config import BOT_TOKEN

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
application = None
initialized = False

async def telegram_webhook(request: Request) -> Response:
    """Recebe updates do Telegram via webhook"""
    global initialized
    if not initialized:
        await initialize_app()
    
    try:
        data = await request.json()
        # Aguarda o bot estar pronto
        if not bot.bot:
            await bot.initialize()
        
        update = Update.de_json(data, bot)
        await application.process_update(update)
    except Exception as e:
        print(f"❌ Erro ao processar webhook do Telegram: {e}")
        import traceback
        traceback.print_exc()
    
    return Response("ok", status_code=200)

async def supabase_webhook(request: Request) -> Response:
    """Recebe notificações do Supabase"""
    try:
        data = await request.json()
        print(f"--- WEBHOOK DO SUPABASE RECEBIDO ---\n{data}\n---------------------------------")

        user_id = data.get('user_id')
        title = data.get('title')
        new_status = data.get('new_status')
        
        if user_id and new_status:
            message = ""
            if new_status == 'added':
                message = f"🎉 Boas notícias! O título que você pediu, '{title}', já está disponível no nosso catálogo!"
            elif new_status == 'denied':
                message = f"😔 Olha! Sobre o seu pedido '{title}', infelizmente não conseguimos adicioná-lo ao catálogo no momento."
            
            if message:
                await bot.send_message(chat_id=user_id, text=message)
        
        return Response(status_code=200)
    except Exception as e:
        print(f"Erro ao processar webhook do Supabase: {e}")
        return Response(status_code=500)

async def health_check(request: Request) -> Response:
    """Verificação de saúde do servidor"""
    return Response("Servidor e Bot estão online!", status_code=200)

async def initialize_app():
    """Inicializa a aplicação do bot"""
    global application, initialized
    if initialized:
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(handlers.start_handler)
    application.add_handler(handlers.button_click_handler)
    application.add_handler(handlers.inline_search_handler)
    application.add_handler(handlers.watch_handler)
    application.add_handler(handlers.text_handler)
    application.add_handler(handlers.cancel_command_handler)
    application.add_handler(handlers.help_command_handler)
    application.add_handler(handlers.request_command_handler)
    
    await application.initialize()
    initialized = True
    print("✅ Bot de USUÁRIO (webhook) inicializado!")

async def register_webhook():
    """Registra o webhook no Telegram"""
    webhook_url = "https://banco-pedido.squareweb.app/webhook"
    try:
        await bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook registrado: {webhook_url}")
    except Exception as e:
        print(f"❌ Erro ao registrar webhook: {e}")

# Define as rotas
routes = [
    Route("/webhook", endpoint=telegram_webhook, methods=["POST"]),
    Route("/webhook/supabase", endpoint=supabase_webhook, methods=["POST"]),
    Route("/health", endpoint=health_check, methods=["GET"]),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    import uvicorn
    
    # Registra webhook
    asyncio.run(register_webhook())
    
    port = int(os.environ.get("PORT", 8000))
    print(f"[WEB] Servidor iniciando em http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)