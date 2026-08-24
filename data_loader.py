"""
SQL Server connection and query execution helpers.

All connection details come from config.py (which reads them from ".env").
Never log the connection string itself -- only high-level status.
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

import config

log = logging.getLogger(__name__)


def get_engine() -> Engine:
    """Build a SQLAlchemy engine for the ParentCO SQL Server database.

    Uses the ODBC Driver 18 for SQL Server. If a different driver is
    installed locally, override PYODBC_DRIVER in .env (not currently
    exposed as a setting -- edit the constant below if needed).
    """
    driver = "ODBC Driver 18 for SQL Server"

    if config.DB_TRUSTED_CONNECTION:
        odbc_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={config.DB_SERVER};"
            f"DATABASE={config.DB_NAME};"
            f"Trusted_Connection=yes;"
            f"Encrypt=yes;"
        )
    else:
        odbc_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={config.DB_SERVER};"
            f"DATABASE={config.DB_NAME};"
            f"UID={config.DB_USER};"
            f"PWD={config.DB_PASSWORD};"
            f"Encrypt=yes;"
        )

    connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_str)}"
    engine = create_engine(connection_url)
    log.info("Connected to SQL Server %s / %s", config.DB_SERVER, config.DB_NAME)
    return engine


def run_query(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a parameterized query and return the result as a DataFrame."""
    df = pd.read_sql(sql, engine, params=params or {})
    log.info("Query returned %d rows", len(df))
    return df
