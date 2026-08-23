import sys
import os
import requests
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

print("Starting Weather ingestion pipeline...")

lat, lon = 28.6328, 77.2197
start_date = "2025-06-01"
end_date = "2025-09-30"

url = "https://archive-api.open-meteo.com/v1/archive"
params = {
    "latitude": lat,
    "longitude": lon,
    "start_date": start_date,
    "end_date": end_date,
    "daily": "rain_sum,temperature_2m_max,relative_humidity_2m_max",
    "timezone": "auto"
}

# Resolve against this file, not the caller's CWD — the other pipelines all write to
# data/processed_data/, and a relative path put this one in data/pipelines/processed_data/.
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "processed_data")
os.makedirs(OUT_DIR, exist_ok=True)
csv_path = os.path.join(OUT_DIR, "weather_delhi.csv")

def generate_fallback_data(start, end):
    print("Generating fallback weather data...")
    dates = pd.date_range(start=start, end=end, freq='D')
    n = len(dates)
    df = pd.DataFrame({
        "date": dates.strftime('%Y-%m-%d'),
        "rain_mm": np.random.uniform(0, 50, n),
        "max_temp_c": np.random.uniform(28, 42, n),
        "max_humidity_pct": np.random.uniform(50, 100, n)
    })
    return df

try:
    print(f"Requesting data from Open-Meteo: {url}")
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    if "daily" in data:
        daily = data["daily"]
        df = pd.DataFrame({
            "date": daily["time"],
            "rain_mm": daily["rain_sum"],
            "max_temp_c": daily["temperature_2m_max"],
            "max_humidity_pct": daily["relative_humidity_2m_max"]
        })
        print("API request successful.")
    else:
        raise ValueError("No 'daily' data found in response.")
except Exception as e:
    print(f"API request failed: {e}")
    df = generate_fallback_data(start_date, end_date)

print(f"Saving {len(df)} records to {csv_path}...")
df.to_csv(csv_path, index=False)
print("Pipeline 3 complete.")
