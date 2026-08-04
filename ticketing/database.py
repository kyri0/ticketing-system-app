"""Lakebase connection handling using a single LAKEBASE_URL secret.

Connects with a standard Postgres connection URL, e.g.

    postgresql://role:password@host:5432/databricks_postgres?sslmode=require

pointing at a native Postgres role with a static, non-expiring password. The URL
is stored in a Databricks secret scope, so deployment needs one secret instead of
several connection environment variables.

For local development, set LAKEBASE_URL directly and the secret lookup is skipped.
"""

from __future__ import annotations

import base64
import os
from contextlib import contextmanager
from functools import lru_cache

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool


class DatabaseConfigurationError(RuntimeError):
    """The app could not obtain a Lakebase connection URL."""


@lru_cache(maxsize=1)
def lakebase_url() -> str:
    """Return the Lakebase connection URL, preferring a local env override.

    The password is static, so the resolved URL is cached for the process
    lifetime rather than re-read from the secret scope on every connection.
    """
    override = os.getenv("LAKEBASE_URL")
    if override:
        return override

    scope = os.getenv("LAKEBASE_SECRET_SCOPE", "database")
    key = os.getenv("LAKEBASE_SECRET_KEY", "lakebase-url")
    try:
        secret = WorkspaceClient().secrets.get_secret(scope=scope, key=key)
        return base64.b64decode(secret.value).decode("utf-8")
    except Exception as error:  # noqa: BLE001 - surfaced as a configuration error
        raise DatabaseConfigurationError(
            f"Could not read the Lakebase URL from secret '{scope}/{key}'. "
            "Set LAKEBASE_URL for local development, or check the secret scope "
            "and the app service principal's READ permission on it."
        ) from error


class LakebasePool:
    """A small pool over the static-password connection URL.

    The reference helper opens a new connection per query. Pooling avoids a
    TCP+TLS handshake on every request. The credential model is unchanged.
    """

    def __init__(self, minconn: int = 1, maxconn: int = 5):
        try:
            self._pool = ThreadedConnectionPool(
                minconn,
                maxconn,
                dsn=lakebase_url(),
                cursor_factory=RealDictCursor,
                application_name=os.getenv("PGAPPNAME", "support-ticket-manager"),
            )
        except psycopg2.Error as error:
            raise DatabaseConfigurationError(
                "Could not connect to Lakebase with the configured LAKEBASE_URL."
            ) from error

    @contextmanager
    def connection(self):
        """Check a connection out of the pool and always return it."""
        connection = self._pool.getconn()
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        finally:
            self._pool.putconn(connection)

    def close(self) -> None:
        self._pool.closeall()


def create_pool() -> LakebasePool:
    """Create the pool used for the lifetime of the worker process."""
    return LakebasePool()
