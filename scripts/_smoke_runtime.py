from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _sqlite_database_url(path: Path) -> str:
    return f"sqlite:///{path}"


@contextmanager
def managed_smoke_database(
    repo_root: Path,
    *,
    migrate_timeout: int = 1200,
) -> Iterator[dict[str, str]]:
    """Provision an isolated SQLite DB so smoke runs never depend on local dev data."""

    temp_dir = Path(tempfile.mkdtemp(prefix="eduitit-smoke-db-"))
    db_path = temp_dir / "smoke.sqlite3"
    database_url = _sqlite_database_url(db_path)
    previous_database_url = os.environ.get("DATABASE_URL")

    os.environ["DATABASE_URL"] = database_url

    try:
        subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput"],
            cwd=str(repo_root),
            env={**os.environ, "DATABASE_URL": database_url},
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=migrate_timeout,
        )
        yield {
            "DATABASE_URL": database_url,
            "SMOKE_DB_PATH": str(db_path),
        }
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        shutil.rmtree(temp_dir, ignore_errors=True)
