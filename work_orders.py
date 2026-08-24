"""
Parse Yardi "Work Order Directory" exports and compute ticket metrics.

These are NOT flat CSVs -- they're grouped Excel reports:
  Row 1: title ("Work Order Directory")
  Row 2: report-level property filter description
  Row 3: column headers
  Then, repeated per property:
    - a separator row "Property : <code>" (only the first column populated)
    - one row per work order ticket
    - a subtotal row "Total ( N )"
  Final row: "Grand Total( N )"

*** OPEN ITEM ***
Only a small sample (63 rows) was available when this was built. The full
set of Status values, and which ones should count as "closed" beyond
"Work Completed", should be confirmed once the full historical export
(back to 1/1/2025) is available.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import openpyxl
import pandas as pd

log = logging.getLogger(__name__)

EXPECTED_HEADER = [
    "WO#", "Property", "Unit", "Building", "Priority", "Status", "Category",
    "Brief Desc.", "Call Date", "Schedule Date", "Complete Date",
    "Material Amount", "Labor Amount", "Commission Amount", "Total Payable Amount",
]

CLOSED_STATUS_VALUES = {"Work Completed"}


def _is_noise_row(first_cell) -> bool:
    if first_cell is None:
        return False
    text = str(first_cell).strip()
    return text.startswith("Property :") or text.startswith("Total (") or text.startswith("Grand Total(")


def _load_single_file(path: Path) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]

    header = None
    records = []
    for row in ws.iter_rows(values_only=True):
        if header is None:
            if row and row[0] == "WO#":
                header = list(row[: len(EXPECTED_HEADER)])
            continue
        if not row or all(v is None for v in row):
            continue
        if _is_noise_row(row[0]):
            continue
        records.append(row[: len(header)])

    wb.close()

    if header is None:
        raise ValueError(f"Could not find the 'WO#' header row in {path}")

    df = pd.DataFrame(records, columns=header)
    df["Property"] = df["Property"].astype(str).str.strip()
    df["_source_file"] = path.name
    return df


def load_work_orders(work_order_dir: Path) -> pd.DataFrame:
    """Load and concatenate every Work Order Directory export in a folder."""
    files = sorted(work_order_dir.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No .xlsx work order exports found in {work_order_dir}")

    frames = [_load_single_file(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="WO#", keep="last")
    log.info("Loaded %d work order tickets from %d file(s)", len(df), len(files))
    return df


def _in_period(series: pd.Series, start: date, end: date) -> pd.Series:
    dates = pd.to_datetime(series, errors="coerce")
    return (dates >= pd.Timestamp(start)) & (dates < pd.Timestamp(end))


def total_tickets(df: pd.DataFrame, start: date, end: date, property_codes: set[str] | None = None) -> int:
    subset = df[_in_period(df["Call Date"], start, end)]
    if property_codes is not None:
        subset = subset[subset["Property"].isin(property_codes)]
    return len(subset)


def closed_tickets(df: pd.DataFrame, start: date, end: date, property_codes: set[str] | None = None) -> int:
    subset = df[_in_period(df["Call Date"], start, end)]
    if property_codes is not None:
        subset = subset[subset["Property"].isin(property_codes)]
    subset = subset[subset["Status"].isin(CLOSED_STATUS_VALUES) & subset["Complete Date"].notna()]
    return len(subset)


def avg_days_to_close(df: pd.DataFrame, start: date, end: date, property_codes: set[str] | None = None) -> float | None:
    subset = df[_in_period(df["Call Date"], start, end)]
    if property_codes is not None:
        subset = subset[subset["Property"].isin(property_codes)]
    subset = subset[subset["Status"].isin(CLOSED_STATUS_VALUES) & subset["Complete Date"].notna()]
    if subset.empty:
        return None

    call = pd.to_datetime(subset["Call Date"])
    complete = pd.to_datetime(subset["Complete Date"])
    days = (complete - call).dt.total_seconds() / 86400
    return round(days.mean(), 1)
