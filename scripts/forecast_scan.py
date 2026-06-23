"""Forward-looking forecast scan: exact transit hits, stations, and eclipses
for the outer planets (Jupiter-Pluto) over a date range, via build_packet's
forecast block. No server, no LLM, no tokens.

  python scripts/forecast_scan.py
  python scripts/forecast_scan.py --from 2026-06-20 --months 12
  python scripts/forecast_scan.py --from 2026-06-20 --to 2027-06-20
  python scripts/forecast_scan.py --date 1990-01-15 --time 14:30 --city "Novi Sad"
"""
import sys
import os
import json
import argparse
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.core.packet import build_packet, InputError  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="1984-07-24")
    ap.add_argument("--time", default="05:10:00")
    ap.add_argument("--city", default="Belgrade, Serbia")
    ap.add_argument("--accuracy", default="exact", choices=["exact", "approx", "unknown"])
    ap.add_argument("--from", dest="start", default=date.today().isoformat())
    ap.add_argument("--to", dest="end", help="YYYY-MM-DD; overrides --months")
    ap.add_argument("--months", type=int, default=12)
    args = ap.parse_args()

    req = {
        "birth": {"date": args.date, "time": args.time,
                  "time_accuracy": args.accuracy, "place_label": args.city},
        "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
        "forecast": {"enabled": True, "start_date": args.start},
    }
    if args.end:
        req["forecast"]["end_date"] = args.end
    else:
        req["forecast"]["months"] = args.months

    try:
        packet = build_packet(req)
    except InputError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(2)

    print(json.dumps(packet, ensure_ascii=False, indent=2))
    print(f"  validated_for_interpretation: {packet['validation']['validated_for_interpretation']}",
         file=sys.stderr)


if __name__ == "__main__":
    main()
