#
# Arquivo que contém as respostas e lógicas para os comandos.
# VERSÃO 3.2 - CORRIGINDO ERRO DE SINTAXE (CallbackQuery)
#
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery # <-- MUDANÇA 1
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import database as db
import tmdb_api
from config import ADMIN_IDS, STORAGE_CHANNEL_ID
import re
import os
from thefuzz import fuzz
import uuid
import sys
import asyncio # <--- IMPORTANTE PARA O DELAY

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# =================================================================
# === FUNÇÕES DE SEGURANÇA (COM RETENTATIVAS) ===
# =================================================================

async def safe_edit_message(message, new_text, **kwargs):
    """
    Tenta editar uma mensagem, com 3 retentativas em caso de erro de rede.
    Implementa a lógica de "backoff exponencial" (espera 2s, 4s).
    """
    if not message:
        print("⚠️ [safe_edit_message] Tentou editar uma mensagem nula.")
        return

    retries = 3
    delay = 2  # Começa com 2 segundos
    for i in range(retries):
        try:
            await message.edit_text(new_text, **kwargs)
            return  # Sucesso, sai da função
        except Exception as e:
            # Apenas loga o erro e tenta de novo
            print(f"⚠️ Erro de rede ao TENTAR EDITAR (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1:  # Se não for a última tentativa
                await asyncio.sleep(delay)
                delay *= 2  # Dobra a espera para a próxima tentativa (2s, 4s)
            else:
                print(f"❌ FALHA AO EDITAR MENSAGEM '{message.text[:20]}...' após 3 tentativas.")

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
                return None  # Retorna None se falhar

async def safe_answer_query(query: CallbackQuery, **kwargs): # <-- MUDANÇA 2
    """Tenta responder um callback query, com 3 retentativas."""
    retries = 3
    delay = 1 # Resposta de query pode ser mais rápida
    for i in range(retries):
        try:
            await query.answer(**kwargs)
            return # Sucesso
        except Exception as e:
            print(f"⚠️ Erro de rede ao TENTAR RESPONDER QUERY (Tentativa {i+1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)
            else:
                print(f"❌ FALHA AO RESPONDER QUERY após 3 tentativas.")

# =================================================================
# === HANDLERS COM LOGS DE DEBUG ADICIONADOS ===
# =================================================================

async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensagem de início simples para o bot de admin."""
    try:
        await update.message.reply_text("🤖 Olá, Admin! Bot de indexação online e pronto para receber arquivos.")
    except Exception as e:
        print(f"⚠️ Erro de rede no /start (ignorado): {e}")

async def button_handler_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa APENAS os cliques de confirmação de indexação do admin."""
    
    # --- DEBUG PRINT ADICIONADO ---
    print("\n" + "="*50)
    print(f"DEBUG: [button_handler_admin] ACIONADO!")
    
    query = update.callback_query
    
    if not query:
        print(f"DEBUG: [button_handler_admin] ERRO: Objeto 'query' está NULO.")
        print("="*50 + "\n")
        return
        
    callback_data = query.data
    user_id = query.from_user.id

    print(f"DEBUG: [button_handler_admin] User ID: {user_id}")
    print(f"DEBUG: [button_handler_admin] Callback Data: {callback_data}")
    print("="*50 + "\n")
    # --- FIM DO DEBUG PRINT ---

    # (Nota: o handler 'debug_all_updates' em main.py já deve ter logado isso)
    # Este log aqui só aparece se o 'debug_all_updates' já funcionou.

    if callback_data.startswith("confirm_"):
        if user_id not in ADMIN_IDS:
            print("DEBUG: [button_handler_admin] Ação restrita para este usuário.")
            await safe_answer_query(query, "Ação restrita.", show_alert=True)
            return
        
        print("DEBUG: [button_handler_admin] Callback data 'confirm_' VÁLIDO. Processando...")
        await safe_answer_query(query) # <--- Agora com retries
        parts = callback_data.split('_')
        request_id, action = parts[1], parts[2]
        
        print(f"DEBUG: [button_handler_admin] Request ID: {request_id}, Action: {action}")
        
        request_data = context.bot_data.get(request_id)

        if not request_data:
            print(f"DEBUG: [button_handler_admin] ERRO: Pedido expirou (request_data não encontrado para ID: {request_id}).")
            await safe_edit_message(query.message, "❌ Este pedido expirou.") # <--- Agora com retries
            return
            
        if action == "ignore":
            print("DEBUG: [button_handler_admin] Ação 'ignore' selecionada. Arquivo ignorado.")
            await safe_edit_message(query.message, "Ok, arquivo ignorado.") # <--- Agora com retries
            if request_id in context.bot_data:
                del context.bot_data[request_id]
            return

        try:
            tmdb_id_to_confirm = int(action)
        except ValueError:
            print(f"DEBUG: [button_handler_admin] ERRO: Ação '{action}' não é um número (TMDb ID) nem 'ignore'.")
            return
            
        print(f"DEBUG: [button_handler_admin] TMDb ID selecionado: {tmdb_id_to_confirm}")
        
        chosen_movie_details = next((opt for opt in request_data['options'] if opt.get('tmdb_id') == tmdb_id_to_confirm), None)
        
        if not chosen_movie_details:
            print("DEBUG: [button_handler_admin] ERRO: Opção inválida (chosen_movie_details não encontrado).")
            print(f"DEBUG: Opções disponíveis eram: {request_data.get('options')}")
            await safe_edit_message(query.message, "❌ Erro: Opção inválida.") # <--- Agora com retries
            if request_id in context.bot_data:
                del context.bot_data[request_id]
            return

        print(f"DEBUG: [button_handler_admin] Processando filme: '{chosen_movie_details['title']}'...")
        await safe_edit_message(query.message, f"⏳ Processando: '{chosen_movie_details['title']}'...") # <--- Agora com retries
        
        try:
            existing_movie = db.find_movie_by_title_and_year(title=chosen_movie_details['title'], year=chosen_movie_details['year'])
            if existing_movie:
                print("DEBUG: [button_handler_admin] Filme existe. Atualizando file_id...")
                success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=request_data['file_id'], audio_type=request_data['audio_type'])
                msg = f"🔄 Filme '{chosen_movie_details['title']}' atualizado!" if success else "❌ Erro ao ATUALIZAR."
            else:
                print("DEBUG: [button_handler_admin] Filme novo. Adicionando ao DB...")
                if request_data['audio_type'].upper() == 'DUB':
                    chosen_movie_details['dubbed_file_id'] = request_data['file_id']
                else:
                    chosen_movie_details['subtitled_file_id'] = request_data['file_id']
                
                chosen_movie_details.pop('button_text', None)
                success = db.add_movie(chosen_movie_details)
                msg = f"✅ Filme '{chosen_movie_details['title']}' adicionado!" if success else "❌ Erro ao SALVAR."
            
            print(f"DEBUG: [button_handler_admin] Resultado: {msg}")
            await safe_edit_message(query.message, msg) # <--- Agora com retries
            if request_id in context.bot_data:
                del context.bot_data[request_id]
        
        except Exception as e:
            print(f"❌ ERRO CRÍTICO no Banco de Dados (button_handler): {e}")
            import traceback
            traceback.print_exc()
            await safe_edit_message(query.message, f"❌ ERRO CRÍTICO no Banco de Dados: {e}")
            
        return
    else:
        # --- DEBUG PRINT ---
        print(f"DEBUG: [button_handler_admin] IGNORADO: Callback data '{callback_data}' não começa com 'confirm_'.")
        print("="*50 + "\n")
        # --- FIM DO DEBUG PRINT ---
    
async def get_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retorna o file_id de uma mídia, APENAS PARA ADMINS."""
    if update.effective_user.id not in ADMIN_IDS:
        print(f"[ALERTA] Uso não autorizado do /getid pelo usuário {update.effective_user.id}.")
        return 
    try:
        if update.message.reply_to_message and update.message.reply_to_message.video:
            file_id = update.message.reply_to_message.video.file_id
            await update.message.reply_text(f"Video File ID:\n`{file_id}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("Responda a um vídeo com /getid para obter o File ID.")
    except Exception as e:
        print(f"⚠️ Erro de rede no /getid (ignorado): {e}")

async def add_movie_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Escuta por vídeos enviados pelo admin, busca as opções no TMDb
    e pede confirmação se houver múltiplos resultados.
    """
    if update.effective_user.id not in ADMIN_IDS:
        return

    status_msg = None
    try:
        if not update.message.video:
            await update.message.reply_text("❗️Erro: Envie um vídeo válido.")
            return
        
        file_name = update.message.caption or update.message.video.file_name
        
        if not file_name:
            await update.message.reply_text("❗️Erro: O vídeo precisa ter um caption ou nome de arquivo válido.")
            return
        
        file_size_mb = update.message.video.file_size / (1024**2) if update.message.video.file_size else 0
        MAX_FILE_SIZE_MB = 3900
        
        if file_size_mb > MAX_FILE_SIZE_MB:
            await update.message.reply_text(
                f"⚠️ **Arquivo muito grande!**\n\n"
                f"📊 Tamanho: {file_size_mb:.0f}MB\n"
                f"📌 Limite: {MAX_FILE_SIZE_MB}MB\n\n"
                f"❌ Arquivo não pode ser indexado."
            )
            return
        
        file_id = update.message.video.file_id
        status_msg = await update.message.reply_text(f"⏳ Processando '{file_name}'...")

        audio_type_match = re.search(r'\[(DUB|LEG)\]', file_name, re.IGNORECASE)
        if not audio_type_match:
            await safe_edit_message(status_msg, f"❓ Falha: O nome precisa conter [DUB] ou [LEG].")
            return
        
        audio_type = audio_type_match.group(1).upper()
        temp_name = re.sub(r'\s*\[(DUB|LEG)\]\s*', '', file_name, flags=re.IGNORECASE).strip()
        search_query, _ = os.path.splitext(temp_name)
        search_query_clean = re.sub(r'\s*4k?\s*$', '', search_query, flags=re.IGNORECASE).strip()
        has_4k = bool(re.search(r'4k', search_query, re.IGNORECASE))
        query_log = f"{search_query_clean} (4K)" if has_4k else search_query_clean
        print(f"[LOG] Processando: {query_log}")
        
        movie_options = tmdb_api.search_movie_options(search_query_clean)

        if not movie_options:
            await safe_edit_message(status_msg, f"❌ Não encontrei nenhum resultado no TMDb para '{search_query_clean}'.")
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
            await safe_edit_message(status_msg, f"✅ Correspondência encontrada: '{high_confidence_match['title']}'. Salvando...")
            movie_details = high_confidence_match

            existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
            if existing_movie:
                success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=file_id, audio_type=audio_type)
                msg = f"🔄 Filme '{movie_details['title']}' atualizado com sucesso!" if success else f"❌ Erro ao ATUALIZAR '{movie_details['title']}'."
                await safe_edit_message(status_msg, msg)
            else:
                if audio_type == 'DUB': 
                    movie_details['dubbed_file_id'] = file_id
                else: 
                    movie_details['subtitled_file_id'] = file_id
                movie_details.pop('button_text', None)
                success = db.add_movie(movie_details)
                msg = f"✅ Filme '{movie_details['title']}' adicionado com sucesso!" if success else f"❌ Erro ao SALVAR '{movie_details['title']}'."
                await safe_edit_message(status_msg, msg)

        else:
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
            
            await safe_edit_message(
                status_msg,
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no add_movie_handler: {e}")
        import traceback
        traceback.print_exc()
        try:
            await safe_edit_message(status_msg, f"❌ Erro crítico ao processar o vídeo: {e}")
        except:
            await safe_send_message(context, update.effective_chat.id, f"❌ Erro crítico ao processar o vídeo: {e}")


async def get_chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retorna o ID do chat atual."""
    chat_id = update.effective_chat.id
    try:
        await update.message.reply_text(f"O ID deste chat é: `{chat_id}`")
    except Exception as e:
        print(f"⚠️ Erro de rede no /id (ignorado): {e}")


async def new_movie_in_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Bot indexador que lê caption ou nome do arquivo.
    AGORA COM PROTEÇÃO DE REDE E RETRIES.
    """
    post = update.channel_post or update.message
    if not post or post.chat.id != STORAGE_CHANNEL_ID or not post.video:
        return

    status_msg = None
    
    try:
        file_size_mb = post.video.file_size / (1024**2) if post.video.file_size else 0
        MAX_FILE_SIZE_MB = 3900
        
        if file_size_mb > MAX_FILE_SIZE_MB:
            await safe_send_message(
                context, 
                chat_id=ADMIN_IDS[0], 
                text=f"⚠️ Arquivo descartado: muito grande ({file_size_mb:.0f}MB > {MAX_FILE_SIZE_MB}MB)"
            )
            return

        file_name = post.caption or post.video.file_name
        if not file_name:
            return

        file_id = post.video.file_id
        
        audio_type_match = re.search(r'\[(DUB|LEG)\]', file_name, re.IGNORECASE)
        if not audio_type_match:
            return
            
        audio_type = audio_type_match.group(1)
        
        temp_name = re.sub(r'\s*\[(DUB|LEG)\]\s*', '', file_name, flags=re.IGNORECASE).strip()
        search_query, _ = os.path.splitext(temp_name)
        search_query_clean = re.sub(r'\s*4k?\s*$', '', search_query, flags=re.IGNORECASE).strip()
        has_4k = bool(re.search(r'4k', search_query, re.IGNORECASE))
        query_log = f"{search_query_clean} (4K)" if has_4k else search_query_clean
        print(f"[LOG CANAL] Processando: {query_log}")

        movie_options = tmdb_api.search_movie_options(search_query_clean)

        if not movie_options:
            await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"❌ Não encontrei nenhum resultado no TMDb para '{search_query_clean}'.")
            return

        high_confidence_match = None
        for option in movie_options:
            ratio = fuzz.ratio(search_query_clean.lower(), f"{option['title']} ({option['year']})".lower())
            if ratio > 85:
                high_confidence_match = option
                break

        if high_confidence_match:
            # Esta é a chamada de rede que envia "Indexando..."
            status_msg = await safe_send_message(context, chat_id=ADMIN_IDS[0], text=f"⏳ Indexando automaticamente '{query_log}'...")
            
            movie_details = high_confidence_match

            # --- Lógica de Banco de Dados ---
            existing_movie = db.find_movie_by_title_and_year(title=movie_details['title'], year=movie_details['year'])
            if existing_movie:
                success = db.update_movie_file_id(movie_id=existing_movie['movie_id'], file_id=file_id, audio_type=audio_type)
                msg = f"🔄 Filme '{movie_details['title']}' atualizado com sucesso!" if success else f"❌ Erro ao ATUALIZAR '{movie_details['title']}'."
                await safe_edit_message(status_msg, msg) # <--- Agora com retries
            else:
                if audio_type.upper() == 'DUB': 
                    movie_details['dubbed_file_id'] = file_id
                else: 
                    movie_details['subtitled_file_id'] = file_id
                movie_details.pop('button_text', None)
                success = db.add_movie(movie_details)
                msg = f"✅ Filme '{movie_details['title']}' adicionado com sucesso!" if success else f"❌ Erro ao SALVAR '{movie_details['title']}'."
                
                # ESTA ERA A LINHA QUE QUEBRAVA (agora tem retries)
                await safe_edit_message(status_msg, msg) # <--- Agora com retries
        else:
            # Se não tem certeza, pede ajuda ao admin
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
                button_text = f"{option['title']} ({option['year']})" # <--- (Mantendo a correção de bug da v2.0)
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data_str)])
            
            keyboard.append([InlineKeyboardButton("❌ Nenhum destes", callback_data=f"confirm_{request_id}_ignore")])
            
            # --- CORREÇÃO DO ERRO 'parse_code' ---
            await safe_send_message(
                context,
                chat_id=ADMIN_IDS[0], text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown" # <-- CORRIGIDO
            )
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO no new_movie_in_channel_handler: {e}")
        import traceback
        traceback.print_exc()
        try:
            await safe_edit_message(status_msg, f"❌ Erro crítico ao processar o vídeo: {e}")
        except:
            await safe_send_message(context, ADMIN_IDS[0], f"❌ Erro crítico ao processar o vídeo: {e}")


# --- Definição dos Handlers ---
start_handler = CommandHandler("start", start_admin)
button_click_handler = CallbackQueryHandler(button_handler_admin)
get_id_command_handler = CommandHandler("getid", get_id_handler)
admin_video_handler = MessageHandler(filters.VIDEO & ~filters.COMMAND & filters.ChatType.PRIVATE, add_movie_handler)
get_chat_id_command_handler = CommandHandler("id", get_chat_id_handler)
channel_video_handler = MessageHandler(filters.VIDEO & filters.Chat(chat_id=STORAGE_CHANNEL_ID), new_movie_in_channel_handler)

