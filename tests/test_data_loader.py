"""
Unit tests for data_loader.get_engine(): connection-string construction and
the driver-not-found / SSL-handshake error handling.

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import unquote_plus

from sqlalchemy.exc import DBAPIError

import config
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


class _FakeSslHandshakeError(Exception):
    def __str__(self):
        return (
            "('08001', '[08001] [Microsoft][ODBC SQL Server Driver][DBNETLIB]SSL Security "
            "error (18) (SQLDriverConnect); [08001] [Microsoft][ODBC SQL Server Driver]"
            "[DBNETLIB]ConnectionOpen (SECDoClientHandshake()). (271)')"
        )


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

    def test_ssl_handshake_error_with_encrypt_set_suggests_removing_it(self):
        fake_engine = MagicMock()
        fake_engine.connect.side_effect = DBAPIError("stmt", {}, _FakeSslHandshakeError())

        with patch("data_loader.create_engine", return_value=fake_engine), \
             patch.object(config, "DB_ENCRYPT", "yes"):
            with self.assertRaises(SystemExit) as ctx:
                data_loader.get_engine()

        message = str(ctx.exception.code)
        self.assertIn("DB_ENCRYPT", message)
        self.assertIn("removing", message.lower())

    def test_ssl_handshake_error_with_encrypt_unset_gives_troubleshooting_steps(self):
        fake_engine = MagicMock()
        fake_engine.connect.side_effect = DBAPIError("stmt", {}, _FakeSslHandshakeError())

        with patch("data_loader.create_engine", return_value=fake_engine), \
             patch.object(config, "DB_ENCRYPT", ""):
            with self.assertRaises(SystemExit) as ctx:
                data_loader.get_engine()

        message = str(ctx.exception.code)
        self.assertIn("DB_DRIVER", message)
        self.assertNotIn("removing DB_ENCRYPT", message)

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


class ConnectionStringTests(unittest.TestCase):
    def _build_odbc_str(self) -> str:
        fake_engine = MagicMock()
        fake_engine.connect.return_value.__enter__ = MagicMock(return_value=None)
        fake_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("data_loader.create_engine", return_value=fake_engine) as mock_create:
            data_loader.get_engine()

        connection_url = mock_create.call_args.args[0]
        # connection_url looks like mssql+pyodbc:///?odbc_connect=<quoted odbc string>
        encoded = connection_url.split("odbc_connect=", 1)[1]
        return unquote_plus(encoded)

    def test_encrypt_omitted_by_default(self):
        with patch.object(config, "DB_ENCRYPT", ""):
            odbc_str = self._build_odbc_str()
        self.assertNotIn("Encrypt=", odbc_str)

    def test_encrypt_included_when_set(self):
        with patch.object(config, "DB_ENCRYPT", "yes"):
            odbc_str = self._build_odbc_str()
        self.assertIn("Encrypt=yes;", odbc_str)


if __name__ == "__main__":
    unittest.main()
