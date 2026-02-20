import datetime
import pytz
import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# ================= CONFIGURAÇÕES =================
CANAL_ID = "7108893421" # Coloque a tag do seu canal oficial
BOT_PRINCIPAL = "MeuCinePipocaBot" # O username do seu bot de usuários (sem o @)

# IDs dos Stickers (Se não souber pegar, me avise que te ensino!)
STICKER_BOM_DIA = "CAACAgUAAxkBAAFC2W9pmISt24IF-VV0UrlvEiwLQS2PmAACmgADqZrmFt-aDpzFm4eFOgQ"
STICKER_TARDE = "CAACAgUAAxkBAAFC2W9pmISt24IF-VV0UrlvEiwLQS2PmAACmgADqZrmFt-aDpzFm4eFOgQ"
# =================================================

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
        titulo_formatado = urllib.parse.quote(serie.get('title', ''))
        link_assistir = f"https://t.me/{BOT_PRINCIPAL}?inline={titulo_formatado}"
        
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
