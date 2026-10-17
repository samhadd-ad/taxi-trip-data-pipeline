"""
Generate a messy raw export of taxi & limousine trips (synthetic).

Real dispatch exports are rarely clean, so this file deliberately includes the
problems a data engineer meets in practice:
  - duplicate rows                 - fares stored as text ("$45.00")
  - negative / zero fares          - zone names with inconsistent spelling and spaces
  - missing pickup zones           - mixed date formats
  - drop-off before pick-up        - impossible distances

Run:  python data/generate_raw.py
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(11)
OUT = Path(__file__).parent / "raw_trips.csv"
N_TRIPS = 20000

ZONES = {  # zone: (weight, typical km to downtown)
    "Pearson Airport": (30, 27), "Downtown Toronto": (22, 3), "Mississauga": (14, 25),
    "North York": (9, 15), "Union Station": (10, 1), "Square One": (6, 26),
    "Etobicoke": (5, 16), "Brampton": (4, 35),
}
VEHICLES = [("Sedan", 0.70, 1.0), ("SUV", 0.22, 1.35), ("Limousine", 0.08, 2.4)]
PAYMENTS = ["Card", "Card", "Card", "App", "App", "Cash", "Corporate Account"]


def messy_zone(z: str) -> str:
    r = random.random()
    if r < 0.05:
        return z.lower()
    if r < 0.09:
        return f"  {z} "
    if r < 0.11 and z == "Pearson Airport":
        return random.choice(["YYZ", "Pearson Intl Airport"])
    return z


def fmt_time(t: datetime) -> str:
    return t.strftime("%d/%m/%Y %H:%M") if random.random() < 0.08 else t.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    zones, weights = list(ZONES), [v[0] for v in ZONES.values()]
    start = datetime(2026, 7, 1)
    rows = []
    for i in range(1, N_TRIPS + 1):
        pz = random.choices(zones, weights)[0]
        dz = random.choices([z for z in zones if z != pz], [ZONES[z][0] for z in zones if z != pz])[0]
        vtype, _, mult = random.choices(VEHICLES, [v[1] for v in VEHICLES])[0]
        day = start + timedelta(days=random.randrange(92))
        # demand peaks in the morning and early evening
        hour = random.choices(range(24), [1, 1, 1, 1, 3, 6, 9, 10, 8, 6, 5, 5, 5, 5, 6, 7, 9, 10, 8, 6, 5, 4, 3, 2])[0]
        scheduled = day.replace(hour=hour, minute=random.randrange(0, 60, 5))
        booked = scheduled - timedelta(minutes=random.choice([10, 20, 45, 90, 180, 720, 1440, 2880]))
        dist = round(abs(ZONES[pz][1] - ZONES[dz][1]) + random.uniform(3, 9), 1)
        delay = max(-5, int(random.gauss(4 if pz == "Pearson Airport" else 2, 7)))
        actual = scheduled + timedelta(minutes=delay)
        duration = int(dist * random.uniform(1.4, 2.4)) + 5
        dropoff = actual + timedelta(minutes=duration)
        fare = round((4.5 + dist * 2.1) * mult * random.uniform(0.95, 1.08), 2)
        status = random.choices(["completed", "cancelled", "no_show"], [0.9, 0.07, 0.03])[0]

        row = {
            "trip_id": f"T{i:06d}", "booking_time": fmt_time(booked), "scheduled_pickup": fmt_time(scheduled),
            "actual_pickup": fmt_time(actual) if status == "completed" else "",
            "dropoff_time": fmt_time(dropoff) if status == "completed" else "",
            "pickup_zone": messy_zone(pz), "dropoff_zone": messy_zone(dz), "vehicle_type": vtype,
            "distance_km": dist if status == "completed" else "",
            "fare": (f"${fare:.2f}" if random.random() < 0.1 else fare) if status == "completed" else 0,
            "tip": round(fare * random.choice([0, 0, 0.1, 0.15, 0.2]), 2) if status == "completed" else 0,
            "payment_type": random.choice(PAYMENTS), "status": status,
            "driver_id": f"D{random.randint(1, 85):03d}",
            "rating": random.choices([5, 4, 3, 2, 1], [55, 28, 9, 5, 3])[0] if status == "completed" else "",
        }
        # ---- inject data-quality problems ----
        r = random.random()
        if status == "completed":
            if r < 0.006:
                row["fare"] = -abs(fare)                   # negative fare
            elif r < 0.010:
                row["distance_km"] = random.choice([0, 950, 1200])  # impossible distance
            elif r < 0.014:
                row["dropoff_time"] = fmt_time(actual - timedelta(minutes=20))  # drop-off before pick-up
        if random.random() < 0.01:
            row["pickup_zone"] = ""                        # missing zone
        rows.append(row)
        if random.random() < 0.02:
            rows.append(dict(row))                         # duplicate export row

    random.shuffle(rows)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows):,} raw rows to {OUT}")


if __name__ == "__main__":
    main()
