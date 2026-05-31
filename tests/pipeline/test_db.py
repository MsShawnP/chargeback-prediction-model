"""Tests for src/pipeline/db.py — connection helper behavior."""

import os
from unittest.mock import patch

import pytest

# Import at module scope so load_dotenv() in db.py fires before any test
# patches os.environ. If imported inside a patch.dict context, load_dotenv()
# would run during the patch and re-inject DATABASE_URL from .env.
from src.pipeline.db import DatabaseConnectionError, _get_url


def test_missing_database_url_raises_descriptive_error():
    """DatabaseConnectionError is raised with a helpful message when DATABASE_URL is not set."""
    env_without_url = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    with patch.dict(os.environ, env_without_url, clear=True):
        with pytest.raises(DatabaseConnectionError) as exc_info:
            _get_url()

        msg = str(exc_info.value)
        assert "DATABASE_URL" in msg
        assert "flyctl" in msg or "postgresql" in msg.lower()


def test_missing_database_url_error_is_not_raw_psycopg2_exception():
    """The error we raise is our own type, not a raw psycopg2 exception."""
    env_without_url = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    with patch.dict(os.environ, env_without_url, clear=True):
        with pytest.raises(DatabaseConnectionError):
            _get_url()
