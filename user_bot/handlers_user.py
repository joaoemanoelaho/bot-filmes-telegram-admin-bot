#
# Arquivo que contém as respostas e lógicas para os comandos.
#
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultPhoto
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, InlineQueryHandler, MessageHandler, filters
import database as db
import tmdb_api
from config import ADMIN_IDS, STORAGE_CHANNEL_ID
import payments
import base64
import io
import time
import re
import os
import sys
from thefuzz import fuzz
from starlette.requests import Request
from starlette.responses import Response
import uuid
import tastedive_api

    
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Função chamada pelo comando /start ou pelo botão "Voltar ao Menu".
    Com lógica de Deep Linking.
    """
    is_query = update.callback_query is not None
    
    if is_query:
        user = update.callback_query.from_user
        message_to_reply = update.callback_query.message
    else:
        user = update.effective_user
        message_to_reply = update.message
        
    if context.args:
        payload = context.args[0]
        if payload.startswith("watch_"):
            movie_id = payload.split('_')[1]
            context.args = [movie_id]
            # Usa o update original para chamar o handler
            return await watch_command_handler(update, context)

    db.get_or_create_user(user_id=user.id, first_name=user.first_name)
    keyboard = [
        [
            InlineKeyboardButton("Buscar Filme 🔎", switch_inline_query_current_chat=""),
        ],
        [
            InlineKeyboardButton("Adquirir VIP 🚀", callback_data="main_vip")
        ],
        [
            InlineKeyboardButton("Pedir Filme/Série 💡", callback_data="main_request"),
            InlineKeyboardButton("Top Filmes 🏆", callback_data="main_top")
        ]
    ]
    main_menu = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        f"Olá {user.mention_html()}! 👋\n\n"
        "Gosta de maratonar? Esse bot é perfeito para isso 😉.\n\n"
        "Clique no botão \"Buscar Filme 🔎\" para começar.\n\n"
        "Ficou com dúvidas? Envie o comando /help"
    )
    
    # Se for uma query (botão Voltar), edita a mensagem. Se for comando /start, responde.
    if is_query:
        try:
            await message_to_reply.edit_text(welcome_text, reply_markup=main_menu, parse_mode='HTML')
        except Exception as e:
            print(f"Erro ao editar mensagem de volta ao menu: {e}")
            # Fallback para enviar nova mensagem se a edição falhar
            await context.bot.send_message(chat_id=user.id, text=welcome_text, reply_markup=main_menu, parse_mode='HTML')
    else:
        await message_to_reply.reply_html(welcome_text, reply_markup=main_menu)

async def request_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia o fluxo de pedido de filme/série via comando /pedir."""
    # Coloca o usuário no "estado de espera"
    context.user_data['state'] = 'awaiting_request'
    # Envia a mensagem pedindo o nome do filme
    await update.message.reply_text(
        "Qual filme ou série você gostaria de ver no catálogo?\n\n"
        "Por favor, envie o nome completo. Para cancelar, digite /cancelar."
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa TODOS os cliques em botões inline."""
    query = update.callback_query
    # A linha 'await query.answer()' foi movida para dentro de cada bloco lógico
    # para corrigir o bug da resposta dupla.

    callback_data = query.data
    user_id = query.from_user.id
    print(f"Usuário {user_id} clicou no botão: {callback_data}")

    # --- LÓGICA PARA ENVIAR O FILME ---
    if callback_data.startswith("play_"):
        await query.answer()
        _, movie_id_str, audio_choice = callback_data.split('_')
        movie_id = int(movie_id_str)
        
        await query.edit_message_caption(caption="⏳ Carregando seu filme, por favor aguarde...")

        movie = db.get_movie_by_id(movie_id)
        if not movie:
            await query.edit_message_caption(caption="Erro: Filme não encontrado.")
            return

        file_id_to_send = movie.get('dubbed_file_id') if audio_choice == "dub" else movie.get('subtitled_file_id')
        
        if file_id_to_send:
            await query.delete_message()
            
            bot_username = context.bot.username
            video_caption = (
                f"🎬 *{movie['title']}* ({movie['year']})\n\n"
                f"🎭 *Gênero:* {movie['genre']}\n\n"
                f"---\n"
                f"🍿 Assistido com @{bot_username}"
            )

            keyboard = [[InlineKeyboardButton("Compartilhar ❤️", switch_inline_query=f"{movie   ['title']}"), InlineKeyboardButton("🍿 Relacionados", callback_data=f"related_{movie_id}")]]
            video_reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_video(
                chat_id=query.message.chat.id,
                video=file_id_to_send,
                caption=video_caption,
                parse_mode="Markdown",
                reply_markup=video_reply_markup,
                protect_content=True
            )
            
            db.log_movie_view(movie_id=movie_id, user_id=user_id)
        else:
            await query.edit_message_caption(caption="😔 Desculpe, esta versão do filme não está disponível.")

    elif callback_data.startswith("related_"):
        await query.answer()
        movie_id = int(callback_data.split('_')[1])
        movie = db.get_movie_by_id(movie_id)
        
        if not movie:
            # Se não encontrar o filme base, envia uma mensagem e para.
            await context.bot.send_message(chat_id=user_id, text="Não consegui encontrar o filme original para buscar recomendações.")
            return

        # V--- A MENSAGEM AGORA É EDITÁVEL ---V
        # Envia a mensagem "Buscando..." e a guarda em uma variável para poder editá-la ou excluí-la depois.
        status_msg = await context.bot.send_message(chat_id=user_id, text=f"⏳ Buscando filmes relacionados a '{movie['title']}' que estão no nosso catálogo...")
        
        # 1. Pega as recomendações da API
        recommendations_from_api = tastedive_api.get_recommendations(movie['title'])
        
        # 2. Se a API retornou algo, filtra contra nosso banco de dados
        if recommendations_from_api:
            existing_recommendations = db.filter_existing_titles(recommendations_from_api)
        else:
            existing_recommendations = []

        # 3. Verifica se SOBROU alguma recomendação após o filtro
        if not existing_recommendations:
            # Edita a mensagem "Buscando..." para a mensagem de "não encontrado".
            await status_msg.edit_text("Não encontrei nenhuma recomendação que já esteja em nosso catálogo no momento.")
            return

        # 4. Cria os botões apenas com os filmes que temos
        keyboard = []
        for title in existing_recommendations:
            # O botão agora inicia uma busca inline para o usuário clicar e ver o card do filme.
            keyboard.append([InlineKeyboardButton(f"🔎 {title}", switch_inline_query_current_chat=title)])
            
        message_text = f"Se você gostou de '{movie['title']}', talvez também goste destes:\n\nClique em um título para buscar:"
        
        # Edita a mensagem "Buscando..." e a substitui pela lista final de filmes.
        await status_msg.edit_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard))

    # --- LÓGICA PARA O BOTÃO DE PEDIDO ---
    elif callback_data == "main_request":
        await query.answer()
        context.user_data['state'] = 'awaiting_request'
        await query.edit_message_text(
            text="Qual filme ou série você gostaria de ver no catálogo?\n\n"
                 "Por favor, envie o nome completo. Para cancelar, digite /cancelar."
        )
    
    # --- LÓGICA PARA O BOTÃO TOP FILMES (MENU DE PERÍODO) ---
    elif callback_data == "main_top":
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("🏆 Top Semana", callback_data="top_7")],
            [InlineKeyboardButton("🗓️ Top Mês", callback_data="top_30")],
            [InlineKeyboardButton("🌎 Top Geral", callback_data="top_0")],
            [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Selecione o período do ranking que deseja visualizar:", reply_markup=reply_markup)

    # --- LÓGICA PARA PROCESSAR A ESCOLHA DO RANKING ---
    elif callback_data.startswith("top_"):
        await query.answer()
        period_days = int(callback_data.split('_')[1])
        
        period_text = "Geral (Todos os Tempos)"
        if period_days == 7: period_text = "da Semana"
        if period_days == 30: period_text = "do Mês"

        await query.edit_message_text(f"🏆 Buscando o Top 10 {period_text}, aguarde...")
        
        trending_movies = db.get_trending(period_days=period_days)
        
        if not trending_movies:
            await query.edit_message_text("Ainda não há dados suficientes para gerar um ranking para este período.")
            return
            
        # Cria uma lista de botões com os filmes
        keyboard = []
        for movie in trending_movies:
            # O callback_data agora será para mostrar o card do filme específico
            button = [InlineKeyboardButton(f"{movie['title']} ({movie['year']})", callback_data=f"show_card_{movie['movie_id']}")]
            keyboard.append(button)
        
        # Adiciona o botão de voltar
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="main_top")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = f"🏆 **Top 10 {period_text}** 🏆\n\nClique em um filme abaixo para ver mais detalhes:"

        await query.edit_message_text(message_text, parse_mode="Markdown", reply_markup=reply_markup)

    elif callback_data.startswith("show_card_"):
        await query.answer()
        movie_id = int(callback_data.split('_')[2])
        movie = db.get_movie_by_id(movie_id)

        if not movie:
            await query.edit_message_text("Desculpe, este filme não foi encontrado.")
            return

        # Apaga a lista de Top Filmes para manter o chat limpo
        await query.delete_message()

        # Reutiliza a mesma lógica do "Card Viral" que já temos
        bot_username = context.bot.username
        watch_url = f"https://t.me/{bot_username}?start=watch_{movie['movie_id']}"
        
        keyboard = [[
            InlineKeyboardButton("Assistir ⏯️", url=watch_url),
            InlineKeyboardButton("Compartilhar ❤️", switch_inline_query=movie['title'])
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        invisible_char = "\u200b"
        card_text_content = (
            f"[{invisible_char}]({movie['poster_url']})"
            f"🎬 *{movie['title']}* ({movie['year']})\n"
            f"🎭 *Gênero:* {movie['genre']}"
        )
        
        # Envia o card como uma nova mensagem
        await context.bot.send_message(
            chat_id=user_id,
            text=card_text_content,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=False
        )

    # --- LÓGICA PARA O BOTÃO DE VOLTAR AO MENU PRINCIPAL ---
    elif callback_data == "back_to_main":
        await query.answer()
        await start(update, context)
        
    # --- LÓGICA DE PAGAMENTO VIP ---
    elif callback_data == "main_vip":
        await query.answer()
        if db.is_user_vip(user_id):
            await query.edit_message_text("✨ Você já é um membro VIP! Aproveite o catálogo.")
            return

        user_details = db.get_user_details(user_id)
        active_payment_id = user_details.get('active_payment_id') if user_details else None
        
        if active_payment_id:
            await query.edit_message_text("⏳ Verificando seu pagamento anterior, aguarde...")
            status = payments.check_payment_status(active_payment_id)
            if status == 'created':
                await query.edit_message_text("Você já possui uma cobrança PIX pendente. Por favor, realize o pagamento ou aguarde expirar antes de gerar uma nova.")
                return 

        await query.edit_message_text("⏳ Gerando sua cobrança PIX, aguarde...")
        vip_price = 2.00
        payment_data = payments.create_pix_payment(user_id=user_id, amount=vip_price)
        
        if payment_data and payment_data.get("qr_code_base64"):
            payment_id = payment_data['payment_id']
            db.set_user_active_payment_id(user_id, payment_id)

            base64_string = payment_data['qr_code_base64']
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            qr_image_data = base64.b64decode(base64_string)
            qr_image_file = io.BytesIO(qr_image_data)
            pix_code = payment_data['qr_code_text']

            caption = (
                f"✨ **Seu Acesso VIP está quase pronto!** ✨\n\n"
                f"Para concluir, faça o pagamento de R${vip_price:.2f} via PIX.\n\n"
                f"**1.** Escaneie o QR Code acima.\n"
                f"**2.** Ou use o PIX Copia e Cola abaixo:\n"
                f"`{pix_code}`\n\n"
                "Após pagar, clique no botão 'Já Paguei' para verificar.\n\n"
                "⚠️ *Este código de pagamento expira em alguns minutos. Garanta sua vaga!*"
            )
            keyboard = [[InlineKeyboardButton("✅ Já Paguei", callback_data=f"check_payment_{payment_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.delete_message()
            await context.bot.send_photo(
                chat_id=user_id, photo=qr_image_file, caption=caption,
                parse_mode="Markdown", reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("😕 Desculpe, não foi possível gerar a cobrança PIX no momento. Tente novamente mais tarde.")

    elif callback_data.startswith("check_payment_"):
        payment_id = callback_data.split('_')[2]

        now = time.time()
        # Pega o horário da última verificação, ou 0 se nunca verificou
        last_check = context.user_data.get('last_payment_check', 0)

        # Se a última verificação foi há menos de 60 segundos, bloqueia.
        if now - last_check < 60:
            await query.answer(
                text=f"✋ Por favor, aguarde {int(60 - (now - last_check))} segundos antes de verificar novamente.",
                show_alert=True
            )
            return

        # Se passou, registra o novo horário e continua
        context.user_data['last_payment_check'] = now

        status = payments.check_payment_status(payment_id)

        # A verificação agora é muito mais simples
        if status == 'paid':
            await query.answer()
            db.set_user_as_vip(user_id, duration_days=30)
            db.clear_user_active_payment_id(user_id)
            await query.message.delete()
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 **Pagamento confirmado!** 🎉\n\n"
                     "Você agora é um membro VIP! Aproveite todo o nosso catálogo sem limites. Obrigado pelo seu apoio!",
                parse_mode="Markdown"
            )
        else:
            await query.answer(
                text=" Pagamento ainda não confirmado.\n\nA confirmação pode levar alguns instantes.",
                show_alert=True
            )
    # --- FIM DA LÓGICA DE PAGAMENTO ---

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lida com as buscas em modo inline."""
    query_text = update.inline_query.query

    if not query_text:
        help_result = [
            InlineQueryResultArticle(
                id="help_bubble",
                title="Digite o nome do Filme",
                description="Comece a digitar no teclado para que os resultados da busca apareçam aqui.",
                thumbnail_url="https://cdn-icons-png.flaticon.com/512/3931/3931294.png",
                input_message_content=InputTextMessageContent("👍")
            )
        ]
        await update.inline_query.answer(help_result, is_personal=True, cache_time=5)
        return
    
    results_from_db = db.search_movies(query_text)
    results = []
    for movie in results_from_db:
        if movie.get('poster_url'):
            bot_username = context.bot.username
            watch_url = f"https://t.me/{bot_username}?start=watch_{movie['movie_id']}"

            keyboard = [[
                InlineKeyboardButton("Assistir ⏯️", url=watch_url),
            ],
            [InlineKeyboardButton("Compartilhar ❤️", switch_inline_query=movie['title'])]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # V--- INÍCIO DA CORREÇÃO ---V
            
            # 1. Este será o texto enviado QUANDO O USUÁRIO CLICAR.
            # Removemos o link do pôster para evitar a "citação".
            card_text_content = (
                f"🎬 *{movie['title']}* ({movie['year']})\n"
                f"🎭 *Gênero:* {movie['genre']}"
            )
            
            results.append(
                # 2. Voltamos para 'InlineQueryResultArticle'
                InlineQueryResultArticle(
                    id=f"movie_{movie['movie_id']}",
                    
                    # 3. Isso cria a LISTA VERTICAL que você quer
                    title=movie['title'],
                    description=f"{movie['year']} - {movie['genre']}",
                    thumbnail_url=movie.get('poster_url'),
                    
                    # 4. Anexa os botões
                    reply_markup=reply_markup,
                    
                    # 5. Define a MENSAGEM DE SAÍDA como o texto limpo
                    input_message_content=InputTextMessageContent(
                        card_text_content,
                        parse_mode="Markdown",
                        # Garante que NENHUMA preview de link seja gerada
                        disable_web_page_preview=True 
                    )
                )
            )
            # ^--- FIM DA CORREÇÃO ---^

    await update.inline_query.answer(results)

async def watch_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lida com o comando /watch OU é chamada pela função start."""
    if update.message:
        await update.message.delete()
    if not context.args:
        return
    movie_id = context.args[0]
    user_id = update.effective_user.id
    if db.is_user_vip(user_id):
        movie = db.get_movie_by_id(movie_id)
        if movie and movie.get('poster_url'):
            caption = (
                f"🎬 *{movie['title']}*\n\n"
                f"🗓️ *Ano:* {movie['year']}\n"
                f"🎭 *Gênero:* {movie['genre']}\n\n"
                f"📝 *Sinopse:* {movie['description']}\n\n"
                "---\n"
                "Selecione o áudio desejado abaixo:"
            )
            keyboard = [[
                InlineKeyboardButton("Dublado 🇧🇷", callback_data=f"play_{movie_id}_dub"),
                InlineKeyboardButton("Legendado 🇺🇸", callback_data=f"play_{movie_id}_sub")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=movie['poster_url'],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Filme não encontrado ou sem pôster disponível.")
    else:
        keyboard = [[InlineKeyboardButton("Adquirir Acesso VIP 🚀", callback_data="main_vip")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = (
            "✨ *Você precisa do Passe Premium para assistir!* ✨\n\n"
            "✅ Acesse TODOS os filmes e séries disponíveis.\n"
            "✅ Ajude a manter o bot online e sempre melhorando.\n\n"
            "Clique no botão abaixo para se tornar VIP!"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lida com mensagens de texto para capturar respostas a perguntas do bot."""
    user_state = context.user_data.get('state')
    if user_state == 'awaiting_request':
        del context.user_data['state']
        requested_title = update.message.text
        user_id = update.effective_user.id
        if db.add_request(user_id=user_id, title=requested_title):
            await update.message.reply_text(
                f"✅ Obrigado! Sua sugestão \"{requested_title}\" foi registrada e será analisada.\n\n"
                "Se aprovada, estará disponível em nosso catálogo em até 24 horas!"
            )
        else:
            await update.message.reply_text("😕 Desculpe, ocorreu um erro ao salvar seu pedido. Tente novamente mais tarde.")

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancela a conversa atual."""
    if 'state' in context.user_data:
        del context.user_data['state']
        await update.message.reply_text("Operação cancelada.")
    else:
        await update.message.reply_text("Não há nenhuma operação para cancelar.")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia uma mensagem de ajuda explicando como usar o bot."""
    help_text = (
        "Olá! Eu sou o Cine Pipoca, seu assistente de filmes. Veja como me usar:\n\n"
        "🔎 **Para Buscar um Filme:**\n"
        "Vá em qualquer chat, digite o `@username` do bot e comece a escrever o nome do filme. Uma lista de resultados aparecerá!\n\n"
        "💡 **Pedir um Filme:**\n"
        "Use o botão 'Pedir Filme/Série' no menu principal para sugerir um título que você não encontrou.\n\n"
        "🏆 **Top Filmes:**\n"
        "Quer saber o que está em alta? Clique no botão 'Top Filmes' no menu e escolha o período.\n\n"
        "🚀 **Acesso VIP:**\n"
        "O acesso VIP te dá direito a assistir todo o catálogo. Você pode adquirir o seu através do botão no menu principal."
    )
    # Adiciona o username do bot dinamicamente
    help_text = help_text.replace("@username", f"@{context.bot.username}")
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- Definição dos Handlers ---
start_handler = CommandHandler("start", start)
button_click_handler = CallbackQueryHandler(button_handler)
inline_search_handler = InlineQueryHandler(inline_query_handler)
watch_handler = CommandHandler("watch", watch_command_handler)
text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler)
cancel_command_handler = CommandHandler("cancelar", cancel_handler)
help_command_handler = CommandHandler("help", help_handler)
request_command_handler = CommandHandler("pedir", request_command_handler)