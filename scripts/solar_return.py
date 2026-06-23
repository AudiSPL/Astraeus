"""Solar return: full chart cast for the moment the transiting Sun returns to
its natal degree in a given year, plus aspects back to natal. Natal location
by default; pass --sr-city or --sr-lat/--sr-lon to relocate. No server, no
LLM, no tokens.

  python scripts/solar_return.py --year 2026
  python scripts/solar_return.py --year 2026 --sr-city "New York"
  python scripts/solar_return.py --year 2026 --sr-lat 40.7128 --sr-lon -74.0060 --sr-tz "America/New_York"
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
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--sr-city", help="relocate the solar return chart (default: natal location)")
    ap.add_argument("--sr-lat", type=float)
    ap.add_argument("--sr-lon", type=float)
    ap.add_argument("--sr-tz")
    ap.add_argument("--sr-house-system", choices=["placidus", "whole_sign", "koch", "equal"])
    args = ap.parse_args()

    req = {
        "birth": {"date": args.date, "time": args.time,
                  "time_accuracy": args.accuracy, "place_label": args.city},
        "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
        "solar_return": {"year": args.year},
    }
    if args.sr_city:
        req["solar_return"]["city"] = args.sr_city
    if args.sr_lat is not None and args.sr_lon is not None:
        req["solar_return"]["latitude"] = args.sr_lat
        req["solar_return"]["longitude"] = args.sr_lon
        if args.sr_tz:
            req["solar_return"]["timezone"] = args.sr_tz
    if args.sr_house_system:
        req["solar_return"]["house_system"] = args.sr_house_system

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
