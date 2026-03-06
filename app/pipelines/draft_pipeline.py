"""
Draft pipeline: from review or instruction -> Planner -> Writer -> Gatekeeper.
Stores pending draft for approval; create_issue/create_pr only via approve_draft().
"""
import uuid
from typing import Any, Optional

from app.agents.gatekeeper import run_gatekeeper
from app.agents.planner import run_planner
from app.agents.writer import run_writer_issue, run_writer_pr
from app.config import GITHUB_REPO, REPO_PATH, has_github_token
from app.tools.git_tools import get_repo_info

# In-memory pending drafts: draft_id -> { title, body, kind, repo_slug, head, base, ... }
_pending_drafts: dict[str, dict[str, Any]] = {}


def run_draft(
    source: str,
    instruction: Optional[str] = None,
    review_result: Optional[dict[str, Any]] = None,
    draft_type: str = "issue",
    model: Optional[str] = None,
    repo_slug: Optional[str] = None,
) -> dict[str, Any]:
    """
    source: 'review' | 'instruction'
    If review: use review_result (reviewer_output + planner_output + diff). If instruction: use instruction text.
    draft_type: 'issue' | 'pr'
    Returns draft (title, body), reflection artifact, and draft_id for approval.
    """
    if source == "review" and not review_result:
        from app.pipelines.review_pipeline import _last_review_result
        review_result = _last_review_result
    if source == "review" and review_result:
        context = f"Reviewer:\n{review_result.get('reviewer_output', '')}\n\nPlanner:\n{review_result.get('planner_output', '')}\n\nDiff (preview):\n{review_result.get('diff_preview', '')}"
        planner_input = review_result.get("planner_output", "") or review_result.get("reviewer_output", "")
    else:
        context = instruction or ""
        planner_input = context

    planner_output = run_planner(
        reviewer_output=planner_input,
        instruction=instruction,
        draft_type=draft_type,
        model=model,
    )
    if draft_type == "pr":
        title, body = run_writer_pr(planner_output, context, model=model)
    else:
        title, body = run_writer_issue(planner_output, context, model=model)
    reflection = run_gatekeeper(title=title, body=body, is_pr=(draft_type == "pr"), model=model)

    draft_id = str(uuid.uuid4())
    repo_info = get_repo_info() if REPO_PATH else {}
    effective_repo = (repo_slug or GITHUB_REPO or "").strip()
    pending = {
        "title": title,
        "body": body,
        "kind": draft_type,
        "repo_slug": effective_repo,
        "head": repo_info.get("branch", "HEAD"),
        "base": "main",
        "reflection_verdict": reflection.verdict,
        "reflection_artifact": reflection.to_display(),
    }
    _pending_drafts[draft_id] = pending

    return {
        "draft_id": draft_id,
        "draft_type": draft_type,
        "title": title,
        "body": body,
        "planner_output": planner_output,
        "reflection_verdict": reflection.verdict,
        "reflection_artifact": reflection.to_display(),
        "reflection_findings": reflection.checklist_findings,
    }


def get_pending_draft(draft_id: str) -> Optional[dict[str, Any]]:
    return _pending_drafts.get(draft_id)


def approve_draft(draft_id: str, approved: bool) -> dict[str, Any]:
    """
    If approved=True and token set: create issue or PR on GitHub and return link.
    If approved=True and no token: return copy_draft with title/body/repo for manual creation.
    If approved=False: abort, no changes.
    """
    pending = _pending_drafts.pop(draft_id, None)
    if not pending:
        return {"ok": False, "message": "Draft not found or already used.", "created": None, "copy_draft": False}
    if not approved:
        return {"ok": True, "message": "Draft rejected. No changes made.", "created": None, "copy_draft": False}

    title = pending["title"]
    body = pending["body"]
    kind = pending["kind"]
    repo_slug = (pending.get("repo_slug") or "").strip()
    head = pending.get("head", "HEAD")
    base = pending.get("base", "main")

    if not has_github_token():
        return {
            "ok": True,
            "message": "Copy this draft and create the issue/PR on GitHub yourself.",
            "created": None,
            "copy_draft": True,
            "title": title,
            "body": body,
            "kind": kind,
            "repo_slug": repo_slug or GITHUB_REPO,
        }
    from app.tools.github_tools import create_issue, create_pull_request
    try:
        if kind == "issue":
            result = create_issue(repo_slug, title, body)
            return {
                "ok": True,
                "message": "Issue created.",
                "created": {"url": result["html_url"], "number": result["number"], "kind": "issue"},
                "copy_draft": False,
            }
        else:
            result = create_pull_request(repo_slug, title, body, head=head, base=base)
            return {
                "ok": True,
                "message": "Pull request created.",
                "created": {"url": result["html_url"], "number": result["number"], "kind": "pr"},
                "copy_draft": False,
            }
    except Exception as e:
        return {"ok": False, "message": str(e), "created": None, "copy_draft": False}
