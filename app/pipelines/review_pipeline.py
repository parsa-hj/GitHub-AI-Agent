"""
Review pipeline: get_diff -> Reviewer -> Planner -> Reflection -> result.
Returns category, risk, decision, evidence, reflection artifact.
"""
from typing import Any, Optional

from app.agents.gatekeeper import run_gatekeeper
from app.agents.planner import run_planner
from app.agents.reflection import run_reflection_review
from app.agents.reviewer import run_reviewer
from app.config import GITHUB_REPO, REPO_PATH
from app.tools.git_tools import get_diff, get_repo_info

# Last review result for "Draft from review" flow (in-memory)
_last_review_result: dict | None = None


def _tool_runner(name: str, args: dict) -> str:
    if name == "read_file":
        from app.tools.file_tools import read_file
        path = args.get("path") or args.get("file_path") or ""
        try:
            return read_file(path)
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown tool: {name}"


def run_review(
    base: Optional[str] = None,
    range_spec: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run review pipeline. Pass either base (e.g. 'main') or range_spec (e.g. 'HEAD~3..HEAD').
    """
    diff_text = get_diff(base=base, range_spec=range_spec)
    repo_info = get_repo_info() if REPO_PATH else {}

    reviewer_output = run_reviewer(
        diff_text=diff_text,
        file_snippets=None,
        tool_runner=_tool_runner,
        model=model,
    )
    planner_output = run_planner(
        reviewer_output=reviewer_output,
        instruction=None,
        draft_type=None,
        model=model,
    )
    reflection = run_reflection_review(reviewer_output, planner_output, model=model)

    global _last_review_result
    _last_review_result = {
        "reviewer_output": reviewer_output,
        "planner_output": planner_output,
        "reflection_verdict": reflection.verdict,
        "reflection_artifact": reflection.to_display(),
        "diff_preview": (diff_text or "")[:4000],
        "repo_info": repo_info,
        "github_repo": GITHUB_REPO,
    }

    return {
        "reviewer_output": reviewer_output,
        "planner_output": planner_output,
        "reflection_verdict": reflection.verdict,
        "reflection_artifact": reflection.to_display(),
        "reflection_findings": reflection.checklist_findings,
        "diff_preview": (diff_text or "")[:4000],
        "repo_info": repo_info,
        "github_repo": GITHUB_REPO,
    }
