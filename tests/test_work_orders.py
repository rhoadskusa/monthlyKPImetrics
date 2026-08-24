"""
Unit tests for work_orders.py against a synthetic Work Order Directory
export that mimics the real Yardi structure (title/description rows,
per-property separators, subtotal + grand total rows).

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import openpyxl

from work_orders import avg_days_to_close, closed_tickets, load_work_orders, total_tickets


def _build_sample_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report1"

    ws.append(["Work Order Directory"])
    ws.append(["Property : All Active MFM Properites (.active)"])
    ws.append([
        "WO#", "Property", "Unit", "Building", "Priority", "Status", "Category",
        "Brief Desc.", "Call Date", "Schedule Date", "Complete Date",
        "Material Amount", "Labor Amount", "Commission Amount", "Total Payable Amount",
    ])

    ws.append(["Property : 100"])
    ws.append([
        "1001", "100", "210", "1", "High", "Work Completed", "Apartment - Exterior",
        "key", datetime(2026, 6, 5, 9, 0), None, datetime(2026, 6, 6, 10, 0), 0, 0, 0, 0,
    ])
    ws.append([
        "1002", "100", "211", "1", "Medium", "Work Completed", "Apartment - Plumbing",
        "toilet", datetime(2026, 6, 10, 9, 0), None, datetime(2026, 6, 20, 10, 0), 0, 0, 0, 0,
    ])
    ws.append([
        "1003", "100", "212", "1", "Low", "Call", "Apartment - Electrical",
        "outlet", datetime(2026, 6, 25, 9, 0), None, None, 0, 0, 0, 0,
    ])
    ws.append(["Total ( 3 )", None, None, None, None, None, None, None, None, None, None, 0, 0, 0, 0])

    ws.append(["Property : 200"])
    ws.append([
        "2001", "200", "10", None, "High", "Canceled", "HVAC",
        "no heat", datetime(2026, 6, 3, 9, 0), None, None, 0, 0, 0, 0,
    ])
    ws.append(["Total ( 1 )", None, None, None, None, None, None, None, None, None, None, 0, 0, 0, 0])
    ws.append(["Grand Total( 4 )", None, None, None, None, None, None, None, None, None, None, 0, 0, 0, 0])

    wb.save(path)


class WorkOrdersTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)
        _build_sample_workbook(self.dir / "sample_2026_06.xlsx")
        self.df = load_work_orders(self.dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_loads_only_ticket_rows(self):
        self.assertEqual(len(self.df), 4)
        self.assertNotIn("Property :", "".join(self.df["Property"].astype(str)))

    def test_total_tickets_in_period(self):
        count = total_tickets(self.df, date(2026, 6, 1), date(2026, 7, 1))
        self.assertEqual(count, 4)

    def test_total_tickets_scoped_to_property(self):
        count = total_tickets(self.df, date(2026, 6, 1), date(2026, 7, 1), {"100"})
        self.assertEqual(count, 3)

    def test_closed_tickets_only_work_completed_with_complete_date(self):
        count = closed_tickets(self.df, date(2026, 6, 1), date(2026, 7, 1))
        self.assertEqual(count, 2)

    def test_avg_days_to_close(self):
        avg = avg_days_to_close(self.df, date(2026, 6, 1), date(2026, 7, 1))
        # ticket 1001: 1 day, ticket 1002: 10 days -> mean 5.5
        self.assertEqual(avg, 5.5)

    def test_avg_days_to_close_none_when_nothing_closed(self):
        avg = avg_days_to_close(self.df, date(2026, 6, 1), date(2026, 7, 1), {"200"})
        self.assertIsNone(avg)


if __name__ == "__main__":
    unittest.main()
