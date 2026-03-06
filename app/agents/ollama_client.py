"""
Thin Ollama wrapper: chat with optional tools. Executes tool calls in a loop
until the model returns no tool calls (for Reviewer and other tool-using agents).
"""
import json
from typing import Any, Callable, Optional

import ollama
from ollama import ChatResponse

from app.config import OLLAMA_HOST, OLLAMA_MODEL

# Use custom host if set (ollama client may need env OLLAMA_HOST)
_client: Optional[Any] = None


def _client_ensure():
    global _client
    if _client is None:
        ollama.Client(host=OLLAMA_HOST)


def _message_to_dict(msg: Any) -> dict:
    """Convert ollama message object to dict for appending to conversation."""
    content = getattr(msg, "content", None) or ""
    out = {"role": "assistant", "content": content}
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        out["tool_calls"] = []
        for tc in tool_calls:
            fn = getattr(tc, "function", None) or tc
            name = getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else None)
            args = getattr(fn, "arguments", None)
            if args is None and isinstance(fn, dict):
                args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    args = {}
            out["tool_calls"].append({"type": "function", "function": {"name": name, "arguments": args or {}}})
    return out


def _extract_tool_calls(msg: Any) -> list[tuple[str, dict]]:
    """Return list of (name, arguments) from message."""
    tool_calls = getattr(msg, "tool_calls", None) or []
    result = []
    for tc in tool_calls:
        fn = getattr(tc, "function", None) or tc
        name = getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else "")
        args = getattr(fn, "arguments", None)
        if args is None and isinstance(fn, dict):
            args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args) if args else {}
            except json.JSONDecodeError:
                args = {}
        result.append((name, args or {}))
    return result


def chat(
    messages: list[dict[str, Any]],
    model: Optional[str] = None,
    tools: Optional[list[Callable]] = None,
) -> ChatResponse:
    """Single chat turn. If tools are passed and model returns tool_calls, caller must handle them."""
    _client_ensure()
    model = model or OLLAMA_MODEL
    kwargs = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    return ollama.chat(**kwargs)


def chat_with_tools(
    messages: list[dict[str, Any]],
    tools: list[Callable],
    tool_runner: Callable[[str, dict], str],
    model: Optional[str] = None,
    max_tool_rounds: int = 10,
) -> str:
    """
    Chat with tools: run model, execute any tool_calls via tool_runner(name, arguments),
    append results to messages, repeat until no tool_calls or max_tool_rounds.
    Returns the final assistant message content.
    """
    model = model or OLLAMA_MODEL
    current = list(messages)
    for _ in range(max_tool_rounds):
        response = chat(model=model, messages=current, tools=tools)
        msg = response.message
        tool_calls_list = _extract_tool_calls(msg)
        if not tool_calls_list:
            return (getattr(msg, "content", None) or "").strip()
        current.append(_message_to_dict(msg))
        for name, args in tool_calls_list:
            result = tool_runner(name, args)
            current.append({"role": "tool", "tool_name": name, "content": str(result)})
    last = current[-1] if current else {}
    return (last.get("content") or "").strip()
