"""
Writer agent: drafts Issue or PR content (title + body) or improved version for existing Issue/PR.
Output: title and body in markdown.
"""
from typing import Optional

from app.agents import ollama_client


def run_writer_issue(
    planner_output: str,
    context: str,
    model: Optional[str] = None,
) -> tuple[str, str]:
    """
    Draft an Issue. Returns (title, body).
    Body must include: problem description, evidence, acceptance criteria, risk level.
    """
    prompt = f"""You are the **Writer** agent. Draft a GitHub Issue.

--- Planner / scope ---
{planner_output}

--- Context (diff or instruction) ---
{context}

Output format (use exactly these headers):
Title: <one line title>

Body:
## Problem description
<text>

## Evidence
<from diff or context>

## Acceptance criteria
- <criterion 1>
- <criterion 2>

## Risk level
<low | medium | high>
"""
    messages = [{"role": "user", "content": prompt}]
    resp = ollama_client.chat(messages, model=model)
    text = (getattr(resp.message, "content", None) or "").strip()
    return _parse_title_body(text)


def run_writer_pr(
    planner_output: str,
    context: str,
    model: Optional[str] = None,
) -> tuple[str, str]:
    """
    Draft a PR. Returns (title, body).
    Body must include: summary, files affected, behavior change, test plan, risk level.
    """
    prompt = f"""You are the **Writer** agent. Draft a GitHub Pull Request.

--- Planner / scope ---
{planner_output}

--- Context (diff or instruction) ---
{context}

Output format (use exactly these headers):
Title: <one line title>

Body:
## Summary
<text>

## Files affected
<list>

## Behavior change
<what changed>

## Test plan
<how to verify>

## Risk level
<low | medium | high>
"""
    messages = [{"role": "user", "content": prompt}]
    resp = ollama_client.chat(messages, model=model)
    text = (getattr(resp.message, "content", None) or "").strip()
    return _parse_title_body(text)


def run_writer_improve(
    critique: str,
    current_title: str,
    current_body: str,
    is_pr: bool,
    model: Optional[str] = None,
) -> tuple[str, str]:
    """
    Propose improved title and body for an existing Issue/PR. Critique first, then suggest.
    Returns (improved_title, improved_body). No silent changes—structured suggestion only.
    """
    kind = "Pull Request" if is_pr else "Issue"
    prompt = f"""You are the **Writer** agent. Propose an improved structured version of this {kind}.

--- Critique (what is unclear or missing) ---
{critique}

--- Current title ---
{current_title}

--- Current body ---
{current_body}

Propose improved title and full body. Fix vague language, add or clarify acceptance criteria, structure sections.
Output format:
Title: <improved title>

Body:
<full improved body in markdown>
"""
    messages = [{"role": "user", "content": prompt}]
    resp = ollama_client.chat(messages, model=model)
    text = (getattr(resp.message, "content", None) or "").strip()
    return _parse_title_body(text)


def _parse_title_body(text: str) -> tuple[str, str]:
    """Extract Title: and Body: (or first line as title, rest as body)."""
    title = ""
    body = text
    if "Title:" in text:
        a, _, rest = text.partition("Title:")
        if "Body:" in rest:
            title_part, _, body = rest.partition("Body:")
            title = title_part.strip().strip("\n")
            body = body.strip()
        else:
            lines = rest.strip().split("\n")
            title = lines[0].strip() if lines else ""
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    elif "\n\n" in text:
        first, _, rest = text.partition("\n\n")
        if first.strip().endswith(":") is False and len(first) < 120:
            title = first.strip()
            body = rest.strip()
    if not title and text:
        title = text.split("\n")[0].strip() or "Untitled"
    return title or "Untitled", body or text
