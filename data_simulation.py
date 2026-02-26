"""
data_simulation.py – NASA C-MAPSS FD001 Live Streamer
Reads rows from the local train_FD001.txt and pushes one telemetry document
to Elasticsearch every 5 seconds, simulating a live degrading engine.

Pauses automatically when the Gantry API reports system_halted=True
(i.e. after trigger_failure.py fires) and resumes once the operator
accepts the solution and the system is resumed.
"""

import os
import io
import time
import json
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ES_URL = os.getenv("ELASTIC_ES_URL") or os.getenv("ELASTIC_SIM_URL")
API_KEY = os.getenv("ELASTIC_ES_API_KEY") or os.getenv("ELASTIC_SIM_API_KEY")
INDEX_NAME = "gantry_telemetry"
API_BASE = os.getenv("GANTRY_API_BASE", "http://localhost:8000")

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "Content-Type": "application/json",
}

LOCAL_FILE = "train_FD001.txt"
COL_NAMES = ["unit_id", "cycle", "op_1", "op_2", "op_3"] + [f"s_{i}" for i in range(1, 22)]

# ── Load dataset ─────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    mirror_url = (
        "https://raw.githubusercontent.com/biswajitsahoo1111/"
        "rul_codes_open/master/dataset/train_FD001.txt"
    )
    if os.path.exists(LOCAL_FILE):
        print(f"✅ Found local data: {LOCAL_FILE}")
        df = pd.read_csv(LOCAL_FILE, sep=r"\s+", header=None, names=COL_NAMES)
    else:
        print("🌐 Downloading NASA dataset …")
        resp = requests.get(mirror_url, timeout=15)
        resp.raise_for_status()
        with open(LOCAL_FILE, "w") as f:
            f.write(resp.text)
        df = pd.read_csv(io.StringIO(resp.text), sep=r"\s+", header=None, names=COL_NAMES)

    max_cycles = df.groupby("unit_id")["cycle"].max().reset_index()
    max_cycles.columns = ["unit_id", "max_cycle"]
    df = df.merge(max_cycles, on="unit_id")
    df["rul_label"] = df["max_cycle"] - df["cycle"]
    return df


def _is_system_halted() -> bool:
    """Check if the Gantry API has halted the system (failure active)."""
    try:
        resp = requests.get(f"{API_BASE}/api/status", timeout=2)
        return resp.json().get("halted", False)
    except Exception:
        return False  # if API unreachable, don't block simulation


# ── Stream one row every 5 s ────────────────────────────────────────────────

def stream_telemetry(unit: int = 1, interval: float = 5.0):
    """
    Streams rows for a single engine unit to Elasticsearch one-by-one.
    Only cycles through the HEALTHY portion (RUL > 50) so the dashboard
    stays in safe territory — trigger_failure.py creates the dramatic shift.
    """
    df = load_data()
    engine_df = df[df["unit_id"] == unit].sort_values("cycle").reset_index(drop=True)

    if engine_df.empty:
        print(f"❌ No data for unit {unit}. Available: {sorted(df['unit_id'].unique())}")
        return

    # Only keep healthy rows (RUL > 50) so the demo stays green until trigger_failure.py
    healthy_df = engine_df[engine_df["rul_label"] > 50].reset_index(drop=True)
    if healthy_df.empty:
        healthy_df = engine_df.head(20).reset_index(drop=True)

    total_rows = len(healthy_df)
    print(f"🚀 Streaming {total_rows} HEALTHY cycles for ENGINE-{unit:03d} @ {interval}s interval …")
    print(f"   (RUL range: {healthy_df['rul_label'].min()} – {healthy_df['rul_label'].max()})")
    print(f"   Run trigger_failure.py to create the dramatic failure event.")

    idx = 0
    while True:
        # ── Pause while the system is halted (failure active) ──────────
        if _is_system_halted():
            print("⏸  System halted — simulation paused (waiting for operator resolution)…")
            while _is_system_halted():
                time.sleep(3)
            print("▶  System resumed — simulation restarting.")

        row = healthy_df.iloc[idx % total_rows]

        doc = {
            "@timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "unit_id": f"ENGINE-{int(row['unit_id']):03d}",
            "cycle": int(row["cycle"]),
            "sensor_measure_11": float(row["s_11"]),
            "rul_label": int(row["rul_label"]),
            "vibration": round(abs(float(row["s_11"])) * 0.005, 6),
            "op_1": float(row["op_1"]),
            "op_2": float(row["op_2"]),
            "op_3": float(row["op_3"]),
        }

        try:
            resp = requests.post(
                f"{ES_URL}/{INDEX_NAME}/_doc",
                headers=HEADERS,
                data=json.dumps(doc),
            )
            status_icon = "📡" if resp.status_code == 201 else "⚠️"
            print(
                f"{status_icon}  cycle={doc['cycle']:>3}  "
                f"RUL={doc['rul_label']:>3}  "
                f"S11={doc['sensor_measure_11']:.4f}  "
                f"vib={doc['vibration']:.6f}"
            )
        except Exception as e:
            print(f"❌ ES error: {e}")

        idx += 1
        time.sleep(interval)


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stream NASA telemetry to Elasticsearch")
    parser.add_argument("--unit", type=int, default=1, help="Engine unit_id (default: 1)")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between rows (default: 5)")
    args = parser.parse_args()

    stream_telemetry(unit=args.unit, interval=args.interval)