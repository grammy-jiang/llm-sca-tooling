"""Transaction helper protocol."""

from __future__ import annotations

from contextlib import contextmanager
from sqlite3 import Connection
from typing import Iterator


@contextmanager
def transaction(conn: Connection, _reason: str = "storage") -> Iterator[None]:
    try:
        conn.execute("BEGIN")
        yield
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
