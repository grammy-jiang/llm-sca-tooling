"""Compatibility stdio transport for MCP server startup."""

from __future__ import annotations

import asyncio
import queue
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TextIO

import anyio
import anyio.lowlevel
import mcp.types as types
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.shared.message import SessionMessage


class _StdinEof:
    pass


_STDIN_EOF = _StdinEof()
_StdinItem = str | Exception | _StdinEof


@asynccontextmanager
async def threaded_stdio_server(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> AsyncIterator[
    tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
    ]
]:
    """MCP stdio transport using thread-backed text IO.

    The upstream MCP stdio transport wraps ``sys.stdin`` with ``anyio.wrap_file``.
    In the Codex Python 3.14 sandbox that read path can block indefinitely on
    piped stdio, which prevents MCP initialization from receiving the client's
    first JSON-RPC message. Reading and writing through AnyIO worker threads
    keeps the same JSONL protocol while avoiding that blocked async-file path.
    """

    input_file = stdin or sys.stdin
    output_file = stdout or sys.stdout
    stdin_queue: queue.Queue[_StdinItem] = queue.Queue()

    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream[
        SessionMessage | Exception
    ](100)
    write_stream, write_stream_reader = anyio.create_memory_object_stream[
        SessionMessage
    ](0)

    def read_stdin_lines() -> None:
        try:
            while True:
                line = input_file.readline()
                if line == "":
                    break
                stdin_queue.put(line)
        except Exception as exc:  # pragma: no cover - defensive transport guard
            stdin_queue.put(exc)
        finally:
            stdin_queue.put(_STDIN_EOF)

    threading.Thread(target=read_stdin_lines, daemon=True).start()

    async def stdin_reader() -> None:
        try:
            async with read_stream_writer:
                while True:
                    try:
                        item = stdin_queue.get_nowait()
                    except queue.Empty:
                        await anyio.sleep(0.01)
                        continue
                    if isinstance(item, _StdinEof):
                        break
                    if isinstance(item, Exception):
                        await read_stream_writer.send(item)
                        await anyio.lowlevel.checkpoint()
                        continue
                    try:
                        message = types.JSONRPCMessage.model_validate_json(item)
                    except Exception as exc:
                        await read_stream_writer.send(exc)
                        await anyio.lowlevel.checkpoint()
                        continue
                    await read_stream_writer.send(SessionMessage(message))
                    await anyio.lowlevel.checkpoint()
        except anyio.ClosedResourceError:  # pragma: no cover
            await anyio.lowlevel.checkpoint()

    async def stdout_writer() -> None:
        loop = asyncio.get_running_loop()
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    payload = session_message.message.model_dump_json(
                        by_alias=True,
                        exclude_none=True,
                    )
                    await loop.run_in_executor(None, _write_line, output_file, payload)
        except anyio.ClosedResourceError:  # pragma: no cover
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tg:
        tg.start_soon(stdin_reader)
        tg.start_soon(stdout_writer)
        yield read_stream, write_stream


def install_threaded_stdio_server() -> None:
    """Install the compatibility transport for FastMCP stdio startup."""

    import fastmcp.server.mixins.transport as fastmcp_transport
    import mcp.server.stdio as mcp_stdio

    mcp_stdio.stdio_server = threaded_stdio_server  # type: ignore[assignment]
    fastmcp_transport.stdio_server = threaded_stdio_server  # type: ignore[attr-defined,assignment]


def _write_line(output_file: TextIO, payload: str) -> None:
    output_file.write(payload + "\n")
    output_file.flush()
