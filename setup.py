#!/usr/bin/env python3
"""
Setup script — verifies the pipeline dependencies are ready.

Groq (recommended): set OPENAI_API_KEY in your .env — no local services needed.
Ollama (local/offline): install Ollama and run `ollama pull llama3.2:3b`.

Run once after installing dependencies: python setup.py
"""
import os
import subprocess
import sys
from pathlib import Path

import requests


def _load_dotenv(path: str = ".env") -> None:
    """Parse a .env file and inject missing keys into os.environ."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_BASE_URL = "http://localhost:11434"


def check_static_ffmpeg() -> bool:
    """Register the static-ffmpeg binary and confirm it resolves."""
    try:
        import static_ffmpeg

        static_ffmpeg.add_paths()
        import shutil

        if shutil.which("ffmpeg"):
            print("✓ ffmpeg ready (via static-ffmpeg — no system install required)")
            return True
        # static-ffmpeg may not have been downloaded yet; that's fine — it
        # downloads on first use during the pipeline run.
        print("✓ static-ffmpeg installed (binary downloads on first pipeline run)")
        return True
    except Exception as exc:
        print(f"✗ static-ffmpeg not available: {exc}")
        print("  Run: pip install static-ffmpeg")
        return False


def check_groq() -> bool:
    """Check whether a Groq API key is configured."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        print("✓ OPENAI_API_KEY set — Groq path active")
        return True
    return False


def check_ollama() -> list | None:
    """Return the list of local Ollama models, or None if Ollama is not running."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            print("✓ ollama running")
            return r.json().get("models", [])
    except requests.exceptions.ConnectionError:
        pass
    return None


def ensure_model(existing_models: list, model: str = DEFAULT_OLLAMA_MODEL) -> bool:
    names = [m.get("name", "") for m in (existing_models or [])]
    if any(model in n for n in names):
        print(f"✓ model ready ({model})")
        return True
    print(f"  Pulling {model} …")
    result = subprocess.run(["ollama", "pull", model], check=False)
    if result.returncode == 0:
        print(f"✓ model ready ({model})")
        return True
    print(f"✗ failed to pull {model}")
    return False


def main() -> None:
    ok = True
    ok &= check_static_ffmpeg()

    groq_ready = check_groq()
    if groq_ready:
        print("  (Ollama check skipped — using Groq API)")
    else:
        print("  OPENAI_API_KEY not set — checking Ollama …")
        models = check_ollama()
        if models is None:
            print("✗ ollama not running")
            print("  Option A (recommended): set OPENAI_API_KEY in .env to use Groq")
            print("  Option B (local/offline): install Ollama — https://ollama.com/download")
            print("                            then run: ollama serve && ollama pull llama3.2:3b")
            ok = False
        else:
            ok &= ensure_model(models)

    if not ok:
        print("\nFix the issues above, then re-run python setup.py")
        sys.exit(1)

    print("\nAll checks passed — ready to run the pipeline.")


if __name__ == "__main__":
    main()
