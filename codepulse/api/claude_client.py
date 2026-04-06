"""
DispatchClient — spawns the Claude Code CLI as a subprocess.

Mirrors the pattern from claude-dispatch-codepulse/server/claudeRunner.js.
No API key required — uses your existing Claude Code authentication.

CLI invoked:
    claude --print <prompt> --output-format stream-json --verbose
                   [--model MODEL] [--resume SESSION_ID]
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Optional

from codepulse.config import CLAUDE_MODEL, SYNOPSIS_MODEL


class DispatchClient:
    """
    Spawns `claude` CLI subprocesses and yields text chunks from stream-json.

    After each stream_completion() or one_shot() call, self.last_session_id
    is updated with the captured Claude Code session ID (for --resume on
    subsequent turns).
    """

    def __init__(self, model: str = CLAUDE_MODEL, synopsis_model: str = SYNOPSIS_MODEL) -> None:
        self.model = model
        self.synopsis_model = synopsis_model
        self.last_session_id: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────────

    async def stream_completion(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
        model: Optional[str] = None,
        on_tool_call: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream text chunks from a claude CLI call.
        Updates self.last_session_id when the session init event arrives.
        Calls on_tool_call(tool_name) whenever Claude invokes a tool.
        """
        async for chunk in self._spawn_stream(
            prompt=prompt,
            model=model or self.model,
            session_id=session_id,
            cwd=cwd,
            on_tool_call=on_tool_call,
        ):
            yield chunk

    async def one_shot(
        self,
        prompt: str,
        use_synopsis_model: bool = True,
        cwd: Optional[str] = None,
    ) -> str:
        """
        Non-streaming call — collects all text and returns the full response.
        Always starts a fresh session (no --resume) so synopsis calls don't
        pollute the main conversation.
        """
        model = self.synopsis_model if use_synopsis_model else self.model
        parts: list[str] = []
        async for chunk in self._spawn_stream(
            prompt=prompt,
            model=model,
            session_id=None,  # fresh context every time
            cwd=cwd,
        ):
            parts.append(chunk)
        return "".join(parts)

    async def stream_one_shot(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
        use_synopsis_model: bool = False,
    ) -> AsyncIterator[str]:
        """Used by /discuss mode — stream with optional session resume."""
        model = self.synopsis_model if use_synopsis_model else self.model
        async for chunk in self._spawn_stream(
            prompt=prompt,
            model=model,
            session_id=session_id,
            cwd=cwd,
        ):
            yield chunk

    # ── Internal subprocess spawner ───────────────────────────────────────────

    async def _spawn_stream(
        self,
        prompt: str,
        model: str,
        session_id: Optional[str],
        cwd: Optional[str],
        on_tool_call: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[str]:
        """
        Spawns: claude --print <prompt> --output-format stream-json --verbose
                       [--model MODEL] [--resume SESSION_ID]

        Parses each stdout line as JSON following the claudeRunner.js event
        schema and yields text chunks.
        """
        args = [
            "claude",
            "--print", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--model", model,
        ]
        if session_id:
            args += ["--resume", session_id]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "The `claude` CLI was not found on PATH.\n"
                "Install it with: npm install -g @anthropic-ai/claude-code"
            )

        line_buffer = ""

        async for raw_chunk in proc.stdout:  # type: ignore[union-attr]
            line_buffer += raw_chunk.decode("utf-8", errors="replace")
            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                chunk = self._parse_line(line.strip(), on_tool_call=on_tool_call)
                if chunk is not None:
                    yield chunk

        # Flush any remaining buffer
        if line_buffer.strip():
            chunk = self._parse_line(line_buffer.strip(), on_tool_call=on_tool_call)
            if chunk is not None:
                yield chunk

        await proc.wait()

    def _parse_line(
        self,
        line: str,
        on_tool_call: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        Parse a single stream-json line.
        Returns text to yield, or None. Updates last_session_id on init events.
        Calls on_tool_call(name) when a tool_use block is encountered.
        """
        if not line:
            return None

        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            return None

        evt_type = evt.get("type", "")

        # Capture session ID from the init event
        if evt_type == "system" and evt.get("subtype") == "init" and evt.get("session_id"):
            self.last_session_id = evt["session_id"]
            return None

        # Top-level tool_call event (some CLI versions)
        if evt_type == "tool_call" and on_tool_call:
            tool_name = evt.get("name") or evt.get("tool_name") or ""
            if tool_name:
                on_tool_call(tool_name)
            return None

        # Assistant message — may contain text blocks AND tool_use blocks
        if evt_type == "assistant":
            message = evt.get("message") or {}
            content = message.get("content") or []
            text_parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(block["text"])
                elif block.get("type") == "tool_use" and on_tool_call:
                    tool_name = block.get("name", "")
                    if tool_name:
                        on_tool_call(tool_name)
            return "".join(text_parts) if text_parts else None

        # Result event — fallback session ID capture
        if evt_type == "result":
            if not self.last_session_id and evt.get("session_id"):
                self.last_session_id = evt["session_id"]
            return None

        return None
