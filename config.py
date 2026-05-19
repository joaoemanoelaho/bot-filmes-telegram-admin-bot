import os
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# Telegram
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")

# TMDb
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Pyrogram
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID"))
STORAGE_CHANNEL_ID_SERIES = int(os.getenv("STORAGE_CHANNEL_ID_SERIES"))
PUSHINPAY_API_KEY = os.getenv("PUSHINPAY_API_KEY")

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

M3U_FILE_PATH = os.getenv("M3U_FILE_PATH")
DOWNLOAD_FOLDER = os.getenv("DOWNLOAD_FOLDER")
LOG_FILE = os.getenv("LOG_FILE")
REFERER_URL = os.getenv("REFERER_URL")

USER_AGENT = os.getenv("USER_AGENT") 

PROXY_URL = os.getenv("PROXY_URL")
SESSION_STRING = os.environ.get('PYROGRAM_SESSION_STRING')

API_KEY = TMDB_API_KEY
BASE_URL = os.getenv("BASE_URL")

CANAL_ID = os.getenv("CANAL_ID")
GRUPO_ID = os.getenv("GRUPO_ID")
BOT_PRINCIPAL = os.getenv("BOT_PRINCIPAL")

STICKER_BOM_DIA = os.getenv("STICKER_BOM_DIA")
STICKER_TARDE = os.getenv("STICKER_TARDE")

ADMIN_WEBHOOK_URL = os.getenv("ADMIN_WEBHOOK_URL")

# Validações
if not TMDB_API_KEY:
    raise ValueError("❌ TMDB_API_KEY não configurado!")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Credenciais Supabase não configuradas!")
if not API_ID or not API_HASH:
    raise ValueError("❌ Credenciais Pyrogram não configuradas!")
if not STORAGE_CHANNEL_ID:
    raise ValueError("❌ STORAGE_CHANNEL_ID não configurado!")
if not PUSHINPAY_API_KEY:
    raise ValueError("❌ PUSHINPAY_API_KEY não configurado!")
print("✅ Configurações carregadas com sucesso!")