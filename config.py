"""
Configuration for the monthly KPI metrics report.

Loads secrets and paths from a ".env" file located next to this script (never
from the current working directory, so the report behaves the same no matter
where it's launched from). See ".env.example" for the full list of required
keys and what they mean.

Nothing in this file should ever print or log a secret value -- only whether
it was found.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")


def _require_env(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        sys.exit(
            f"Missing required setting '{key}'.\n"
            f"Add it to a \".env\" file at {SCRIPT_DIR / '.env'} "
            f"(see .env.example for the full list)."
        )
    return value


def _optional_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# --- SQL Server ---
DB_SERVER = _require_env("DB_SERVER")
DB_NAME = _require_env("DB_NAME")
DB_TRUSTED_CONNECTION = _optional_env("DB_TRUSTED_CONNECTION", "no").lower() in (
    "yes",
    "true",
    "1",
)
DB_USER = "" if DB_TRUSTED_CONNECTION else _require_env("DB_USER")
DB_PASSWORD = "" if DB_TRUSTED_CONNECTION else _require_env("DB_PASSWORD")

# --- AirTable ---
AIRTABLE_API_KEY = _require_env("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = _require_env("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_PROPERTIES = _require_env("AIRTABLE_TABLE_PROPERTIES")

# PropStatus values that count as "active portfolio" for this report.
ACTIVE_PROPSTATUS_VALUES = {
    "Active / Owned & Managed",
    "Active / Owned & 3PM",
}

# --- Yardi work order exports ---
WORK_ORDER_DIR = Path(_require_env("WORK_ORDER_DIR"))

# --- Output ---
_output_dir_setting = _optional_env("REPORT_OUTPUT_DIR")
REPORT_OUTPUT_DIR = Path(_output_dir_setting) if _output_dir_setting else SCRIPT_DIR / "output"

# --- Report period ---
_period_setting = _optional_env("REPORT_PERIOD")
if _period_setting:
    REPORT_PERIOD = date.fromisoformat(f"{_period_setting}-01")
else:
    REPORT_PERIOD = (date.today().replace(day=1) - relativedelta(months=1))


# ---------------------------------------------------------------------------
# GL account groupings (from the ParentCO Chart of Accounts / parentco-reference
# skill). All values are the integer acct_id form -- always filter/join on the
# integer id column (gpt_acctid / pmb_acctnum-after-dash-removal), never the
# dashed text acct_num, to avoid SQL type coercion issues.
# ---------------------------------------------------------------------------

TOTAL_RENTAL_INCOME = [
    4011000, 4011001, 4011002, 4011003, 4012000, 4013000, 4014000, 4015000,
    4016000, 4017000, 4017001, 4018000, 4018004, 4019000, 4020000, 4022000,
    4023000, 4023001,
]

TOTAL_OTHER_INCOME = [
    4101000, 4102000, 4103000, 4104000, 4105000, 4106000, 4107000, 4119000,
    4120000, 4121000, 4123000, 4124000, 4150000, 4150001, 4150002, 4150003,
    4150004, 4150005, 4170000,
]

TOTAL_REVENUE_ACCOUNTS = TOTAL_RENTAL_INCOME + TOTAL_OTHER_INCOME

TOTAL_UTILITIES = [5002000, 5002002, 5003000, 5003002, 5004000, 5005001, 5005002, 5006000, 5009000]
TOTAL_ADVERTISING = [
    5013000, 5013001, 5013002, 5013003, 5013004, 5014000, 5016000, 5016002,
    5016003, 5016004, 5016005, 5017000, 5018000, 5019000, 5020000, 5021000,
    5024000, 5025000,
]
TOTAL_PAYROLL = [
    5101000, 5101001, 5101002, 5101003, 5102000, 5103000, 5104000, 5105000,
    5106000, 5107000, 5107001, 5108000, 5109000, 5110000, 5112000, 5112001,
    5114000, 5114001, 5124000, 5130000, 5140000, 5150000, 5160000, 5160001,
    5160002, 5160003, 5160004,
]
TOTAL_MAINTENANCE_AND_REPAIRS = [
    5201000, 5201001, 5202000, 5202001, 5203000, 5204000, 5204001, 5205000,
    5206000, 5207000, 5208000, 5209000, 5210000, 5211000, 5212000, 5213000,
    5214000, 5298000, 5298002, 5298003, 5298004,
]
TOTAL_UT_COST_TURNOVER_OCCUPIED = [
    5301000, 5302000, 5303000, 5304000, 5305000, 5306000, 5308000, 5309000, 5330000,
]
TOTAL_GROUNDS_AND_POOL = [
    5401000, 5402000, 5403000, 5404000, 5405000, 5406000, 5407000, 5408000, 5409000,
]
TOTAL_SECURITY = [5501000, 5502001, 5502002, 5503000]
TOTAL_ENVIRONMENTAL_AND_SAFETY = [5601000, 5602000, 5603000, 5604000]
TOTAL_MGMT_AND_ADMIN_FEES = [5701000, 5702000, 5703000, 5704000, 5705000]
TOTAL_RESIDENT_RELATED = [5801000, 5802000, 5803000, 5803001, 5803002, 5807000, 5808000]
TOTAL_PROP_MGMT_GENERAL_AND_ADMIN = [
    7001000, 7002000, 7003000, 7004000, 7004001, 7004002, 7004003, 7004004,
    7004005, 7005000, 7006000, 7007000, 7008000, 7009001, 7009002, 7009003,
    7009004, 7010000, 7011000, 7011001, 7011002, 7011003, 7012000, 7013000,
    7014000,
]
TOTAL_TAXES_AND_INSURANCE = [7101000, 7102000, 7103000, 7104000]

TOTAL_OPERATING_EXPENSE_ACCOUNTS = (
    TOTAL_UTILITIES
    + TOTAL_ADVERTISING
    + TOTAL_PAYROLL
    + TOTAL_MAINTENANCE_AND_REPAIRS
    + TOTAL_UT_COST_TURNOVER_OCCUPIED
    + TOTAL_GROUNDS_AND_POOL
    + TOTAL_SECURITY
    + TOTAL_ENVIRONMENTAL_AND_SAFETY
    + TOTAL_MGMT_AND_ADMIN_FEES
    + TOTAL_RESIDENT_RELATED
    + TOTAL_PROP_MGMT_GENERAL_AND_ADMIN
    + TOTAL_TAXES_AND_INSURANCE
)

# M&R is also reported standalone (it's a subset of TOTAL_OPERATING_EXPENSE_ACCOUNTS).
MR_ACCOUNTS = TOTAL_MAINTENANCE_AND_REPAIRS

# CapEx = TOTAL REPLACEMENTS group (under TOTAL NON OPERATION EXPENSE).
CAPEX_ACCOUNTS = [
    8301000, 8302000, 8302001, 8303000, 8304000, 8304001, 8305000, 8306000,
    8307000, 8308000, 8309000, 8310000, 8311000, 8312000, 8313000, 8314000,
    8315000, 8316000, 8316001, 8316002, 8316003, 8316004, 8316005, 8316006,
    8316007, 8316008, 8317000, 8318000, 8319000,
]

# Cash Flow (NOI - CapEx - Debt Service) is intentionally not implemented yet
# -- the user is still finalizing the debt-service treatment. See
# calculations.calculate_cash_flow_stub().

# Economic Occupancy accounts (ported from the user's Power Query M code).
# All are credit-normal (subset of TOTAL_RENTAL_INCOME) -- negate when summing.
GROSS_POTENTIAL_RENT_ACCOUNT = 4011003
ECONOMIC_OCCUPANCY_ACCOUNTS = [
    4011003,  # Gross Potential Rent
    4015000,  # Gain/Loss to Lease
    4016000,  # Vacancy Loss
    4017001,  # Model Units
    4018000,  # Resident Concessions
    4018004,  # Recurring Concessions
]

# Physical occupancy EOM-snapshot lookup tolerance: PM_UnitAvailability
# entries can land a couple of days off the true end-of-month date.
UNIT_AVAILABILITY_DATE_TOLERANCE_DAYS = 5
