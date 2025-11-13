import matplotlib.pyplot as plt
import csv

def load_latencies(filename):
    vals = []
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            vals.append(float(row["latency_ms"]))
    return vals

def main():
    labels = ["fake_1", "fake_2", "real_1", "real_2"]
    data = [load_latencies(f"{name}.csv") for name in labels]

    plt.figure()
    plt.boxplot(data, labels=labels, showmeans=True)
    plt.ylabel("Latency (ms)")
    plt.title("API Latency: 100 calls per test case")
    plt.tight_layout()
    plt.savefig("latency_boxplot.png")
    print("Saved latency_boxplot.png")

if __name__ == "__main__":
    main()
