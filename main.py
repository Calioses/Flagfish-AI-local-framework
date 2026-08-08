import os
import sqlite3
import subprocess
import asyncio
import discord
from discord.ext import commands
import chromadb
from sentence_transformers import SentenceTransformer
import httpx
import yaml
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter


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
OLLAMA_URL = config["ollama"].get("url", "http://localhost:11434/api/generate")
OLLAMA_MODEL = config["ollama"].get("model", "qwen2.5-coder:14b")
CHROMA_PATH = config.get("chroma_path", "./chroma_db")
SQLITE_PATH = config.get("sqlite_path", "./sitemap.db")
EMBEDDING_MODEL = config.get("embedding_model", "all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="codebase")
embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

db_conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
db_conn.execute(
    "CREATE TABLE IF NOT EXISTS visited_urls (url TEXT PRIMARY KEY, title TEXT)"
)


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


def process_target_path(target_path, splitter, docs, ids, metadatas):
    if not os.path.exists(target_path):
        return

    def parse_file(file_path):
        if file_path.endswith(INDEXED_EXTENSIONS):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                chunks = splitter.split_text(content)
                for i, chunk in enumerate(chunks):
                    docs.append(chunk)
                    ids.append(f"{file_path}:{i}")
                    metadatas.append({"source": "local", "path": file_path})
            except Exception:
                pass

    if os.path.isfile(target_path):
        parse_file(target_path)
    elif os.path.isdir(target_path):
        for root, dirs, files in os.walk(target_path):
            # Prune ignored directories in-place so os.walk skips descending into them
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES]

            for file in files:
                parse_file(os.path.join(root, file))


def reindex_all():
    existing = collection.get(where={"source": "local"})
    if existing and existing["ids"]:
        collection.delete(ids=existing["ids"])

    splitter = RecursiveCharacterTextSplitter.from_language(
        language="python", chunk_size=1000, chunk_overlap=100
    )
    docs, ids, metadatas = [], [], []

    for repo_path in GIT_REPOS:
        process_target_path(repo_path, splitter, docs, ids, metadatas)

    for path in LOCAL_PATHS:
        process_target_path(path, splitter, docs, ids, metadatas)

    if docs:
        embeddings = embedder.encode(docs).tolist()
        collection.add(documents=docs, embeddings=embeddings,
                       ids=ids, metadatas=metadatas)


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
                "INSERT OR IGNORE INTO visited_urls (url, title) VALUES (?, ?)",
                (url, title)
            )
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


async def send_large_message(ctx, text: str):
    for i in range(0, len(text), 1900):
        await ctx.send(text[i:i+1900])

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command(name="ask")
async def ask(ctx, *, query: str):
    query_emb = embedder.encode(query).tolist()
    results = collection.query(query_embeddings=[query_emb], n_results=3)
    context = "\n".join(
        results["documents"][0]) if results["documents"] and results["documents"][0] else ""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"Context:\n{context}\n\nQuestion:\n{query}",
        "stream": False
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        data = resp.json()

    await send_large_message(ctx, data.get("response", "No response generated."))


@bot.command(name="search")
async def search(ctx, *, query: str):
    web_context = await search_and_store(query)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"Web Context:\n{web_context}\n\nQuestion:\n{query}",
        "stream": False
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        data = resp.json()

    await send_large_message(ctx, data.get("response", "No response generated."))


@bot.event
async def on_ready():
    reindex_all()
    bot.loop.create_task(git_sync_loop())

if __name__ == "__main__":
    if DISCORD_TOKENS:
        bot.run(DISCORD_TOKENS[0])
