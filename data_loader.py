"""
SQL Server connection and query execution helpers.

All connection details come from config.py (which reads them from ".env").
Never log the connection string itself -- only high-level status.
"""

from __future__ import annotations

import logging
import sys
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

import config

log = logging.getLogger(__name__)


def _installed_odbc_drivers() -> list[str]:
    try:
        import pyodbc

        return pyodbc.drivers()
    except Exception:
        return []


def get_engine() -> Engine:
    """Build a SQLAlchemy engine for the ParentCO SQL Server database and
    verify it actually connects before handing it back.

    Uses the ODBC driver named by DB_DRIVER in .env (defaults to "ODBC
    Driver 18 for SQL Server"). If that driver isn't installed, pyodbc
    fails with a cryptic "Data source name not found" error -- caught here
    and turned into a message naming the drivers that ARE installed, so
    fixing DB_DRIVER doesn't require reading a traceback.

    Does NOT force Encrypt=yes -- that broke a TLS handshake that worked
    fine in other scripts using the exact same credentials/driver without
    it. DB_ENCRYPT in .env can add it back explicitly if ever needed.
    """
    driver = config.DB_DRIVER

    if config.DB_TRUSTED_CONNECTION:
        odbc_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={config.DB_SERVER};"
            f"DATABASE={config.DB_NAME};"
            f"Trusted_Connection=yes;"
        )
    else:
        odbc_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={config.DB_SERVER};"
            f"DATABASE={config.DB_NAME};"
            f"UID={config.DB_USER};"
            f"PWD={config.DB_PASSWORD};"
        )

    if config.DB_ENCRYPT:
        odbc_str += f"Encrypt={config.DB_ENCRYPT};"

    connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_str)}"
    engine = create_engine(connection_url)

    try:
        with engine.connect():
            pass
    except DBAPIError as exc:
        message = str(exc.orig) if exc.orig else str(exc)
        lower_message = message.lower()

        if "data source name not found" in lower_message or "im002" in lower_message:
            installed = _installed_odbc_drivers()
            installed_note = (
                f"Drivers installed on this machine: {', '.join(installed)}"
                if installed
                else "Could not detect any installed ODBC drivers -- you may need to install one "
                "(e.g. Microsoft's \"ODBC Driver 18 for SQL Server\")."
            )
            sys.exit(
                f"Couldn't find the ODBC driver \"{driver}\" (set via DB_DRIVER in .env).\n"
                f"{installed_note}\n"
                f"Set DB_DRIVER in your .env to one of the names above (no braces needed)."
            )

        if "ssl security error" in lower_message or "secdoclienthandshake" in lower_message:
            if config.DB_ENCRYPT:
                sys.exit(
                    f"TLS/SSL handshake failed while connecting with driver \"{driver}\" "
                    f"and DB_ENCRYPT={config.DB_ENCRYPT}.\n"
                    "Try removing DB_ENCRYPT from your .env entirely (leave it unset) and "
                    "run again -- forcing Encrypt can break a handshake that otherwise works "
                    "fine with this driver/credentials."
                )
            sys.exit(
                f"TLS/SSL handshake failed while connecting with driver \"{driver}\".\n"
                "DB_ENCRYPT is already unset, so this isn't the forced-encryption issue. "
                "Next things to check: confirm DB_DRIVER matches a driver actually installed "
                "on this machine (python -c \"import pyodbc; print(pyodbc.drivers())\"), and "
                "confirm this same driver/credentials work from another tool (e.g. a script "
                "that has connected successfully before) to rule out a network/firewall issue."
            )

        raise

    log.info("Connected to SQL Server %s / %s", config.DB_SERVER, config.DB_NAME)
    return engine


def run_query(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a parameterized query and return the result as a DataFrame."""
    df = pd.read_sql(sql, engine, params=params or {})
    log.info("Query returned %d rows", len(df))
    return df
