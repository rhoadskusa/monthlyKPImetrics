#!/usr/bin/env python3
"""
Monthly KPI Metrics Report -- ParentCO Multifamily

Pulls portfolio-level financial and operational KPIs (NOI, CapEx, OpEx %,
M&R, Physical/Economic Occupancy, Work Order stats), all normalized
$/Bedroom where applicable, and writes a monthly summary report as both
Excel and CSV.

Requirements:
    pip install -r requirements.txt

Setup:
    1. Copy .env.example to .env (same folder as this script).
    2. Fill in real SQL Server / AirTable credentials and the local
       OneDrive-synced work order folder path. NEVER commit .env or paste
       its contents anywhere -- it's gitignored on purpose.

Usage:
    python main.py                  # reports on the previous calendar month
    python main.py --period 2026-07 # reports on a specific month (YYYY-MM)

Output:
    output/<year>_<month>_metrics_report.xlsx
    output/<year>_<month>_metrics_report.csv
    (or wherever REPORT_OUTPUT_DIR in .env points)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import config
from calculations import (
    Periods,
    calculate_capex,
    calculate_cash_flow_stub,
    calculate_economic_occupancy,
    calculate_mr,
    calculate_noi,
    calculate_opex_ratio,
    calculate_physical_occupancy,
    calculate_work_order_metrics,
    total_bedrooms,
)
from report_generator import build_summary_table, write_reports

log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the monthly KPI metrics report.")
    parser.add_argument(
        "--period",
        type=str,
        default=None,
        help="Target report month, formatted YYYY-MM. Defaults to REPORT_PERIOD in .env, "
        "or the previous calendar month if that's also unset.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    log_dir = config.SCRIPT_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "report.log", encoding="utf-8"),
        ],
    )


def main() -> None:
    configure_logging()
    args = parse_args()

    period = date.fromisoformat(f"{args.period}-01") if args.period else config.REPORT_PERIOD
    log.info("Generating KPI report for %s-%02d", period.year, period.month)

    from data_loader import get_engine
    from airtable_extractor import get_active_property_codes
    from work_orders import load_work_orders
    import queries

    engine = get_engine()

    log.info("Pulling active property list from AirTable...")
    active_property_codes = get_active_property_codes()
    if not active_property_codes:
        sys.exit("No active properties returned from AirTable -- check PropStatus values and .env settings.")

    log.info("Pulling unit inventory from PM_Units...")
    units_df = queries.unit_inventory(engine, sorted(active_property_codes))
    bedrooms = total_bedrooms(units_df)
    if not bedrooms:
        log.warning("Total bedroom count is zero -- $/Bedroom metrics will report N/A.")

    periods = Periods.from_period(period)

    log.info("Calculating financial metrics...")
    rows = [
        calculate_noi(engine, active_property_codes, bedrooms, periods),
        calculate_cash_flow_stub(),
        calculate_capex(engine, active_property_codes, bedrooms, periods),
        calculate_opex_ratio(engine, active_property_codes, periods),
        calculate_mr(engine, active_property_codes, bedrooms, periods),
        calculate_physical_occupancy(units_df, periods),
        calculate_economic_occupancy(engine, units_df, active_property_codes, periods),
    ]

    log.info("Loading work order exports from %s...", config.WORK_ORDER_DIR)
    try:
        work_orders_df = load_work_orders(config.WORK_ORDER_DIR)
        rows.extend(calculate_work_order_metrics(work_orders_df, active_property_codes, periods))
    except FileNotFoundError as exc:
        log.warning("Skipping work order metrics: %s", exc)

    df = build_summary_table(rows)
    csv_path, xlsx_path = write_reports(df, period, config.REPORT_OUTPUT_DIR)

    print(f"\nReport complete for {period.year}-{period.month:02d}:")
    print(f"  {xlsx_path}")
    print(f"  {csv_path}")


if __name__ == "__main__":
    main()
