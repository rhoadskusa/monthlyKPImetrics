"""
Unit tests for the driver-not-found error handling in data_loader.get_engine().

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DBAPIError

import data_loader


class _FakeDriverNotFoundError(Exception):
    def __str__(self):
        return (
            "(pyodbc.InterfaceError) ('IM002', '[IM002] [Microsoft][ODBC Driver Manager] "
            "Data source name not found and no default driver specified (0) (SQLDriverConnect)')"
        )


class _FakeOtherError(Exception):
    def __str__(self):
        return "(pyodbc.OperationalError) ('08001', 'Login timeout expired')"


class GetEngineDriverErrorTests(unittest.TestCase):
    def test_driver_not_found_exits_with_helpful_message(self):
        fake_engine = MagicMock()
        fake_engine.connect.side_effect = DBAPIError("stmt", {}, _FakeDriverNotFoundError())

        with patch("data_loader.create_engine", return_value=fake_engine), \
             patch("data_loader._installed_odbc_drivers", return_value=["ODBC Driver 17 for SQL Server", "SQL Server"]):
            with self.assertRaises(SystemExit) as ctx:
                data_loader.get_engine()

        message = str(ctx.exception.code)
        self.assertIn("DB_DRIVER", message)
        self.assertIn("ODBC Driver 17 for SQL Server", message)
        self.assertIn("SQL Server", message)

    def test_driver_not_found_with_no_drivers_detected(self):
        fake_engine = MagicMock()
        fake_engine.connect.side_effect = DBAPIError("stmt", {}, _FakeDriverNotFoundError())

        with patch("data_loader.create_engine", return_value=fake_engine), \
             patch("data_loader._installed_odbc_drivers", return_value=[]):
            with self.assertRaises(SystemExit) as ctx:
                data_loader.get_engine()

        self.assertIn("install", str(ctx.exception.code).lower())

    def test_other_dbapi_errors_are_not_swallowed(self):
        fake_engine = MagicMock()
        fake_engine.connect.side_effect = DBAPIError("stmt", {}, _FakeOtherError())

        with patch("data_loader.create_engine", return_value=fake_engine):
            with self.assertRaises(DBAPIError):
                data_loader.get_engine()

    def test_successful_connection_returns_engine(self):
        fake_engine = MagicMock()
        fake_engine.connect.return_value.__enter__ = MagicMock(return_value=None)
        fake_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("data_loader.create_engine", return_value=fake_engine):
            result = data_loader.get_engine()

        self.assertIs(result, fake_engine)


if __name__ == "__main__":
    unittest.main()
