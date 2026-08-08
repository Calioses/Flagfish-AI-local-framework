import os
import sqlite3
import subprocess
import asyncio
import hashlib
import discord
from discord import app_commands
from discord.ext import commands
import chromadb
from sentence_transformers import SentenceTransformer
import httpx
import yaml
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()

DISCORD_TOKENS = config.get("discord_tokens", [])
GIT_REPOS = config.get("git_repos", [])
LOCAL_PATHS = config.get("local_paths", [])
INDEXED_EXTENSIONS = tuple(config.get("indexed_extensions", [
                           ".py", ".go", ".sql", ".md", ".txt", ".json", ".cpp", ".h"]))
IGNORED_DIRECTORIES = set(config.get("ignored_directories", [
                          ".git", "__pycache__", "node_modules", ".venv"]))
SYNC_INTERVAL = int(config.get("sync_interval", 60))
OLLAMA_URL = config["ollama"].get("url", "http://localhost:11434/api/chat")
OLLAMA_MODEL = config["ollama"].get("model", "qwen3.5-coder:b")
CHROMA_PATH = config.get("chroma_path", "./chroma_db")
SQLITE_PATH = config.get("sqlite_path", "./sitemap.db")
EMBEDDING_MODEL = config.get("embedding_model", "all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="codebase")
embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

db_conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
db_conn.execute(
    "CREATE TABLE IF NOT EXISTS visited_urls (url TEXT PRIMARY KEY, title TEXT)")
db_conn.execute(
    "CREATE TABLE IF NOT EXISTS file_hashes (path TEXT PRIMARY KEY, hash TEXT)")
db_conn.commit()

# Extension to LangChain language mapping
EXTENSION_LANG_MAP = {
    ".py": Language.PYTHON,
    ".go": Language.GO,
    ".cpp": Language.CPP,
    ".h": Language.CPP,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".rs": Language.RUST,
    ".html": Language.HTML,
    ".md": Language.MARKDOWN,
}

SEARCH_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "duckduckgo_search",
        "description": "Searches the web using DuckDuckGo to retrieve up-to-date information, external documentation, or real-time web content.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query term to look up on the web."
                }
            },
            "required": ["query"]
        }
    }
}


def get_file_hash(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_splitter_for_file(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in EXTENSION_LANG_MAP:
        return RecursiveCharacterTextSplitter.from_language(
            language=EXTENSION_LANG_MAP[ext], chunk_size=1000, chunk_overlap=100
        )
    return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


async def git_sync_loop():
    while True:
        await asyncio.sleep(SYNC_INTERVAL)
        updated = False
        for repo_path in GIT_REPOS:
            if os.path.exists(repo_path):
                res = subprocess.run(
                    ["git", "-C", repo_path, "pull"], capture_output=True, text=True)
                if "Already up to date." not in res.stdout:
                    updated = True
        if updated:
            reindex_all()


def process_target_path(target_path, docs, ids, metadatas):
    if not os.path.exists(target_path):
        return

    def parse_file(file_path):
        if not file_path.endswith(INDEXED_EXTENSIONS):
            return

        current_hash = get_file_hash(file_path)
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT hash FROM file_hashes WHERE path = ?", (file_path,))
        row = cursor.fetchone()

        # Skip unchanged files
        if row and row[0] == current_hash:
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            splitter = get_splitter_for_file(file_path)
            chunks = splitter.split_text(content)

            # Purge old vectors for this specific modified file before adding new ones
            existing = collection.get(where={"path": file_path})
            if existing and existing["ids"]:
                collection.delete(ids=existing["ids"])

            for i, chunk in enumerate(chunks):
                docs.append(chunk)
                ids.append(f"{file_path}:{i}")
                metadatas.append({"source": "local", "path": file_path})

            cursor.execute(
                "INSERT OR REPLACE INTO file_hashes (path, hash) VALUES (?, ?)", (file_path, current_hash))
            db_conn.commit()
        except Exception:
            pass

    if os.path.isfile(target_path):
        parse_file(target_path)
    elif os.path.isdir(target_path):
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES]
            for file in files:
                parse_file(os.path.join(root, file))


def reindex_all():
    docs, ids, metadatas = [], [], []

    for repo_path in GIT_REPOS:
        process_target_path(repo_path, docs, ids, metadatas)

    for path in LOCAL_PATHS:
        process_target_path(path, docs, ids, metadatas)

    # Batch inserts to avoid ChromaDB batch limits
    BATCH_SIZE = 500
    if docs:
        for i in range(0, len(docs), BATCH_SIZE):
            batch_docs = docs[i:i + BATCH_SIZE]
            batch_ids = ids[i:i + BATCH_SIZE]
            batch_meta = metadatas[i:i + BATCH_SIZE]

            embeddings = embedder.encode(batch_docs).tolist()
            collection.add(documents=batch_docs, embeddings=embeddings,
                           ids=batch_ids, metadatas=batch_meta)


async def search_and_store(query: str) -> str:
    loop = asyncio.get_running_loop()

    def sync_search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=3))

    results = await loop.run_in_executor(None, sync_search)
    web_texts = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for r in results:
            url = r.get("href")
            title = r.get("title", "")

            if not url:
                continue

            db_conn.execute(
                "INSERT OR IGNORE INTO visited_urls (url, title) VALUES (?, ?)", (url, title))
            db_conn.commit()

            try:
                res = await client.get(url)
                soup = BeautifulSoup(res.text, "html.parser")
                text = " ".join([p.get_text() for p in soup.find_all("p")])
                if text.strip():
                    web_texts.append(text[:2000])
            except Exception:
                continue

    return "\n".join(web_texts)


async def query_ollama_with_tools(messages: list, allow_tools: bool = True) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": 2000
        }
    }
    if allow_tools:
        payload["tools"] = [SEARCH_TOOL_DEFINITION]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        response_data = resp.json()
        message = response_data.get("message", {})

        tool_calls = message.get("tool_calls")
        if tool_calls and allow_tools:
            messages.append(message)
            for tool_call in tool_calls:
                func_name = tool_call.get("function", {}).get("name")
                arguments = tool_call.get("function", {}).get("arguments", {})

                if func_name == "duckduckgo_search":
                    search_query = arguments.get("query", "")
                    web_results = await search_and_store(search_query)
                    messages.append({
                        "role": "tool",
                        "content": web_results if web_results else "No web results found."
                    })

            return await query_ollama_with_tools(messages, allow_tools=False)

        return message.get("content", "No response generated.")


async def send_large_interaction_message(interaction: discord.Interaction, text: str):
    chunks = [text[i:i + 1900] for i in range(0, len(text), 1900)]
    if not chunks:
        await interaction.followup.send("No response generated.")
        return

    await interaction.followup.send(chunks[0])
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk)


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


class QueryGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="query", description="Query local codebase or web")

    @app_commands.command(name="ask", description="Query local codebase context")
    @app_commands.describe(query="Your question about the codebase")
    async def ask(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        try:
            query_emb = embedder.encode(query).tolist()
            results = collection.query(
                query_embeddings=[query_emb], n_results=3)
            context = "\n".join(
                results["documents"][0]) if results["documents"] and results["documents"][0] else ""

            messages = [
                {
                    "role": "system",
                    "content": "Keep your answer detailed yet concise, under 8,000 characters total. Use Orwell's rules for writing. If the provided local codebase context is insufficient to answer the question, you may use the duckduckgo_search tool to look up information on the web."
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion:\n{query}"
                }
            ]

            response_text = await query_ollama_with_tools(messages, allow_tools=True)
            await send_large_interaction_message(interaction, response_text)
        except Exception as e:
            await interaction.followup.send(f"Error processing request: {str(e)}")

    @app_commands.command(name="search", description="Search the web and query local LLM")
    @app_commands.describe(query="Your search query")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        try:
            web_context = await search_and_store(query)

            messages = [
                {
                    "role": "user",
                    "content": f"Web Context:\n{web_context}\n\nQuestion:\n{query}"
                }
            ]

            response_text = await query_ollama_with_tools(messages, allow_tools=False)
            await send_large_interaction_message(interaction, response_text)
        except Exception as e:
            await interaction.followup.send(f"Error processing search request: {str(e)}")


bot.tree.add_command(QueryGroup())


@bot.event
async def on_ready():
    reindex_all()
    await bot.tree.sync()
    bot.loop.create_task(git_sync_loop())

if __name__ == "__main__":
    if DISCORD_TOKENS:
        bot.run(DISCORD_TOKENS[0])
