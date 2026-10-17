"""
Run the full pipeline:  raw CSV → Bronze → Silver → Gold

Run:  python run_pipeline.py
Outputs:
  warehouse/trips.db           SQLite database with every layer
  warehouse/gold/*.csv         gold tables (ready for Power BI / Excel)
  reports/data_quality.md      what was found and fixed
"""

import sqlite3
from pathlib import Path

from pipeline.bronze import load_bronze
from pipeline.gold import build_gold
from pipeline.silver import build_silver

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw_trips.csv"
DB = ROOT / "warehouse" / "trips.db"
GOLD_CSV = ROOT / "warehouse" / "gold"
REPORT = ROOT / "reports" / "data_quality.md"


def write_report(checks: dict, gold: dict) -> None:
    daily = gold["gold_daily_kpis"]
    lines = ["# Data Quality Report", "", "| Check | Rows |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ').capitalize()} | {v:,} |" for k, v in checks.items()]
    kept = checks["clean_rows"] / (checks["raw_rows"] - checks["duplicates_removed"])
    lines += ["", f"**{kept:.1%} of unique trips passed every check.** "
                  "Rejected rows are kept in the `silver_rejected` table with the reason.", "",
              "# Headline KPIs (Jul–Sep 2026, synthetic data)", "",
              f"- Bookings: {int(daily['bookings'].sum()):,}",
              f"- Completed trips: {int(daily['completed_trips'].sum()):,}",
              f"- Revenue (fares + tips): ${daily['revenue'].sum():,.0f}",
              f"- Average on-time pickup rate: {daily['on_time_rate'].mean():.1%}",
              f"- Average cancellation rate: {daily['cancellation_rate'].mean():.1%}",
              f"- Average rating: {daily['avg_rating'].mean():.2f} / 5"]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not RAW.exists():
        raise SystemExit("No raw data. Run:  python data/generate_raw.py")
    DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB) as con:
        bronze = load_bronze(RAW, con)
        print(f"[Bronze] {len(bronze):,} raw rows landed")
        silver, checks = build_silver(bronze, con)
        print(f"[Silver] {checks['clean_rows']:,} clean rows, {checks['duplicates_removed']:,} duplicates removed, "
              f"{checks['rejected_rows']:,} rejected")
        gold = build_gold(silver, con)
        print(f"[Gold]   {len(gold)} KPI tables: {', '.join(gold)}")

    GOLD_CSV.mkdir(parents=True, exist_ok=True)
    for name, table in gold.items():
        table.to_csv(GOLD_CSV / f"{name}.csv", index=False)
    write_report(checks, gold)
    print(f"\nDone. Database: {DB.relative_to(ROOT)} | Report: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
