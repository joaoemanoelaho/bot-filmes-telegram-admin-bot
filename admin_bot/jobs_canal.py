import datetime
import pytz
import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

from config import CANAL_ID, BOT_PRINCIPAL, STICKER_BOM_DIA, STICKER_TARDE, GRUPO_ID

async def postar_filme_10h(context: ContextTypes.DEFAULT_TYPE):
    """Job que posta um filme às 10h da manhã."""
    filme = await db.get_random_movie_for_post()
    if not filme: return

    try:
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_BOM_DIA)

        # TEXTO ATUALIZADO (Sem hora, com Gênero)
        texto_post = (
            f"<tg-emoji emoji-id='5375464961822695044'>🎬</tg-emoji> <tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> <b>SESSÃO PIPOCA</b>\n\n"
            f"<b>{filme.get('title')} ({filme.get('year')})</b>\n"
            f"<tg-emoji emoji-id='5359441070201513074'>🎭</tg-emoji> <b>Gênero:</b> {filme.get('genre', 'Não informado')}\n\n"
            f"<tg-emoji emoji-id='5334882760735598374'>📝</tg-emoji> <b>Sinopse:</b> {filme.get('description', 'Sinopse não informada no momento.')[:300]}...\n\n"
            f"<tg-emoji emoji-id='5371081166013078244'>🍿</tg-emoji> <tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> <i>Disponível agora no nosso catálogo!</i>"
        )

        # LINK CORRIGIDO (Puxa o movie_id do banco de dados)
        id_filme = filme.get('movie_id', filme.get('id'))
        link_assistir = f"https://t.me/{BOT_PRINCIPAL}?start=watch_{id_filme}"
        
        teclado = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ ASSISTIR AGORA", url=link_assistir)]])

        await context.bot.send_photo(
            chat_id=CANAL_ID,
            photo=filme.get('poster_url', 'https://via.placeholder.com/500x750?text=Sem+Poster'), 
            caption=texto_post,
            parse_mode="HTML",
            reply_markup=teclado
        )

        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_BOM_DIA)
        print("✅ [JOB] Filme postado com sucesso!")

    except Exception as e:
        print(f"❌ [JOB] Erro ao postar filme: {e}")

async def postar_serie_16h(context: ContextTypes.DEFAULT_TYPE):
    """Job que posta uma série às 16h da tarde."""
    serie = await db.get_random_series_for_post()
    if not serie: return

    try:
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_TARDE)

        # TEXTO ATUALIZADO (Sem hora, com Gênero)
        texto_post = (
            f"<tg-emoji emoji-id='5373330964372004748'>📺</tg-emoji> <tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> <b>SESSÃO MARATONA</b>\n\n"
            f"<b>{serie.get('title')} ({serie.get('year')})</b>\n"
            f"<tg-emoji emoji-id='5359441070201513074'>🎭</tg-emoji> <b>Gênero:</b> {serie.get('genre', 'Não informado')}\n\n"
            f"<tg-emoji emoji-id='5334882760735598374'>📝</tg-emoji> <b>Sinopse:</b> {serie.get('description', 'Sinopse não informada no momento.')[:300]}...\n\n"
            f"<tg-emoji emoji-id='5371081166013078244'>🍿</tg-emoji> <tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> <i>Disponível agora no nosso catálogo!</i>"
        )

        # LINK CORRIGIDO PARA SÉRIES (Abre o bot na busca inline com o nome da série já digitado)
        titulo_limpo = str(serie.get('title', '')).replace(' ', '%20')
        link_assistir = f"https://t.me/{BOT_PRINCIPAL}?inline={titulo_limpo}"
        
        teclado = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ COMEÇAR MARATONA", url=link_assistir)]])

        await context.bot.send_photo(
            chat_id=CANAL_ID,
            photo=serie.get('poster_url', 'https://via.placeholder.com/500x750?text=Sem+Poster'), 
            caption=texto_post,
            parse_mode="HTML",
            reply_markup=teclado
        )

        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_TARDE)
        print("✅ [JOB] Série postada com sucesso!")

    except Exception as e:
        print(f"❌ [JOB] Erro ao postar série: {e}")

async def teste_bypass_grupo_canal(context: ContextTypes.DEFAULT_TYPE):
    """Job de Teste: Manda no Grupo e Copia pro Canal"""
    
    # Texto com o emoji animado de FOGO que pegamos
    texto_post = "🎬 <tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> <b>TESTE DE BYPASS</b>\nSerá que o Telegram vai deixar?"

    try:
        # 1. Manda no Grupo (Aqui o Telegram deve renderizar o emoji animado)
        msg_grupo = await context.bot.send_message(
            chat_id=GRUPO_ID,
            text=texto_post,
            parse_mode="HTML"
        )
        print("✅ Mandou no grupo!")

        # 2. Copia a exata mensagem do Grupo para o Canal
        await context.bot.copy_message(
            chat_id=CANAL_ID,
            from_chat_id=GRUPO_ID,
            message_id=msg_grupo.message_id
        )
        print("✅ Copiou pro canal! Vai lá olhar como ficou o emoji.")

    except Exception as e:
        print(f"❌ Erro no teste de bypass: {e}")