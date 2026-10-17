"""
KPI dashboard on top of the Gold tables.

Run:  streamlit run dashboard.py   (after python run_pipeline.py)
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB = Path(__file__).parent / "warehouse" / "trips.db"
st.set_page_config(page_title="Taxi Trip KPIs", page_icon="🚕", layout="wide")


@st.cache_data
def read(table: str) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql(f"SELECT * FROM {table}", con)


if not DB.exists():
    st.error("No warehouse found. Run `python data/generate_raw.py` then `python run_pipeline.py`.")
    st.stop()

st.title("🚕 Taxi & Limousine Operations Dashboard")
st.caption("Built from the Gold layer of the Bronze → Silver → Gold pipeline (synthetic data, Jul–Sep 2026).")

daily = read("gold_daily_kpis")
daily["trip_date"] = pd.to_datetime(daily["trip_date"])
picked = st.sidebar.date_input("Date range", (daily["trip_date"].min(), daily["trip_date"].max()))
start, end = (picked[0], picked[-1]) if isinstance(picked, (list, tuple)) and picked else (picked, picked)
d = daily[(daily["trip_date"] >= pd.Timestamp(start)) & (daily["trip_date"] <= pd.Timestamp(end))]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Completed trips", f"{int(d['completed_trips'].sum()):,}")
c2.metric("Revenue", f"${d['revenue'].sum():,.0f}")
c3.metric("On-time pickups", f"{d['on_time_rate'].mean():.1%}")
c4.metric("Cancellation rate", f"{d['cancellation_rate'].mean():.1%}")
c5.metric("Avg rating", f"{d['avg_rating'].mean():.2f} ★")

st.subheader("Daily revenue")
st.line_chart(d.set_index("trip_date")["revenue"])

left, right = st.columns(2)
with left:
    st.subheader("Bookings by hour of day")
    st.bar_chart(read("gold_hourly_demand").set_index("hour")["bookings"])
with right:
    st.subheader("On-time rate by pickup zone")
    zones = read("gold_zone_performance")
    st.bar_chart(zones.set_index("pickup_zone")["on_time_rate"].sort_values())

st.subheader("Zone performance")
st.dataframe(read("gold_zone_performance"), width="stretch", hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader("Top routes")
    st.dataframe(read("gold_top_routes"), width="stretch", hide_index=True)
with right:
    st.subheader("Vehicle mix")
    st.dataframe(read("gold_vehicle_summary"), width="stretch", hide_index=True)
