#
# Arquivo que contém as respostas e lógicas para os comandos.
# VERSÃO 4.1 - CORREÇÃO DO PARSER DE SÉRIES (ANO)
#
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import database as db
import tmdb_api
# --- MUDANÇA 1: Importar AMBAS as IDs de Canal ---
from config import ADMIN_IDS, STORAGE_CHANNEL_ID, STORAGE_CHANNEL_ID_SERIES
import re
import os
from thefuzz import fuzz
import uuid
import sys
import asyncio

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# --- MUDANÇA 2: O REGEX DE SÉRIES ---
# Este Regex é o cérebro para identificar séries.
# G1: Título, G2: (Ano) - opcional, G3: Temporada, G4: Episódio, G5: Áudio
SERIES_REGEX = re.compile(
    r"^(.*)(?: \((\d{4})\))? S(\d{1,2})\s?E(\d{1,3}) \[([A-Z0-9]+)\]$",
    re.IGNORECASE
)


# =================================================================
# === FUNÇÕES DE SEGURANÇA (COM RETENTATIVAS) ===
# =================================================================
# (Suas funções 'safe_edit_message', 'safe_send_message', 
# 'safe_answer_query' permanecem exatamente iguais. 
# Elas são perfeitas.)

async def safe_edit_message(message, new_text, **kwargs):
    """Tenta editar uma mensagem, com 3 retentativas."""
    if not message: return
    retries = 3
    delay = 2
    for i in range(retries):
        try:
            await message.edit_text(new_text, **kwargs)
            return
        except Exception as e:
            print(f"⚠️ Erro de rede ao TENTAR EDITAR (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(f"❌ FALHA AO EDITAR MENSAGEM após 3 tentativas.")

async def safe_send_message(context: ContextTypes.DEFAULT_TYPE, chat_id, text, **kwargs):
    """Tenta enviar uma mensagem, com 3 retentativas."""
    retries = 3
    delay = 2
    for i in range(retries):
        try:
            return await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception as e:
            print(f"⚠️ Erro de rede ao TENTAR ENVIAR (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(f"❌ FALHA AO ENVIAR MENSAGEM para {chat_id} após 3 tentativas.")
                return None

async def safe_answer_query(query: CallbackQuery, **kwargs):
    """Tenta responder um callback query, com 3 retentativas."""
    retries = 3
    delay = 1
    for i in range(retries):
        try:
            await query.answer(**kwargs)
            return
        except Exception as e:
            print(f"⚠️ Erro de rede ao TENTAR RESPONDER QUERY (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)
            else:
                print(f"❌ FALHA AO RESPONDER QUERY após 3 tentativas.")


# =================================================================
# === NOVAS FUNÇÕES "WORKER" (PARA EVITAR REPETIÇÃO) ===
# =================================================================

async def _index_series_episode(
    tmdb_id: int, 
    season_number: int, 
    episode_number: int, 
    audio_type: str, 
    file_id: str
) -> (bool, str):
    """
    Função "Worker" que faz todo o trabalho de indexar um episódio.
    Busca/cria a série, a temporada e o episódio.
    Retorna (True/False, "Mensagem de Resultado")
    """
    try:
        # 1. Busca/Cria a Série
        series_data = db.get_or_create_series(tmdb_id)
        if not series_data:
            return False, "❌ Erro: Não foi possível buscar/criar a série no DB."
        
        # 2. Busca/Cria a Temporada
        season_data = db.get_or_create_season(
            series_id=series_data['id'], 
            season_number=season_number
        )
        if not season_data:
            return False, "❌ Erro: Não foi possível buscar/criar a temporada no DB."
        
        # 3. Adiciona/Atualiza o Episódio
        success = db.add_or_update_episode(
            season_id=season_data['id'],
            tmdb_id=tmdb_id, # Passa o tmdb_id para a busca de nome de ep
            season_number=season_number,
            episode_number=episode_number,
            audio_type=audio_type,
            file_id=file_id
        )
        
        if success:
            msg = f"✅ Episódio '{series_data['title']} S{season_number:02d} E{episode_number:02d}' indexado!"
            return True, msg
        else:
            return False, "❌ Erro desconhecido ao salvar o episódio."
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no _index_series_episode: {e}")
        import traceback
        traceback.print_exc()
        return False, f"❌ Erro Crítico no Worker: {e}"


# =================================================================
# === HANDLERS PRINCIPAIS (ATUALIZADOS) ===
# =================================================================

async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensagem de início simples (sem mudança)."""
    try:
        await update.message.reply_text("🤖 Olá, Admin! Bot de indexação (Filmes e Séries) online.")
    except Exception as e:
        print(f"⚠️ Erro de rede no /start (ignorado): {e}")

async def button_handler_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa cliques de confirmação.
    AGORA SUPORTA 'confirm_movie_' E 'confirm_series_'.
    """
    query = update.callback_query
    if not query: return
        
    callback_data = query.data
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        await safe_answer_query(query, "Ação restrita.", show_alert=True)
        return

    # --- ROTEADOR DE FILMES ---
    if callback_data.startswith("confirm_movie_"):
        print("[Handlers] Botão 'confirm_movie_' detectado.")
        await safe_answer_query(query)
        parts = callback_data.split('_')
        request_id, action = parts[2], parts[3]
        
        request_data = context.bot_data.get(request_id)

        if not request_data:
            await safe_edit_message(query.message, "❌ Este pedido de FILME expirou.")
            return
            
        if action == "ignore":
            await safe_edit_message(query.message, "Ok, FILME ignorado.")
            if request_id in context.bot_data: del context.bot_data[request_id]
            return

        try:
            tmdb_id_to_confirm = int(action)
        except ValueError:
            return
            
        chosen_movie_details = next((opt for opt in request_data['options'] if opt.get('tmdb_id') == tmdb_id_to_confirm), None)
        
        if not chosen_movie_details:
            await safe_edit_message(query.message, "❌ Erro: Opção de FILME inválida.")
            if request_id in context.bot_data: del context.bot_data[request_id]
            return

        await safe_edit_message(query.message, f"⏳ Processando FILME: '{chosen_movie_details['title']}'...")
        
        try:
            existing_movie = db.find_movie_by_title_and_year(title=chosen_movie_details['title'], year=chosen_movie_details['year'])
            if existing_movie:
                success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=request_data['file_id'], audio_type=request_data['audio_type'])
                msg = f"🔄 Filme '{chosen_movie_details['title']}' atualizado!"
            else:
                if request_data['audio_type'].upper() == 'DUB':
                    chosen_movie_details['dubbed_file_id'] = request_data['file_id']
                else:
                    chosen_movie_details['subtitled_file_id'] = request_data['file_id']
                
                chosen_movie_details.pop('button_text', None)
                success = db.add_movie(chosen_movie_details)
                msg = f"✅ Filme '{chosen_movie_details['title']}' adicionado!"
            
            await safe_edit_message(query.message, msg)
            if request_id in context.bot_data: del context.bot_data[request_id]
        
        except Exception as e:
            print(f"❌ ERRO CRÍTICO no Banco de Dados (button_handler/movie): {e}")
            await safe_edit_message(query.message, f"❌ ERRO CRÍTICO (Filme): {e}")
        
        return # Fim da lógica de filmes

    # --- ROTEADOR DE SÉRIES ---
    elif callback_data.startswith("confirm_series_"):
        print("[Handlers] Botão 'confirm_series_' detectado.")
        await safe_answer_query(query)
        parts = callback_data.split('_')
        request_id, action = parts[2], parts[3]
        
        request_data = context.bot_data.get(request_id)

        if not request_data:
            await safe_edit_message(query.message, "❌ Este pedido de SÉRIE expirou.")
            return
            
        if action == "ignore":
            await safe_edit_message(query.message, "Ok, SÉRIE ignorada.")
            if request_id in context.bot_data: del context.bot_data[request_id]
            return

        try:
            tmdb_id_to_confirm = int(action)
        except ValueError:
            return
            
        # Pega o 'tmdb_id' da opção que o admin clicou
        chosen_series_details = next((opt for opt in request_data['options'] if opt.get('tmdb_id') == tmdb_id_to_confirm), None)
        
        if not chosen_series_details:
            await safe_edit_message(query.message, "❌ Erro: Opção de SÉRIE inválida.")
            if request_id in context.bot_data: del context.bot_data[request_id]
            return
            
        await safe_edit_message(query.message, f"⏳ Processando SÉRIE: '{chosen_series_details['title']}'...")
        
        # Chama o worker
        success, msg = await _index_series_episode(
            tmdb_id=tmdb_id_to_confirm,
            season_number=request_data['season_number'],
            episode_number=request_data['episode_number'],
            audio_type=request_data['audio_type'],
            file_id=request_data['file_id']
        )
        
        await safe_edit_message(query.message, msg)
        if request_id in context.bot_data: del context.bot_data[request_id]
        return # Fim da lógica de séries
        
    else:
        # Ação de botão não reconhecida
        print(f"[Handlers] Callback ignorado: {callback_data}")


async def get_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retorna o file_id de uma mídia (sem mudança)."""
    if update.effective_user.id not in ADMIN_IDS: return 
    try:
        if update.message.reply_to_message and update.message.reply_to_message.video:
            file_id = update.message.reply_to_message.video.file_id
            await update.message.reply_text(f"Video File ID:\n`{file_id}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("Responda a um vídeo com /getid.")
    except Exception as e:
        print(f"⚠️ Erro de rede no /getid (ignorado): {e}")

#
# --- MUDANÇA 3: O HANDLER MANUAL AGORA É UM ROTEADOR ---
#
async def admin_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Escuta por vídeos enviados pelo admin NO PRIVADO.
    Verifica se é FILME ou SÉRIE pelo nome do arquivo/caption.
    """
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not update.message.video:
        await update.message.reply_text("❗️Erro: Envie um vídeo válido.")
        return
        
    file_name = update.message.caption or update.message.video.file_name
    
    if not file_name:
        await update.message.reply_text("❗️Erro: O vídeo precisa ter um caption ou nome de arquivo válido.")
        return
        
    # Limpa o nome do arquivo (ex: ".mp4")
    clean_file_name, _ = os.path.splitext(file_name)
    
    # --- ROTEADOR LÓGICO ---
    series_match = SERIES_REGEX.search(clean_file_name)
    
    if series_match:
        print(f"[Handlers] Vídeo (Manual) detectado como SÉRIE: {clean_file_name}")
        await _process_series_upload(update, context, clean_file_name, series_match)
    else:
        print(f"[Handlers] Vídeo (Manual) detectado como FILME: {clean_file_name}")
        await _process_movie_upload(update, context, clean_file_name)


async def _process_movie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, file_name: str):
    """Lógica que o admin_video_handler usava (anteriormente add_movie_handler)."""
    status_msg = None
    try:
        file_id = update.message.video.file_id
        status_msg = await update.message.reply_text(f"⏳ Processando FILME '{file_name}'...")

        # (A lógica de verificação de tamanho de arquivo foi movida para os uploaders)
        
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
            await safe_edit_message(status_msg, f"❌ (Filme) Não encontrei resultados no TMDb para '{search_query_clean}'.")
            return

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

        if high_confidence_match:
            await safe_edit_message(status_msg, f"✅ (Filme) Correspondência: '{high_confidence_match['title']}'. Salvando...")
            movie_details = high_confidence_match
            existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
            
            if existing_movie:
                success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=file_id, audio_type=audio_type)
                msg = f"🔄 Filme '{movie_details['title']}' atualizado!"
            else:
                if audio_type == 'DUB': movie_details['dubbed_file_id'] = file_id
                else: movie_details['subtitled_file_id'] = file_id
                movie_details.pop('button_text', None)
                success = db.add_movie(movie_details)
                msg = f"✅ Filme '{movie_details['title']}' adicionado!"
            await safe_edit_message(status_msg, msg)

        else:
            request_id = str(uuid.uuid4())
            context.bot_data[request_id] = {
                'file_id': file_id, 'audio_type': audio_type, 'options': movie_options
            }
            message_text = f"❓ **Ajuda (Filme)**\n\nArquivo: `{search_query_clean}`\n\nQual o correto?"
            keyboard = []
            for option in movie_options:
                # --- MUDANÇA 4: Prefixo do botão atualizado ---
                callback_data_str = f"confirm_movie_{request_id}_{option['tmdb_id']}"
                button_text = f"{option['title']} ({option['year']})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data_str)])
            keyboard.append([InlineKeyboardButton("❌ Nenhum destes", callback_data=f"confirm_movie_{request_id}_ignore")])
            await safe_edit_message(status_msg, text=message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no _process_movie_upload: {e}")
        import traceback
        traceback.print_exc()
        await safe_edit_message(status_msg, f"❌ Erro crítico (Filme): {e}")


async def _process_series_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, file_name: str, series_match: re.Match):
    """Lógica de SÉRIE (COM ATUALIZAÇÃO DO PLANO)"""
    status_msg = None
    try:
        file_id = update.message.video.file_id
        status_msg = await update.message.reply_text(f"⏳ Processando SÉRIE '{file_name}'...")
        
        #
        # --- MUDANÇA 3: LÓGICA DE EXTRAÇÃO CORRIGIDA ---
        # (Usando os 5 grupos do Regex Universal)
        #
        series_title_clean = series_match.group(1).strip() # G1: Título (já limpo)
        series_year = series_match.group(2).strip() if series_match.group(2) else None # G2: Ano (opcional)
        season_number = int(series_match.group(3)) # G3: Temporada
        episode_number = int(series_match.group(4)) # G4: Episódio
        audio_type = series_match.group(5).upper() # G5: Áudio
        
        print(f"[Handlers] Título: '{series_title_clean}', Ano: {series_year}, S{season_number} E{episode_number}")
        
        # 2. Buscar opções no TMDb (AGORA PASSANDO O ANO)
        series_options = tmdb_api.search_series_options(series_title_clean, year=series_year)
        # --- FIM DA MUDANÇA ---
        #

        if not series_options:
            await safe_edit_message(status_msg, f"❌ (Série) Não encontrei resultados no TMDb para '{series_title_clean}'.")
            return

        # 3. Verificar alta confiança (usando fuzz)
        high_confidence_match = None
        for option in series_options:
            # Compara o título limpo com o título da opção
            ratio = fuzz.ratio(series_title_clean.lower(), option['title'].lower())
            if ratio > 80: 
                high_confidence_match = option
                break

        # 4.A. ALTA CONFIANÇA
        if high_confidence_match:
            tmdb_id = high_confidence_match['tmdb_id']
            await safe_edit_message(status_msg, f"✅ (Série) Correspondência: '{high_confidence_match['title']}'. Salvando...")
            success, msg = await _index_series_episode(
                tmdb_id=tmdb_id,
                season_number=season_number,
                episode_number=episode_number,
                audio_type=audio_type,
                file_id=file_id
            )
            await safe_edit_message(status_msg, msg)

        # 4.B. BAIXA CONFIANÇA
        else:
            request_id = str(uuid.uuid4())
            context.bot_data[request_id] = {
                'file_id': file_id, 
                'audio_type': audio_type, 
                'options': series_options,
                'season_number': season_number,
                'episode_number': episode_number
            }
            message_text = f"❓ **Ajuda (Série)**\n\nArquivo: `{file_name}`\n\nQual série é esta?"
            keyboard = []
            for option in series_options:
                callback_data_str = f"confirm_series_{request_id}_{option['tmdb_id']}"
                button_text = f"{option['title']} ({option['year']})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data_str)])
            keyboard.append([InlineKeyboardButton("❌ Nenhuma destas", callback_data=f"confirm_series_{request_id}_ignore")])
            await safe_edit_message(status_msg, text=message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no _process_series_upload: {e}")
        import traceback
        traceback.print_exc()
        await safe_edit_message(status_msg, f"❌ Erro crítico (Série): {e}")

async def get_chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retorna o ID do chat atual (sem mudança)."""
    chat_id = update.effective_chat.id
    try:
        await update.message.reply_text(f"O ID deste chat é: `{chat_id}`")
    except Exception as e:
        print(f"⚠️ Erro de rede no /id (ignorado): {e}")


# --- MUDANÇA 6: O HANDLER DE CANAL DE FILMES (Original) ---
# (A lógica interna é a mesma, mas os prefixos de botão mudaram)
#
async def new_movie_in_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Bot indexador que lê caption ou nome do arquivo do canal de FILMES.
    """
    post = update.channel_post or update.message
    if not post or post.chat.id != STORAGE_CHANNEL_ID or not post.video:
        return

    status_msg = None
    try:
        file_name = post.caption or post.video.file_name
        if not file_name: return
        file_id = post.video.file_id
        
        audio_type_match = re.search(r'\[(DUB|LEG)\]', file_name, re.IGNORECASE)
        if not audio_type_match: return
            
        audio_type = audio_type_match.group(1).upper()
        temp_name = re.sub(r'\s*\[(DUB|LEG)\]\s*', '', file_name, flags=re.IGNORECASE).strip()
        search_query, _ = os.path.splitext(temp_name)
        search_query_clean = re.sub(r'\s*4k?\s*$', '', search_query, flags=re.IGNORECASE).strip()
        
        print(f"[LOG CANAL FILMES] Processando: {search_query_clean}")

        movie_options = tmdb_api.search_movie_options(search_query_clean)

        if not movie_options:
            await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❌ (Filme) Não encontrei resultados para '{search_query_clean}'.")
            return

        high_confidence_match = None
        for option in movie_options:
            ratio = fuzz.ratio(search_query_clean.lower(), f"{option['title']} ({option['year']})".lower())
            if ratio > 85:
                high_confidence_match = option
                break

        if high_confidence_match:
            status_msg = await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"⏳ Indexando FILME: '{search_query_clean}'...")
            movie_details = high_confidence_match
            existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
            
            if existing_movie:
                success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=file_id, audio_type=audio_type)
                msg = f"🔄 Filme '{movie_details['title']}' atualizado!"
            else:
                if audio_type == 'DUB': movie_details['dubbed_file_id'] = file_id
                else: movie_details['subtitled_file_id'] = file_id
                movie_details.pop('button_text', None)
                success = db.add_movie(movie_details)
                msg = f"✅ Filme '{movie_details['title']}' adicionado!"
            await safe_edit_message(status_msg, msg)
        else:
            # Baixa confiança, pede ajuda
            request_id = str(uuid.uuid4())
            context.bot_data[request_id] = {
                'file_id': file_id, 'audio_type': audio_type, 'options': movie_options
            }
            message_text = f"❓ **Ajuda (Filme)**\n\nArquivo: `{search_query_clean}`\n\nQual o correto?"
            keyboard = []
            for option in movie_options:
                # --- MUDANÇA 7: Prefixo do botão atualizado ---
                callback_data_str = f"confirm_movie_{request_id}_{option['tmdb_id']}"
                button_text = f"{option['title']} ({option['year']})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data_str)])
            keyboard.append([InlineKeyboardButton("❌ Nenhum destes", callback_data=f"confirm_movie_{request_id}_ignore")])
            
            await safe_send_message(
                context, chat_id=ADMIN_IDS[0], text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no new_movie_in_channel_handler: {e}")
        import traceback
        traceback.print_exc()
        await safe_send_message(context, ADMIN_IDS[0], f"❌ Erro crítico (Filme): {e}")


#
# --- MUDANÇA 8: O NOVO HANDLER DE CANAL DE SÉRIES ---
#
async def new_series_in_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Bot indexador que lê caption ou nome do arquivo do NOVO canal de SÉRIES.
    (VERSÃO ATUALIZADA v4.1)
    """
    post = update.channel_post or update.message
    if not post or post.chat.id != STORAGE_CHANNEL_ID_SERIES or not post.video:
        return
    status_msg = None
    try:
        file_name = post.caption or post.video.file_name
        if not file_name: return
        
        file_id = post.video.file_id
        clean_file_name, _ = os.path.splitext(file_name)
        
        # 1. Tenta aplicar o Regex de Séries
        series_match = SERIES_REGEX.search(clean_file_name)
        
        if not series_match:
            await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❌ Falha (Série): O nome '{clean_file_name}' não bate com o padrão 'Nome SXX EXX [AUDIO]'.")
            return
            
        #
        # --- MUDANÇA 5: LÓGICA DE EXTRAÇÃO CORRIGIDA ---
        # (Usando os 5 grupos do Regex Universal)
        #
        series_title_clean = series_match.group(1).strip() # G1: Título (já limpo)
        series_year = series_match.group(2).strip() if series_match.group(2) else None # G2: Ano (opcional)
        season_number = int(series_match.group(3)) # G3: Temporada
        episode_number = int(series_match.group(4)) # G4: Episódio
        audio_type = series_match.group(5).upper() # G5: Áudio
        
        # Este é o log que vai aparecer correto agora
        print(f"[LOG CANAL SÉRIES] Processando: {series_title_clean} (Ano: {series_year}) S{season_number:02d} E{episode_number:02d}")
        
        # 3. Buscar opções no TMDb (AGORA PASSANDO O ANO)
        series_options = tmdb_api.search_series_options(series_title_clean, year=series_year)
        # --- FIM DA MUDANÇA ---
        #

        if not series_options:
            await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❌ (Série) Não encontrei resultados no TMDb para '{series_title_clean}'.")
            return

        # 4. Verificar alta confiança (usando fuzz)
        high_confidence_match = None
        for option in series_options:
            ratio = fuzz.ratio(series_title_clean.lower(), option['title'].lower())
            if ratio > 80:
                high_confidence_match = option
                break

        # 5.A. ALTA CONFIANÇA
        if high_confidence_match:
            tmdb_id = high_confidence_match['tmdb_id']
            status_msg = await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"⏳ Indexando SÉRIE: '{clean_file_name}'...")
            success, msg = await _index_series_episode(
                tmdb_id=tmdb_id,
                season_number=season_number,
                episode_number=episode_number,
                audio_type=audio_type,
                file_id=file_id
            )
            await safe_edit_message(status_msg, msg)

        # 5.B. BAIXA CONFIANÇA
        else:
            request_id = str(uuid.uuid4())
            context.bot_data[request_id] = {
                'file_id': file_id, 
                'audio_type': audio_type, 
                'options': series_options,
                'season_number': season_number,
                'episode_number': episode_number
            }
            message_text = f"❓ **Ajuda (Série)**\n\nArquivo: `{clean_file_name}`\n\nQual série é esta?"
            keyboard = []
            for option in series_options:
                callback_data_str = f"confirm_series_{request_id}_{option['tmdb_id']}"
                button_text = f"{option['title']} ({option['year']})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data_str)])
            keyboard.append([InlineKeyboardButton("❌ Nenhuma destas", callback_data=f"confirm_series_{request_id}_ignore")])
            await safe_send_message(
                context, chat_id=ADMIN_IDS[0], text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no new_series_in_channel_handler: {e}")
        import traceback
        traceback.print_exc()
        await safe_send_message(context, ADMIN_IDS[0], f"❌ Erro crítico (Série): {e}")
        
# --- MUDANÇA 9: Definição dos Handlers ---
# (Precisamos adicionar o novo handler de canal de séries)
#
start_handler = CommandHandler("start", start_admin)
button_click_handler = CallbackQueryHandler(button_handler_admin)
get_id_command_handler = CommandHandler("getid", get_id_handler)
get_chat_id_command_handler = CommandHandler("id", get_chat_id_handler)

# Este handler manual (privado) agora é o roteador
admin_video_handler = MessageHandler(filters.VIDEO & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_video_handler)

# Handler para o canal de FILMES
channel_video_handler = MessageHandler(filters.VIDEO & filters.Chat(chat_id=STORAGE_CHANNEL_ID), new_movie_in_channel_handler)

# NOVO HANDLER para o canal de SÉRIES
channel_series_handler = MessageHandler(filters.VIDEO & filters.Chat(chat_id=STORAGE_CHANNEL_ID_SERIES), new_series_in_channel_handler)
