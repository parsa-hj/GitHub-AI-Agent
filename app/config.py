"""Configuration loaded from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GITHUB_TOKEN: str = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_REPO: str = (os.getenv("GITHUB_REPO") or "").strip()
REPO_PATH: str = os.getenv("REPO_PATH", "")

# Resolve REPO_PATH to absolute when set
if REPO_PATH:
    _repo = Path(REPO_PATH).resolve()
    if not _repo.is_dir():
        raise ValueError(f"REPO_PATH is not a directory: {_repo}")
    REPO_PATH = str(_repo)
else:
    # Default to cwd if not set (e.g. for first run)
    REPO_PATH = str(Path.cwd())


def has_github_token() -> bool:
    """True if a GitHub token is configured (enables creating issues/PRs via API)."""
    return bool(GITHUB_TOKEN)


def validate_ollama_reachable() -> bool:
    """Check if Ollama is reachable at OLLAMA_HOST."""
    return get_ollama_status()["reachable"]


def get_ollama_status() -> dict:
    """
    Check Ollama connection and whether the configured model is available.
    Returns dict: reachable (bool), model_available (bool), configured_model (str),
    available_models (list), message (str), error (str | None).
    """
    import json
    import urllib.request
    result = {
        "reachable": False,
        "model_available": False,
        "configured_model": OLLAMA_MODEL,
        "available_models": [],
        "message": "",
        "error": None,
    }
    try:
        url = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                result["error"] = f"Ollama returned status {resp.status}"
                return result
            data = json.loads(resp.read().decode())
            result["reachable"] = True
            models = data.get("models") or []
            result["available_models"] = [m.get("name", "").strip() for m in models if m.get("name")]
            configured = (OLLAMA_MODEL or "").strip()
            if not configured:
                result["message"] = "Ollama is running. Set OLLAMA_MODEL in .env to use a model."
                return result
            # Match model name (Ollama returns "name:tag" e.g. llama3.2:latest)
            result["model_available"] = any(
                configured == m or m.startswith(configured + ":") or m.split(":")[0] == configured
                for m in result["available_models"]
            )
            if not result["available_models"]:
                result["message"] = "Ollama is running but no models are installed. Run: ollama pull " + configured
                return result
            if result["model_available"]:
                result["message"] = f"Connected. Model '{configured}' is available."
            else:
                result["message"] = f"Ollama is running but model '{configured}' not found. Available: {', '.join(result['available_models'][:5])}{'…' if len(result['available_models']) > 5 else ''}. Run: ollama pull {configured}"
            return result
    except Exception as e:
        result["error"] = str(e)
        result["message"] = "Cannot reach Ollama. Is it running? Start with: ollama serve"
        return result
