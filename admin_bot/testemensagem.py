import asyncio
from pyrogram import Client
from config import API_ID, API_HASH, STORAGE_CHANNEL_ID

SESSION_NAME = "minha_conta_de_upload"

async def test():
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)
    
    async with app:
        try:
            msg = await app.send_message(STORAGE_CHANNEL_ID, "✅ Teste funcionando!")
            print(f"✅ Sucesso! Mensagem ID: {msg.id}")
        except Exception as e:
            print(f"❌ Erro: {e}")

asyncio.run(test())