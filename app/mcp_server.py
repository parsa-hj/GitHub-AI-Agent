"""MCP (Model Context Protocol) server exposing GitHub Agent tools.

Run standalone in STDIO mode (for MCP clients such as Claude Desktop):

    python -m app.mcp_server

Or import ``get_mcp_sse_app()`` to mount the SSE endpoint on the FastAPI
application at ``/mcp``.

Claude Desktop ``settings.json`` snippet::

    {
      "mcpServers": {
        "github-agent": {
          "command": "python",
          "args": ["-m", "app.mcp_server"]
        }
      }
    }
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "GitHub Agent Tools",
    instructions=(
        "Tools for reviewing code, reading repository files, and "
        "interacting with GitHub issues and pull requests."
    ),
)


# ---------------------------------------------------------------------------
# Git tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_diff(base: str = "", range_spec: str = "") -> str:
    """Return the git diff for the configured repository (REPO_PATH).

    Pass ``base`` (e.g. ``'main'``) for a diff against a branch, or
    ``range_spec`` (e.g. ``'HEAD~3..HEAD'``) for a commit range.
    """
    from app.tools.git_tools import get_diff as _get_diff

    return _get_diff(base=base or None, range_spec=range_spec or None)


@mcp.tool()
def get_repo_info() -> dict:
    """Return the current branch, last commit SHA, and remote URL of the
    configured repository (REPO_PATH)."""
    from app.tools.git_tools import get_repo_info as _get_repo_info

    return _get_repo_info()


# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file inside the configured repository (REPO_PATH).

    Path traversal outside the repository is blocked.
    """
    from app.tools.file_tools import read_file as _read_file

    return _read_file(path)


# ---------------------------------------------------------------------------
# GitHub tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_issue(repo_slug: str, number: int) -> dict:
    """Fetch a GitHub issue by number.

    ``repo_slug`` must be ``'owner/repo'`` or a full GitHub URL.
    Works for public repos without a token.
    """
    from app.tools.github_tools import get_issue as _get_issue

    return _get_issue(repo_slug, number)


@mcp.tool()
def get_pull_request(repo_slug: str, number: int) -> dict:
    """Fetch a GitHub pull request by number.

    ``repo_slug`` must be ``'owner/repo'`` or a full GitHub URL.
    Works for public repos without a token.
    """
    from app.tools.github_tools import get_pull_request as _get_pull_request

    return _get_pull_request(repo_slug, number)


# ---------------------------------------------------------------------------
# Pipeline tool
# ---------------------------------------------------------------------------


@mcp.tool()
def run_review(base: str = "", range_spec: str = "") -> dict:
    """Run the full review pipeline: Reviewer → Planner → Reflection.

    Returns a dict with ``reviewer_output``, ``planner_output``,
    ``reflection_verdict``, ``reflection_artifact``, and ``diff_preview``.
    Pass ``base`` (branch) or ``range_spec`` (commit range).
    """
    from app.pipelines.review_pipeline import run_review as _run_review

    return _run_review(base=base or None, range_spec=range_spec or None)


# ---------------------------------------------------------------------------
# ASGI helper
# ---------------------------------------------------------------------------


def get_mcp_sse_app():
    """Return the MCP SSE Starlette app for mounting on FastAPI at ``/mcp``."""
    return mcp.sse_app(mount_path="/mcp")


if __name__ == "__main__":
    mcp.run(transport="stdio")
