import re
import asyncio
from telegram import CallbackQuery
from telegram.ext import ContextTypes

# Regex global para Séries
SERIES_REGEX = re.compile(
    r"^(?P<nome>.+?)\s*(?:\((?P<ano>\d{4})\))?\s*S(?P<temporada>\d{1,2})\s*E(?P<episodio>\d{1,3})\s*\[(?P<audio>[A-Z0-9]+)\]$",
    re.IGNORECASE
)

async def notificar_usuarios_radar(context: ContextTypes.DEFAULT_TYPE, users_ids: list, titulo: str):
    if not users_ids: return
    print(f"📢 Notificando {len(users_ids)} usuários sobre '{titulo}'...")
    for user_id in users_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 **Seu pedido foi atendido!**\n\n"
                    f"🎬 **{titulo}**\n"
                    f"Acabou de ser adicionado ao nosso catálogo.\n"
                    f"Use a busca no bot para assistir! 🍿"
                ),
                parse_mode="Markdown"
            )
            await asyncio.sleep(0.5) 
        except Exception as e:
            print(f"⚠️ Não consegui avisar o user {user_id} (Bloqueou o bot?): {e}")

async def safe_edit_message(message, new_text, **kwargs):
    if not message: return
    retries = 3
    delay = 2
    for i in range(retries):
        try:
            await message.edit_text(new_text, **kwargs)
            return
        except Exception as e:
            print(f"⚠️ Erro ao EDITAR (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(f"❌ FALHA AO EDITAR MENSAGEM.")

async def safe_send_message(context: ContextTypes.DEFAULT_TYPE, chat_id, text, **kwargs):
    retries = 3
    delay = 2
    for i in range(retries):
        try:
            return await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception as e:
            print(f"⚠️ Erro ao ENVIAR (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(f"❌ FALHA AO ENVIAR MENSAGEM.")
                return None

async def safe_answer_query(query: CallbackQuery, **kwargs):
    retries = 3
    delay = 1
    for i in range(retries):
        try:
            await query.answer(**kwargs)
            return
        except Exception as e:
            print(f"⚠️ Erro ao RESPONDER QUERY (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1: await asyncio.sleep(delay)
            else: print(f"❌ FALHA AO RESPONDER QUERY.")
            