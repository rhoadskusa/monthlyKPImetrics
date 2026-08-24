"""
Unit tests for the pure (no-DB) parts of calculations.py.

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from calculations import (
    NA,
    Periods,
    _per_bedroom,
    _variance,
    calculate_cash_flow_stub,
    calculate_physical_occupancy,
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


class HelperTests(unittest.TestCase):
    def test_per_bedroom(self):
        self.assertEqual(_per_bedroom(1000, 100), 10.0)

    def test_per_bedroom_zero_bedrooms(self):
        self.assertEqual(_per_bedroom(1000, 0), NA)

    def test_variance(self):
        self.assertEqual(_variance(110, 100), 10)

    def test_variance_na_propagates(self):
        self.assertEqual(_variance(NA, 100), NA)


class OccupancyTests(unittest.TestCase):
    def test_physical_occupancy(self):
        units_df = pd.DataFrame({
            "unit_status": ["Occupied", "Occupied", "Vacant-Unrented", "Occupied"],
        })
        row = calculate_physical_occupancy(units_df, Periods.from_period(date(2026, 7, 1)))
        self.assertEqual(row["Actual"], 75.0)

    def test_physical_occupancy_empty(self):
        units_df = pd.DataFrame({"unit_status": []})
        row = calculate_physical_occupancy(units_df, Periods.from_period(date(2026, 7, 1)))
        self.assertEqual(row["Actual"], NA)

    def test_total_bedrooms(self):
        units_df = pd.DataFrame({"unit_bedrooms": [1, 2, 2, None]})
        self.assertEqual(total_bedrooms(units_df), 5.0)


class CashFlowStubTests(unittest.TestCase):
    def test_all_fields_pending(self):
        row = calculate_cash_flow_stub()
        for key in ("Actual", "Budget", "Variance", "Last Month", "YTD", "Same Period LY"):
            self.assertEqual(row[key], "Pending")


if __name__ == "__main__":
    unittest.main()
