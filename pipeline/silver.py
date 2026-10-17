"""
SILVER: clean, standardise and validate.

Every row either passes all checks or is moved to `silver_rejected` with the
reason, so no data silently disappears.
"""

import sqlite3

import numpy as np
import pandas as pd

ZONE_FIXES = {
    "yyz": "Pearson Airport",
    "pearson intl airport": "Pearson Airport",
}
VALID_STATUSES = {"completed", "cancelled", "no_show"}
MAX_DISTANCE_KM = 200


def parse_time(s: pd.Series) -> pd.Series:
    """Handle both '2026-07-01 08:30:00' and '01/07/2026 08:30'."""
    iso = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    dmy = pd.to_datetime(s, format="%d/%m/%Y %H:%M", errors="coerce")
    return iso.fillna(dmy)


def clean_zone(s: pd.Series) -> pd.Series:
    s = s.str.strip()
    fixed = s.str.lower().map(ZONE_FIXES)
    s = fixed.fillna(s.str.title())
    return s.replace("", np.nan)


def to_money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.replace("$", "", regex=False).str.strip(), errors="coerce")


def build_silver(bronze: pd.DataFrame, con: sqlite3.Connection) -> tuple[pd.DataFrame, dict]:
    df = bronze.drop(columns=["_ingested_at", "_source_file"]).copy()
    checks = {"raw_rows": len(df)}

    # 1. Duplicates (same trip exported twice)
    before = len(df)
    df = df.drop_duplicates(subset="trip_id", keep="first")
    checks["duplicates_removed"] = before - len(df)

    # 2. Standardise types and text
    for col in ["booking_time", "scheduled_pickup", "actual_pickup", "dropoff_time"]:
        df[col] = parse_time(df[col])
    df["pickup_zone"] = clean_zone(df["pickup_zone"])
    df["dropoff_zone"] = clean_zone(df["dropoff_zone"])
    df["fare"] = to_money(df["fare"])
    df["tip"] = to_money(df["tip"])
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["status"] = df["status"].str.strip().str.lower()

    # 3. Validation rules: (reason, rows that break it)
    done = df["status"] == "completed"
    rules = [
        ("missing pickup zone", df["pickup_zone"].isna()),
        ("invalid status", ~df["status"].isin(VALID_STATUSES)),
        ("unreadable scheduled time", df["scheduled_pickup"].isna()),
        ("non-positive fare", done & ~(df["fare"] > 0)),
        ("impossible distance", done & ~df["distance_km"].between(0.5, MAX_DISTANCE_KM)),
        ("drop-off before pick-up", done & (df["dropoff_time"] <= df["actual_pickup"])),
    ]
    reason = pd.Series("", index=df.index)
    for name, bad in rules:
        reason = reason.mask(bad & (reason == ""), name)
        checks[f"rejected: {name}"] = int((bad & (reason == name)).sum())

    rejected = df[reason != ""].assign(reject_reason=reason[reason != ""])
    clean = df[reason == ""].copy()

    # 4. Derived columns used by the KPIs
    clean["pickup_delay_min"] = (clean["actual_pickup"] - clean["scheduled_pickup"]).dt.total_seconds() / 60
    clean["on_time"] = np.where(clean["status"] == "completed", clean["pickup_delay_min"] <= 5, np.nan)
    clean["trip_minutes"] = (clean["dropoff_time"] - clean["actual_pickup"]).dt.total_seconds() / 60
    clean["revenue"] = clean["fare"].fillna(0) + clean["tip"].fillna(0)
    clean["trip_date"] = clean["scheduled_pickup"].dt.date.astype(str)
    clean["hour"] = clean["scheduled_pickup"].dt.hour

    checks["clean_rows"] = len(clean)
    checks["rejected_rows"] = len(rejected)
    clean.to_sql("silver_trips", con, if_exists="replace", index=False)
    rejected.to_sql("silver_rejected", con, if_exists="replace", index=False)
    return clean, checks
