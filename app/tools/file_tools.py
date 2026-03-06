"""Read files under REPO_PATH only. Path traversal is blocked."""
from pathlib import Path

from app.config import REPO_PATH


def read_file(path: str) -> str:
    """
    Read file content under REPO_PATH. Path must resolve inside the repo (no escape).
    Returns file contents or raises if outside repo or not found.
    """
    if not REPO_PATH:
        return ""
    base = Path(REPO_PATH).resolve()
    # Normalize and resolve to avoid .. escape
    full = (base / path).resolve()
    if not str(full).startswith(str(base)):
        raise PermissionError(f"Path outside repository: {path}")
    if not full.is_file():
        raise FileNotFoundError(f"Not a file or not found: {path}")
    return full.read_text(encoding="utf-8", errors="replace")
