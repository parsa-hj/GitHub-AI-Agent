"""A2A (Agent-to-Agent) protocol layer for the GitHub Agent.

Each sub-agent (Reviewer, Planner, Writer, Gatekeeper) is exposed as a
separate A2A endpoint.  Import ``build_a2a_apps`` from ``app.a2a.router``
to obtain the mountable Starlette sub-applications.
"""
