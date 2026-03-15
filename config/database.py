"""Helpers for DATABASE_URL normalization and network overrides."""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse


_TRUE_VALUES = {"1", "true", "yes", "on"}


def normalize_database_url(database_url: str) -> str:
    value = str(database_url or "").strip()

    if value.startswith("psql"):
        value = value.replace("psql", "", 1).strip()

    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        value = value[1:-1]

    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql://", 1)

    return value


def apply_database_network_overrides(db_config: dict, database_url: str) -> dict:
    config = dict(db_config)
    options = dict(config.get("OPTIONS") or {})

    hostaddr = str(os.environ.get("DATABASE_HOSTADDR") or os.environ.get("PGHOSTADDR") or "").strip()

    if not hostaddr and _env_flag("DATABASE_PREFER_IPV4"):
        parsed = urlparse(database_url)
        hostname = str(config.get("HOST") or parsed.hostname or "").strip()
        port = int(config.get("PORT") or parsed.port or 5432)
        if hostname:
            hostaddr = _resolve_ipv4_address(hostname, port)

    if hostaddr:
        options["hostaddr"] = hostaddr
        config["OPTIONS"] = options

    return config


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in _TRUE_VALUES


def _resolve_ipv4_address(hostname: str, port: int) -> str:
    try:
        candidates = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return ""

    for _, _, _, _, sockaddr in candidates:
        if sockaddr and sockaddr[0]:
            return str(sockaddr[0])
    return ""
