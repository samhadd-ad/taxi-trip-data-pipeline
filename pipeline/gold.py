"""
GOLD: business-ready KPI tables that a dashboard or Power BI can read directly.
"""

import sqlite3

import pandas as pd


def build_gold(silver: pd.DataFrame, con: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    s = silver.copy()
    s["is_completed"] = (s["status"] == "completed").astype(int)
    s["is_cancelled"] = (s["status"] == "cancelled").astype(int)
    s["is_no_show"] = (s["status"] == "no_show").astype(int)
    done = s[s["is_completed"] == 1]

    tables = {}

    # Daily performance
    daily = s.groupby("trip_date").agg(
        bookings=("trip_id", "count"),
        completed_trips=("is_completed", "sum"),
        cancellation_rate=("is_cancelled", "mean"),
        no_show_rate=("is_no_show", "mean"),
    )
    daily = daily.join(done.groupby("trip_date").agg(
        revenue=("revenue", "sum"), avg_fare=("fare", "mean"),
        on_time_rate=("on_time", "mean"), avg_rating=("rating", "mean")))
    tables["gold_daily_kpis"] = daily.reset_index().round(3)

    # Demand by hour of day
    tables["gold_hourly_demand"] = (s.groupby("hour").agg(bookings=("trip_id", "count"))
                                    .reset_index())

    # Performance by pickup zone
    tables["gold_zone_performance"] = (done.groupby("pickup_zone").agg(
        trips=("trip_id", "count"), revenue=("revenue", "sum"),
        avg_delay_min=("pickup_delay_min", "mean"), on_time_rate=("on_time", "mean"))
        .sort_values("revenue", ascending=False).reset_index().round(2))

    # Top routes
    tables["gold_top_routes"] = (done.groupby(["pickup_zone", "dropoff_zone"]).agg(
        trips=("trip_id", "count"), avg_fare=("fare", "mean"), avg_km=("distance_km", "mean"))
        .sort_values("trips", ascending=False).head(15).reset_index().round(2))

    # Vehicle mix
    tables["gold_vehicle_summary"] = (done.groupby("vehicle_type").agg(
        trips=("trip_id", "count"), revenue=("revenue", "sum"), avg_fare=("fare", "mean"),
        avg_rating=("rating", "mean")).sort_values("revenue", ascending=False).reset_index().round(2))

    # Driver performance (min. 50 trips so averages are meaningful)
    drivers = done.groupby("driver_id").agg(
        trips=("trip_id", "count"), avg_rating=("rating", "mean"),
        on_time_rate=("on_time", "mean"), revenue=("revenue", "sum"))
    tables["gold_driver_performance"] = (drivers[drivers["trips"] >= 50]
                                         .sort_values("avg_rating", ascending=False).reset_index().round(3))

    for name, table in tables.items():
        table.to_sql(name, con, if_exists="replace", index=False)
    return tables
