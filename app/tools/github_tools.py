"""GitHub API via PyGithub: fetch issues/PRs (unauthenticated for public repos); create only with token."""
import re
from typing import Any, Optional

from github import Github

from app.config import GITHUB_REPO, GITHUB_TOKEN


def parse_repo_from_link(link_or_slug: str) -> Optional[str]:
    """
    Parse owner/repo from a GitHub URL or return owner/repo if already in that form.
    Examples: https://github.com/owner/repo -> owner/repo; owner/repo -> owner/repo.
    """
    s = (link_or_slug or "").strip()
    if not s:
        return None
    # GitHub URL patterns
    m = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/?#]+)", s, re.IGNORECASE)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # owner/repo
    if "/" in s and " " not in s and len(s.split("/")) == 2:
        return s
    return None


def _get_github_client(authenticated: bool = True):
    """Authenticated client (for create) or unauthenticated (for public repo read; 60 req/hr limit)."""
    if authenticated and GITHUB_TOKEN:
        return Github(GITHUB_TOKEN)
    return Github()  # unauthenticated: public repos only, rate limited


def _get_repo(repo_slug: Optional[str] = None, *, require_auth: bool = False):
    slug = (repo_slug or GITHUB_REPO or "").strip()
    if not slug:
        raise ValueError("Repo required: set GITHUB_REPO or provide repo (owner/name or GitHub URL).")
    if require_auth and not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN required to create issues or PRs. Use read-only mode or set a token.")
    client = _get_github_client(authenticated=require_auth)
    return client.get_repo(slug)


def get_issue(repo_slug: str, number: int) -> dict[str, Any]:
    """Fetch issue by number (public repos work without token; rate limit applies). Returns title, body, state."""
    slug = parse_repo_from_link(repo_slug) or repo_slug
    repo = _get_repo(slug, require_auth=False)
    issue = repo.get_issue(number)
    return {
        "title": issue.title,
        "body": issue.body or "",
        "state": issue.state,
        "number": issue.number,
        "html_url": issue.html_url,
    }


def get_pull_request(repo_slug: str, number: int) -> dict[str, Any]:
    """Fetch PR by number (public repos work without token; rate limit applies). Returns title, body, state, base, head."""
    slug = parse_repo_from_link(repo_slug) or repo_slug
    repo = _get_repo(slug, require_auth=False)
    pr = repo.get_pull(number)
    return {
        "title": pr.title,
        "body": pr.body or "",
        "state": pr.state,
        "base": pr.base.ref,
        "head": pr.head.ref,
        "number": pr.number,
        "html_url": pr.html_url,
    }


def create_issue(
    repo_slug: Optional[str], title: str, body: str, labels: Optional[list[str]] = None
) -> dict[str, Any]:
    """
    Create a GitHub issue. Call only after human approval. Requires GITHUB_TOKEN.
    Returns created issue URL and number.
    """
    slug = (repo_slug or GITHUB_REPO or "").strip()
    if slug and parse_repo_from_link(slug):
        slug = parse_repo_from_link(slug)
    repo = _get_repo(slug, require_auth=True)
    kwargs = {"title": title, "body": body}
    if labels:
        kwargs["labels"] = labels
    issue = repo.create_issue(**kwargs)
    return {"number": issue.number, "html_url": issue.html_url, "title": issue.title}


def create_pull_request(
    repo_slug: Optional[str],
    title: str,
    body: str,
    head: str,
    base: str,
) -> dict[str, Any]:
    """
    Create a GitHub pull request. Call only after human approval. Requires GITHUB_TOKEN.
    Returns created PR URL and number.
    """
    slug = (repo_slug or GITHUB_REPO or "").strip()
    if slug and parse_repo_from_link(slug):
        slug = parse_repo_from_link(slug)
    repo = _get_repo(slug, require_auth=True)
    pr = repo.create_pull(title=title, body=body, head=head, base=base)
    return {"number": pr.number, "html_url": pr.html_url, "title": pr.title}
