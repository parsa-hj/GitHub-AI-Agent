"""Build mountable A2A Starlette sub-applications for each sub-agent.

Usage in FastAPI ``main.py``::

    from app.a2a.router import build_a2a_apps
    from app.config import A2A_BASE_URL

    for name, starlette_app in build_a2a_apps(A2A_BASE_URL).items():
        app.mount(f"/a2a/{name}", starlette_app)

Each sub-app exposes:
- ``GET  /.well-known/agent-card.json``  — the A2A agent card
- ``POST /``                             — the A2A JSON-RPC endpoint
"""
from starlette.applications import Starlette

from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from app.a2a.agent_cards import (
    gatekeeper_card,
    planner_card,
    reviewer_card,
    writer_card,
)
from app.a2a.executors import (
    GatekeeperExecutor,
    PlannerExecutor,
    ReviewerExecutor,
    WriterExecutor,
)


def _build_starlette_app(card, executor) -> Starlette:
    """Wire up an AgentExecutor into a ready-to-mount Starlette app."""
    task_store = InMemoryTaskStore()
    queue_manager = InMemoryQueueManager()
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
        queue_manager=queue_manager,
    )
    a2a_app = A2AStarletteApplication(agent_card=card, http_handler=handler)
    return a2a_app.build()


def build_a2a_apps(base_url: str) -> dict[str, Starlette]:
    """Return a mapping of agent name → mountable Starlette app.

    ``base_url`` is the public root URL of the FastAPI application
    (e.g. ``http://localhost:8000``).  It is used to populate the ``url``
    field in each AgentCard so that A2A clients can resolve the correct
    endpoint.

    Mount each app under ``/a2a/{name}`` on the FastAPI instance::

        for name, sub_app in build_a2a_apps("http://localhost:8000").items():
            app.mount(f"/a2a/{name}", sub_app)
    """
    return {
        "reviewer": _build_starlette_app(
            reviewer_card(f"{base_url}/a2a/reviewer"),
            ReviewerExecutor(),
        ),
        "planner": _build_starlette_app(
            planner_card(f"{base_url}/a2a/planner"),
            PlannerExecutor(),
        ),
        "writer": _build_starlette_app(
            writer_card(f"{base_url}/a2a/writer"),
            WriterExecutor(),
        ),
        "gatekeeper": _build_starlette_app(
            gatekeeper_card(f"{base_url}/a2a/gatekeeper"),
            GatekeeperExecutor(),
        ),
    }
