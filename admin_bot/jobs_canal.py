import datetime
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# ================= CONFIGURAÇÕES =================
CANAL_ID = "-1003516192401" # Coloque a tag do seu canal oficial
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
        # 1. Manda o Sticker
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_BOM_DIA)

        # 2. Monta o texto (Usando Emojis Animados Premium - Troque o emoji-id pelos seus)
        texto_post = (
            f"🎬 <tg-emoji emoji-id='5368324170671202286'>🔥</tg-emoji> <b>SESSÃO PIPOCA (10h)</b>\n\n"
            f"<b>{filme.get('title')} ({filme.get('year')})</b>\n\n"
            f"📝 <b>Sinopse:</b> {filme.get('overview', 'Sem sinopse disponível no momento.')[:300]}...\n\n"
            f"🍿 <tg-emoji emoji-id='5422863925760803451'>✨</tg-emoji> <i>Disponível agora no nosso catálogo!</i>"
        )

        # 3. Monta o Botão com Deep Link (Direto pro Bot Principal)
        # Atenção: Ajuste o 'watch_{id}' para o formato exato que seu bot principal usa
        link_assistir = f"https://t.me/{BOT_PRINCIPAL}?start=watch_{filme['tmdb_id']}"
        teclado = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ ASSISTIR AGORA", url=link_assistir)]])

        # 4. Manda o Pôster com o texto e botão
        await context.bot.send_photo(
            chat_id=CANAL_ID,
            photo=filme.get('poster_url', 'https://via.placeholder.com/500x750?text=Sem+Poster'), 
            caption=texto_post,
            parse_mode="HTML",
            reply_markup=teclado
        )

        # 5. Fecha com o mesmo Sticker
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_BOM_DIA)
        print("✅ [JOB] Filme postado com sucesso às 10h!")

    except Exception as e:
        print(f"❌ [JOB] Erro ao postar filme das 10h: {e}")

async def postar_serie_16h(context: ContextTypes.DEFAULT_TYPE):
    """Job que posta uma série às 16h da tarde."""
    serie = await db.get_random_series_for_post()
    if not serie: return

    try:
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_TARDE)

        texto_post = (
            f"📺 <tg-emoji emoji-id='5368324170671202286'>🔥</tg-emoji> <b>SESSÃO MARATONA (16h)</b>\n\n"
            f"<b>{serie.get('title')} ({serie.get('year')})</b>\n\n"
            f"📝 <b>Sinopse:</b> {serie.get('overview', 'Sem sinopse disponível no momento.')[:300]}...\n\n"
            f"🍿 <tg-emoji emoji-id='5422863925760803451'>✨</tg-emoji> <i>Disponível agora no nosso catálogo!</i>"
        )

        # Ajuste o link deep link de série conforme o seu bot principal (ex: show_ep_ ou algo que abra a série)
        link_assistir = f"https://t.me/{BOT_PRINCIPAL}?start=series_{serie['tmdb_id']}"
        teclado = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ COMEÇAR MARATONA", url=link_assistir)]])

        await context.bot.send_photo(
            chat_id=CANAL_ID,
            photo=serie.get('poster_url', 'https://via.placeholder.com/500x750?text=Sem+Poster'), 
            caption=texto_post,
            parse_mode="HTML",
            reply_markup=teclado
        )

        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_TARDE)
        print("✅ [JOB] Série postada com sucesso às 16h!")

    except Exception as e:
        print(f"❌ [JOB] Erro ao postar série das 16h: {e}")