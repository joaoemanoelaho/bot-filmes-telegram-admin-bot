import re
import os
import uuid
from thefuzz import fuzz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

import database as db
import tmdb_api
from config import ADMIN_IDS, STORAGE_CHANNEL_ID, STORAGE_CHANNEL_ID_SERIES

# Importando das nossas novas "caixas de ferramentas"
from utils import SERIES_REGEX, safe_answer_query, safe_edit_message, safe_send_message, notificar_usuarios_radar
from core_indexer import _index_series_episode, _process_movie_upload, _process_series_upload

async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try: await update.message.reply_text("🤖 Olá, Admin! Bot de indexação (Filmes e Séries) online.")
    except Exception as e: print(f"⚠️ Erro de rede no /start (ignorado): {e}")

async def button_handler_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    callback_data = query.data

    if query.from_user.id not in ADMIN_IDS:
        await safe_answer_query(query, "Ação restrita.", show_alert=True)
        return

    # --- ROTEADOR DE FILMES ---
    if callback_data.startswith("confirm_movie_"):
        await safe_answer_query(query)
        parts = callback_data.split('_')
        request_id, action = parts[2], parts[3]
        request_data = context.bot_data.get(request_id)

        if not request_data:
            await safe_edit_message(query.message, "❌ Este pedido de FILME expirou.")
            return
            
        if action == "ignore":
            await safe_edit_message(query.message, "Ok, FILME ignorado.")
            del context.bot_data[request_id]
            return

        try: tmdb_id_to_confirm = int(action)
        except ValueError: return
            
        chosen_movie_details = next((opt for opt in request_data['options'] if opt.get('tmdb_id') == tmdb_id_to_confirm), None)
        if not chosen_movie_details:
            await safe_edit_message(query.message, "❌ Erro: Opção de FILME inválida.")
            del context.bot_data[request_id]
            return

        await safe_edit_message(query.message, f"⏳ Processando FILME: '{chosen_movie_details['title']}'...")
        try:
            file_id, unique_id, msg_id = request_data['file_id'], request_data['unique_id'], request_data['msg_id']
            audio_type = request_data['audio_type']
            
            existing_movie = db.find_movie_by_title_and_year(title=chosen_movie_details['title'], year=chosen_movie_details['year'])
            if existing_movie:
                success = db.update_movie_file_id(
                    movie_id=existing_movie['movie_id'], file_id=file_id, unique_id=unique_id,
                    msg_id=msg_id, audio_type=audio_type
                )
                msg = f"🔄 Filme '{chosen_movie_details['title']}' atualizado!"
            else:
                if audio_type.upper() == 'DUB':
                    chosen_movie_details['dubbed_file_id'] = file_id
                    chosen_movie_details['dubbed_unique_id'] = unique_id 
                    chosen_movie_details['dubbed_msg_id'] = msg_id 
                else:
                    chosen_movie_details['subtitled_file_id'] = file_id
                    chosen_movie_details['subtitled_unique_id'] = unique_id
                    chosen_movie_details['subtitled_msg_id'] = msg_id 
                
                chosen_movie_details.pop('button_text', None)
                success = db.add_movie(chosen_movie_details)
                msg = f"✅ Filme '{chosen_movie_details['title']}' adicionado!"

            if success:
                users = db.verificar_pedidos_atendidos(chosen_movie_details['title'])
                await notificar_usuarios_radar(context, users, chosen_movie_details['title'])
            
            await safe_edit_message(query.message, msg)
            del context.bot_data[request_id]
        except Exception as e:
            await safe_edit_message(query.message, f"❌ ERRO CRÍTICO (Filme): {e}")

    # --- ROTEADOR DE SÉRIES ---
    elif callback_data.startswith("confirm_series_"):
        await safe_answer_query(query)
        parts = callback_data.split('_')
        request_id, action = parts[2], parts[3]
        request_data = context.bot_data.get(request_id)

        if not request_data:
            await safe_edit_message(query.message, "❌ Este pedido de SÉRIE expirou.")
            return
            
        if action == "ignore":
            await safe_edit_message(query.message, "Ok, SÉRIE ignorada.")
            del context.bot_data[request_id]
            return

        try: tmdb_id_to_confirm = int(action)
        except ValueError: return
            
        chosen_series_details = next((opt for opt in request_data['options'] if opt.get('tmdb_id') == tmdb_id_to_confirm), None)
        if not chosen_series_details:
            await safe_edit_message(query.message, "❌ Erro: Opção de SÉRIE inválida.")
            del context.bot_data[request_id]
            return
            
        await safe_edit_message(query.message, f"⏳ Processando SÉRIE: '{chosen_series_details['title']}'...")
        success, msg, users_alert = await _index_series_episode(
            tmdb_id=tmdb_id_to_confirm, season_number=request_data['season_number'],
            episode_number=request_data['episode_number'], audio_type=request_data['audio_type'],
            file_id=request_data['file_id'], unique_id=request_data['unique_id'], msg_id=request_data['msg_id']
        )
        await safe_edit_message(query.message, msg)

        if users_alert: await notificar_usuarios_radar(context, users_alert, chosen_series_details['title'])
        del context.bot_data[request_id]

async def get_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS: return 
    try:
        if update.message.reply_to_message and update.message.reply_to_message.video:
            file_id = update.message.reply_to_message.video.file_id
            await update.message.reply_text(f"Video File ID:\n`{file_id}`", parse_mode="Markdown")
        else: await update.message.reply_text("Responda a um vídeo com /getid.")
    except Exception as e: print(f"⚠️ Erro no /getid: {e}")

async def get_chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    try: await update.message.reply_text(f"O ID deste chat é: `{chat_id}`")
    except Exception as e: print(f"⚠️ Erro no /id: {e}")

async def admin_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS or not update.message.video: return
        
    file_name = update.message.caption or update.message.video.file_name
    if not file_name:
        await update.message.reply_text("❗️Erro: O vídeo precisa ter um caption ou nome.")
        return
        
    clean_file_name = file_name.rsplit('.', 1)[0] if file_name.lower().endswith(('.mp4', '.mkv', '.avi')) else file_name
    series_match = SERIES_REGEX.search(clean_file_name)
    
    if series_match: await _process_series_upload(update, context, clean_file_name, series_match)
    else: await _process_movie_upload(update, context, clean_file_name)

async def new_movie_in_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post or update.message
    if not post or post.chat.id != STORAGE_CHANNEL_ID or not post.video: return

    file_name = post.caption or post.video.file_name
    if not file_name: return
    
    file_id, unique_id, msg_id = post.video.file_id, post.video.file_unique_id, post.message_id
    
    audio_type_match = re.search(r'\[(DUB|LEG)\]', file_name, re.IGNORECASE)
    if not audio_type_match: return
        
    audio_type = audio_type_match.group(1).upper()
    temp_name = re.sub(r'\s*\[(DUB|LEG)\]\s*', '', file_name, flags=re.IGNORECASE).strip()
    search_query_clean = re.sub(r'\s*4k?\s*$', '', os.path.splitext(temp_name)[0], flags=re.IGNORECASE).strip()
    
    movie_options = tmdb_api.search_movie_options(search_query_clean)
    if not movie_options:
        await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❌ (Filme) Sem resultados para '{search_query_clean}'.")
        return

    high_confidence_match = next((opt for opt in movie_options if fuzz.ratio(search_query_clean.lower(), f"{opt['title']} ({opt['year']})".lower()) > 85), None)

    if high_confidence_match:
        status_msg = await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"⏳ Indexando FILME: '{search_query_clean}'...")
        movie_details = high_confidence_match
        existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
        
        if existing_movie:
            db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=file_id, unique_id=unique_id, msg_id=msg_id, audio_type=audio_type)
            msg = f"🔄 Filme '{movie_details['title']}' atualizado!"
        else:
            if audio_type == 'DUB': movie_details.update({'dubbed_file_id': file_id, 'dubbed_unique_id': unique_id, 'dubbed_msg_id': msg_id})
            else: movie_details.update({'subtitled_file_id': file_id, 'subtitled_unique_id': unique_id, 'subtitled_msg_id': msg_id})
            movie_details.pop('button_text', None)
            if db.add_movie(movie_details):
                await notificar_usuarios_radar(context, db.verificar_pedidos_atendidos(movie_details['title']), movie_details['title'])
            msg = f"✅ Filme '{movie_details['title']}' adicionado!"
        await safe_edit_message(status_msg, msg)
    else:
        request_id = str(uuid.uuid4())
        context.bot_data[request_id] = {'file_id': file_id, 'unique_id': unique_id, 'msg_id': msg_id, 'audio_type': audio_type, 'options': movie_options}
        keyboard = [[InlineKeyboardButton(f"{opt['title']} ({opt['year']})", callback_data=f"confirm_movie_{request_id}_{opt['tmdb_id']}")] for opt in movie_options]
        keyboard.append([InlineKeyboardButton("❌ Nenhum destes", callback_data=f"confirm_movie_{request_id}_ignore")])
        await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❓ **Ajuda (Filme)**\n\nArquivo: `{search_query_clean}`\n\nQual o correto?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def new_series_in_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post or update.message
    if not post or post.chat.id != STORAGE_CHANNEL_ID_SERIES or not post.video: return
    
    file_name = post.caption or post.video.file_name
    if not file_name: return
    
    file_id, unique_id, msg_id = post.video.file_id, post.video.file_unique_id, post.message_id
    clean_file_name = file_name.rsplit('.', 1)[0] if file_name.lower().endswith(('.mp4', '.mkv', '.avi')) else file_name
    clean_file_name = re.sub(r'^[^\w(]+', '', re.sub(r'[★☆✦✧✨⭐❖❥•■□◆◇●○♦♥♡♠♣☀☁☂☃☄☾☽♬♪♫♩]', '', re.sub(r"\s+", " ", clean_file_name.replace("…", "...").replace("_", " ").strip()))).strip()
    
    series_match = SERIES_REGEX.search(clean_file_name)
    if not series_match:
        await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❌ Falha: O nome '{clean_file_name}' não bate com 'Nome SXX EXX [AUDIO]'.")
        return
        
    series_title_clean, series_year, season_number, episode_number, audio_type = series_match.group(1).strip(), series_match.group(2), int(series_match.group(3)), int(series_match.group(4)), series_match.group(5).upper()
    
    series_options = tmdb_api.search_series_options(series_title_clean, year=series_year)
    if not series_options:
        await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❌ (Série) Sem resultados para '{series_title_clean}'.")
        return

    high_confidence_match, best_ratio = None, 0
    for option in series_options:
        current_max = max(fuzz.ratio(series_title_clean.lower(), option.get('title', '').lower()), fuzz.ratio(series_title_clean.lower(), (option.get('original_name', '') or option.get('original_title', '')).lower()))
        if current_max > best_ratio:
            best_ratio, high_confidence_match = current_max, option

    if high_confidence_match and best_ratio >= 85:
        status_msg = await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"⏳ Indexando SÉRIE: '{clean_file_name}'...")
        success, msg, users_alert = await _index_series_episode(high_confidence_match['tmdb_id'], season_number, episode_number, audio_type, file_id, unique_id, msg_id)
        await safe_edit_message(status_msg, msg)
        if users_alert: await notificar_usuarios_radar(context, users_alert, series_title_clean)
    else:
        request_id = str(uuid.uuid4())
        context.bot_data[request_id] = {'file_id': file_id, 'unique_id': unique_id, 'msg_id': msg_id, 'audio_type': audio_type, 'options': series_options, 'season_number': season_number, 'episode_number': episode_number}
        keyboard = [[InlineKeyboardButton(f"{opt['title']} ({opt['year']})", callback_data=f"confirm_series_{request_id}_{opt['tmdb_id']}")] for opt in series_options]
        keyboard.append([InlineKeyboardButton("❌ Nenhuma destas", callback_data=f"confirm_series_{request_id}_ignore")])
        await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❓ **Ajuda (Série)**\n\nArquivo: `{clean_file_name}`\n\nQual série é esta?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# === EXPORTAÇÃO DOS HANDLERS (Igual ao seu original) ===
start_handler = CommandHandler("start", start_admin)
button_click_handler = CallbackQueryHandler(button_handler_admin)
get_id_command_handler = CommandHandler("getid", get_id_handler)
get_chat_id_command_handler = CommandHandler("id", get_chat_id_handler)

admin_video_handler = MessageHandler(filters.VIDEO & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_video_handler)
channel_video_handler = MessageHandler(filters.VIDEO & filters.Chat(chat_id=STORAGE_CHANNEL_ID), new_movie_in_channel_handler)
channel_series_handler = MessageHandler(filters.VIDEO & filters.Chat(chat_id=STORAGE_CHANNEL_ID_SERIES), new_series_in_channel_handler)
