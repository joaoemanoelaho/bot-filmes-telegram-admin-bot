#
# Arquivo que contém as respostas e lógicas para os comandos.
#
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import database as db
import tmdb_api
from config import ADMIN_IDS, STORAGE_CHANNEL_ID
import re
import os
from thefuzz import fuzz
import uuid
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensagem de início simples para o bot de admin."""
    await update.message.reply_text("🤖 Olá, Admin! Bot de indexação online e pronto para receber arquivos.")

async def button_handler_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa APENAS os cliques de confirmação de indexação do admin."""
    query = update.callback_query
    callback_data = query.data
    user_id = query.from_user.id

    if callback_data.startswith("confirm_"):
        if user_id not in ADMIN_IDS:
            await query.answer("Ação restrita.", show_alert=True)
            return
        
        await query.answer()
        parts = callback_data.split('_')
        request_id, action = parts[1], parts[2]
        request_data = context.bot_data.get(request_id)

        if not request_data:
            await query.edit_message_text("❌ Este pedido expirou.")
            return
        if action == "ignore":
            await query.edit_message_text("Ok, arquivo ignorado.")
            del context.bot_data[request_id]
            return

        tmdb_id_to_confirm = int(action)
        chosen_movie_details = next((opt for opt in request_data['options'] if opt['tmdb_id'] == tmdb_id_to_confirm), None)
        
        if not chosen_movie_details:
            await query.edit_message_text("❌ Erro: Opção inválida.")
            del context.bot_data[request_id]
            return

        await query.edit_message_text(f"⏳ Processando: '{chosen_movie_details['title']}'...")
        
        existing_movie = db.find_movie_by_title_and_year(title=chosen_movie_details['title'], year=chosen_movie_details['year'])
        if existing_movie:
            success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=request_data['file_id'], audio_type=request_data['audio_type'])
            msg = f"🔄 Filme '{chosen_movie_details['title']}' atualizado!" if success else "❌ Erro ao ATUALIZAR."
        else:
            if request_data['audio_type'].upper() == 'DUB':
                chosen_movie_details['dubbed_file_id'] = request_data['file_id']
            else:
                chosen_movie_details['subtitled_file_id'] = request_data['file_id']
            
            chosen_movie_details.pop('button_text', None)
            success = db.add_movie(chosen_movie_details)
            msg = f"✅ Filme '{chosen_movie_details['title']}' adicionado!" if success else "❌ Erro ao SALVAR."
            
        await query.edit_message_text(msg)
        del context.bot_data[request_id]
        return
    
async def get_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retorna o file_id de uma mídia, APENAS PARA ADMINS."""
    if update.effective_user.id not in ADMIN_IDS:
        print(f"[ALERTA] Uso não autorizado do /getid pelo usuário {update.effective_user.id}.")
        return 
    if update.message.reply_to_message and update.message.reply_to_message.video:
        file_id = update.message.reply_to_message.video.file_id
        await update.message.reply_text(f"Video File ID:\n`{file_id}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("Responda a um vídeo com /getid para obter o File ID.")

async def add_movie_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Escuta por vídeos enviados pelo admin, busca as opções no TMDb
    e pede confirmação se houver múltiplos resultados.
    Agora lê o caption e remove "4K" do nome.
    """
    if update.effective_user.id not in ADMIN_IDS:
        return

    # 1. Validação e extração de dados do vídeo
    if not update.message.video:
        await update.message.reply_text("❗️Erro: Envie um vídeo válido.")
        return
    
    # Tenta pegar o caption primeiro, depois o nome do arquivo
    file_name = update.message.caption or update.message.video.file_name
    
    if not file_name:
        await update.message.reply_text("❗️Erro: O vídeo precisa ter um caption ou nome de arquivo válido.")
        return
    
    file_size_mb = update.message.video.file_size / (1024**2) if update.message.video.file_size else 0
    MAX_FILE_SIZE_MB = 3900  # Limite seguro (Telegram permite 4GB)
    
    if file_size_mb > MAX_FILE_SIZE_MB:
        await update.message.reply_text(
            f"⚠️ **Arquivo muito grande!**\n\n"
            f"📊 Tamanho: {file_size_mb:.0f}MB\n"
            f"📌 Limite: {MAX_FILE_SIZE_MB}MB\n\n"
            f"❌ Arquivo não pode ser indexado.\n\n"
            f"💡 Dica: Considere usar uma versão em qualidade menor (1080p em vez de 4K)."
        )
        return
    
    file_id = update.message.video.file_id
    status_msg = await update.message.reply_text(f"⏳ Processando '{file_name}'...")

    # Extrai tipo de áudio
    audio_type_match = re.search(r'\[(DUB|LEG)\]', file_name, re.IGNORECASE)
    if not audio_type_match:
        await status_msg.edit_text(f"❓ Falha: O nome precisa conter [DUB] ou [LEG].")
        return
    
    audio_type = audio_type_match.group(1).upper()
    
    # Remove [DUB] ou [LEG] e 4K do nome
    temp_name = re.sub(r'\s*\[(DUB|LEG)\]\s*', '', file_name, flags=re.IGNORECASE).strip()
    search_query, _ = os.path.splitext(temp_name)  # Remove extensão
    
    # Remove "4K" ou "4k" do final e armazena versão sem 4K para busca
    search_query_clean = re.sub(r'\s*4k?\s*$', '', search_query, flags=re.IGNORECASE).strip()
    has_4k = bool(re.search(r'4k', search_query, re.IGNORECASE))
    
    # Log interno para rastreamento
    query_log = f"{search_query_clean} (4K)" if has_4k else search_query_clean
    print(f"[LOG] Processando: {query_log}")
    
    # 2. Busca pelas opções de filmes
    movie_options = tmdb_api.search_movie_options(search_query_clean)

    if not movie_options:
        await status_msg.edit_text(f"❌ Não encontrei nenhum resultado no TMDb para '{search_query_clean}'.")
        return

    # 3. Lógica de Auto-Confirmação
    high_confidence_match = None
    if len(movie_options) == 1:
        high_confidence_match = movie_options[0]
    else:
        for option in movie_options:
            option_full_title = f"{option['title']} ({option['year']})"
            ratio = fuzz.ratio(search_query_clean.lower(), option_full_title.lower())
            if ratio > 85:
                high_confidence_match = option
                break

    # 4. Decide se processa automaticamente ou se pede ajuda
    if high_confidence_match:
        await status_msg.edit_text(f"✅ Correspondência encontrada: '{high_confidence_match['title']}'. Salvando...")
        movie_details = high_confidence_match

        existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
        if existing_movie:
            success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=file_id, audio_type=audio_type)
            if success: 
                await status_msg.edit_text(f"🔄 Filme '{movie_details['title']}' atualizado com sucesso!")
            else: 
                await status_msg.edit_text(f"❌ Erro ao ATUALIZAR '{movie_details['title']}'.")
        else:
            if audio_type == 'DUB': 
                movie_details['dubbed_file_id'] = file_id
            else: 
                movie_details['subtitled_file_id'] = file_id
            movie_details.pop('button_text', None)
            success = db.add_movie(movie_details)
            if success: 
                await status_msg.edit_text(f"✅ Filme '{movie_details['title']}' adicionado com sucesso!")
            else: 
                await status_msg.edit_text(f"❌ Erro ao SALVAR '{movie_details['title']}'.")

    else:
        # 5. Se não tem certeza, pede ajuda ao admin
        request_id = str(uuid.uuid4())
        
        context.bot_data[request_id] = {
            'file_id': file_id,
            'audio_type': audio_type,
            'options': movie_options
        }
        
        message_text = f"❓ **Ajuda para Indexar**\n\nArquivo: `{query_log}`\n\nEncontrei estes resultados. Qual o correto?"
        keyboard = []
        for option in movie_options:
            callback_data_str = f"confirm_{request_id}_{option['tmdb_id']}"
            button_text = f"{option['title']} ({option['year']})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data_str)])
        
        keyboard.append([InlineKeyboardButton("❌ Nenhum destes", callback_data=f"confirm_{request_id}_ignore")])
        
        await status_msg.edit_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def get_chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retorna o ID do chat atual."""
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"O ID deste chat é: `{chat_id}`")

async def new_movie_in_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Bot indexador que lê caption ou nome do arquivo.
    Remove "4K" do nome para busca e log.
    """
    post = update.channel_post or update.message
    if not post or post.chat.id != STORAGE_CHANNEL_ID or not post.video:
        return

    file_size_mb = post.video.file_size / (1024**2) if post.video.file_size else 0
    MAX_FILE_SIZE_MB = 3900
    
    if file_size_mb > MAX_FILE_SIZE_MB:
        await context.bot.send_message(
            chat_id=ADMIN_IDS[0], 
            text=f"⚠️ Arquivo descartado: muito grande ({file_size_mb:.0f}MB > {MAX_FILE_SIZE_MB}MB)"
        )
        return

    # Tenta pegar caption primeiro, depois nome do arquivo
    file_name = post.caption or post.video.file_name
    
    if not file_name:
        return

    file_id = post.video.file_id
    
    # Extrai tipo de áudio
    audio_type_match = re.search(r'\[(DUB|LEG)\]', file_name, re.IGNORECASE)
    if not audio_type_match:
        return
        
    audio_type = audio_type_match.group(1)
    
    # Remove [DUB] ou [LEG] e 4K
    temp_name = re.sub(r'\s*\[(DUB|LEG)\]\s*', '', file_name, flags=re.IGNORECASE).strip()
    search_query, _ = os.path.splitext(temp_name)
    
    # Remove "4K" e identifica se tinha
    search_query_clean = re.sub(r'\s*4k?\s*$', '', search_query, flags=re.IGNORECASE).strip()
    has_4k = bool(re.search(r'4k', search_query, re.IGNORECASE))
    
    # Log com identificação 4K
    query_log = f"{search_query_clean} (4K)" if has_4k else search_query_clean
    print(f"[LOG CANAL] Processando: {query_log}")

    movie_options = tmdb_api.search_movie_options(search_query_clean)

    if not movie_options:
        await context.bot.send_message(chat_id=ADMIN_IDS[0], text=f"❌ Não encontrei nenhum resultado no TMDb para '{search_query_clean}'.")
        return

    # Lógica de auto-confirmação
    high_confidence_match = None
    for option in movie_options:
        ratio = fuzz.ratio(search_query_clean.lower(), f"{option['title']} ({option['year']})".lower())
        if ratio > 85:
            high_confidence_match = option
            break

    if high_confidence_match:
        status_msg = await context.bot.send_message(chat_id=ADMIN_IDS[0], text=f"⏳ Indexando automaticamente '{query_log}'...")
        
        movie_details = high_confidence_match

        existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
        if existing_movie:
            success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=file_id, audio_type=audio_type)
            if success: 
                await status_msg.edit_text(f"🔄 Filme '{movie_details['title']}' atualizado com sucesso!")
            else: 
                await status_msg.edit_text(f"❌ Erro ao ATUALIZAR '{movie_details['title']}'.")
        else:
            if audio_type.upper() == 'DUB': 
                movie_details['dubbed_file_id'] = file_id
            else: 
                movie_details['subtitled_file_id'] = file_id
            movie_details.pop('button_text', None)
            success = db.add_movie(movie_details)
            if success: 
                await status_msg.edit_text(f"✅ Filme '{movie_details['title']}' adicionado com sucesso!")
            else: 
                await status_msg.edit_text(f"❌ Erro ao SALVAR '{movie_details['title']}'.")
    else:
        request_id = str(uuid.uuid4())
        
        context.bot_data[request_id] = {
            'file_id': file_id,
            'audio_type': audio_type,
            'options': movie_options
        }
        
        message_text = f"❓ **Ajuda para Indexar**\n\nArquivo: `{query_log}`\n\nSelecione o filme correto:"
        keyboard = []
        for option in movie_options:
            callback_data_str = f"confirm_{request_id}_{option['tmdb_id']}"
            button_text = f"{option['button_text']} ({option['year']})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data_str)])
        
        keyboard.append([InlineKeyboardButton("❌ Nenhum destes", callback_data=f"confirm_{request_id}_ignore")])
        
        await context.bot.send_message(
            chat_id=ADMIN_IDS[0], text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


# --- Definição dos Handlers ---
start_handler = CommandHandler("start", start_admin)
button_click_handler = CallbackQueryHandler(button_handler_admin) # <-- Nome da função de admin
get_id_command_handler = CommandHandler("getid", get_id_handler)
admin_video_handler = MessageHandler(filters.VIDEO & ~filters.COMMAND & filters.ChatType.PRIVATE, add_movie_handler)
get_chat_id_command_handler = CommandHandler("id", get_chat_id_handler)
channel_video_handler = MessageHandler(filters.VIDEO & filters.Chat(chat_id=STORAGE_CHANNEL_ID), new_movie_in_channel_handler)