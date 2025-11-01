import sys
import os
import logging
import asyncio
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response
from telegram import Update
# --- MUDANÇA 1: IMPORTAR O DictPersistence E TypeHandler ---
from telegram.ext import Application, DictPersistence, TypeHandler, ContextTypes
import handlers_admin as handlers
from config import ADMIN_BOT_TOKEN

# --- DEBUG PRINT ---
print("[DEBUG-ADMIN] Versão do código: 1.4 (com Debug Handler)")
# ---------------------

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

application: Application = None
APP_INITIALIZED = asyncio.Event()

async def error_handler(update: object, context):
    """Loga os erros causados pelos handlers."""
    print(f"❌ [ADMIN] Erro no handler: {context.error}")
    import traceback
    traceback.print_exc()

# --- NOVO HANDLER DE DEBUG ---
async def debug_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Imprime um log para QUALQUER update recebido pelo processador."""
    print("\n" + "--- [DEBUG_ALL_UPDATES] ---")
    if update.message:
        print(f"Tipo: Message (Texto: {update.message.text})")
    elif update.channel_post:
        print(f"Tipo: Channel Post")
    elif update.callback_query:
        print(f"Tipo: CallbackQuery (Botão!)")
        print(f"Dados Recebidos: {update.callback_query.data}")
    else:
        print(f"Tipo desconhecido: {type(update)}")
    print("-----------------------------" + "\n")
# --- FIM DO NOVO HANDLER ---

async def startup():
    """Inicializa o bot ao iniciar o servidor"""
    global application
    
    print("[DEBUG-ADMIN] Função startup() iniciada.")
    
    try:
        # --- HABILITAR A PERSISTÊNCIA EM MEMÓRIA RAM ---
        # Isso não cria arquivos, mas liga o context.bot_data
        persistence = DictPersistence()
        
        application = Application.builder().token(ADMIN_BOT_TOKEN).persistence(persistence).build()
        
        # --- MUDANÇA 3: ADICIONAR O DEBUG HANDLER ---
        # O group=-1 garante que ele rode ANTES dos seus handlers normais.
        application.add_handler(TypeHandler(Update, debug_all_updates), group=-1)

        # Handlers (reordenados para priorizar botões)
        # É uma boa prática registrar o handler de botões primeiro.
        application.add_handler(handlers.button_click_handler)
        application.add_handler(handlers.start_handler)
        application.add_handler(handlers.get_id_command_handler)
        application.add_handler(handlers.admin_video_handler)
        application.add_handler(handlers.get_chat_id_command_handler)
        application.add_handler(handlers.channel_video_handler)
        application.add_handler(handlers.admin_video_handler) # O roteador manual
        application.add_handler(handlers.channel_video_handler) # Canal de Filmes

        # --- ADICIONE ESTA LINHA ---
        application.add_handler(handlers.channel_series_handler) # Canal de Séries
        
        print("[DEBUG-ADMIN] Adicionando error_handler...")
        application.add_error_handler(error_handler)
        
        await application.initialize()
        print("✅ Bot de ADMIN (webhook) inicializado com PERSISTÊNCIA EM RAM!")
        
        print("[DEBUG-ADMIN] Sinalizando APP_INITIALIZED.set()")
        APP_INITIALIZED.set() 
        print("[DEBUG-ADMIN] Startup concluído.")
        
    except Exception as e:
        print(f"❌ [ADMIN] ERRO NO STARTUP: {e}")
        import traceback
        traceback.print_exc()
        raise

async def telegram_webhook(request: Request) -> Response:
    """Recebe updates do Telegram via webhook"""
    
    print("[DEBUG-ADMIN] /webhook/admin recebido. Aguardando APP_INITIALIZED...")
    await APP_INITIALIZED.wait() 
    print("[DEBUG-ADMIN] APP_INITIALIZED está 'set'. Processando webhook.")
    
    try:
        data = await request.json()
        print(f"📨 [ADMIN] Dados recebidos no webhook: {data}")
        
        if not isinstance(data, dict) or 'update_id' not in data:
            print(f"⚠️ [ADMIN] Dados inválidos recebidos: {type(data)}")
            return Response("ok", status_code=200)
        
        update = Update.de_json(data, application.bot) 
        await application.process_update(update)
        print(f"✅ [ADMIN] Update processado: {data.get('update_id')}")
        
    except Exception as e:
        print(f"❌ [ADMIN] Erro ao processar webhook do Telegram: {e}")
        import traceback
        traceback.print_exc()
    
    return Response("ok", status_code=200)

async def health_check(request: Request) -> Response:
    """Verificação de saúde do servidor"""
    return Response("Servidor do Bot ADMIN está online!", status_code=200)

# Define as rotas
routes = [
    # Rota ÚNICA para o bot de admin
    Route("/webhook/admin", endpoint=telegram_webhook, methods=["POST"]),
    Route("/health", endpoint=health_check, methods=["GET"]),
]

app = Starlette(routes=routes, on_startup=[startup])

if __name__ == "__main__":
    import uvicorn
    
    # O Square Cloud define a porta como 80, mas 8000 é um bom padrão local
    port = int(os.environ.get("PORT", 8000)) 
    print(f"[WEB-ADMIN] Servidor iniciando em http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

