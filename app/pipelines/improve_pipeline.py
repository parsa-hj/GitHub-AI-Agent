"""
Improve pipeline: fetch issue/PR -> Reviewer critique -> Writer improved draft -> Gatekeeper reflection.
Returns critique + improved title/body (no GitHub edit).
"""
from typing import Any, Optional

from app.agents.gatekeeper import run_gatekeeper
from app.agents.writer import run_writer_improve
from app.config import GITHUB_REPO
from app.tools.github_tools import get_issue, get_pull_request


def run_improve_issue(
    issue_number: int,
    repo_slug: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Improve an existing issue: critique then suggest improved title/body."""
    slug = repo_slug or GITHUB_REPO
    if not slug:
        return {"error": "GITHUB_REPO not set"}
    from app.agents import ollama_client
    data = get_issue(slug, issue_number)
    title, body = data["title"], data["body"] or ""
    critique_messages = [{"role": "user", "content": f"""You are the **Reviewer** agent. Critique this GitHub Issue. Identify:
- Unclear or missing information
- Vague language
- Missing or weak acceptance criteria
- What could be improved

Issue title: {title}

Issue body:
{body}

Respond with a short critique (bullets) and suggested improvements for structure and clarity."""}]
    resp = ollama_client.chat(critique_messages, model=model)
    critique = (getattr(resp.message, "content", None) or "").strip()

    improved_title, improved_body = run_writer_improve(
        critique=critique,
        current_title=title,
        current_body=body,
        is_pr=False,
        model=model,
    )
    reflection = run_gatekeeper(improved_title, improved_body, is_pr=False, model=model)
    return {
        "critique": critique,
        "improved_title": improved_title,
        "improved_body": improved_body,
        "reflection_verdict": reflection.verdict,
        "reflection_artifact": reflection.to_display(),
        "original_number": issue_number,
        "original_url": data.get("html_url"),
    }


def run_improve_pr(
    pr_number: int,
    repo_slug: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Improve an existing PR: critique then suggest improved title/body."""
    slug = repo_slug or GITHUB_REPO
    if not slug:
        return {"error": "GITHUB_REPO not set"}
    data = get_pull_request(slug, pr_number)
    title, body = data["title"], data["body"] or ""
    from app.agents import ollama_client
    critique_messages = [{"role": "user", "content": f"""You are the **Reviewer** agent. Critique this GitHub Pull Request. Identify:
- Unclear or missing information
- Vague language
- Missing test plan or behavior description
- What could be improved

PR title: {title}

PR body:
{body}

Respond with a short critique (bullets) and suggested improvements."""}]
    resp = ollama_client.chat(critique_messages, model=model)
    critique = (getattr(resp.message, "content", None) or "").strip()

    improved_title, improved_body = run_writer_improve(
        critique=critique,
        current_title=title,
        current_body=body,
        is_pr=True,
        model=model,
    )
    reflection = run_gatekeeper(improved_title, improved_body, is_pr=True, model=model)
    return {
        "critique": critique,
        "improved_title": improved_title,
        "improved_body": improved_body,
        "reflection_verdict": reflection.verdict,
        "reflection_artifact": reflection.to_display(),
        "original_number": pr_number,
        "original_url": data.get("html_url"),
    }
