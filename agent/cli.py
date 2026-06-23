"""Terminal test for the Astraeus agent. The calc service must be running
(uvicorn app.main:app --port 8080) and an LLM key must be set.

  python -m agent.cli
  python -m agent.cli --transit 2026-06-19 --question "career focus this year?"
  python -m agent.cli --time-accuracy unknown      # demonstrates the refusal gate
"""
import argparse
import sys

from .client import get_reading, NotValidated

DEFAULT = {
    "birth": {"date": "1984-07-24", "time": "05:10:00", "time_accuracy": "exact",
              "place_label": "Belgrade, Serbia"},
    "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transit", help="transit date YYYY-MM-DD (adds a transit reading)")
    ap.add_argument("--question", help="optional question to steer the reading")
    ap.add_argument("--time-accuracy", choices=["exact", "approx", "unknown"], default="exact")
    args = ap.parse_args()

    payload = {**DEFAULT, "birth": {**DEFAULT["birth"], "time_accuracy": args.time_accuracy}}
    if args.transit:
        payload["transit"] = {"date": args.transit, "time": "12:00:00",
                              "timezone": "Europe/Belgrade"}

    try:
        result = get_reading(payload, question=args.question)
        print(result["reading"])
    except NotValidated as e:
        print("REFUSED — chart not valid for interpretation:", file=sys.stderr)
        for r in e.reasons:
            print("  -", r, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
