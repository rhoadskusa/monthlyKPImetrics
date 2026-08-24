"""
Metric formulas: pull GL/budget/unit/occupancy data for the needed date
ranges, apply the $/bedroom normalization, and assemble each metric's
comparison row (Actual, Budget, Variance, Last Month, YTD, Same Period LY).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy.engine import Engine

import config
import queries
import work_orders as wo

log = logging.getLogger(__name__)

NA = "N/A"
PENDING = "Pending"


@dataclass
class Periods:
    """Date ranges derived from the target report month."""

    current_start: date
    current_end: date
    last_month_start: date
    last_month_end: date
    same_ly_start: date
    same_ly_end: date
    ytd_start: date
    ytd_end: date

    @classmethod
    def from_period(cls, period: date) -> "Periods":
        current_start = period.replace(day=1)
        current_end = current_start + relativedelta(months=1)
        last_month_start = current_start - relativedelta(months=1)
        last_month_end = current_start
        same_ly_start = current_start - relativedelta(years=1)
        same_ly_end = current_end - relativedelta(years=1)
        ytd_start = current_start.replace(month=1)
        ytd_end = current_end
        return cls(
            current_start, current_end,
            last_month_start, last_month_end,
            same_ly_start, same_ly_end,
            ytd_start, ytd_end,
        )

    def eom(self, which: str) -> date:
        """End-of-month date for 'current', 'last_month', or 'same_ly'."""
        start_end_map = {
            "current": self.current_end,
            "last_month": self.last_month_end,
            "same_ly": self.same_ly_end,
        }
        return start_end_map[which] - timedelta(days=1)


def _gl_total(
    engine: Engine,
    acct_ids: list[int],
    start: date,
    end: date,
    property_codes: set[str],
    credit: bool = False,
) -> float:
    df = queries.trial_bal_property_totals(engine, acct_ids, start, end, sorted(property_codes), credit=credit)
    return float(df["total"].sum()) if not df.empty else 0.0


def _budget_total(engine: Engine, acct_ids: list[int], period_start: date, property_codes: set[str]) -> float:
    df = queries.budget_by_property(engine, acct_ids, period_start, sorted(property_codes))
    return float(df["total"].sum()) if not df.empty else 0.0


def total_bedrooms(units_df: pd.DataFrame) -> float:
    return float(units_df["unit_bedrooms"].fillna(0).sum())


def _per_bedroom(amount: float, bedrooms: float) -> float | str:
    if not bedrooms:
        return NA
    return round(amount / bedrooms, 2)


def _variance(actual, budget):
    if actual in (None, NA) or budget in (None, NA):
        return NA
    return round(actual - budget, 2)


def _financial_metric_row(
    engine: Engine,
    label: str,
    acct_ids: list[int],
    property_codes: set[str],
    bedrooms: float,
    periods: Periods,
    credit: bool = False,
    include_budget: bool = True,
    per_bedroom: bool = True,
) -> dict:
    actual_raw = _gl_total(engine, acct_ids, periods.current_start, periods.current_end, property_codes, credit)
    last_month_raw = _gl_total(engine, acct_ids, periods.last_month_start, periods.last_month_end, property_codes, credit)
    same_ly_raw = _gl_total(engine, acct_ids, periods.same_ly_start, periods.same_ly_end, property_codes, credit)
    ytd_raw = _gl_total(engine, acct_ids, periods.ytd_start, periods.ytd_end, property_codes, credit)

    if per_bedroom:
        actual = _per_bedroom(actual_raw, bedrooms)
        last_month = _per_bedroom(last_month_raw, bedrooms)
        same_ly = _per_bedroom(same_ly_raw, bedrooms)
        ytd = _per_bedroom(ytd_raw, bedrooms)
    else:
        actual, last_month, same_ly, ytd = actual_raw, last_month_raw, same_ly_raw, ytd_raw

    if include_budget:
        budget_raw = _budget_total(engine, acct_ids, periods.current_start, property_codes)
        budget = _per_bedroom(budget_raw, bedrooms) if per_bedroom else budget_raw
    else:
        budget = NA

    return {
        "Metric": label,
        "Actual": actual,
        "Budget": budget,
        "Variance": _variance(actual, budget),
        "Last Month": last_month,
        "YTD": ytd,
        "Same Period LY": same_ly,
    }


def calculate_noi(engine: Engine, property_codes: set[str], bedrooms: float, periods: Periods) -> dict:
    def noi_total(start, end):
        revenue = _gl_total(engine, config.TOTAL_REVENUE_ACCOUNTS, start, end, property_codes, credit=True)
        opex = _gl_total(engine, config.TOTAL_OPERATING_EXPENSE_ACCOUNTS, start, end, property_codes, credit=False)
        return revenue - opex

    actual_raw = noi_total(periods.current_start, periods.current_end)
    last_month_raw = noi_total(periods.last_month_start, periods.last_month_end)
    same_ly_raw = noi_total(periods.same_ly_start, periods.same_ly_end)
    ytd_raw = noi_total(periods.ytd_start, periods.ytd_end)

    revenue_budget = _budget_total(engine, config.TOTAL_REVENUE_ACCOUNTS, periods.current_start, property_codes)
    opex_budget = _budget_total(engine, config.TOTAL_OPERATING_EXPENSE_ACCOUNTS, periods.current_start, property_codes)
    budget_raw = revenue_budget - opex_budget

    actual = _per_bedroom(actual_raw, bedrooms)
    budget = _per_bedroom(budget_raw, bedrooms)
    return {
        "Metric": "NOI $/BR",
        "Actual": actual,
        "Budget": budget,
        "Variance": _variance(actual, budget),
        "Last Month": _per_bedroom(last_month_raw, bedrooms),
        "YTD": _per_bedroom(ytd_raw, bedrooms),
        "Same Period LY": _per_bedroom(same_ly_raw, bedrooms),
    }


def calculate_capex(engine: Engine, property_codes: set[str], bedrooms: float, periods: Periods) -> dict:
    return _financial_metric_row(engine, "CapEx $/BR", config.CAPEX_ACCOUNTS, property_codes, bedrooms, periods, credit=False)


def calculate_mr(engine: Engine, property_codes: set[str], bedrooms: float, periods: Periods) -> dict:
    return _financial_metric_row(engine, "M&R $/BR", config.MR_ACCOUNTS, property_codes, bedrooms, periods, credit=False)


def calculate_opex_ratio(engine: Engine, property_codes: set[str], periods: Periods) -> dict:
    def ratio(start, end):
        revenue = _gl_total(engine, config.TOTAL_REVENUE_ACCOUNTS, start, end, property_codes, credit=True)
        opex = _gl_total(engine, config.TOTAL_OPERATING_EXPENSE_ACCOUNTS, start, end, property_codes, credit=False)
        return round((opex / revenue) * 100, 2) if revenue else NA

    revenue_budget = _budget_total(engine, config.TOTAL_REVENUE_ACCOUNTS, periods.current_start, property_codes)
    opex_budget = _budget_total(engine, config.TOTAL_OPERATING_EXPENSE_ACCOUNTS, periods.current_start, property_codes)
    budget = round((opex_budget / revenue_budget) * 100, 2) if revenue_budget else NA

    actual = ratio(periods.current_start, periods.current_end)
    return {
        "Metric": "OpEx %",
        "Actual": actual,
        "Budget": budget,
        "Variance": _variance(actual, budget),
        "Last Month": ratio(periods.last_month_start, periods.last_month_end),
        "YTD": ratio(periods.ytd_start, periods.ytd_end),
        "Same Period LY": ratio(periods.same_ly_start, periods.same_ly_end),
    }


def nearest_availability_snapshot(
    engine: Engine,
    target_eom: date,
    property_codes: set[str],
    tolerance_days: int = config.UNIT_AVAILABILITY_DATE_TOLERANCE_DAYS,
) -> pd.DataFrame:
    """Find each property's PM_UnitAvailability row closest to target_eom.

    PM_UnitAvailability should have one entry per property per end-of-month
    date, but entries can land a few days off the true EOM. Pulls a window
    around the target date and picks the closest as_of_date per property;
    logs a warning for any requested property with no row in the window.
    """
    window_start = target_eom - timedelta(days=tolerance_days)
    window_end = target_eom + timedelta(days=tolerance_days)
    df = queries.unit_availability_window(engine, window_start, window_end, sorted(property_codes))

    if df.empty:
        log.warning(
            "No PM_UnitAvailability rows found within %d days of %s for %d propert(y/ies)",
            tolerance_days, target_eom, len(property_codes),
        )
        return df

    df["_diff_days"] = (pd.to_datetime(df["as_of_date"]) - pd.Timestamp(target_eom)).abs()
    nearest = df.sort_values("_diff_days").drop_duplicates(subset="property_code", keep="first")

    missing = property_codes - set(nearest["property_code"])
    if missing:
        log.warning(
            "No PM_UnitAvailability entry within %d days of %s for properties: %s",
            tolerance_days, target_eom, ", ".join(sorted(missing)),
        )

    return nearest.drop(columns="_diff_days")


def _weighted_occupancy_pct(snapshot: pd.DataFrame) -> float | str:
    if snapshot.empty:
        return NA
    total_units = snapshot["pua_units"].fillna(0).sum()
    if not total_units:
        return NA
    weighted = (snapshot["pua_pctocc"].fillna(0) * snapshot["pua_units"].fillna(0)).sum() / total_units
    return round(weighted, 2)


def calculate_physical_occupancy(engine: Engine, property_codes: set[str], periods: Periods) -> dict:
    """Portfolio physical occupancy = unit-weighted average of pua_pctocc
    across properties, using the PM_UnitAvailability snapshot nearest each
    period's end-of-month date. Budget/YTD are N/A (no budgeted occupancy
    source and occupancy isn't a summable YTD figure)."""
    actual_snapshot = nearest_availability_snapshot(engine, periods.eom("current"), property_codes)
    last_month_snapshot = nearest_availability_snapshot(engine, periods.eom("last_month"), property_codes)
    same_ly_snapshot = nearest_availability_snapshot(engine, periods.eom("same_ly"), property_codes)

    return {
        "Metric": "Physical Occupancy %",
        "Actual": _weighted_occupancy_pct(actual_snapshot),
        "Budget": NA,
        "Variance": NA,
        "Last Month": _weighted_occupancy_pct(last_month_snapshot),
        "YTD": NA,
        "Same Period LY": _weighted_occupancy_pct(same_ly_snapshot),
    }


def calculate_economic_occupancy(engine: Engine, property_codes: set[str], periods: Periods) -> dict:
    """Economic Occupancy = EconIncome / Gross Potential Rent, where
    EconIncome sums Gross Potential Rent, Vacancy Loss, Gain/Loss to Lease,
    Recurring Concessions, Resident Concessions, and Model Units -- ported
    from the user's Power Query M code against uvwGL_PMTrialBals. All of
    these accounts are credit-normal, so activity is negated before summing.
    """
    def econ_pct(start, end):
        df = queries.trial_bal_account_totals(engine, config.ECONOMIC_OCCUPANCY_ACCOUNTS, start, end, sorted(property_codes))
        if df.empty:
            return NA
        totals = df.set_index("acct_id")["total"] * -1
        econ_income = totals.sum()
        gpr = totals.get(config.GROSS_POTENTIAL_RENT_ACCOUNT, 0)
        if not gpr:
            return NA
        return round((econ_income / gpr) * 100, 2)

    return {
        "Metric": "Economic Occupancy %",
        "Actual": econ_pct(periods.current_start, periods.current_end),
        "Budget": NA,
        "Variance": NA,
        "Last Month": econ_pct(periods.last_month_start, periods.last_month_end),
        "YTD": NA,
        "Same Period LY": econ_pct(periods.same_ly_start, periods.same_ly_end),
    }


def calculate_cash_flow_stub() -> dict:
    """Cash Flow (NOI - CapEx - Debt Service) is paused -- the user is still
    finalizing the debt-service treatment. Row is included so the report
    doesn't silently drop it, but every value is explicitly "Pending"."""
    return {
        "Metric": "Cash Flow $/BR",
        "Actual": PENDING, "Budget": PENDING, "Variance": PENDING,
        "Last Month": PENDING, "YTD": PENDING, "Same Period LY": PENDING,
    }


def calculate_work_order_metrics(work_orders_df: pd.DataFrame, property_codes: set[str], periods: Periods) -> list[dict]:
    def row(label, fn):
        return {
            "Metric": label,
            "Actual": fn(periods.current_start, periods.current_end),
            "Budget": NA,
            "Variance": NA,
            "Last Month": fn(periods.last_month_start, periods.last_month_end),
            "YTD": fn(periods.ytd_start, periods.ytd_end),
            "Same Period LY": NA,
        }

    def total(start, end):
        return wo.total_tickets(work_orders_df, start, end, property_codes)

    def closed(start, end):
        return wo.closed_tickets(work_orders_df, start, end, property_codes)

    def avg_days(start, end):
        result = wo.avg_days_to_close(work_orders_df, start, end, property_codes)
        return result if result is not None else NA

    return [
        row("Total Tickets", total),
        row("Closed Tickets", closed),
        row("Avg Days to Close", avg_days),
    ]
