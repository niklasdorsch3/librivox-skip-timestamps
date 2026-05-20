#!/usr/bin/env python3
"""
Setup script — verifies ffmpeg and ollama are ready, then pulls the default model.
Run once before using the pipeline: python setup.py
"""
import shutil
import subprocess
import sys

import requests

DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_BASE_URL = "http://localhost:11434"


def check_ffmpeg():
    if shutil.which("ffmpeg"):
        print("✓ ffmpeg installed")
        return True
    print("✗ ffmpeg not found")
    print("  Install ffmpeg:")
    print("  macOS:   brew install ffmpeg")
    print("  Ubuntu:  sudo apt-get install ffmpeg")
    print("  Windows: https://ffmpeg.org/download.html")
    return False


def check_ollama():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            print("✓ ollama running")
            return r.json().get("models", [])
    except requests.exceptions.ConnectionError:
        pass
    print("✗ ollama not running")
    print("  Install ollama: https://ollama.com/download")
    print("  Start it with:  ollama serve")
    return None


def ensure_model(existing_models, model=DEFAULT_OLLAMA_MODEL):
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


def main():
    ok = True
    ok &= check_ffmpeg()
    models = check_ollama()
    if models is None:
        ok = False
    else:
        ok &= ensure_model(models)

    if not ok:
        print("\nFix the issues above, then re-run python setup.py")
        sys.exit(1)

    print("\nAll checks passed — ready to run the pipeline.")


if __name__ == "__main__":
    main()
