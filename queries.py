"""
Parameterized SQL against the ParentCO Yardi-backed database.

*** OPEN ITEM ***
The exact column names for transaction amount and property code in
uvwGL_PMTrans, and for amount/period/property in PM_Budgets, were not
confirmed at build time (the reference schema doc didn't cover them). The
constants below are best-guess placeholders based on the Yardi/ParentCO
naming convention (gpt_* / pmb_* prefixes) documented for the columns we DO
know. Before running this against the real database:

  1. Run, e.g.:
       SELECT TOP 5 * FROM uvwGL_PMTrans
       SELECT TOP 5 * FROM PM_Budgets WHERE pmb_type = 'BUD'
  2. Fix the *_AMOUNT_COL / *_PROPCODE_COL / *_PERIOD_COL constants below to
     match the real column names.

All queries filter on gpt_fdate + gpt_acctid (or the budget equivalents)
first, per the parentco-reference guidance, since uvwGL_PMTrans has ~11.9M
rows.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy.engine import Engine

from data_loader import run_query

# --- uvwGL_PMTrans (GL transactions) ---
GLTRANS_TABLE = "uvwGL_PMTrans"
GLTRANS_DATE_COL = "gpt_fdate"
GLTRANS_ACCTID_COL = "gpt_acctid"
GLTRANS_AMOUNT_COL = "gpt_amount"  # TODO: confirm real column name
GLTRANS_PROPCODE_COL = "gpt_propertycode"  # TODO: confirm real column name

# --- PM_Budgets ---
BUDGET_TABLE = "PM_Budgets"
BUDGET_TYPE_COL = "pmb_type"
BUDGET_ACCTID_COL = "pmb_acctid"  # TODO: confirm (acct_id integer form of pmb_acctnum)
BUDGET_AMOUNT_COL = "pmb_amount"  # TODO: confirm real column name
BUDGET_DATE_COL = "pmb_fdate"  # TODO: confirm real column name
BUDGET_PROPCODE_COL = "pmb_propertycode"  # TODO: confirm real column name

# --- PM_Units ---
UNITS_TABLE = "PM_Units"


def gl_actuals_by_property(
    engine: Engine,
    acct_ids: list[int],
    start_date: date,
    end_date: date,
    property_codes: list[str] | None = None,
) -> pd.DataFrame:
    """Sum GL transaction amounts for the given accounts and date range.

    Returns one row per property code (TRIMmed) with a `total` column, so
    portfolio scoping (AirTable active-property list) can be applied in
    Python after the fact.
    """
    acct_placeholders = ", ".join(f":acct{i}" for i in range(len(acct_ids)))
    params = {f"acct{i}": acct_id for i, acct_id in enumerate(acct_ids)}
    params["start_date"] = start_date
    params["end_date"] = end_date

    property_filter = ""
    if property_codes:
        prop_placeholders = ", ".join(f":prop{i}" for i in range(len(property_codes)))
        params.update({f"prop{i}": code for i, code in enumerate(property_codes)})
        property_filter = f"AND TRIM({GLTRANS_PROPCODE_COL}) IN ({prop_placeholders})"

    sql = f"""
        SELECT
            TRIM({GLTRANS_PROPCODE_COL}) AS property_code,
            SUM({GLTRANS_AMOUNT_COL}) AS total
        FROM {GLTRANS_TABLE}
        WHERE {GLTRANS_DATE_COL} >= :start_date
          AND {GLTRANS_DATE_COL} < :end_date
          AND {GLTRANS_ACCTID_COL} IN ({acct_placeholders})
          {property_filter}
        GROUP BY TRIM({GLTRANS_PROPCODE_COL})
    """
    return run_query(engine, sql, params)


def budget_by_property(
    engine: Engine,
    acct_ids: list[int],
    period_start: date,
    property_codes: list[str] | None = None,
) -> pd.DataFrame:
    """Sum budgeted amounts for the given accounts and month."""
    acct_placeholders = ", ".join(f":acct{i}" for i in range(len(acct_ids)))
    params = {f"acct{i}": acct_id for i, acct_id in enumerate(acct_ids)}
    params["period_start"] = period_start

    property_filter = ""
    if property_codes:
        prop_placeholders = ", ".join(f":prop{i}" for i in range(len(property_codes)))
        params.update({f"prop{i}": code for i, code in enumerate(property_codes)})
        property_filter = f"AND TRIM({BUDGET_PROPCODE_COL}) IN ({prop_placeholders})"

    sql = f"""
        SELECT
            TRIM({BUDGET_PROPCODE_COL}) AS property_code,
            SUM({BUDGET_AMOUNT_COL}) AS total
        FROM {BUDGET_TABLE}
        WHERE {BUDGET_TYPE_COL} = 'BUD'
          AND {BUDGET_DATE_COL} = :period_start
          AND {BUDGET_ACCTID_COL} IN ({acct_placeholders})
          {property_filter}
    """
    return run_query(engine, sql, params)


def unit_inventory(engine: Engine, property_codes: list[str] | None = None) -> pd.DataFrame:
    """Pull unit-level inventory (bedrooms, status, rent, move dates).

    Excludes units flagged unit_excluded = 1. Drops etl_* pipeline columns.
    """
    params: dict = {}
    property_filter = ""
    if property_codes:
        prop_placeholders = ", ".join(f":prop{i}" for i in range(len(property_codes)))
        params.update({f"prop{i}": code for i, code in enumerate(property_codes)})
        property_filter = f"AND TRIM(unit_propcode) IN ({prop_placeholders})"

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
