"""Unit tests for MCP server and A2A agent protocol layer.

These tests do NOT require a live Ollama instance or GitHub token.
Agent calls are mocked at the function level so the test validates
protocol wiring only.
"""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# MCP server tests
# ---------------------------------------------------------------------------


class TestMCPServerTools(unittest.TestCase):
    """Verify that the MCP server registers the expected tools."""

    def test_tools_registered(self):
        import os
        os.environ.setdefault("REPO_PATH", "/tmp")
        from app.mcp_server import mcp

        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        expected = {"get_diff", "get_repo_info", "read_file", "get_issue", "get_pull_request", "run_review"}
        self.assertTrue(expected.issubset(tool_names), f"Missing tools: {expected - tool_names}")

    def test_get_mcp_sse_app_returns_starlette(self):
        import os
        os.environ.setdefault("REPO_PATH", "/tmp")
        from starlette.applications import Starlette

        from app.mcp_server import get_mcp_sse_app

        app = get_mcp_sse_app()
        self.assertIsInstance(app, Starlette)


# ---------------------------------------------------------------------------
# A2A agent card tests
# ---------------------------------------------------------------------------


class TestAgentCards(unittest.TestCase):
    """Verify that AgentCards are constructed with the correct URL and metadata."""

    BASE_URL = "http://testserver"

    def test_reviewer_card(self):
        from app.a2a.agent_cards import reviewer_card

        card = reviewer_card(f"{self.BASE_URL}/a2a/reviewer")
        self.assertEqual(card.name, "GitHub Reviewer Agent")
        self.assertTrue(card.url.startswith(self.BASE_URL))
        self.assertEqual(len(card.skills), 1)
        self.assertEqual(card.skills[0].id, "review_diff")

    def test_planner_card(self):
        from app.a2a.agent_cards import planner_card

        card = planner_card(f"{self.BASE_URL}/a2a/planner")
        self.assertEqual(card.name, "GitHub Planner Agent")
        self.assertEqual(card.skills[0].id, "plan_action")

    def test_writer_card(self):
        from app.a2a.agent_cards import writer_card

        card = writer_card(f"{self.BASE_URL}/a2a/writer")
        self.assertEqual(card.name, "GitHub Writer Agent")
        self.assertEqual(card.skills[0].id, "draft_content")

    def test_gatekeeper_card(self):
        from app.a2a.agent_cards import gatekeeper_card

        card = gatekeeper_card(f"{self.BASE_URL}/a2a/gatekeeper")
        self.assertEqual(card.name, "GitHub Gatekeeper Agent")
        self.assertEqual(card.skills[0].id, "gate_draft")

    def test_card_url_trailing_slash(self):
        from app.a2a.agent_cards import reviewer_card

        # base_url with trailing slash must still produce a valid URL
        card = reviewer_card("http://host:9000/a2a/reviewer/")
        self.assertTrue(card.url.endswith("/"))
        self.assertNotIn("//", card.url.replace("://", ""))


# ---------------------------------------------------------------------------
# A2A router tests
# ---------------------------------------------------------------------------


class TestA2ARouter(unittest.TestCase):
    """Verify that build_a2a_apps returns mountable Starlette apps."""

    def test_build_a2a_apps_returns_all_agents(self):
        from starlette.applications import Starlette

        from app.a2a.router import build_a2a_apps

        apps = build_a2a_apps("http://localhost:8000")
        self.assertEqual(set(apps.keys()), {"reviewer", "planner", "writer", "gatekeeper"})
        for name, sub_app in apps.items():
            self.assertIsInstance(sub_app, Starlette, f"{name} app is not a Starlette instance")


# ---------------------------------------------------------------------------
# A2A executor tests (async, with mocked agent functions)
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


class _FakeEventQueue:
    """Minimal in-memory EventQueue stub for testing executors."""

    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)

    async def close(self):
        pass


class _FakeRequestContext:
    """Minimal RequestContext stub for testing executors."""

    def __init__(self, text: str):
        self._text = text
        self.task_id = "task-001"
        self.context_id = "ctx-001"

    def get_user_input(self) -> str:
        return self._text


class TestReviewerExecutor(unittest.TestCase):
    def test_execute_produces_artifact(self):
        from a2a.server.tasks import TaskUpdater

        from app.a2a.executors import ReviewerExecutor

        executor = ReviewerExecutor()
        ctx = _FakeRequestContext("diff --git a/foo.py")
        queue = _FakeEventQueue()

        with patch("app.agents.reviewer.run_reviewer", return_value="Category: bugfix\nRisk: low"):
            with patch.object(TaskUpdater, "update_status", new_callable=AsyncMock):
                with patch.object(TaskUpdater, "add_artifact", new_callable=AsyncMock):
                    with patch.object(TaskUpdater, "complete", new_callable=AsyncMock):
                        _run_async(executor.execute(ctx, queue))

    def test_execute_handles_exception_gracefully(self):
        from a2a.server.tasks import TaskUpdater

        from app.a2a.executors import ReviewerExecutor

        executor = ReviewerExecutor()
        ctx = _FakeRequestContext("some diff")
        queue = _FakeEventQueue()

        with patch("app.agents.reviewer.run_reviewer", side_effect=RuntimeError("model error")):
            with patch.object(TaskUpdater, "update_status", new_callable=AsyncMock):
                with patch.object(TaskUpdater, "failed", new_callable=AsyncMock):
                    _run_async(executor.execute(ctx, queue))


class TestPlannerExecutor(unittest.TestCase):
    def test_execute_plain_text_input(self):
        from a2a.server.tasks import TaskUpdater

        from app.a2a.executors import PlannerExecutor

        executor = PlannerExecutor()
        ctx = _FakeRequestContext("Create Issue: missing tests")
        queue = _FakeEventQueue()

        with patch("app.agents.planner.run_planner", return_value="Decision: Create Issue"):
            with patch.object(TaskUpdater, "update_status", new_callable=AsyncMock):
                with patch.object(TaskUpdater, "add_artifact", new_callable=AsyncMock):
                    with patch.object(TaskUpdater, "complete", new_callable=AsyncMock):
                        _run_async(executor.execute(ctx, queue))

    def test_execute_json_input(self):
        from a2a.server.tasks import TaskUpdater

        from app.a2a.executors import PlannerExecutor

        executor = PlannerExecutor()
        payload = json.dumps(
            {"reviewer_output": "Risk: high", "instruction": "Add tests", "draft_type": "pr"}
        )
        ctx = _FakeRequestContext(payload)
        queue = _FakeEventQueue()

        captured = {}

        def fake_planner(reviewer_output, instruction=None, draft_type=None, model=None):
            captured.update({"reviewer_output": reviewer_output, "instruction": instruction, "draft_type": draft_type})
            return "Decision: Create PR"

        with patch("app.agents.planner.run_planner", side_effect=fake_planner):
            with patch.object(TaskUpdater, "update_status", new_callable=AsyncMock):
                with patch.object(TaskUpdater, "add_artifact", new_callable=AsyncMock):
                    with patch.object(TaskUpdater, "complete", new_callable=AsyncMock):
                        _run_async(executor.execute(ctx, queue))

        self.assertEqual(captured["reviewer_output"], "Risk: high")
        self.assertEqual(captured["instruction"], "Add tests")
        self.assertEqual(captured["draft_type"], "pr")


class TestWriterExecutor(unittest.TestCase):
    def test_execute_returns_json_title_body(self):
        from a2a.server.tasks import TaskUpdater

        from app.a2a.executors import WriterExecutor

        executor = WriterExecutor()
        payload = json.dumps({"planner_output": "Create Issue", "context": "diff", "draft_type": "issue"})
        ctx = _FakeRequestContext(payload)
        queue = _FakeEventQueue()

        artifact_parts = {}

        async def fake_add_artifact(parts, name=None, **kw):
            artifact_parts["parts"] = parts
            artifact_parts["name"] = name

        with patch("app.agents.writer.run_writer_issue", return_value=("My Title", "My Body")):
            with patch.object(TaskUpdater, "update_status", new_callable=AsyncMock):
                with patch.object(TaskUpdater, "add_artifact", side_effect=fake_add_artifact):
                    with patch.object(TaskUpdater, "complete", new_callable=AsyncMock):
                        _run_async(executor.execute(ctx, queue))

        self.assertEqual(artifact_parts["name"], "writer_output")
        text = artifact_parts["parts"][0].root.text
        data = json.loads(text)
        self.assertEqual(data["title"], "My Title")
        self.assertEqual(data["body"], "My Body")


class TestGatekeeperExecutor(unittest.TestCase):
    def test_execute_returns_pass_verdict(self):
        from a2a.server.tasks import TaskUpdater

        from app.a2a.executors import GatekeeperExecutor
        from app.agents.reflection import ReflectionArtifact

        executor = GatekeeperExecutor()
        payload = json.dumps({"title": "Fix bug", "body": "## Evidence\nfoo", "is_pr": False})
        ctx = _FakeRequestContext(payload)
        queue = _FakeEventQueue()

        artifact_parts = {}

        async def fake_add_artifact(parts, name=None, **kw):
            artifact_parts["parts"] = parts
            artifact_parts["name"] = name

        fake_result = ReflectionArtifact(verdict="PASS", checklist_findings=[], raw_comment="Looks good.")

        with patch("app.agents.gatekeeper.run_gatekeeper", return_value=fake_result):
            with patch.object(TaskUpdater, "update_status", new_callable=AsyncMock):
                with patch.object(TaskUpdater, "add_artifact", side_effect=fake_add_artifact):
                    with patch.object(TaskUpdater, "complete", new_callable=AsyncMock):
                        _run_async(executor.execute(ctx, queue))

        self.assertEqual(artifact_parts["name"], "gatekeeper_output")
        text = artifact_parts["parts"][0].root.text
        data = json.loads(text)
        self.assertEqual(data["verdict"], "PASS")


# ---------------------------------------------------------------------------
# Config test
# ---------------------------------------------------------------------------


class TestConfig(unittest.TestCase):
    def test_a2a_base_url_default(self):
        import importlib
        import os

        os.environ.pop("A2A_BASE_URL", None)
        os.environ.setdefault("REPO_PATH", "/tmp")

        import app.config as cfg

        importlib.reload(cfg)
        self.assertTrue(cfg.A2A_BASE_URL.startswith("http"))
        self.assertFalse(cfg.A2A_BASE_URL.endswith("/"))

    def test_a2a_base_url_custom(self):
        import importlib
        import os

        os.environ["A2A_BASE_URL"] = "https://my-agent.example.com/"
        os.environ.setdefault("REPO_PATH", "/tmp")

        import app.config as cfg

        importlib.reload(cfg)
        # Trailing slash should be stripped
        self.assertEqual(cfg.A2A_BASE_URL, "https://my-agent.example.com")
        os.environ.pop("A2A_BASE_URL", None)


if __name__ == "__main__":
    unittest.main()

