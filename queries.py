"""
Parameterized SQL against the ParentCO Yardi-backed database.

*** OPEN ITEM ***
PM_Budgets column names for amount/period/property are still unconfirmed --
the constants below (BUDGET_*) are best-guess placeholders. Before relying
on budget figures, run:
    SELECT TOP 5 * FROM PM_Budgets WHERE pmb_type = 'BUD'
and fix BUDGET_AMOUNT_COL / BUDGET_DATE_COL / BUDGET_PROPCODE_COL to match.

Everything else here (uvwGL_PMTrialBals, PM_Units, PM_UnitAvailability) uses
confirmed real column names.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy.engine import Engine

from data_loader import run_query

# --- uvwGL_PMTrialBals (monthly trial balance -- use this, NOT uvwGL_PMTrans,
# which is still being updated/unreliable per the user) ---
TRIALBAL_TABLE = "uvwGL_PMTrialBals"
TRIALBAL_DATE_COL = "pmtb_fdate"
TRIALBAL_ACCTID_COL = "pmtb_acctid"
TRIALBAL_ACTIVITY_COL = "pmtb_activityamt"
TRIALBAL_PROPCODE_COL = "pmtb_propertycode"

# --- PM_Budgets ---
BUDGET_TABLE = "PM_Budgets"
BUDGET_TYPE_COL = "pmb_type"
BUDGET_ACCTID_COL = "pmb_acctid"  # TODO: confirm (acct_id integer form of pmb_acctnum)
BUDGET_AMOUNT_COL = "pmb_amount"  # TODO: confirm real column name
BUDGET_DATE_COL = "pmb_fdate"  # TODO: confirm real column name
BUDGET_PROPCODE_COL = "pmb_propertycode"  # TODO: confirm real column name

# --- PM_Units ---
UNITS_TABLE = "PM_Units"

# --- PM_UnitAvailability (per-property, per-as-of-date occupancy snapshot) ---
AVAILABILITY_TABLE = "PM_UnitAvailability"
AVAILABILITY_PROPCODE_COL = "pua_propcode"
AVAILABILITY_DATE_COL = "pua_asOfDate"


def _placeholders(prefix: str, values: list) -> tuple[str, dict]:
    names = [f"{prefix}{i}" for i in range(len(values))]
    sql = ", ".join(f":{n}" for n in names)
    params = {n: v for n, v in zip(names, values)}
    return sql, params


def trial_bal_property_totals(
    engine: Engine,
    acct_ids: list[int],
    start_date: date,
    end_date: date,
    property_codes: list[str] | None = None,
    credit: bool = False,
) -> pd.DataFrame:
    """Sum trial balance activity for the given accounts and date range.

    Returns one row per (TRIMmed) property code with a `total` column.

    `credit=True` negates the sum -- Yardi stores credit-normal accounts
    (revenue) as negative in pmtb_activityamt, so revenue/income account
    groups need `credit=True` to come out positive. Debit-normal accounts
    (all expense/CapEx groups) should use the default `credit=False`.
    """
    acct_sql, acct_params = _placeholders("acct", acct_ids)
    params = {**acct_params, "start_date": start_date, "end_date": end_date}

    property_filter = ""
    if property_codes:
        prop_sql, prop_params = _placeholders("prop", property_codes)
        params.update(prop_params)
        property_filter = f"AND TRIM({TRIALBAL_PROPCODE_COL}) IN ({prop_sql})"

    sign = "-1 *" if credit else ""
    sql = f"""
        SELECT
            TRIM({TRIALBAL_PROPCODE_COL}) AS property_code,
            SUM({sign} {TRIALBAL_ACTIVITY_COL}) AS total
        FROM {TRIALBAL_TABLE}
        WHERE {TRIALBAL_DATE_COL} >= :start_date
          AND {TRIALBAL_DATE_COL} < :end_date
          AND {TRIALBAL_ACCTID_COL} IN ({acct_sql})
          {property_filter}
        GROUP BY TRIM({TRIALBAL_PROPCODE_COL})
    """
    return run_query(engine, sql, params)


def trial_bal_account_totals(
    engine: Engine,
    acct_ids: list[int],
    start_date: date,
    end_date: date,
    property_codes: list[str] | None = None,
) -> pd.DataFrame:
    """Sum trial balance activity for the given accounts and date range,
    grouped by account instead of property. Returns raw (un-negated)
    totals -- the caller applies the credit/debit sign convention.

    Used for Economic Occupancy, which needs each account's contribution
    broken out (Gross Potential Rent, Vacancy Loss, Concessions, etc.)
    rather than a single combined sum.
    """
    acct_sql, acct_params = _placeholders("acct", acct_ids)
    params = {**acct_params, "start_date": start_date, "end_date": end_date}

    property_filter = ""
    if property_codes:
        prop_sql, prop_params = _placeholders("prop", property_codes)
        params.update(prop_params)
        property_filter = f"AND TRIM({TRIALBAL_PROPCODE_COL}) IN ({prop_sql})"

    sql = f"""
        SELECT
            {TRIALBAL_ACCTID_COL} AS acct_id,
            SUM({TRIALBAL_ACTIVITY_COL}) AS total
        FROM {TRIALBAL_TABLE}
        WHERE {TRIALBAL_DATE_COL} >= :start_date
          AND {TRIALBAL_DATE_COL} < :end_date
          AND {TRIALBAL_ACCTID_COL} IN ({acct_sql})
          {property_filter}
        GROUP BY {TRIALBAL_ACCTID_COL}
    """
    return run_query(engine, sql, params)


def budget_by_property(
    engine: Engine,
    acct_ids: list[int],
    period_start: date,
    property_codes: list[str] | None = None,
) -> pd.DataFrame:
    """Sum budgeted amounts for the given accounts and month."""
    acct_sql, acct_params = _placeholders("acct", acct_ids)
    params = {**acct_params, "period_start": period_start}

    property_filter = ""
    if property_codes:
        prop_sql, prop_params = _placeholders("prop", property_codes)
        params.update(prop_params)
        property_filter = f"AND TRIM({BUDGET_PROPCODE_COL}) IN ({prop_sql})"

    sql = f"""
        SELECT
            TRIM({BUDGET_PROPCODE_COL}) AS property_code,
            SUM({BUDGET_AMOUNT_COL}) AS total
        FROM {BUDGET_TABLE}
        WHERE {BUDGET_TYPE_COL} = 'BUD'
          AND {BUDGET_DATE_COL} = :period_start
          AND {BUDGET_ACCTID_COL} IN ({acct_sql})
          {property_filter}
    """
    return run_query(engine, sql, params)


def unit_inventory(engine: Engine, property_codes: list[str] | None = None) -> pd.DataFrame:
    """Pull unit-level inventory (bedrooms, rent, move dates).

    Excludes units flagged unit_excluded = 1. Drops etl_* pipeline columns.
    """
    params: dict = {}
    property_filter = ""
    if property_codes:
        prop_sql, prop_params = _placeholders("prop", property_codes)
        params.update(prop_params)
        property_filter = f"AND TRIM(unit_propcode) IN ({prop_sql})"

    sql = f"""
        SELECT
            TRIM(unit_propcode) AS property_code,
            unit_code,
            unit_type,
            unit_bedrooms,
            unit_bathrooms,
            unit_rent,
            unit_sqft,
            unit_status,
            unit_rentReady,
            unit_moveindate,
            unit_moveoutdate
        FROM {UNITS_TABLE}
        WHERE (unit_excluded IS NULL OR unit_excluded = 0)
          {property_filter}
    """
    return run_query(engine, sql, params)


def unit_availability_window(
    engine: Engine,
    window_start: date,
    window_end: date,
    property_codes: list[str] | None = None,
) -> pd.DataFrame:
    """Pull all PM_UnitAvailability rows within a date window.

    Used by calculations.nearest_availability_snapshot() to find the
    closest as-of-date to a target end-of-month when the EOM date itself
    isn't present (entries can land +/- a couple of days off EOM).
    """
    params: dict = {"window_start": window_start, "window_end": window_end}
    property_filter = ""
    if property_codes:
        prop_sql, prop_params = _placeholders("prop", property_codes)
        params.update(prop_params)
        property_filter = f"AND TRIM({AVAILABILITY_PROPCODE_COL}) IN ({prop_sql})"

    sql = f"""
        SELECT
            TRIM({AVAILABILITY_PROPCODE_COL}) AS property_code,
            {AVAILABILITY_DATE_COL} AS as_of_date,
            pua_units,
            pua_pctocc,
            pua_avgrent
        FROM {AVAILABILITY_TABLE}
        WHERE {AVAILABILITY_DATE_COL} BETWEEN :window_start AND :window_end
          {property_filter}
    """
    return run_query(engine, sql, params)
