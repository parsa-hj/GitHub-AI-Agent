"""
Reviewer agent: analyzes diff (and optional file content), categorizes change,
assesses risk, cites evidence, recommends Issue / PR / No action.
Uses read_file tool when needed.
"""
from typing import Callable, Optional

from app.agents import ollama_client
from app.tools.file_tools import read_file


def _read_file_tool(path: str) -> str:
    """Wrapper for ollama tool schema: read a file under the repo."""
    try:
        return read_file(path)
    except Exception as e:
        return f"Error: {e}"


def run_reviewer(
    diff_text: str,
    file_snippets: Optional[dict[str, str]] = None,
    tool_runner: Optional[Callable[[str, dict], str]] = None,
    model: Optional[str] = None,
) -> str:
    """
    Run Reviewer agent. Optionally pass tool_runner that handles 'read_file' (path) so
    the model can request more file content. If tool_runner is None, only diff and file_snippets are used.
    Returns structured analysis: category, risk, findings, evidence, recommendation.
    """
    snippets = file_snippets or {}
    parts = [
        "You are the **Reviewer** agent. Analyze the following git diff and any file snippets.",
        "Identify potential issues or improvements. Categorize the change (e.g. feature, bugfix, refactor, docs, chore).",
        "Assess risk: low, medium, or high. Cite evidence from the diff or file content.",
        "Recommend one of: Create Issue, Create PR, or No action required. Justify with evidence.",
        "\n--- Git diff ---\n",
        diff_text or "(no diff)",
    ]
    if snippets:
        parts.append("\n--- File snippets (for context) ---\n")
        for path, content in snippets.items():
            parts.append(f"\n### {path}\n```\n{content[:8000]}\n```\n")
    parts.append("\nRespond with: Category, Risk, Findings (bullets), Evidence (from diff/files), Recommendation (Issue/PR/No action) and justification.")

    user_content = "".join(parts)
    messages = [{"role": "user", "content": user_content}]

    if tool_runner is not None:
        tools = [_read_file_tool]
        return ollama_client.chat_with_tools(messages, tools, tool_runner, model=model)
    resp = ollama_client.chat(messages, model=model)
    return (getattr(resp.message, "content", None) or "").strip()
