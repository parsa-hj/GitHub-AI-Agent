"""
Planner agent: decides action (Create Issue, Create PR, No action) and scope.
Input: Reviewer output or user instruction. Output: decision + justification with evidence.
"""
from typing import Optional

from app.agents import ollama_client


def run_planner(
    reviewer_output: str,
    instruction: Optional[str] = None,
    draft_type: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Run Planner. reviewer_output is the Reviewer's analysis. If instruction is set, we're in draft-from-instruction mode.
    draft_type: 'issue' or 'pr' when drafting. Returns: decision (Issue/PR/No action) + scope/justification.
    """
    parts = [
        "You are the **Planner** agent. Based on the following context, decide the action and scope.",
        "\n--- Context ---\n",
        reviewer_output,
    ]
    if instruction:
        parts.append(f"\n--- User instruction for draft ---\n{instruction}")
        if draft_type:
            parts.append(f"\nRequested draft type: {draft_type}. Validate scope and what the draft should cover.")
    parts.append(
        "\nOutput: (1) Decision: Create Issue | Create PR | No action. "
        "(2) Scope: what the issue/PR should cover. (3) Justification with evidence."
    )
    messages = [{"role": "user", "content": "".join(parts)}]
    resp = ollama_client.chat(messages, model=model)
    return (getattr(resp.message, "content", None) or "").strip()
