# Monthly KPI Metrics Report — ParentCO Multifamily

Generates a monthly portfolio KPI summary for ParentCO Multifamily properties, pulling financial data from the Yardi-backed SQL Server database, active-property scoping from AirTable, and maintenance ticket data from Yardi Work Order Directory exports. Outputs an Excel and CSV report with Actual, Budget, Variance, Last Month, YTD, and Same Period Last Year columns per metric.

## KPIs Reported

| Metric | Description |
|---|---|
| NOI $/BR | Net Operating Income per bedroom (Revenue − OpEx) |
| CapEx $/BR | Capital expenditures per bedroom |
| OpEx % | Operating expenses as a % of revenue |
| M&R $/BR | Maintenance & repairs spend per bedroom |
| Physical Occupancy % | Unit-weighted occupancy from the nearest availability snapshot to month-end |
| Economic Occupancy % | Economic income ÷ Gross Potential Rent |
| Cash Flow $/BR | Not yet implemented — reports as "Pending" |
| Total Tickets / Closed Tickets / Avg Days to Close | Work order volume and turnaround |

## Data Sources

- **Azure SQL Server** (Yardi Voyager–backed): `uvwGL_PMTrialBals` (GL activity), `PM_Budgets` (budget), `PM_Units` (unit inventory), `PM_UnitAvailability` (occupancy snapshots)
- **AirTable** "Properties" table: determines the active property portfolio (`PropStatus`, `Yardi Code`)
- **Yardi Work Order Directory** exports (`.xlsx`, synced locally via OneDrive/SharePoint): ticket volume and close times

See `queries.py` for the SQL against each table and `config.py` for the GL account groupings (Chart of Accounts) that map to each KPI.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to a `.env` file kept **outside** this cloned repo folder (e.g. Documents or OneDrive), and fill in real SQL Server, AirTable, and Work Order folder values. Never commit a real `.env` or paste its contents anywhere.
3. By default, every run opens a file picker asking you to select that `.env` file. To pick it once and have future runs reuse that choice automatically, set `REMEMBER_ENV_FILE = 1` in `main.py` — the choice is then saved to `.env_location` (gitignored).

## Usage

```
python main.py                  # reports on the previous calendar month
python main.py --period 2026-07 # reports on a specific month (YYYY-MM)
```

## Output

```
output/<year>_<month>_metrics_report.xlsx
output/<year>_<month>_metrics_report.csv
```
(or wherever `REPORT_OUTPUT_DIR` in `.env` points)

## Project Structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — orchestrates the pull, calculation, and report write |
| `config.py` | Env/config loading, GL account groupings (Chart of Accounts) |
| `data_loader.py` | Azure SQL Server connection |
| `queries.py` | Parameterized SQL against Yardi/ParentCO tables |
| `calculations.py` | KPI formulas |
| `airtable_extractor.py` | AirTable REST API pull (active property list) |
| `work_orders.py` / `convert_work_orders.py` | Work order Excel export parsing, dedup, and parquet caching |
| `report_generator.py` | Builds and writes the final CSV/XLSX report |
| `tests/` | Unit tests |

## Known Gaps

- **Cash Flow $/BR** is stubbed out (`calculate_cash_flow_stub`) — debt-service treatment hasn't been decided yet.
- **AirTable field names** in `airtable_extractor.py` are flagged in-code as unconfirmed against the live base.
