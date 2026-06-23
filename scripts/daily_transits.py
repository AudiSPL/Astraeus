"""Generate daily transit snapshots from today to end of July 2026.
Output: single JSON array, one entry per day.

  python scripts/daily_transits.py
  python scripts/daily_transits.py > jul_tranziti.json
  python scripts/daily_transits.py --from 2026-06-19 --to 2026-07-31
"""
import sys
import os
import json
import argparse
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.core.packet import build_packet, InputError

BIRTH = {
    "birth": {
        "date": "1984-07-24",
        "time": "05:10:00",
        "time_accuracy": "exact",
        "place_label": "Belgrade, Serbia",
    },
    "settings": {
        "zodiac": "tropical",
        "house_system": "placidus",
        "node_type": "true",
    },
}


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def slim(packet: dict, day: str) -> dict:
    """Keep only what's useful per day — transits + validation. Natal is the
    same every day so we strip it to keep the file small."""
    return {
        "date": day,
        "validated": packet["validation"]["validated_for_interpretation"],
        "transits": packet["transits"],
        "warnings": packet["warnings"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2026-06-19")
    ap.add_argument("--to", dest="end", default="2026-07-31")
    ap.add_argument("--full", action="store_true",
                    help="include full natal packet on each day (big file)")
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    days = list(daterange(start, end))

    results = []
    for d in days:
        day_str = d.isoformat()
        req = {**BIRTH, "transit": {
            "date": day_str,
            "time": "12:00:00",
            "timezone": "Europe/Belgrade",
        }}
        try:
            packet = build_packet(req)
            entry = packet if args.full else slim(packet, day_str)
            results.append(entry)
            print(f"  {day_str} ok", file=sys.stderr)
        except Exception as e:
            results.append({"date": day_str, "error": str(e)})
            print(f"  {day_str} ERROR: {e}", file=sys.stderr)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
