"""Real git operations: diff and repo info. No fabricated content."""
import subprocess
from typing import Optional

from app.config import REPO_PATH


def get_diff(base: Optional[str] = None, range_spec: Optional[str] = None) -> str:
    """
    Run git diff in REPO_PATH.
    Either pass base (e.g. 'main') for diff against branch, or range_spec (e.g. 'HEAD~3..HEAD').
    Returns stdout; stderr raised as exception.
    """
    if not REPO_PATH:
        return ""
    cmd = ["git", "diff"]
    if range_spec:
        cmd.append(range_spec)
    elif base:
        cmd.append(base)
    else:
        cmd.append("HEAD")  # uncommitted changes
    result = subprocess.run(
        cmd,
        cwd=REPO_PATH,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0 and result.stderr:
        if "fatal:" in result.stderr or "not a git repository" in result.stderr:
            raise RuntimeError(f"git diff failed: {result.stderr.strip()}")
    return result.stdout or ""


def get_repo_info() -> dict:
    """Return branch, last commit hash, and remote URL for the repo at REPO_PATH."""
    if not REPO_PATH:
        return {"branch": "", "last_commit": "", "remote_url": ""}
    out = {}
    for label, cmd in [
        ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        ("last_commit", ["git", "rev-parse", "--short", "HEAD"]),
        ("remote_url", ["git", "config", "--get", "remote.origin.url"]),
    ]:
        r = subprocess.run(cmd, cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
        out[label] = (r.stdout or "").strip() if r.returncode == 0 else ""
    return out
