import os
import sys
import json
import time
import shutil
import subprocess
import urllib.request

CONFIG_FILE = "config.yaml"
REQUIREMENTS_FILE = "requirements.txt"

LOGO = r"""

___________.__                  _____.__        .__     
\_   _____/|  | _____   _____/ ____\__| _____|  |__  
 |   __)  |  | \__  \  / ___\  __\|  |/  ___/  |  \ 
 |    \   |  |__/ __ \_/ /_/  >  |  |  |\___ \|   Y  \
 \___  /   |____(____  /\___  /|__|  |__/____  >___|  /
     \/              \//_____/               \/     \/ 

\n
"""


def show_popups():
    print(LOGO)
    print("==================================================")
    print("              APPLICATION LAUNCHER                ")
    print("==================================================")
    print("  License: MIT License")
    print("  Copyright (c) 2026 All Rights Reserved.")
    print("\n  Press ENTER to accept terms and continue...")
    print("==================================================")
    input()


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: Required configuration file '{CONFIG_FILE}' not found.")
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print("Installing PyYAML to read config...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyyaml"])
        import yaml

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def install_dependencies(config):
    if os.path.exists(REQUIREMENTS_FILE):
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])

    # 1. Verify chromadb import
    try:
        import chromadb
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "chromadb"])

    # 2. Check Ollama executable
    if not shutil.which("ollama"):
        print("Error: 'ollama' command not found. Please install Ollama from https://ollama.com")
        sys.exit(1)

    # 3. Read model directly from loaded config
    model_name = config.get("ollama", {}).get("model")
    if not model_name:
        print("Error: No 'model' specified under 'ollama' section in config.yaml.")
        sys.exit(1)

    # 4. Check if Ollama server is running; start background process if not
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as response:
            pass
    except Exception:
        print("Ollama service not detected. Starting 'ollama serve' in background...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)

    # 5. Fetch installed models and pull if missing
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            installed_models = [m.get("name") for m in data.get("models", [])]

        if not any(model_name in m for m in installed_models):
            print(
                f"Model '{model_name}' not found locally. Pulling with Ollama...")
            subprocess.check_call(["ollama", "pull", model_name])
    except Exception as e:
        print(f"Error checking/pulling Ollama model: {e}")
        sys.exit(1)


def run_setup():
    show_popups()
    config = load_config()
    install_dependencies(config)


if __name__ == "__main__":
    run_setup()
