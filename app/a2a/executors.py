"""AgentExecutor implementations for each sub-agent.

Each executor:
1. Reads the user's text from the A2A request context.
2. Parses it (plain text or JSON depending on the agent).
3. Calls the corresponding synchronous agent function in a thread pool so it
   does not block the event loop.
4. Publishes the result as an artifact and marks the task completed.
"""
import asyncio
import json
import uuid
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Message, Part, Role, TaskState, TextPart


def _text_message(text: str, role: Role = Role.agent) -> Message:
    """Convenience helper: wrap a string as a single-part A2A Message."""
    return Message(
        role=role,
        message_id=str(uuid.uuid4()),
        parts=[Part(root=TextPart(text=text))],
    )


class ReviewerExecutor(AgentExecutor):
    """Run the Reviewer agent on a git diff provided as message text."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.working)
        try:
            diff_text = context.get_user_input()
            from app.agents.reviewer import run_reviewer

            output = await asyncio.get_event_loop().run_in_executor(
                None, lambda: run_reviewer(diff_text=diff_text)
            )
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=output))],
                name="reviewer_output",
            )
            await updater.complete()
        except Exception as exc:
            await updater.failed(message=_text_message(f"Reviewer error: {exc}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.canceled, final=True)


class PlannerExecutor(AgentExecutor):
    """Run the Planner agent.

    Accepts either plain-text reviewer output, or a JSON object::

        {
            "reviewer_output": "...",
            "instruction": "...",   // optional
            "draft_type": "issue"   // optional: "issue" | "pr"
        }
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.working)
        try:
            text = context.get_user_input()
            reviewer_output = text
            instruction: str | None = None
            draft_type: str | None = None
            try:
                data: dict[str, Any] = json.loads(text)
                reviewer_output = data.get("reviewer_output", text)
                instruction = data.get("instruction")
                draft_type = data.get("draft_type")
            except (json.JSONDecodeError, TypeError):
                pass

            from app.agents.planner import run_planner

            output = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_planner(
                    reviewer_output=reviewer_output,
                    instruction=instruction,
                    draft_type=draft_type,
                ),
            )
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=output))],
                name="planner_output",
            )
            await updater.complete()
        except Exception as exc:
            await updater.failed(message=_text_message(f"Planner error: {exc}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.canceled, final=True)


class WriterExecutor(AgentExecutor):
    """Run the Writer agent to draft an issue or pull request.

    Expects a JSON object::

        {
            "planner_output": "...",
            "context": "...",         // diff or instruction text
            "draft_type": "issue"     // "issue" | "pr"
        }

    Returns JSON: ``{"title": "...", "body": "..."}``.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.working)
        try:
            text = context.get_user_input()
            planner_output = text
            ctx_text = ""
            draft_type = "issue"
            try:
                data: dict[str, Any] = json.loads(text)
                planner_output = data.get("planner_output", text)
                ctx_text = data.get("context", "")
                draft_type = data.get("draft_type", "issue")
            except (json.JSONDecodeError, TypeError):
                pass

            from app.agents.writer import run_writer_issue, run_writer_pr

            if draft_type == "pr":
                title, body = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: run_writer_pr(planner_output, ctx_text)
                )
            else:
                title, body = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: run_writer_issue(planner_output, ctx_text)
                )

            result = json.dumps({"title": title, "body": body})
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=result))],
                name="writer_output",
            )
            await updater.complete()
        except Exception as exc:
            await updater.failed(message=_text_message(f"Writer error: {exc}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.canceled, final=True)


class GatekeeperExecutor(AgentExecutor):
    """Run the Gatekeeper reflection agent on a draft.

    Expects a JSON object::

        {
            "title": "...",
            "body":  "...",
            "is_pr": false
        }

    Returns JSON::

        {
            "verdict":     "PASS" | "FAIL",
            "findings":    [...],
            "raw_comment": "..."
        }
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.working)
        try:
            text = context.get_user_input()
            title = text
            body = ""
            is_pr = False
            try:
                data: dict[str, Any] = json.loads(text)
                title = data.get("title", text)
                body = data.get("body", "")
                is_pr = bool(data.get("is_pr", False))
            except (json.JSONDecodeError, TypeError):
                pass

            from app.agents.gatekeeper import run_gatekeeper

            artifact = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_gatekeeper(title=title, body=body, is_pr=is_pr),
            )
            result = json.dumps(
                {
                    "verdict": artifact.verdict,
                    "findings": artifact.checklist_findings,
                    "raw_comment": artifact.raw_comment,
                }
            )
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=result))],
                name="gatekeeper_output",
            )
            await updater.complete()
        except Exception as exc:
            await updater.failed(message=_text_message(f"Gatekeeper error: {exc}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.canceled, final=True)
