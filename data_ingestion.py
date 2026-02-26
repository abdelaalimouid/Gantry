import os
import io
import pandas as pd
import requests
from elasticsearch import Elasticsearch, helpers
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# 1. Configuration (from .env)
ENDPOINT_URL = os.getenv("ELASTIC_ES_URL")
API_KEY = os.getenv("ELASTIC_ES_API_KEY")
INDEX_NAME = "gantry_telemetry"

es = Elasticsearch(hosts=[ENDPOINT_URL], api_key=API_KEY)

def load_data():
    # Mirror: Research repo by Biswajit Sahoo (very stable)
    url = "https://raw.githubusercontent.com/biswajitsahoo1111/rul_codes_open/master/dataset/train_FD001.txt"
    local_file = "train_FD001.txt"
    col_names = ['unit_id', 'cycle', 'op_1', 'op_2', 'op_3'] + [f's_{i}' for i in range(1, 22)]

    # Logic: If local file exists, use it. If not, download and SAVE it.
    if os.path.exists(local_file):
        print(f"✅ Found local data: {local_file}. Loading...")
        return pd.read_csv(local_file, sep=r'\s+', header=None, names=col_names)
    
    try:
        print(f"🌐 Downloading NASA dataset from stable mirror...")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        # Save locally for future enterprise resilience
        with open(local_file, 'w') as f:
            f.write(response.text)
        print(f"💾 Data saved locally as {local_file}")
        
        return pd.read_csv(io.StringIO(response.text), sep=r'\s+', header=None, names=col_names)
    except Exception as e:
        print(f"❌ Mirror failed: {e}")
        print("\n--- MANUAL ACTION REQUIRED ---")
        print("1. Go to: https://github.com/biswajitsahoo1111/rul_codes_open/raw/master/dataset/train_FD001.txt")
        print(f"2. Save the page as '{local_file}' in your {os.getcwd()} folder.")
        print("3. Run this script again.")
        exit()

# Execute Load
df = load_data()

# 3. Process & Ingest
print("⚡ Processing telemetry and RUL...")
max_cycles = df.groupby('unit_id')['cycle'].max().reset_index()
max_cycles.columns = ['unit_id', 'max_cycle']
df = df.merge(max_cycles, on='unit_id')
df['rul_label'] = df['max_cycle'] - df['cycle']

def generate_data(dataframe):
    # Anchor timestamps in the past so Kibana "Last 30 days" shows everything
    max_cycle = int(dataframe['cycle'].max())
    end_time = datetime.now()  # most recent record = now
    for _, row in dataframe.iterrows():
        # Spread records across the past — each cycle = 10 min apart
        cycles_ago = max_cycle - int(row['cycle'])
        timestamp = end_time - timedelta(minutes=10 * cycles_ago)
        yield {
            "_index": INDEX_NAME,
            "_source": {
                "@timestamp": timestamp.isoformat(),
                "unit_id": f"ENGINE-{int(row['unit_id']):03d}",
                "cycle": int(row['cycle']),
                "sensor_measure_11": float(row['s_11']),
                "rul_label": int(row['rul_label'])
            }
        }

print(f"🚀 Streaming to Elastic Serverless...")
helpers.bulk(es, generate_data(df))
print(f"🎉 Success! Ingested {len(df)} records.")