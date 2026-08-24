"""
Unit tests for the pure/DB-mocked parts of calculations.py.

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

import queries
from calculations import (
    NA,
    Periods,
    _per_bedroom,
    _variance,
    _weighted_occupancy_pct,
    calculate_cash_flow_stub,
    calculate_economic_occupancy,
    calculate_physical_occupancy,
    nearest_availability_snapshot,
    total_bedrooms,
)


class PeriodsTests(unittest.TestCase):
    def test_from_period_boundaries(self):
        p = Periods.from_period(date(2026, 7, 15))
        self.assertEqual(p.current_start, date(2026, 7, 1))
        self.assertEqual(p.current_end, date(2026, 8, 1))
        self.assertEqual(p.last_month_start, date(2026, 6, 1))
        self.assertEqual(p.last_month_end, date(2026, 7, 1))
        self.assertEqual(p.same_ly_start, date(2025, 7, 1))
        self.assertEqual(p.same_ly_end, date(2025, 8, 1))
        self.assertEqual(p.ytd_start, date(2026, 1, 1))
        self.assertEqual(p.ytd_end, date(2026, 8, 1))

    def test_eom(self):
        p = Periods.from_period(date(2026, 7, 15))
        self.assertEqual(p.eom("current"), date(2026, 7, 31))
        self.assertEqual(p.eom("last_month"), date(2026, 6, 30))
        self.assertEqual(p.eom("same_ly"), date(2025, 7, 31))


class HelperTests(unittest.TestCase):
    def test_per_bedroom(self):
        self.assertEqual(_per_bedroom(1000, 100), 10.0)

    def test_per_bedroom_zero_bedrooms(self):
        self.assertEqual(_per_bedroom(1000, 0), NA)

    def test_variance(self):
        self.assertEqual(_variance(110, 100), 10)

    def test_variance_na_propagates(self):
        self.assertEqual(_variance(NA, 100), NA)

    def test_total_bedrooms(self):
        units_df = pd.DataFrame({"unit_bedrooms": [1, 2, 2, None]})
        self.assertEqual(total_bedrooms(units_df), 5.0)


class WeightedOccupancyTests(unittest.TestCase):
    def test_weighted_average(self):
        snapshot = pd.DataFrame({
            "property_code": ["100", "200"],
            "pua_units": [100, 50],
            "pua_pctocc": [90.0, 80.0],
        })
        # (100*90 + 50*80) / 150 = 86.666...
        self.assertEqual(_weighted_occupancy_pct(snapshot), 86.67)

    def test_empty_snapshot(self):
        self.assertEqual(_weighted_occupancy_pct(pd.DataFrame()), NA)


class NearestAvailabilitySnapshotTests(unittest.TestCase):
    @patch("queries.unit_availability_window")
    def test_picks_closest_date_per_property(self, mock_window):
        mock_window.return_value = pd.DataFrame({
            "property_code": ["100", "100", "200"],
            "as_of_date": [date(2026, 7, 29), date(2026, 7, 31), date(2026, 8, 2)],
            "pua_units": [100, 100, 50],
            "pua_pctocc": [88.0, 90.0, 80.0],
        })
        result = nearest_availability_snapshot(None, date(2026, 7, 31), {"100", "200"})
        self.assertEqual(len(result), 2)
        row_100 = result[result["property_code"] == "100"].iloc[0]
        self.assertEqual(row_100["pua_pctocc"], 90.0)

    @patch("queries.unit_availability_window")
    def test_empty_when_no_rows(self, mock_window):
        mock_window.return_value = pd.DataFrame()
        result = nearest_availability_snapshot(None, date(2026, 7, 31), {"100"})
        self.assertTrue(result.empty)


class PhysicalOccupancyTests(unittest.TestCase):
    @patch("queries.unit_availability_window")
    def test_uses_nearest_snapshot_per_period(self, mock_window):
        mock_window.return_value = pd.DataFrame({
            "property_code": ["100"],
            "as_of_date": [date(2026, 7, 31)],
            "pua_units": [100],
            "pua_pctocc": [92.5],
        })
        periods = Periods.from_period(date(2026, 7, 15))
        row = calculate_physical_occupancy(None, {"100"}, periods)
        self.assertEqual(row["Actual"], 92.5)
        self.assertEqual(row["Budget"], NA)
        self.assertEqual(row["YTD"], NA)


class EconomicOccupancyTests(unittest.TestCase):
    @patch("queries.trial_bal_account_totals")
    def test_formula_matches_power_query(self, mock_totals):
        # Raw (un-negated) trial balance activity, as it would come from SQL.
        # Real values are negative for credit-normal revenue accounts.
        mock_totals.return_value = pd.DataFrame({
            "acct_id": [4011003, 4015000, 4016000, 4017001, 4018000, 4018004],
            "total": [-100000, 2000, 5000, 1000, 3000, 500],
        })
        periods = Periods.from_period(date(2026, 7, 15))
        row = calculate_economic_occupancy(None, {"100"}, periods)
        # After negation: GPR=100000, others become -2000,-5000,-1000,-3000,-500
        # EconIncome = 100000 - 2000 - 5000 - 1000 - 3000 - 500 = 88500
        # EconPct = 88500 / 100000 * 100 = 88.5
        self.assertEqual(row["Actual"], 88.5)

    @patch("queries.trial_bal_account_totals")
    def test_na_when_no_data(self, mock_totals):
        mock_totals.return_value = pd.DataFrame()
        periods = Periods.from_period(date(2026, 7, 15))
        row = calculate_economic_occupancy(None, {"100"}, periods)
        self.assertEqual(row["Actual"], NA)


class CashFlowStubTests(unittest.TestCase):
    def test_all_fields_pending(self):
        row = calculate_cash_flow_stub()
        for key in ("Actual", "Budget", "Variance", "Last Month", "YTD", "Same Period LY"):
            self.assertEqual(row[key], "Pending")


if __name__ == "__main__":
    unittest.main()
