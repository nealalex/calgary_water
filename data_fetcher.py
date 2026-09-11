"""
data_fetcher.py
Fetches water quality records from City of Calgary Open Data (SODA API)
and stores them into a local SQLite database.
"""

import sqlite3
import os
from datetime import datetime, timedelta
import requests

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calgary_water.db")

WATERSHED_DATASET = "y8as-bmzj"
SONDE_DATASET = "kc8x-fu3f"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS water_samples (
                id TEXT PRIMARY KEY,
                dataset TEXT,
                sample_site TEXT,
                sample_date TEXT,
                numeric_result REAL,
                parameter TEXT,
                result_units TEXT,
                latitude REAL,
                longitude REAL,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sample_date ON water_samples(sample_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parameter ON water_samples(parameter)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_site ON water_samples(sample_site)
        """)
    conn.close()


def fetch_soda_data(dataset_id, parameter="pH", days=400):
    url = f"https://data.calgary.ca/resource/{dataset_id}.json"
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000")

    params = {
        "$where": f"parameter='{parameter}' AND sample_date > '{start_date}'",
        "$order": "sample_date DESC",
        "$limit": 50000,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        print(f"Error {resp.status_code} fetching from {dataset_id}")
    except Exception as e:
        print(f"Fetch failed for {dataset_id}: {e}")
    return []


def sync_data():
    init_db()
    conn = get_db_connection()
    now_str = datetime.utcnow().isoformat()
    inserted = 0

    # 1. Fetch Watershed dataset (discrete grab samples across reservoirs & rivers)
    watershed_rows = fetch_soda_data(WATERSHED_DATASET, days=400)
    # 2. Fetch Sonde dataset (continuous/discrete sensor monitors)
    sonde_rows = fetch_soda_data(SONDE_DATASET, days=60)

    all_rows = [(r, "watershed") for r in watershed_rows] + [(r, "sonde") for r in sonde_rows]

    with conn:
        for r, ds in all_rows:
            sample_id = str(r.get("id") or f"{ds}_{r.get('sample_site')}_{r.get('sample_date')}")
            site = r.get("sample_site", "Unknown")
            date_str = r.get("sample_date", "")
            try:
                val = float(r.get("numeric_result"))
            except (ValueError, TypeError):
                continue

            param = r.get("parameter", "pH")
            units = r.get("result_units", "pH units")
            lat = float(r.get("latitude_degrees")) if r.get("latitude_degrees") else None
            lon = float(r.get("longitude_degrees")) if r.get("longitude_degrees") else None

            conn.execute("""
                INSERT INTO water_samples (
                    id, dataset, sample_site, sample_date, numeric_result,
                    parameter, result_units, latitude, longitude, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    numeric_result=excluded.numeric_result,
                    sample_date=excluded.sample_date
            """, (sample_id, ds, site, date_str, val, param, units, lat, lon, now_str))
            inserted += 1

    conn.close()
    return inserted


def get_summary_stats():
    init_db()
    conn = get_db_connection()

    count = conn.execute("SELECT COUNT(*) FROM water_samples WHERE parameter='pH'").fetchone()[0]
    if count == 0:
        sync_data()

    # Latest Bearspaw sample
    latest_bearspaw = conn.execute("""
        SELECT sample_site, sample_date, numeric_result, dataset
        FROM water_samples
        WHERE parameter='pH' AND sample_site LIKE '%Bearspaw%'
        ORDER BY sample_date DESC
        LIMIT 1
    """).fetchone()

    # Latest Glenmore sample
    latest_glenmore = conn.execute("""
        SELECT sample_site, sample_date, numeric_result, dataset
        FROM water_samples
        WHERE parameter='pH' AND sample_site LIKE '%Glenmore%'
        ORDER BY sample_date DESC
        LIMIT 1
    """).fetchone()

    # Overall latest sample
    latest_overall = conn.execute("""
        SELECT sample_site, sample_date, numeric_result, dataset
        FROM water_samples
        WHERE parameter='pH'
        ORDER BY sample_date DESC
        LIMIT 1
    """).fetchone()

    # Monthly statistics for the past 14 months
    monthly_rows = conn.execute("""
        SELECT
            strftime('%Y-%m', sample_date) as month,
            ROUND(AVG(numeric_result), 2) as avg_ph,
            ROUND(MIN(numeric_result), 2) as min_ph,
            ROUND(MAX(numeric_result), 2) as max_ph,
            COUNT(*) as sample_count
        FROM water_samples
        WHERE parameter='pH' AND sample_date >= date('now', '-14 months')
        GROUP BY strftime('%Y-%m', sample_date)
        ORDER BY month ASC
    """).fetchall()

    # Recent 30 individual samples for timeline
    recent_samples = conn.execute("""
        SELECT sample_site, sample_date, numeric_result, dataset
        FROM water_samples
        WHERE parameter='pH' AND sample_site LIKE '%Bearspaw%'
        ORDER BY sample_date DESC
        LIMIT 30
    """).fetchall()

    conn.close()

    bearspaw_ph = float(latest_bearspaw["numeric_result"]) if latest_bearspaw else 8.21
    delta_target = round(bearspaw_ph - 7.50, 2)

    return {
        "latest_bearspaw": dict(latest_bearspaw) if latest_bearspaw else None,
        "latest_glenmore": dict(latest_glenmore) if latest_glenmore else None,
        "latest_overall": dict(latest_overall) if latest_overall else None,
        "monthly": [dict(r) for r in monthly_rows],
        "recent": [dict(r) for r in recent_samples],
        "current_ph": bearspaw_ph,
        "target_ph": 7.50,
        "delta": delta_target,
        "status": "High / Alkaline" if bearspaw_ph >= 8.20 else ("Moderate" if bearspaw_ph > 7.80 else "Optimal")
    }


if __name__ == "__main__":
    print("Syncing Calgary water quality data...")
    n = sync_data()
    print(f"Synced {n} records.")
    stats = get_summary_stats()
    print("Bearspaw:", stats["latest_bearspaw"])
