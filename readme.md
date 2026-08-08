````markdown
# Discord RAG & Web Search Bot

An intelligent Discord bot that performs local codebase Retrieval-Augmented Generation (RAG) and real-time web search summaries using ChromaDB, DuckDuckGo, and local Ollama LLMs.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Discord.py](https://img.shields.io/badge/Discord.py-v2.0+-5865F2?style=flat&logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![Ollama](https://img.shields.io/badge/Ollama-Supported-black?style=flat&logo=ollama&logoColor=white)](https://ollama.com)

---

## Table of Contents

- [About the Project](#about-the-project)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [License](#license)

---

## About the Project

This project turns your local codebase and web search capabilities into a Discord-accessible AI assistant. By indexing source files into a vector database (`ChromaDB`) using syntax-aware splitters and leveraging `Ollama` for local LLM inference, users can query codebases and live web results directly through native Discord slash commands.

---

## Key Features

- 🔍 **Codebase RAG (`/query ask`):** Performs semantic search over local Git repositories and directory paths using `SentenceTransformers` (`all-MiniLM-L6-v2`) and injects relevant code context into local LLM prompts.
- 🌐 **Web Search Summaries (`/query search`):** Scrapes top web results via DuckDuckGo and `BeautifulSoup`, summarizing fresh web context with Ollama.
- 🗺️ **Sitemap Tracking:** Logs visited URLs and document state into a local SQLite database (`sitemap.db`) to keep track of referenced sources.
- 🔄 **Incremental Indexing:** Computes SHA-256 file hashes to skip unmodified code files and automatically purges/re-indexes modified vectors.
- ⏱️ **Automatic Git Synchronization:** Runs a background loop that monitors specified Git repositories and triggers automatic re-indexing upon `git pull` updates.
- ✂️ **Chunking Safety:** Automatically splits large AI responses into 1,900-character sequential messages to comply with Discord's 2,000-character message limit.

---

## Tech Stack

- **Language:** Python 3.10+
- **Discord Integration:** `discord.py` (Slash Commands via `app_commands`)
- **Vector Database:** ChromaDB
- **Relational Database:** SQLite
- **LLM Engine:** Ollama (`qwen2.5-coder:14b`)
- **Embeddings & Text Splitting:** SentenceTransformers, LangChain Text Splitters
- **Web Scraping & Search:** `duckduckgo-search`, `httpx`, `BeautifulSoup4`

---

## Getting Started

Follow these instructions to run the bot locally on your machine.

### Prerequisites

1. **Python 3.10+**
2. **Git**
3. **Ollama:** Installed and serving models locally (`http://localhost:11434`).
   ```bash
   ollama pull qwen2.5-coder:14b
   ```
````

### Installation

1. **Clone the repository:**

```bash
git clone [https://github.com/your-username/discord-rag-bot.git](https://github.com/your-username/discord-rag-bot.git)
cd discord-rag-bot

```

2. **Create and activate a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

```

3. **Install required packages:**

```bash
pip install -r requirements.txt

```

---

## Configuration

Create a `config.yaml` file in the root directory:

```yaml
discord_tokens:
  - 'YOUR_DISCORD_BOT_TOKEN'

git_repos:
  - '/path/to/your/git/repository'

local_paths:
  - '/path/to/your/local/codebase'

indexed_extensions:
  - '.py'
  - '.go'
  - '.sql'
  - '.md'
  - '.txt'
  - '.json'
  - '.cpp'
  - '.h'

ignored_directories:
  - '.git'
  - '__pycache__'
  - 'node_modules'
  - '.venv'

sync_interval: 60

ollama:
  url: 'http://localhost:11434/api/generate'
  model: 'qwen2.5-coder:14b'

chroma_path: './chroma_db'
sqlite_path: './sitemap.db'
embedding_model: 'all-MiniLM-L6-v2'
```

---

## Usage

1. **Start the application:**

```bash
python main.py

```

2. **Available Slash Commands in Discord:**

- `/query ask query:<question>` – Queries local codebase context indexed in ChromaDB.
- `/query search query:<search_term>` – Fetches live web results via DuckDuckGo and summarizes the findings.

---

## License

Distributed under the MIT License. See `LICENSE` for details.

```

```
