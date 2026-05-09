"""JSON-RPC request dispatch."""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import BinaryIO

from llm_sca_tooling.indexing.lsp.errors import LspCrash, LspTimeout
from llm_sca_tooling.indexing.lsp.protocol import decode_header, encode_message


class RequestDispatcher:
    def __init__(self, stdin: BinaryIO, stdout: BinaryIO) -> None:
        self.stdin = stdin
        self.stdout = stdout
        self._next_id = 1
        self._responses: dict[int, queue.Queue[dict]] = {}
        self._notifications: queue.Queue[dict] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def stop(self) -> None:
        self._running = False

    def request(self, method: str, params: dict, timeout_ms: int) -> dict:
        request_id = self._next_id
        self._next_id += 1
        self._responses[request_id] = queue.Queue(maxsize=1)
        self.stdin.write(encode_message({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}))
        self.stdin.flush()
        try:
            response = self._responses[request_id].get(timeout=timeout_ms / 1000)
        except queue.Empty as exc:
            raise LspTimeout(f"LSP request timed out: {method}") from exc
        finally:
            self._responses.pop(request_id, None)
        if "error" in response:
            raise LspCrash(str(response["error"]))
        return response.get("result", {})

    def notify(self, method: str, params: dict) -> None:
        self.stdin.write(encode_message({"jsonrpc": "2.0", "method": method, "params": params}))
        self.stdin.flush()

    def wait_for_notification(self, method: str, timeout_ms: int) -> dict | None:
        deadline = time.monotonic() + timeout_ms / 1000
        deferred: list[dict] = []
        try:
            while time.monotonic() < deadline:
                try:
                    payload = self._notifications.get(timeout=max(0.0, deadline - time.monotonic()))
                except queue.Empty:
                    return None
                if payload.get("method") == method:
                    return payload
                deferred.append(payload)
        finally:
            for payload in deferred:
                self._notifications.put(payload)
        return None

    def _read_loop(self) -> None:
        while self._running:
            header = b""
            while b"\r\n\r\n" not in header:
                chunk = self.stdout.read(1)
                if not chunk:
                    self._running = False
                    return
                header += chunk
            try:
                length = decode_header(header.split(b"\r\n\r\n", 1)[0])
                payload = json.loads(self.stdout.read(length).decode("utf-8"))
            except Exception:
                continue
            request_id = payload.get("id")
            if isinstance(request_id, int) and request_id in self._responses:
                self._responses[request_id].put(payload)
            elif "method" in payload:
                self._notifications.put(payload)
