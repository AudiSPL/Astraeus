"""Print a chart packet as JSON to stdout. No server, no LLM, no tokens.
Copy the output and paste it into your GPT.

  python scripts/print_chart.py
  python scripts/print_chart.py --transit 2026-06-19
  python scripts/print_chart.py --date 1990-01-15 --time 14:30 --city "Novi Sad"
  python scripts/print_chart.py > chart.json
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.core.packet import build_packet, InputError  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="1984-07-24")
    ap.add_argument("--time", default="05:10:00")
    ap.add_argument("--city", default="Belgrade, Serbia")
    ap.add_argument("--accuracy", default="exact", choices=["exact", "approx", "unknown"])
    ap.add_argument("--transit", help="transit date YYYY-MM-DD (adds a transit snapshot)")
    args = ap.parse_args()

    req = {
        "birth": {"date": args.date, "time": args.time,
                  "time_accuracy": args.accuracy, "place_label": args.city},
        "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
    }
    if args.transit:
        req["transit"] = {"date": args.transit, "time": "12:00:00", "timezone": "Europe/Belgrade"}

    try:
        print(json.dumps(build_packet(req), ensure_ascii=False, indent=2))
    except InputError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
