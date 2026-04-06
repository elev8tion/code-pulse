"""ProcessRunner — async subprocess wrapper with streaming output."""
from __future__ import annotations

import asyncio
import shlex
from collections.abc import Callable
from typing import Optional

from codepulse.process.models import ProcessRecord, ProcessStatus
from codepulse.config import PROCESS_STOP_TIMEOUT_SECS


class ProcessRunner:
    def __init__(
        self,
        record: ProcessRecord,
        on_output: Callable[[str, str], None],
        on_status_change: Callable[[str, ProcessStatus], None],
    ) -> None:
        self._record = record
        self._on_output = on_output
        self._on_status_change = on_status_change
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._stdout_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._wait_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._record.status == ProcessStatus.RUNNING

    @property
    def record(self) -> ProcessRecord:
        return self._record

    async def start(self, cwd: Optional[str] = None) -> None:
        if self.is_running:
            return

        self._record.status = ProcessStatus.RUNNING
        self._record.pid = None
        self._record.exit_code = None
        self._on_status_change(self._record.name, ProcessStatus.RUNNING)

        try:
            self._proc = await asyncio.create_subprocess_shell(
                self._record.command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # New process group so we can kill it cleanly
                start_new_session=True,
            )
            self._record.pid = self._proc.pid
        except Exception as e:
            self._record.status = ProcessStatus.ERROR
            self._on_status_change(self._record.name, ProcessStatus.ERROR)
            self._on_output(self._record.name, f"[error] Failed to start: {e}")
            return

        # Store tasks to prevent GC cancellation
        self._stdout_task = asyncio.create_task(
            self._stream_output(self._proc.stdout, "out")
        )
        self._stderr_task = asyncio.create_task(
            self._stream_output(self._proc.stderr, "err")
        )
        self._wait_task = asyncio.create_task(self._wait_for_exit())

    async def stop(self) -> None:
        if not self._proc or not self.is_running:
            return

        try:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=PROCESS_STOP_TIMEOUT_SECS)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
        except ProcessLookupError:
            pass  # Already dead

        self._record.status = ProcessStatus.STOPPED
        self._on_status_change(self._record.name, ProcessStatus.STOPPED)

    async def _stream_output(self, stream: asyncio.StreamReader, label: str) -> None:
        try:
            async for raw in stream:
                line = raw.decode("utf-8", errors="replace").rstrip("\n\r")
                if line:
                    self._record.output_lines.append(line)
                    self._on_output(self._record.name, line)
        except Exception:
            pass

    async def _wait_for_exit(self) -> None:
        try:
            if self._proc:
                rc = await self._proc.wait()
                self._record.exit_code = rc
                new_status = ProcessStatus.ERROR if rc != 0 else ProcessStatus.STOPPED
                self._record.status = new_status
                self._on_status_change(self._record.name, new_status)
        except Exception:
            pass
