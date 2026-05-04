# 🎸 ConcertArr

> **Artwork fetcher automático para shows e concertos**

ConcertArr é uma ferramenta web para homelab que busca automaticamente **capas, backdrops e logos** para sua coleção de DVDs e Blu-rays de shows musicais e concertos — usando **TMDb** e **Discogs** como fontes.

Feito para rodar em **Docker** junto com Jellyfin, Sonarr, Radarr e toda a stack *arr.

---

## ✨ Funcionalidades

- 🔍 **Busca automática** via TMDb (shows internacionais) e Discogs (artistas brasileiros e DVDs raros)
- 🖼️ **Baixa automaticamente** `poster`, `backdrop`, `landscape` e `logo`
- 📁 **File Browser integrado** — navega pelas pastas do servidor direto na interface
- 🎯 **Mosaico de capas** — visualize e altere capas com um clique
- ⚡ **Busca manual** via link do Discogs para os não encontrados
- 🔔 **Notificação automática** do Jellyfin após o scan
- ⏭️ **Ignora** shows que já têm todas as imagens
- 📊 **Progresso em tempo real** durante a busca
- 🐳 **Docker ready** — roda junto com sua stack homelab

---

## 📸 Screenshots

```
Tela 1 — Selecionar pasta      Tela 2 — Configurar APIs
┌─────────────────────────┐    ┌─────────────────────────┐
│  🎸 ConcertArr          │    │  🎸 ConcertArr          │
│                         │    │                         │
│  Onde estão seus shows? │    │  Chaves de API          │
│  ┌───────────────────┐  │    │  TMDb API Key           │
│  │ /mnt/media/shows  │  │    │  ┌───────────────────┐  │
│  └───────────────────┘  │    │  │ ****************  │  │
│  [📁 Procurar]          │    │  └───────────────────┘  │
│                         │    │  Discogs Token          │
│           [Próximo →]   │    │  ┌───────────────────┐  │
└─────────────────────────┘    │  │ ****************  │  │
                               └─────────────────────────┘

Tela 3 — Buscando             Tela 4 — Resultado
┌─────────────────────────┐    ┌─────────────────────────┐
│  Buscando capas...      │    │  Concluído!             │
│  AC/DC - Live (1992)    │    │  60 shows processados   │
│  ████████████░░  75%    │    │  ┌────┬────┬────┐       │
│                         │    │  │ 39 │ 19 │  2 │       │
│  ✅ AC/DC       TMDb    │    │  │TMDb│Disc│N/A │       │
│  ✅ Adele       TMDb    │    │  └────┴────┴────┘       │
│  ✅ Jorge&Mat   Discogs │    │                         │
│  ⚠️  Um Bazinho  N/A    │    │  [⚡ Busca manual]      │
│                         │    │  [✎ Alterar capa]       │
└─────────────────────────┘    └─────────────────────────┘
```

---

## 🚀 Instalação

### Via Docker (recomendado)

```bash
git clone https://github.com/gabrieldepinhob/concertarr.git
cd concertarr
docker build -t concertarr .
docker run -d \
  --name concertarr \
  --restart unless-stopped \
  -p 8090:8090 \
  -v /mnt/homelab:/mnt/homelab \
  -v /opt/concertarr/data:/app/data \
  concertarr
```

Acessa em `http://localhost:8090`

### Via docker-compose (junto com sua stack)

Adiciona ao seu `docker-compose.yml`:

```yaml
concertarr:
  image: concertarr:latest
  container_name: concertarr
  restart: unless-stopped
  ports:
    - "8090:8090"
  volumes:
    - /mnt/homelab:/mnt/homelab
    - /opt/concertarr/data:/app/data
```

### Manual (sem Docker)

```bash
git clone https://github.com/gabrieldepinhob/concertarr.git
cd concertarr/backend
pip install -r requirements.txt
python main.py
```

---

## ⚙️ Configuração

Na primeira execução o app vai pedir:

| Campo | Descrição | Como obter |
|---|---|---|
| **Pasta dos shows** | Caminho completo onde estão os arquivos | Use o File Browser integrado |
| **TMDb API Key** | Chave da API do The Movie Database | [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) |
| **Discogs Token** | Token pessoal do Discogs | [discogs.com/settings/developers](https://www.discogs.com/settings/developers) |

As configurações são salvas automaticamente para uso futuro.

---

## 📁 Estrutura gerada

Para cada show, o ConcertArr cria:

```
/mnt/media/shows/
  Artista - Nome do Show (2024).mkv
  Artista - Nome do Show (2024)-poster.png      ← capa vertical
  Artista - Nome do Show (2024)-backdrop1.png   ← imagem de fundo
  Artista - Nome do Show (2024)-landscape.png   ← imagem horizontal
  Artista - Nome do Show (2024)-logo.png        ← logo do artista
```

Compatível com **Jellyfin**, **Plex** e **Emby**.

---

## 🔄 Fluxo de busca

```
Arquivo .mkv
    ↓
Extrai título + ano do nome do arquivo
    ↓
Busca no TMDb (shows internacionais)
    ↓ (não encontrou)
Busca no Discogs (DVD/Blu-ray)
    ↓ (não encontrou)
Lista para busca manual via link do Discogs
    ↓
Baixa: poster + backdrop + landscape + logo
    ↓
Notifica o Jellyfin para atualizar a biblioteca
```

---

## 🛠️ Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Frontend | HTML / CSS / JavaScript puro |
| APIs | TMDb + Discogs |
| Container | Docker |

---

## 📡 API Endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/config` | Carrega configuração salva |
| `POST` | `/api/config` | Salva configuração |
| `GET` | `/api/browse` | File Browser — lista pastas |
| `GET` | `/api/shows` | Lista shows com status das capas |
| `GET` | `/api/image` | Serve imagens locais |
| `POST` | `/api/scan` | Inicia o scan em background |
| `GET` | `/api/scan/status` | Status do scan em tempo real |
| `POST` | `/api/manual` | Busca manual via link do Discogs |

Documentação interativa disponível em `http://localhost:8090/docs`

---

## 🏠 Integração com Jellyfin

Após o scan, o ConcertArr notifica o Jellyfin automaticamente para atualizar a biblioteca. Certifique-se de configurar a biblioteca de Shows como **Music Videos** e habilitar o **NFO** nos gravadores de metadados.

---

## 🤝 Contribuindo

Pull requests são bem-vindos! Para mudanças maiores, abra uma issue primeiro para discutir o que você gostaria de mudar.

---

## 📝 Licença

MIT — sinta-se livre para usar, modificar e distribuir.

---

<div align="center">
  Feito com ❤️ para a comunidade homelab
  <br>
  <sub>Parte do stack PinhoFlix 🎬</sub>
</div>
