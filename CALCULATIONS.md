# Calculations Cheat Sheet

Reference for every metric produced by the Monthly KPI Metrics Report
(`main.py`), sourced from ParentCO Multifamily's Yardi-backed database
(`uvwGL_PMTrialBals`, `PM_Budgets`, `PM_Units`, `PM_UnitAvailability`) plus
Yardi Work Order Directory exports. All formulas live in `calculations.py`
unless noted otherwise; GL account groupings live in `config.py`.

## Report columns

Every metric row has up to six columns, built from the `Periods` dataclass
(`calculations.py:27-64`), derived from the target report month:

| Column | Meaning |
|---|---|
| Actual | Current report month |
| Budget | `PM_Budgets` for the current report month (where a budget source exists) |
| Variance | `Actual − Budget` (`_variance`, `calculations.py:94-97`) |
| Last Month | The calendar month before the report month |
| YTD | Jan 1 of the report year through the end of the report month |
| Same Period LY | Same calendar month, one year earlier |

Columns that don't apply to a metric (e.g. no budget source, or a
percentage that can't be summed YTD) are `N/A`.

## Metrics

### NOI $/BR — Net Operating Income per Bedroom
`(Total Revenue − Total OperatingExpense) / Total Bedrooms`

- `calculations.py:141-166` (`calculate_noi`)
- Revenue = `config.TOTAL_REVENUE_ACCOUNTS` (`config.py:156-168`), pulled with `credit=True` (negated, since these are credit-normal accounts).
- OperatingExpense = `config.TOTAL_OPERATING_EXPENSE_ACCOUNTS` (`config.py:205-218`), pulled with `credit=False`.
- Budget computed the same way from `PM_Budgets`.

### Cash Flow $/BR — **Pending / not implemented**
`NOI − CapEx − Debt Service`

- `calculations.py:296-304` (`calculate_cash_flow_stub`)
- Stub only: every column explicitly returns `"Pending"`. The debt-service
  treatment is still being finalized, so this row is included in the
  report layout but produces no real values yet.

### CapEx $/BR
`Sum(CapEx accounts) / Total Bedrooms`

- `calculations.py:169-170` (`calculate_capex`), via the generic `_financial_metric_row` (`calculations.py:100-138`)
- Accounts = `config.CAPEX_ACCOUNTS` (`config.py:224-229`), the "TOTAL REPLACEMENTS" group under Non-Operating Expense. Debit-normal (`credit=False`).

### M&R $/BR — Maintenance & Repairs
`Sum(M&R accounts) / Total Bedrooms`

- `calculations.py:173-174` (`calculate_mr`), via `_financial_metric_row`
- Accounts = `config.MR_ACCOUNTS` = `TOTAL_MAINTENANCE_AND_REPAIRS` (`config.py:182-186, 221`). Also rolled into Total Operating Expense, but reported standalone too.

### OpEx %
`(Total OperatingExpense / Total Revenue) × 100`

- `calculations.py:177-196` (`calculate_opex_ratio`)
- Not normalized per bedroom. Budget ratio computed from budgeted revenue/opex totals the same way.

### Physical Occupancy %
Unit-weighted average of `pua_pctocc` across properties:
`Σ(pua_pctocc × pua_units) / Σ(pua_units)`

- `calculations.py:236-264` (`_weighted_occupancy_pct`, `calculate_physical_occupancy`)
- Uses the `PM_UnitAvailability` snapshot nearest each period's end-of-month date (`nearest_availability_snapshot`, `calculations.py:199-233`), within a tolerance of `config.UNIT_AVAILABILITY_DATE_TOLERANCE_DAYS = 5` days (`config.py:249`), since snapshots can land a few days off true EOM.
- `pua_pctocc` is stored 0–100 already, no rescaling needed.
- Budget and YTD are `N/A` — no budgeted occupancy source exists, and occupancy isn't a summable YTD figure.

### Economic Occupancy %
`EconIncome / Gross Potential Rent × 100`, where
`EconIncome = Σ(Gross Potential Rent, Gain/Loss to Lease, Vacancy Loss, Model Units, Resident Concessions, Recurring Concessions)`

- `calculations.py:267-293` (`calculate_economic_occupancy`)
- Accounts = `config.ECONOMIC_OCCUPANCY_ACCOUNTS` (`config.py:238-245`); `GROSS_POTENTIAL_RENT_ACCOUNT = 4011003` (`config.py:237`)
- All accounts are credit-normal and are negated before summing.
- Ported from the user's original Power Query M code.
- Worked example (`tests/test_calculations.py`, ~line 140): GPR = 100,000, EconIncome = 88,500 → 88.5%.
- Budget and YTD are `N/A`.

### Total Tickets
Count of work orders with `Call Date` in the period (optionally filtered to a property set).

- `work_orders.py:178-182` (`total_tickets`), wired via `calculations.py:307-333` (`calculate_work_order_metrics`)
- Budget and Same Period LY are `N/A`.

### Closed Tickets
Count of work orders in the period with `Status == "Work Completed"` and a non-null `Complete Date`.

- `work_orders.py:185-190` (`closed_tickets`)
- Only `"Work Completed"` counts as closed — every other status (Call, Canceled, In Progress, On Hold, Request Reassignment, Scheduled, Vendor Schedule, Web) is either still open or terminated without completed work (`work_orders.py:14-18`).

### Avg Days to Close
`mean(Complete Date − Call Date in days)` over closed tickets in the period.

- `work_orders.py:193-204` (`avg_days_to_close`)
- Rounded to 1 decimal; returns `N/A` if there are no closed tickets in the period.

## Supporting building blocks

Shared helpers reused across the metrics above (all in `calculations.py`):

| Helper | Location | Purpose |
|---|---|---|
| `_gl_total` | `calculations.py:67-76` | Sums trial balance activity for a set of accounts/date range/properties (`queries.trial_bal_property_totals`); `credit=True` negates for credit-normal (revenue) accounts. |
| `_budget_total` | `calculations.py:79-81` | Sums `PM_Budgets` monthly column (`pmb_MTD01..12`) for given accounts/properties for the report month. |
| `total_bedrooms` | `calculations.py:84-85` | `Σ unit_bedrooms` from `PM_Units` (via `queries.unit_inventory`), excluding `unit_excluded=1` units. |
| `_per_bedroom` | `calculations.py:88-91` | `amount / bedrooms`, rounded to 2 decimals; `N/A` if bedrooms is 0. |
| `_variance` | `calculations.py:94-97` | `Actual − Budget`, propagating `N/A`. |
| `_financial_metric_row` | `calculations.py:100-138` | Generic row assembler for simple GL-sum-based $/BR metrics (used by CapEx and M&R; reusable for future similar metrics). |

## GL account groupings

The chart-of-accounts groupings that feed the metrics above live in
`config.py:156-249` (sourced from the ParentCO Chart of Accounts). Key
groupings: `TOTAL_RENTAL_INCOME`, `TOTAL_OTHER_INCOME` →
`TOTAL_REVENUE_ACCOUNTS`; and the operating-expense sub-groups
(`TOTAL_UTILITIES`, `TOTAL_ADVERTISING`, `TOTAL_PAYROLL`,
`TOTAL_MAINTENANCE_AND_REPAIRS`, `TOTAL_UT_COST_TURNOVER_OCCUPIED`,
`TOTAL_GROUNDS_AND_POOL`, `TOTAL_SECURITY`,
`TOTAL_ENVIRONMENTAL_AND_SAFETY`, `TOTAL_MGMT_AND_ADMIN_FEES`,
`TOTAL_RESIDENT_RELATED`, `TOTAL_PROP_MGMT_GENERAL_AND_ADMIN`,
`TOTAL_TAXES_AND_INSURANCE`) → `TOTAL_OPERATING_EXPENSE_ACCOUNTS`.

Account lists are not duplicated here since they live in code and will
drift — treat `config.py` as the source of truth and this file as the
formula/logic reference.
