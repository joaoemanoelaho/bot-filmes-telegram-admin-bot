import os
import re
import uuid
from thefuzz import fuzz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
import tmdb_api
from utils import safe_edit_message, notificar_usuarios_radar

async def _index_series_episode(tmdb_id: int, season_number: int, episode_number: int, audio_type: str, file_id: str, unique_id: str, msg_id: int) -> (bool, str, list):
    try:
        series_data = db.get_or_create_series(tmdb_id)
        if not series_data: return False, "❌ Erro: Não foi possível buscar/criar a série no DB.", []
        
        season_data = db.get_or_create_season(series_id=series_data['id'], season_number=season_number)
        if not season_data: return False, "❌ Erro: Não foi possível buscar/criar a temporada.", []
        
        success = db.add_or_update_episode(
            season_id=season_data['id'], tmdb_id=tmdb_id, season_number=season_number,
            episode_number=episode_number, audio_type=audio_type, file_id=file_id,
            unique_id=unique_id, msg_id=msg_id
        )

        users_to_alert = []
        if success:
            users_to_alert = db.verificar_pedidos_atendidos(series_data['title'])
            msg = f"✅ Episódio '{series_data['title']} S{season_number:02d} E{episode_number:02d}' indexado!"
            return True, msg, users_to_alert
        return False, "❌ Erro desconhecido ao salvar o episódio.", []
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no _index_series_episode: {e}")
        return False, f"❌ Erro Crítico no Worker: {e}", []

async def _process_movie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, file_name: str):
    status_msg = None
    try:
        file_id = update.message.video.file_id
        unique_id = update.message.video.file_unique_id
        msg_id = update.message.message_id 
        
        status_msg = await update.message.reply_text(f"⏳ Processando FILME '{file_name}'...")
        
        audio_type_match = re.search(r'\[(DUB|LEG)\]', file_name, re.IGNORECASE)
        if not audio_type_match:
            await safe_edit_message(status_msg, f"❓ Falha (Filme): O nome precisa conter [DUB] ou [LEG].")
            return
        
        audio_type = audio_type_match.group(1).upper()
        temp_name = re.sub(r'\s*\[(DUB|LEG)\]\s*', '', file_name, flags=re.IGNORECASE).strip()
        search_query, _ = os.path.splitext(temp_name)
        search_query_clean = re.sub(r'\s*4k?\s*$', '', search_query, flags=re.IGNORECASE).strip()

        movie_options = tmdb_api.search_movie_options(search_query_clean)

        if not movie_options:
            await safe_edit_message(status_msg, f"❌ (Filme) Não encontrei resultados para '{search_query_clean}'.")
            return

        high_confidence_match = None
        if len(movie_options) == 1:
            high_confidence_match = movie_options[0]
        else:
            for option in movie_options:
                option_full_title = f"{option['title']} ({option['year']})"
                if fuzz.ratio(search_query_clean.lower(), option_full_title.lower()) > 85:
                    high_confidence_match = option
                    break

        if high_confidence_match:
            await safe_edit_message(status_msg, f"✅ (Filme) Correspondência: '{high_confidence_match['title']}'. Salvando...")
            movie_details = high_confidence_match
            existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
            
            if existing_movie:
                success = db.update_movie_file_id(
                    movie_id=existing_movie['movie_id'], file_id=file_id, unique_id=unique_id,
                    msg_id=msg_id, audio_type=audio_type
                )
                msg = f"🔄 Filme '{movie_details['title']}' atualizado!"
            else:
                if audio_type == 'DUB': 
                    movie_details['dubbed_file_id'] = file_id
                    movie_details['dubbed_unique_id'] = unique_id
                    movie_details['dubbed_msg_id'] = msg_id
                else: 
                    movie_details['subtitled_file_id'] = file_id
                    movie_details['subtitled_unique_id'] = unique_id
                    movie_details['subtitled_msg_id'] = msg_id 
                
                movie_details.pop('button_text', None)
                success = db.add_movie(movie_details)
                msg = f"✅ Filme '{movie_details['title']}' adicionado!"

            if success:
                users = db.verificar_pedidos_atendidos(movie_details['title'])
                await notificar_usuarios_radar(context, users, movie_details['title'])
            await safe_edit_message(status_msg, msg)

        else:
            request_id = str(uuid.uuid4())
            context.bot_data[request_id] = {
                'file_id': file_id, 'unique_id': unique_id, 'msg_id': msg_id,
                'audio_type': audio_type, 'options': movie_options
            }
            message_text = f"❓ **Ajuda (Filme)**\n\nArquivo: `{search_query_clean}`\n\nQual o correto?"
            keyboard = [[InlineKeyboardButton(f"{opt['title']} ({opt['year']})", callback_data=f"confirm_movie_{request_id}_{opt['tmdb_id']}")] for opt in movie_options]
            keyboard.append([InlineKeyboardButton("❌ Nenhum destes", callback_data=f"confirm_movie_{request_id}_ignore")])
            await safe_edit_message(status_msg, text=message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no _process_movie_upload: {e}")
        await safe_edit_message(status_msg, f"❌ Erro crítico (Filme): {e}")

async def _process_series_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, file_name: str, series_match: re.Match):
    status_msg = None
    try:
        file_id = update.message.video.file_id
        unique_id = update.message.video.file_unique_id
        msg_id = update.message.message_id
        
        status_msg = await update.message.reply_text(f"⏳ Processando SÉRIE '{file_name}'...")
        
        series_title_clean = series_match.group(1).strip() 
        series_year = series_match.group(2).strip() if series_match.group(2) else None
        season_number = int(series_match.group(3)) 
        episode_number = int(series_match.group(4))
        audio_type = series_match.group(5).upper() 
        
        series_options = tmdb_api.search_series_options(series_title_clean, year=series_year)

        if not series_options:
            await safe_edit_message(status_msg, f"❌ (Série) Não encontrei resultados no TMDb para '{series_title_clean}'.")
            return

        high_confidence_match, best_ratio = None, 0
        for option in series_options:
            titulo_pt = option.get('title', '')
            titulo_original = option.get('original_name', '') or option.get('original_title', '')
            
            ratio_pt = fuzz.ratio(series_title_clean.lower(), titulo_pt.lower())
            ratio_en = fuzz.ratio(series_title_clean.lower(), titulo_original.lower())
            
            current_max = max(ratio_pt, ratio_en)
            if current_max > best_ratio:
                best_ratio = current_max
                high_confidence_match = option

        if high_confidence_match and best_ratio >= 85:
            tmdb_id = high_confidence_match['tmdb_id']
            await safe_edit_message(status_msg, f"✅ (Série) Encontrada: '{high_confidence_match['title']}' ({best_ratio}%). Salvando...")
            
            success, msg, users_alert = await _index_series_episode(
                tmdb_id=tmdb_id, season_number=season_number, episode_number=episode_number,
                audio_type=audio_type, file_id=file_id, unique_id=unique_id, msg_id=msg_id
            )
            await safe_edit_message(status_msg, msg)

            if users_alert: await notificar_usuarios_radar(context, users_alert, series_title_clean)

        else:
            request_id = str(uuid.uuid4())
            context.bot_data[request_id] = {
                'file_id': file_id, 'unique_id': unique_id, 'msg_id': msg_id,
                'audio_type': audio_type, 'options': series_options,
                'season_number': season_number, 'episode_number': episode_number
            }
            
            match_info = f" (Melhor chute: {best_ratio}%)" if high_confidence_match else ""
            message_text = f"❓ **Dúvida (Série)**{match_info}\n\nArquivo: `{file_name}`\n\nO robô não teve certeza. Qual é a correta?"
            
            keyboard = [[InlineKeyboardButton(f"{opt['title']} ({opt['year']})", callback_data=f"confirm_series_{request_id}_{opt['tmdb_id']}")] for opt in series_options]
            keyboard.append([InlineKeyboardButton("❌ Nenhuma destas", callback_data=f"confirm_series_{request_id}_ignore")])
            
            await safe_edit_message(status_msg, text=message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no _process_series_upload: {e}")
        await safe_edit_message(status_msg, f"❌ Erro crítico (Série): {e}")
        