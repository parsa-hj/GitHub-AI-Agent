"""AgentCard definitions for each sub-agent.

Each card is constructed with the base URL of the agent's A2A endpoint so
that A2A clients can locate the correct RPC URL.
"""
from a2a.types import AgentCapabilities, AgentCard, AgentSkill


def _make_card(
    name: str,
    description: str,
    skill_id: str,
    skill_name: str,
    skill_description: str,
    skill_tags: list[str],
    base_url: str,
) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        url=base_url.rstrip("/") + "/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id=skill_id,
                name=skill_name,
                description=skill_description,
                tags=skill_tags,
            )
        ],
    )


def reviewer_card(base_url: str) -> AgentCard:
    """AgentCard for the Reviewer agent."""
    return _make_card(
        name="GitHub Reviewer Agent",
        description=(
            "Analyzes git diffs and file content. Returns category, risk level, "
            "findings, evidence, and recommendation (Create Issue / Create PR / No action)."
        ),
        skill_id="review_diff",
        skill_name="Review Diff",
        skill_description=(
            "Send a git diff as the message text.  The agent returns a structured "
            "analysis: Category, Risk, Findings (bullets), Evidence, Recommendation."
        ),
        skill_tags=["review", "git", "diff"],
        base_url=base_url,
    )


def planner_card(base_url: str) -> AgentCard:
    """AgentCard for the Planner agent."""
    return _make_card(
        name="GitHub Planner Agent",
        description=(
            "Decides action and scope from reviewer output or a user instruction. "
            "Returns: decision (Create Issue / Create PR / No action), scope, and justification."
        ),
        skill_id="plan_action",
        skill_name="Plan Action",
        skill_description=(
            "Send reviewer output as plain text, or a JSON object with keys "
            "``reviewer_output``, optional ``instruction``, and optional ``draft_type`` "
            "(``'issue'`` or ``'pr'``)."
        ),
        skill_tags=["planning", "decision"],
        base_url=base_url,
    )


def writer_card(base_url: str) -> AgentCard:
    """AgentCard for the Writer agent."""
    return _make_card(
        name="GitHub Writer Agent",
        description=(
            "Drafts GitHub Issues or Pull Requests from planner output. "
            "Returns title and body in structured markdown."
        ),
        skill_id="draft_content",
        skill_name="Draft Content",
        skill_description=(
            "Send a JSON object with keys ``planner_output`` (str), "
            "``context`` (str, e.g. diff or instruction), and "
            "``draft_type`` (``'issue'`` or ``'pr'``).  "
            "Returns JSON: ``{\"title\": \"...\", \"body\": \"...\"}``."
        ),
        skill_tags=["writing", "draft", "issue", "pr"],
        base_url=base_url,
    )


def gatekeeper_card(base_url: str) -> AgentCard:
    """AgentCard for the Gatekeeper agent."""
    return _make_card(
        name="GitHub Gatekeeper Agent",
        description=(
            "Reflection/verification agent.  Checks a draft against the evidence, "
            "tests, completeness, and policy checklists.  Returns PASS or FAIL."
        ),
        skill_id="gate_draft",
        skill_name="Gate Draft",
        skill_description=(
            "Send a JSON object with keys ``title`` (str), ``body`` (str), "
            "and ``is_pr`` (bool).  "
            "Returns JSON: ``{\"verdict\": \"PASS|FAIL\", \"findings\": [...], "
            "\"raw_comment\": \"...\"}``."
        ),
        skill_tags=["gatekeeper", "reflection", "verification"],
        base_url=base_url,
    )
