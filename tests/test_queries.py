"""
Unit tests for the SQL-building logic in queries.py (mocking run_query so
no real DB connection is needed).

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import queries


class BudgetByPropertyTests(unittest.TestCase):
    @patch("queries.run_query")
    def test_picks_correct_month_column(self, mock_run):
        mock_run.return_value = None
        queries.budget_by_property(None, [4011000], date(2026, 3, 1))
        sql = mock_run.call_args.args[1]
        self.assertIn("pmb_MTD03", sql)
        self.assertNotIn("pmb_MTD07", sql)

    @patch("queries.run_query")
    def test_strips_dashes_from_acctnum_for_matching(self, mock_run):
        mock_run.return_value = None
        queries.budget_by_property(None, [4011000], date(2026, 7, 1))
        sql = mock_run.call_args.args[1]
        self.assertIn("REPLACE(pmb_acctnum, '-', '')", sql)

    @patch("queries.run_query")
    def test_filters_by_year_and_type(self, mock_run):
        mock_run.return_value = None
        queries.budget_by_property(None, [4011000], date(2026, 7, 1))
        params = mock_run.call_args.args[2]
        self.assertEqual(params["year"], 2026)
        sql = mock_run.call_args.args[1]
        self.assertIn("pmb_type = 'BUD'", sql)

    @patch("queries.run_query")
    def test_has_group_by_matching_the_selected_property_expression(self, mock_run):
        # Regression test: SELECT TRIM(pmb_propertycode) alongside
        # SUM(...) with no GROUP BY at all passed our own unit tests
        # (which only mock run_query) but SQL Server rejects it outright:
        # "Column ... is invalid in the select list because it is not
        # contained in either an aggregate function or the GROUP BY
        # clause." Every aggregate query here needs a GROUP BY that
        # matches its non-aggregated SELECT expression exactly.
        mock_run.return_value = None
        queries.budget_by_property(None, [4011000], date(2026, 7, 1))
        sql = mock_run.call_args.args[1]
        self.assertIn("GROUP BY TRIM(pmb_propertycode)", sql)

    @patch("queries.run_query")
    def test_invalid_month_raises(self, mock_run):
        # date() itself won't build a month > 12, so exercise the guard
        # via a minimal stand-in object with an out-of-range .month.
        class FakeDate:
            year = 2026
            month = 13

        with self.assertRaises(ValueError):
            queries.budget_by_property(None, [4011000], FakeDate())


if __name__ == "__main__":
    unittest.main()
