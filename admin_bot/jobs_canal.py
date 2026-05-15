import datetime
import pytz
import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
import random

from config import CANAL_ID, BOT_PRINCIPAL, STICKER_BOM_DIA, STICKER_TARDE, GRUPO_ID

async def postar_filme_10h(context: ContextTypes.DEFAULT_TYPE):
    """Job que posta um filme às 10h da manhã."""
    print("⏰ [JOB] Iniciando postagem do Filme das 10h...")
    
    # 1. Busca a mídia ANTES de tudo
    filme = await db.get_random_movie_for_post()
    if not filme:
        print("⚠️ [JOB] Nenhum filme encontrado no banco para postar às 10h.")
        return

    try:
        # 2. Prepara os textos e botões
        texto_post = (
            f"<tg-emoji emoji-id='5375464961822695044'>🎬</tg-emoji> <tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> <b>SESSÃO PIPOCA</b>\n\n"
            f"<b>{filme.get('title')} ({int(filme.get('year'))})</b>\n"
            f"<tg-emoji emoji-id='5359441070201513074'>🎭</tg-emoji> <b>Gênero:</b> {filme.get('genre', 'Não informado')}\n\n"
            f"<tg-emoji emoji-id='5334882760735598374'>📝</tg-emoji> <b>Sinopse:</b> {filme.get('description', 'Sinopse não informada no momento.')[:300]}...\n\n"
            f"<tg-emoji emoji-id='5371081166013078244'>🍿</tg-emoji> <tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> <i>Disponível agora no nosso catálogo!</i>"
        )

        id_filme = filme.get('movie_id', filme.get('id'))
        link_assistir = f"https://t.me/{BOT_PRINCIPAL}?start=watch_{id_filme}"
        teclado = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ ASSISTIR AGORA", url=link_assistir)]])
        
        poster = filme.get('poster_url') or 'https://via.placeholder.com/500x750?text=Sem+Poster'

        # 3. MANDA TUDO DE UMA VEZ
        # Sticker de cima
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_BOM_DIA)

        # Foto com a legenda
        await context.bot.send_photo(
            chat_id=CANAL_ID,
            photo=poster, 
            caption=texto_post,
            parse_mode="HTML",
            reply_markup=teclado
        )

        # Sticker de baixo
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_BOM_DIA)
        
        print("✅ [JOB] Filme das 10h postado com sucesso!")

    except Exception as e:
        print(f"❌ [JOB] Erro ao postar filme das 10h: {e}")
        # Anota o erro no caderninho para a gente não perder se a tela floodar
        with open("erros_jobs.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()} - Erro no Filme (10h): {e}\n")

async def postar_serie_16h(context: ContextTypes.DEFAULT_TYPE):
    """Job que posta uma série às 16h da tarde."""
    print("⏰ [JOB] Iniciando postagem da Série das 16h...")
    
    # 1. Busca a mídia ANTES de tudo
    serie = await db.get_random_series_for_post()
    if not serie:
        print("⚠️ [JOB] Nenhuma série encontrada no banco para postar às 16h.")
        return

    try:
        # 🛡️ PROTEÇÃO DO ANO: Pega o ano com segurança para não quebrar
        ano_bruto = serie.get('year')
        ano_formatado = f" ({str(ano_bruto).split('-')[0]})" if ano_bruto and str(ano_bruto).lower() != "none" else ""

        # 2. Prepara os textos e botões
        texto_post = (
            f"<tg-emoji emoji-id='5373330964372004748'>📺</tg-emoji> <tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> <b>SESSÃO MARATONA</b>\n\n"
            f"<b>{serie.get('title')}{ano_formatado}</b>\n"
            f"<tg-emoji emoji-id='5359441070201513074'>🎭</tg-emoji> <b>Gênero:</b> {serie.get('genre', 'Não informado')}\n\n"
            f"<tg-emoji emoji-id='5334882760735598374'>📝</tg-emoji> <b>Sinopse:</b> {serie.get('description', 'Sinopse não informada no momento.')[:300]}...\n\n"
            f"<tg-emoji emoji-id='5371081166013078244'>🍿</tg-emoji> <tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> <i>Disponível agora no nosso catálogo!</i>"
        )

        id_serie = serie.get('id', serie.get('series_id'))
        link_assistir = f"https://t.me/{BOT_PRINCIPAL}?start=serie_{id_serie}"
        teclado = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ COMEÇAR MARATONA", url=link_assistir)]])
        
        poster = serie.get('poster_url') or 'https://via.placeholder.com/500x750?text=Sem+Poster'

        # 3. MANDA TUDO DE UMA VEZ
        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_TARDE)

        await context.bot.send_photo(
            chat_id=CANAL_ID,
            photo=poster, 
            caption=texto_post,
            parse_mode="HTML",
            reply_markup=teclado
        )

        await context.bot.send_sticker(chat_id=CANAL_ID, sticker=STICKER_TARDE)
        
        print("✅ [JOB] Série das 16h postada com sucesso!")

    except Exception as e:
        print(f"❌ [JOB] Erro ao postar série das 16h: {e}")
        with open("erros_jobs.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()} - Erro na Série (16h): {e}\n")


# ==========================================
# 📊 ENQUETE 1: QUARTA-FEIRA (BATALHA)
# ==========================================
async def postar_enquete_quarta(context: ContextTypes.DEFAULT_TYPE):
    """Batalha de 3 filmes para animar o meio da semana."""
    f1 = await db.get_random_movie_for_post()
    f2 = await db.get_random_movie_for_post()
    f3 = await db.get_random_movie_for_post()

    if not f1 or not f2 or not f3: return

    pergunta = "🍿 MEIO DA SEMANA: Qual desses você escolheria para relaxar hoje?"
    opcoes = [f"🎬 {f1.get('title')}", f"🔥 {f2.get('title')}", f"✨ {f3.get('title')}"]

    try:
        await context.bot.send_poll(
            chat_id=CANAL_ID, question=pergunta, options=opcoes,
            is_anonymous=True, allows_multiple_answers=False
        )
        print("✅ [JOB] Enquete de Quarta postada!")
    except Exception as e:
        print(f"❌ [JOB] Erro enquete Quarta: {e}")

# ==========================================
# 🏆 ENQUETE 2: SEXTA-FEIRA (QUIZ)
# ==========================================
async def postar_quiz_sexta(context: ContextTypes.DEFAULT_TYPE):
    """Quiz valendo chuva de confetes na tela do usuário."""
    filme = await db.get_random_movie_for_post()
    if not filme or not filme.get('year'): return

    ano_correto = int(filme.get('year'))
    titulo = filme.get('title')
    
    opcoes_anos = [ano_correto, ano_correto - 3, ano_correto + 2, ano_correto - 5]
    random.shuffle(opcoes_anos)
    correta_index = opcoes_anos.index(ano_correto)
    opcoes_str = [str(ano) for ano in opcoes_anos]

    pergunta = f"🤔 SEXTOU COM DESAFIO: Em que ano o filme '{titulo}' foi lançado?"
    explicacao = f"Acertou quem disse {ano_correto}! 🍿 Pesquise por {titulo} no nosso bot para assistir agora."

    try:
        await context.bot.send_poll(
            chat_id=CANAL_ID, question=pergunta, options=opcoes_str,
            type="quiz", correct_option_id=correta_index,
            explanation=explicacao, is_anonymous=True
        )
        print("✅ [JOB] Quiz de Sexta postado!")
    except Exception as e:
        print(f"❌ [JOB] Erro Quiz Sexta: {e}")

# ==========================================
# 🛋️ ENQUETE 3: DOMINGO (FILMES VS SÉRIES)
# ==========================================
async def postar_enquete_domingo(context: ContextTypes.DEFAULT_TYPE):
    """Combate de Domingo: 2 Filmes contra 2 Séries."""
    f1 = await db.get_random_movie_for_post()
    f2 = await db.get_random_movie_for_post()
    s1 = await db.get_random_series_for_post()
    s2 = await db.get_random_series_for_post()

    if not f1 or not f2 or not s1 or not s2: return

    pergunta = "🛋️ DOMINGÃO DA PREGUIÇA: O que vai salvar o seu final de domingo?"
    opcoes = [
        f"🎬 Filme: {f1.get('title')}",
        f"🎬 Filme: {f2.get('title')}",
        f"📺 Série: {s1.get('title')}",
        f"📺 Série: {s2.get('title')}"
    ]

    try:
        await context.bot.send_poll(
            chat_id=CANAL_ID, question=pergunta, options=opcoes,
            is_anonymous=True, allows_multiple_answers=False
        )
        print("✅ [JOB] Enquete de Domingo postada!")
    except Exception as e:
        print(f"❌ [JOB] Erro enquete Domingo: {e}")
        