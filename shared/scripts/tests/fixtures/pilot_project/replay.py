import json
import sys

LEAK_FUTURE = False

SIGNALS = [
    {"timestamp": "2024-06-01T00:00:00", "signal": 1},
    {"timestamp": "2024-06-08T00:00:00", "signal": -1},
]


def main():
    cutoff = sys.argv[sys.argv.index("--cutoff") + 1]
    if LEAK_FUTURE:
        # bug: ignores cutoff, always returns the full series regardless of what's "knowable" at cutoff
        visible = SIGNALS
    else:
        visible = [s for s in SIGNALS if s["timestamp"] <= cutoff + "T23:59:59"]
    print(json.dumps(visible))


if __name__ == "__main__":
    main()
