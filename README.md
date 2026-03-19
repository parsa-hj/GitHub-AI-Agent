# GitHub Repository Agent

A personalized AI agent that uses your local **Ollama** model to review repository code, draft GitHub Issues/PRs, and improve existing ones. All creation on GitHub requires **human approval**.

## Features

- **Review changes**: Analyze `git diff` (by base branch or commit range), get category (feature/bugfix/refactor), risk level, and recommendation (Create Issue / Create PR / No action) with evidence.
- **Draft Issue or PR**: From your last review or from an explicit instruction. Draft includes title, body, evidence, acceptance criteria (issues), or test plan (PRs). With a token you can create after approval; without a token you get a copyable draft and links to create manually.
- **Improve Issue or PR**: Fetch an existing issue/PR (by repo link or `owner/repo`), critique it, and propose an improved structured version.

## Agentic Protocols

### MCP (Model Context Protocol)

The agent exposes all tools via the [Model Context Protocol](https://modelcontextprotocol.io) so any MCP-compatible client (e.g. Claude Desktop, Cursor, Cline) can invoke them directly.

**Available MCP tools**:

| Tool               | Description                                               |
| ------------------ | --------------------------------------------------------- |
| `get_diff`         | Git diff for the configured repo (branch or commit range) |
| `get_repo_info`    | Current branch, last commit SHA, remote URL               |
| `read_file`        | Read a file inside `REPO_PATH` (path traversal blocked)   |
| `get_issue`        | Fetch a GitHub issue by number                            |
| `get_pull_request` | Fetch a GitHub pull request by number                     |
| `run_review`       | Full Reviewer → Planner → Reflection pipeline             |

**STDIO mode** (Claude Desktop / MCP inspector):

```bash
python -m app.mcp_server
```

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github-agent": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "env": { "REPO_PATH": "/path/to/your/repo" }
    }
  }
}
```

**SSE mode** (HTTP streaming, auto-mounted when the FastAPI app starts):

```
GET /mcp/sse          — SSE stream
POST /mcp/messages/   — MCP message endpoint
```

### A2A (Agent-to-Agent Protocol)

Each sub-agent is exposed as a standalone [A2A](https://google.github.io/A2A/) endpoint so it can be called by orchestrators or other agents.

| Agent      | Mount path        | Skill                                                       |
| ---------- | ----------------- | ----------------------------------------------------------- |
| Reviewer   | `/a2a/reviewer`   | `review_diff` — analyze a git diff                          |
| Planner    | `/a2a/planner`    | `plan_action` — decide Create Issue / Create PR / No action |
| Writer     | `/a2a/writer`     | `draft_content` — draft an issue or PR                      |
| Gatekeeper | `/a2a/gatekeeper` | `gate_draft` — reflection PASS/FAIL check                   |

Each agent exposes:

- `GET /.well-known/agent-card.json` — the A2A AgentCard
- `POST /` — the A2A JSON-RPC endpoint (send/receive tasks)

**Example**: fetch the Reviewer's agent card:

```bash
curl http://localhost:8000/a2a/reviewer/.well-known/agent-card.json
```

Set `A2A_BASE_URL` in your `.env` when deploying behind a proxy so the agent cards point to the correct public URL.

## Token optional – read-only mode

You can run the agent **without a GitHub token**:

| Feature     | No token (read-only)                                                                                                                | With token                                                |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **Review**  | Yes (local git diff + file reads)                                                                                                   | Same                                                      |
| **Improve** | Yes for **public** repos; provide repo as GitHub URL or `owner/repo`. Rate limit: 60 requests/hour.                                 | Same; higher rate limit for private repos.                |
| **Draft**   | Draft is generated and shown; you get **Copy draft / Open repo** to copy title and body and create the issue/PR yourself on GitHub. | After approval, the app creates the issue/PR via the API. |

- **Improve without token**: Use the repo field (e.g. `https://github.com/owner/repo` or `owner/repo`). Only public repos are accessible; GitHub’s unauthenticated rate limit applies.
- **Draft without token**: Click “Copy draft / Open repo” after the draft is ready; the next page shows the draft with copy buttons and links to open the repo and the “New issue” or “New pull request” page.

## Patterns

- **Planning**: Planner agent decides scope and action before drafting.
- **Tool use**: Real tools only—`git diff`, file reads under repo, GitHub API (fetch; create only after approval when token is set).
- **Reflection**: Gatekeeper checks drafts against a checklist (evidence, tests, policy) and produces a PASS/FAIL artifact.
- **Multi-agent**: Reviewer (analyzes code), Planner (decides action), Writer (drafts content), Gatekeeper (reflection + approval gate).
- **MCP**: All tools exposed via Model Context Protocol for integration with AI assistants and IDEs.
- **A2A**: Each agent exposed as an A2A endpoint for orchestration and inter-agent communication.

## Setup

1. **Ollama**: Install [Ollama](https://ollama.com) and pull a model, e.g. `ollama pull llama3.2`. Ensure Ollama is running (default: `http://localhost:11434`).

2. **Clone and install**:

   ```bash
   cd GitHub-Agent
   pip install -r requirements.txt
   ```

3. **Environment**: Copy `.env.example` to `.env` and set:
   - `OLLAMA_MODEL` – model name (e.g. `llama3.2`)
   - `GITHUB_TOKEN` – **(optional)** GitHub personal access token (scope: `repo`). Omit for read-only mode.
   - `GITHUB_REPO` – repo in `owner/name` form (optional if you always provide repo in the Improve form)
   - `REPO_PATH` – absolute path to the local git repo to review (optional; defaults to current directory)
   - `A2A_BASE_URL` – **(optional)** public base URL for A2A agent cards (default: `http://localhost:8000`)

## Run

From the project root:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 in a browser.

## Usage

- **Review**: Enter a base branch (e.g. `main`) or commit range (e.g. `HEAD~3..HEAD`). The agent runs the review pipeline and shows [Reviewer], [Planner], and [Gatekeeper] reflection.
- **Draft**: Choose “From instruction” or “From last review.” With a token: Approve or Reject; on Approve the issue/PR is created. Without a token: use “Copy draft / Open repo” to get a page with copyable title/body and links to create the issue/PR on GitHub.
- **Improve**: Enter repo (GitHub URL or `owner/repo`) and an issue or PR number. The agent fetches it (public repos work without a token), critiques it, and suggests an improved title and body.

## n8n Integration

An n8n workflow implementing the agentic protocols (Reviewer → Planner → Writer → Gatekeeper)
is included in the repository at [n8n/schema.json](n8n/schema.json).

## Security

- File reads and `git diff` are restricted to `REPO_PATH` (no path traversal).
- When used, the GitHub token should have minimal scope (`repo` for issues/PRs).
- Nothing is created on GitHub without an explicit Approve in the UI (and a token); in read-only mode you create issues/PRs manually from the draft.
