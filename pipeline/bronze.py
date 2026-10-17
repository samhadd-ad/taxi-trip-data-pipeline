"""
BRONZE: land the raw data exactly as received.

Nothing is fixed here. Keeping an untouched copy means we can always re-run the
cleaning, audit what changed, and prove where a number came from.
"""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pandas as pd


def load_bronze(raw_csv: Path, con: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_csv(raw_csv, dtype=str, keep_default_na=False)  # everything as text, as received
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    df["_source_file"] = raw_csv.name
    df.to_sql("bronze_trips", con, if_exists="replace", index=False)
    return df
