"""FastAPI app: routes and Web UI for GitHub Repository Agent."""
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import A2A_BASE_URL, OLLAMA_MODEL, get_ollama_status, has_github_token
from app.pipelines import approve_draft, run_draft, run_improve_issue, run_improve_pr, run_review

_BASE = Path(__file__).resolve().parent
app = FastAPI(title="GitHub Repository Agent")
templates = Jinja2Templates(directory=str(_BASE / "web" / "templates"))
app.mount("/static", StaticFiles(directory=str(_BASE / "web" / "static")), name="static")

# ---------------------------------------------------------------------------
# MCP (Model Context Protocol) – SSE endpoint at /mcp
# ---------------------------------------------------------------------------
from app.mcp_server import get_mcp_sse_app  # noqa: E402

app.mount("/mcp", get_mcp_sse_app())

# ---------------------------------------------------------------------------
# A2A (Agent-to-Agent) – one sub-app per agent under /a2a/{name}
# ---------------------------------------------------------------------------
from app.a2a.router import build_a2a_apps  # noqa: E402

for _agent_name, _agent_app in build_a2a_apps(A2A_BASE_URL).items():
    app.mount(f"/a2a/{_agent_name}", _agent_app)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Show a friendly error page instead of 500 for pipeline and other errors."""
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error_message": str(exc)},
        status_code=500,
    )


@app.get("/api/ollama-status")
async def ollama_status():
    """Return Ollama connection and model availability for the status indicator."""
    return get_ollama_status()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    status = get_ollama_status()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "ollama_model": OLLAMA_MODEL,
            "ollama_status": status,
            "has_github_token": has_github_token(),
        },
    )


@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    from app.config import REPO_PATH
    return templates.TemplateResponse(
        "review.html",
        {"request": request, "repo_path": REPO_PATH or "(not set)"},
    )


@app.post("/review", response_class=HTMLResponse)
async def review_run(
    request: Request,
    base: Optional[str] = Form(None),
    range_spec: Optional[str] = Form(None),
):
    if not base and not range_spec:
        return templates.TemplateResponse(
            "review.html",
            {"request": request, "error": "Provide either base branch or commit range."},
        )
    try:
        result = run_review(base=base or None, range_spec=range_spec or None)
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error_message": str(e)},
            status_code=500,
        )
    return templates.TemplateResponse(
        "review_result.html",
        {"request": request, "result": result},
    )


@app.get("/draft", response_class=HTMLResponse)
async def draft_page(request: Request):
    from app.config import GITHUB_REPO
    return templates.TemplateResponse(
        "draft.html",
        {"request": request, "github_repo": GITHUB_REPO or ""},
    )


@app.post("/draft", response_class=HTMLResponse)
async def draft_run(
    request: Request,
    source: str = Form("instruction"),
    instruction: Optional[str] = Form(None),
    draft_type: str = Form("issue"),
    repo: Optional[str] = Form(None),
):
    from app.tools.github_tools import parse_repo_from_link
    from app.config import GITHUB_REPO
    repo_slug = None
    if repo and repo.strip():
        repo_slug = parse_repo_from_link(repo.strip())
        if not repo_slug:
            return templates.TemplateResponse(
                "draft.html",
                {"request": request, "github_repo": (repo or "").strip(), "error": "Repo must be owner/repo or a GitHub URL (e.g. https://github.com/owner/repo)."},
            )
    if not repo_slug:
        repo_slug = (GITHUB_REPO or "").strip() or None
    if not repo_slug:
        return templates.TemplateResponse(
            "draft.html",
            {"request": request, "github_repo": "", "error": "Set GITHUB_REPO in .env or enter a GitHub repo (owner/repo or URL) above. Issues/PRs are created in that repo."},
        )
    review_result = None  # from last review (set by review pipeline)
    try:
        result = run_draft(
            source=source,
            instruction=instruction or "",
            review_result=review_result,
            draft_type=draft_type,
            repo_slug=repo_slug,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error_message": str(e)},
            status_code=500,
        )
    return templates.TemplateResponse(
        "draft_result.html",
        {"request": request, "result": result, "has_github_token": has_github_token()},
    )


@app.post("/approve")
async def approve(request: Request, draft_id: str = Form(...), approved: str = Form(None)):
    ok = approved and approved.lower() in ("yes", "true", "1")
    try:
        result = approve_draft(draft_id, approved=ok)
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error_message": str(e)},
            status_code=500,
        )
    if result.get("copy_draft"):
        return templates.TemplateResponse(
            "approve_copy_draft.html",
            {
                "request": request,
                "title": result.get("title", ""),
                "body": result.get("body", ""),
                "kind": result.get("kind", "issue"),
                "repo_slug": result.get("repo_slug", ""),
            },
        )
    if result.get("created"):
        url = result["created"].get("url", "")
        kind = result["created"].get("kind", "issue")
        return RedirectResponse(url=f"/approve_success?url={quote(url, safe='')}&kind={kind}", status_code=302)
    if ok and not result.get("created"):
        return RedirectResponse(url="/approve_rejected?reason=create_failed", status_code=302)
    return RedirectResponse(url="/approve_rejected?reason=rejected", status_code=302)


@app.get("/approve_success", response_class=HTMLResponse)
async def approve_success(request: Request, url: str = "", kind: str = ""):
    return templates.TemplateResponse(
        "approve_result.html",
        {"request": request, "success": True, "url": url, "kind": kind},
    )


@app.get("/approve_rejected", response_class=HTMLResponse)
async def approve_rejected(request: Request, reason: str = "rejected"):
    return templates.TemplateResponse(
        "approve_result.html",
        {"request": request, "success": False, "reason": reason},
    )


@app.get("/improve", response_class=HTMLResponse)
async def improve_page(request: Request):
    from app.config import GITHUB_REPO
    return templates.TemplateResponse("improve.html", {"request": request, "default_repo": GITHUB_REPO or ""})


@app.post("/improve", response_class=HTMLResponse)
async def improve_run(
    request: Request,
    kind: str = Form("issue"),
    number: str = Form(...),
    repo: Optional[str] = Form(None),
):
    try:
        num = int(number.strip())
    except ValueError:
        return templates.TemplateResponse(
            "improve.html",
            {"request": request, "error": "Issue/PR number must be an integer."},
        )
    from app.tools.github_tools import parse_repo_from_link
    from app.config import GITHUB_REPO
    repo_slug = None
    if repo and repo.strip():
        repo_slug = parse_repo_from_link(repo.strip())
        if not repo_slug:
            return templates.TemplateResponse(
                "improve.html",
                {"request": request, "error": "Repo must be owner/repo or a GitHub URL (e.g. https://github.com/owner/repo)."},
            )
    if not repo_slug and GITHUB_REPO:
        repo_slug = parse_repo_from_link(GITHUB_REPO) or GITHUB_REPO
    if not repo_slug:
        return templates.TemplateResponse(
            "improve.html",
            {"request": request, "error": "Provide a repo (owner/repo or GitHub URL) or set GITHUB_REPO in .env."},
        )
    try:
        if kind == "pr":
            result = run_improve_pr(pr_number=num, repo_slug=repo_slug)
        else:
            result = run_improve_issue(issue_number=num, repo_slug=repo_slug)
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error_message": str(e)},
            status_code=500,
        )
    if result.get("error"):
        return templates.TemplateResponse(
            "improve.html",
            {"request": request, "error": result["error"]},
        )
    return templates.TemplateResponse(
        "improve_result.html",
        {"request": request, "result": result, "kind": kind},
    )
