# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Print a startup summary of the effective configuration.

Usage
-----
Called once by ``app.sh`` before Uvicorn starts, so the summary is printed by
the parent process only (not once per worker)::

    python -m fasturl.core.config [workers]

The optional ``workers`` argument overrides ``app.workers`` (``--reload`` mode
always runs a single worker). The database password is never printed.
"""

from __future__ import annotations

import sys

from fasturl.core.config import settings


def summary(workers: int) -> str:
    """Build a human-readable summary of the effective configuration.

    Args:
        workers: Number of Uvicorn worker processes that will be started.

    Returns:
        A multi-line string describing server, database, pool and logging settings.
    """
    db = settings.database
    url = db.url.render_as_string(hide_password=True)
    log = settings.log

    lines = [
        "FastURL configuration",
        f"  Server:   {settings.app.host}:{settings.app.port}, {workers} worker(s)",
    ]

    pg = db.postgresql
    if pg is None:
        lines.append(f"  Database: SQLite — {url}")
    else:
        per_worker = pg.pool_size + pg.max_overflow
        lines += [
            f"  Database: PostgreSQL — {url}",
            f"  Pool:     pool_size={pg.pool_size}, max_overflow={pg.max_overflow} per worker "
            f"(max {workers * per_worker} connections), timeout={pg.pool_timeout}s, recycle={pg.pool_recycle}s",
        ]

    file_info = f"file={log.file} (rotation {log.rotation}, retention {log.retention})" if log.file else "file=off"
    lines.append(f"  Logging:  level={log.level}, console={'on' if log.console else 'off'}, {file_info}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary(workers=int(sys.argv[1]) if len(sys.argv) > 1 else settings.app.workers))
