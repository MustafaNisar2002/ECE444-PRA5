import csv
import time
from datetime import datetime

import requests

BASE_URL = "http://mustafasserver-env.eba-anbepq23.us-east-2.elasticbeanstalk.com/predict"

CASES = {
    "fake_1": "Scientists confirm that drinking bleach cures all diseases.",
    "fake_2": "World to end tomorrow, government officials evacuating to Mars.",
    "real_1": "The central bank kept interest rates unchanged this quarter.",
    "real_2": "Researchers published new findings on battery efficiency in a journal.",
}

def run_case(name, text):
    latencies = []
    filename = f"{name}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iso_timestamp", "latency_ms"])
        for i in range(100):
            t0 = time.perf_counter()
            r = requests.post(BASE_URL, json={"text": text}, timeout=10)
            r.raise_for_status()
            dt_ms = (time.perf_counter() - t0) * 1000.0
            writer.writerow([datetime.utcnow().isoformat(), f"{dt_ms:.3f}"])
            latencies.append(dt_ms)
            time.sleep(0.05)  # small pause so we don't hammer the server
    print(f"{name}: avg latency = {sum(latencies)/len(latencies):.2f} ms")
    return latencies

def main():
    all_latencies = {}
    for name, text in CASES.items():
        all_latencies[name] = run_case(name, text)

if __name__ == "__main__":
    main()
