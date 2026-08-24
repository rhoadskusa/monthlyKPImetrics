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

Confirmed full Status value set: Call, Canceled, In Progress, On Hold,
Request Reassignment, Scheduled, Vendor Schedule, Web, Work Completed.
Only "Work Completed" counts as closed for Closed Tickets / Avg Days to
Close -- every other status is either still open or terminated without
completed work (Canceled).

Each .xlsx export gets a Parquet cache written next to it (same name,
".parquet" extension) the first time it's parsed. Yardi work order exports
carry a per-cell hyperlink back to the ticket/property/unit in Yardi, which
makes openpyxl very slow to open on large files (e.g. a multi-year
historical backfill) even though those links are irrelevant here -- the
cache means that slow parse only ever happens once per file. See also
convert_work_orders.py, a standalone script for pre-building the cache for
a whole folder up front (handy for the initial historical backfill).
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


def _parse_xlsx(path: Path) -> pd.DataFrame:
    """Slow path: parse a raw Yardi .xlsx export. This is the step the
    per-cell hyperlinks make expensive on large files -- avoid calling this
    directly; go through _load_single_file() or convert_to_cache() instead
    so the result gets cached."""
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


def _cache_path_for(xlsx_path: Path) -> Path:
    return xlsx_path.with_suffix(".parquet")


def convert_to_cache(xlsx_path: Path, force: bool = False) -> tuple[Path, pd.DataFrame]:
    """Parse one .xlsx export and write/refresh its Parquet cache.

    Skips re-parsing if the cache already exists and is newer than the
    source file, unless force=True. Returns (cache_path, dataframe).
    Raises ImportError with a clear pip-install hint if pyarrow isn't
    installed (pandas needs it to write/read Parquet).
    """
    cache_path = _cache_path_for(xlsx_path)
    if not force and cache_path.exists() and cache_path.stat().st_mtime >= xlsx_path.stat().st_mtime:
        return cache_path, pd.read_parquet(cache_path)

    df = _parse_xlsx(xlsx_path)
    try:
        df.to_parquet(cache_path, index=False)
    except ImportError as exc:
        raise ImportError(
            "Writing the work order cache requires pyarrow: pip install pyarrow"
        ) from exc
    return cache_path, df


def _load_single_file(path: Path, use_cache: bool = True) -> pd.DataFrame:
    if not use_cache:
        return _parse_xlsx(path)

    cache_path = _cache_path_for(path)
    if cache_path.exists() and cache_path.stat().st_mtime >= path.stat().st_mtime:
        return pd.read_parquet(cache_path)

    try:
        _, df = convert_to_cache(path, force=True)
    except ImportError:
        log.warning("pyarrow not installed -- parsing %s without caching (pip install pyarrow to speed up future runs)", path.name)
        df = _parse_xlsx(path)
    return df


def load_work_orders(work_order_dir: Path, use_cache: bool = True) -> pd.DataFrame:
    """Load and concatenate every Work Order Directory export in a folder.

    Each file is parsed once and cached as Parquet next to it (see
    _load_single_file); subsequent runs read the cache instead of
    re-parsing the slow, hyperlink-heavy .xlsx.
    """
    files = sorted(work_order_dir.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No .xlsx work order exports found in {work_order_dir}")

    frames = [_load_single_file(f, use_cache) for f in files]
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
