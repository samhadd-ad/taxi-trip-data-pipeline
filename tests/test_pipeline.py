import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.gold import build_gold
from pipeline.silver import build_silver, clean_zone, parse_time, to_money

BASE = {"booking_time": "2026-07-01 07:00:00", "scheduled_pickup": "2026-07-01 08:00:00",
        "actual_pickup": "2026-07-01 08:03:00", "dropoff_time": "2026-07-01 08:40:00",
        "pickup_zone": "Pearson Airport", "dropoff_zone": "Union Station", "vehicle_type": "Sedan",
        "distance_km": "27.5", "fare": "62.10", "tip": "6.00", "payment_type": "Card",
        "status": "completed", "driver_id": "D001", "rating": "5",
        "_ingested_at": "x", "_source_file": "x"}


def bronze(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{**BASE, **r} for r in rows])


def test_parse_time_handles_both_formats():
    out = parse_time(pd.Series(["2026-07-01 08:30:00", "01/07/2026 08:30"]))
    assert out.iloc[0] == out.iloc[1]


def test_zone_names_are_standardised():
    out = clean_zone(pd.Series(["  pearson airport ", "YYZ", "Pearson Intl Airport", "union station"]))
    assert list(out) == ["Pearson Airport", "Pearson Airport", "Pearson Airport", "Union Station"]


def test_money_strings_become_numbers():
    assert list(to_money(pd.Series(["$45.00", "12.5"]))) == [45.0, 12.5]


def test_bad_rows_are_rejected_with_a_reason():
    df = bronze([
        {"trip_id": "T1"},                                   # good
        {"trip_id": "T1"},                                   # duplicate
        {"trip_id": "T2", "fare": "-20"},                    # negative fare
        {"trip_id": "T3", "pickup_zone": ""},                # missing zone
        {"trip_id": "T4", "dropoff_time": "2026-07-01 07:50:00"},  # drop-off before pick-up
        {"trip_id": "T5", "distance_km": "950"},             # impossible distance
        {"trip_id": "T6", "status": "cancelled", "fare": "0", "distance_km": "",
         "actual_pickup": "", "dropoff_time": ""},           # cancelled trips are valid
    ])
    with sqlite3.connect(":memory:") as con:
        clean, checks = build_silver(df, con)
        rejected = pd.read_sql("SELECT trip_id, reject_reason FROM silver_rejected", con)
    assert set(clean["trip_id"]) == {"T1", "T6"}
    assert checks["duplicates_removed"] == 1
    assert dict(zip(rejected.trip_id, rejected.reject_reason)) == {
        "T2": "non-positive fare", "T3": "missing pickup zone",
        "T4": "drop-off before pick-up", "T5": "impossible distance"}


def test_gold_kpis():
    df = bronze([{"trip_id": "T1"}, {"trip_id": "T2", "actual_pickup": "2026-07-01 08:20:00"},
                 {"trip_id": "T3", "status": "cancelled", "fare": "0", "distance_km": "",
                  "actual_pickup": "", "dropoff_time": ""}])
    with sqlite3.connect(":memory:") as con:
        clean, _ = build_silver(df, con)
        gold = build_gold(clean, con)
    day = gold["gold_daily_kpis"].iloc[0]
    assert day["bookings"] == 3 and day["completed_trips"] == 2
    assert round(day["cancellation_rate"], 3) == 0.333
    assert day["on_time_rate"] == 0.5          # 3 min late = on time, 20 min late = not
    assert day["revenue"] == 2 * (62.10 + 6.00)
