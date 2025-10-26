import asyncio
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response
from telegram import Bot
from config import BOT_TOKEN

# Crie uma instância do bot aqui, apenas para enviar mensagens
bot = Bot(token=BOT_TOKEN)

async def supabase_webhook_handler(request: Request) -> Response:
    """Recebe e processa as notificações do Supabase."""
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
                message = f"😔 Olá! Sobre o seu pedido '{title}', infelizmente não conseguimos adicioná-lo ao catálogo no momento."
            
            if message:
                await bot.send_message(chat_id=user_id, text=message)
        
        return Response(status_code=200)
    except Exception as e:
        print(f"Erro ao processar webhook do Supabase: {e}")
        return Response(status_code=500)

# Define a rota para o webhook do Supabase
routes = [
    Route('/webhook', endpoint=supabase_webhook_handler, methods=['POST']),
]

# Cria o aplicativo servidor
app = Starlette(routes=routes)

# Função principal para rodar o servidor
if __name__ == "__main__":
    print("Iniciando o servidor de webhooks na porta 80...")
    uvicorn.run(app, host="0.0.0.0", port=80)