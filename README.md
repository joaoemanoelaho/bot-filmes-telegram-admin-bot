# 🎬 Bot Filmes Telegram

Um bot completo para Telegram que gerencia um catálogo de filmes com upload automático, indexação via TMDb e busca inteligente.

**Follow:** [@meucinepipoca](https://t.me/meucinepipoca) 📺

---

## ✨ Funcionalidades Principais

### 👥 Para Usuários
- 🔍 **Busca de filmes** por nome com sugestões inteligentes
- 📊 **Detalhes completos**: sinopse, elenco, avaliação, duração
- 🎯 **Filtros**: dublado/legendado, ano de lançamento
- ⭐ **Sistema de favoritos** (opcional)
- 🚀 **Download direto** via Telegram

### 🤖 Para Administradores
- 📤 **Upload automático** de filmes via Pyrogram
- 🎬 **Indexação automática** com TMDb
- 📥 **Download em massa** com yt-dlp
- 🏷️ **Geração de thumbnails** com FFmpeg
- 📊 **Cache de metadados** para performance
- ⚡ **Rate limiting inteligente** (anti-ban Telegram)
- 🛡️ **Validação de tamanho** (máx 3.9GB)

---

## 🏗️ Arquitetura

```
bot-filmes-telegram/
├── main_bot/
│   ├── bot.py                 # Bot principal (usuários)
│   ├── handlers_users.py      # Comandos do usuário
│   └── handlers_search.py     # Sistema de busca
├── admin_bot/
│   ├── admin_bot.py           # Bot admin
│   ├── handlers_admin.py      # Indexação de filmes
│   ├── m3u_downloader.py      # Download em massa (yt-dlp)
│   ├── uploader_pyrogram.py   # Upload automático
│   └── tmdb_api.py            # Integração TMDb
├── database/
│   └── database.py            # Gerenciamento Supabase
├── config.py                  # Configurações
├── requirements.txt           # Dependências
└── README.md                  # Este arquivo
```

---

## 🚀 Instalação

### Pré-requisitos
- **Python 3.9+**
- **FFmpeg** (para thumbnails)
- **FFprobe** (para metadados)
- Contas: Telegram, TMDb, Supabase

### Passo 1: Clonar repositório
```bash
git clone https://github.com/seu-usuario/bot-filmes-telegram.git
cd bot-filmes-telegram
```

### Passo 2: Criar ambiente virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Passo 3: Instalar dependências
```bash
pip install -r requirements.txt
```

### Passo 4: Configurar credenciais
Edite `config.py` com suas credenciais:

```python
# Telegram
BOT_TOKEN = "seu_token_aqui"
ADMIN_IDS = [seu_id_telegram]

# TMDb
TMDB_API_KEY = "sua_chave_tmdb"

# Supabase
SUPABASE_URL = "sua_url"
SUPABASE_KEY = "sua_chave"

# Pyrogram (uploader)
API_ID = seu_api_id
API_HASH = "seu_api_hash"
STORAGE_CHANNEL_ID = seu_id_canal
```

### Passo 5: Executar bots
```bash
# Bot principal (usuários)
python main_bot/bot.py

# Bot admin (em outro terminal)
python admin_bot/admin_bot.py
```

---

## 📋 Configuração Avançada

### Download em Massa (yt-dlp)
```bash
python admin_bot/m3u_downloader.py
```
- Lê arquivo `.m3u` de streams
- Filtra automaticamente 4K
- Respeita retry automático
- Suporta proxies

### Upload Automático (Pyrogram)
```bash
python admin_bot/uploader_pyrogram.py
```
- Monitora pasta `C:\converter`
- Valida tamanho de arquivo (máx 3.9GB)
- Gera thumbnails automáticas
- Respeita rate limit do Telegram (5-10min entre uploads)
- Sistema anti-flood com exponential backoff

### Indexação Manual
Envie um vídeo para o bot admin com caption:
```
Homem Aranha (2002) [DUB]
```
- Busca automaticamente no TMDb
- Se encontrar, indexa no banco
- Se tiver dúvida, pede confirmação

---

## 🔧 Dependências

| Pacote | Versão | Uso |
|--------|--------|-----|
| `python-telegram-bot` | 20.0+ | Bot Telegram (usuários) |
| `pyrogram` | 2.0+ | Upload automático |
| `tgcrypto` | 1.2+ | Criptografia Pyrogram |
| `yt-dlp` | 2023.12+ | Download de vídeos |
| `tmdbv3api` | 1.7+ | API do TMDb |
| `supabase` | 2.0+ | Banco de dados |
| `aiohttp` | 3.9+ | Requisições async |
| `Pillow` | 10.0+ | Processamento de imagens |
| `thefuzz` | 0.19+ | Fuzzy matching |

---

## 📊 Fluxo de Dados

```
Upload Arquivo
    ↓
M3U Downloader (yt-dlp)
    ↓
Uploader Pyrogram (Telegram)
    ↓
Handler Admin (Indexação)
    ↓
TMDb API (Busca)
    ↓
Supabase (Armazenamento)
    ↓
Bot User (Busca)
    ↓
Usuário Final
```

---

## ⚙️ Variáveis de Ambiente (config.py)

```python
# Telegram Bots
BOT_TOKEN = "seu_token_principal"
ADMIN_BOT_TOKEN = "seu_token_admin"
ADMIN_IDS = [123456789]

# TMDb
TMDB_API_KEY = "sua_chave_api"

# Supabase
SUPABASE_URL = "https://seu-projeto.supabase.co"
SUPABASE_KEY = "sua_chave_anon"

# Pyrogram
API_ID = 123456
API_HASH = "seu_hash"
STORAGE_CHANNEL_ID = -100123456789

# Caminhos
DOWNLOAD_FOLDER = "C:\\converter"
FFMPEG_PATH = "C:\\ffmpeg\\bin\\ffmpeg.exe"
FFPROBE_PATH = "C:\\ffmpeg\\bin\\ffprobe.exe"
```

---

## 🛡️ Segurança

### Anti-Ban Telegram
- ✅ Rate limiting: 5-10 min entre uploads
- ✅ Exponential backoff para erros
- ✅ Respeita FloodWait automático
- ✅ Validação de tamanho de arquivo
- ✅ Buffer aleatório (5-15s)

### Proteção de Dados
- ✅ Credenciais em `config.py` (add ao `.gitignore`)
- ✅ Logs estruturados
- ✅ Cache de metadados local
- ✅ Validação de entrada

---

## 📈 Performance

### Otimizações
- 🚀 **Cache de metadados**: evita reprocessar vídeos
- ⚡ **Requisições async**: paralelização de uploads
- 📊 **Fuzzy matching**: busca mais rápida
- 🔄 **Connection pooling**: reutilização de conexões

### Limites Testados
- ✅ 14.966 filmes indexados
- ✅ 10+ MB/s de upload sustentado
- ✅ 1 upload simultâneo (respeita rate limit)
- ✅ Suporta arquivos até 3.9GB

---

## 🐛 Troubleshooting

### "Can't upload files bigger than 4000 MiB"
```python
# Solução: Arquivo excede limite do Telegram
# m3u_downloader.py já filtra 4K automaticamente
```

### "FloodWait: retry after X seconds"
```python
# Solução: Rate limiting do Telegram
# uploader_pyrogram.py respeita automaticamente
# Aguarda X segundos + buffer aleatório
```

### "TMDb movie not found"
```python
# Solução: Confirmar manualmente no bot admin
# Bot oferece opções para escolher
```

---

## 📝 Logs

Localização: `console output`

Níveis:
- 🟢 `[green]` - Sucesso
- 🟡 `[yellow]` - Aviso/informação
- 🔴 `[red]` - Erro
- 🔵 `[blue]` - Ação em andamento

Exemplo:
```
✅ Download concluído: Bad Boys (2020) [DUB]
⏱️  Aguardando 7.3 minutos até próximo upload...
🔄 Enviando Homem Aranha (2002) [DUB]...
```

---

## 🤝 Contribuição

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está licenciado sob a **MIT License** - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## 📞 Suporte

- 📺 **Telegram**: [@meucinepipoca](https://t.me/meucinepipoca)
- 🐛 **Issues**: [GitHub Issues](../../issues)
- 💬 **Discussões**: [GitHub Discussions](../../discussions)

---

## ⭐ Se gostou, deixe uma estrela!

Desenvolvido com ❤️ para a comunidade Telegram.