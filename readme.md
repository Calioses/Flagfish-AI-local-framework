# Discord RAG & Web Search Bot

An intelligent Discord bot that performs local codebase Retrieval-Augmented Generation (RAG) and real-time web search summaries using ChromaDB, DuckDuckGo, and local Ollama LLMs.

---

## Table of Contents

- [About the Project](#about-the-project)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Quick Setup](#quick-setup)
- [Configuration](#configuration)
- [Launch](#launch)
- [Usage](#usage)
- [License](#license)

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
- **LLM Engine:** Ollama (`qwen3.5-coder:b`)
- **Embeddings & Text Splitting:** SentenceTransformers, LangChain Text Splitters
- **Web Scraping & Search:** `duckduckgo-search`, `httpx`, `BeautifulSoup4`

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Git**
- **Ollama** installed and running locally

### Quick Setup

1. **Clone repository & enter directory:**

```bash
git clone https://github.com/your-username/discord-rag-bot.git
cd discord-rag-bot

```

2. **Create and activate virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

```

3. **Install dependencies:**

```bash
pip install -r requirements.txt

```

4. **Copy the config and adjust to your needs:**

5. **Run:**

## Configuration

Create a `config.yaml` file in the root directory:

---

## Launch

1. **Start Ollama service** _(if not running in background)_:

```bash
ollama serve

```

2. **Run the bot:**

```bash
python main.py

```

On startup, the bot automatically initializes `sitemap.db`, embeds specified local repositories into `chroma_db`, registers slash commands to Discord, and begins background syncing.

---

## Discord Bot Setup Guide

=======================

Step 1

## Create Application in Discord Developer Portal

1.  Navigate to the [Discord Developer Portal](https://discord.com/developers/applications)
    and log in.
2.  Click **New Application** in the top-right corner, enter a name, and click **Create**.

Step 2

## Configure Bot & Get Token

1.  Go to the **Bot** tab on the left sidebar.
2.  Click **Reset Token** (or **Copy**) under the Token section to generate your bot's token. Save this securely—do not share it.
3.  Scroll down to **Privileged Gateway Intents** and enable **Message Content Intent**.
4.  Click **Save Changes**.

Step 3

## Generate Bot Invite Link

1.  Go to **OAuth2** > **URL Generator** on the left menu.
2.  Under **Scopes**, check `bot` and `applications.commands`.
3.  Under **Bot Permissions**, select:
    - **Send Messages**
    - **Read Message History**
    - **Use Application Commands**
4.  Copy the generated URL at the bottom of the page.

Step 4

## Invite Bot to Your Server

1.  Paste the copied URL into your browser.
2.  Select your Discord server from the drop-down list. _(You must have **Manage Server** permission on the target server)_.
3.  Click **Continue** → **Authorize**.

Step 5

## Update Config and Launch

1.  Open your local `config.yaml` file.
2.  Add your copied bot token under `discord_tokens`:

        discord_tokens:
          - "YOUR_BOT_TOKEN_HERE"

3.  Run the Python script:

        python main.py

4.  Once running, type `/query ask` or `/query search` in any text channel where the bot has permission to view.

## Usage

Interact directly in Discord using slash commands:

- `/query ask query:<question>` – Queries local codebase context indexed in ChromaDB.
- `/query search query:<search_term>` – Performs a live DuckDuckGo web search and summarizes findings.

---

## License

Distributed under the MIT License. See `LICENSE` for details.

## Warning ⚠️

This software was built and tested by an idiot.

## 🐐 Credits 🐐

Me

Created by Monkeydew.
Use, modify, and distribute freely.
MIT Licensed.
