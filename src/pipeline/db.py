"""
Database connection helpers for the Cinderhaven pipeline.

Requires DATABASE_URL in the environment (set it in .env or export before running).
Run `flyctl proxy 5432 -a cinderhaven-db` to expose the Fly.io Postgres.
"""

import contextlib
import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class DatabaseConnectionError(Exception):
    """Raised when the pipeline cannot connect to Cinderhaven Postgres."""


def _get_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise DatabaseConnectionError(
            "DATABASE_URL is not set. "
            "Copy .env.example → .env, fill in your credentials, "
            "then run: flyctl proxy 5432 -a cinderhaven-data-platform"
        )
    return url


@contextlib.contextmanager
def connection():
    """Yield a psycopg2 connection; close it on exit regardless of exceptions."""
    conn = psycopg2.connect(_get_url(), connect_timeout=10)
    try:
        yield conn
    finally:
        conn.close()


def query_to_df(sql: str, params=None) -> pd.DataFrame:
    """Execute SQL against Cinderhaven and return results as a DataFrame."""
    with connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)
