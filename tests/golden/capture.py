"""Capture golden calculation packets from the current v1 engine.

Golden files record what v1 *currently produces*. They are not a claim that
the output is astronomically correct. When a real calculation bug is found,
the golden file is updated deliberately, after a test proving the bug passes.

Usage (from the repo root, venv active):

    python -m tests.golden.capture --print-schema
    python -m tests.golden.capture
    python -m tests.golden.capture --only natal_tropical_placidus

--print-schema dumps the ChartRequest JSON schema so the request bodies in
requests.json can be filled in against the real field names rather than
guessed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
REQUESTS_PATH = HERE / "requests.json"
OUT_DIR = HERE / "v1"

TODO_MARKER = "_TODO"


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def print_schema() -> None:
    from app.schemas import ChartRequest

    print(json.dumps(ChartRequest.model_json_schema(), indent=2, ensure_ascii=False))


def load_requests() -> dict[str, dict]:
    data = json.loads(REQUESTS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def capture_one(client, name: str, body: dict, out_dir: Path) -> tuple[str, str]:
    if TODO_MARKER in json.dumps(body):
        return name, "skipped (request body still has a _TODO placeholder)"

    response = client.post("/v1/chart-packet", json=body)
    if response.status_code != 200:
        return name, f"HTTP {response.status_code}: {response.text[:200]}"

    packet = response.json()
    path = out_dir / f"{name}.json"
    path.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return name, f"wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-schema", action="store_true", help="dump the ChartRequest schema and exit")
    parser.add_argument("--only", help="capture a single named request")
    parser.add_argument("--out", default=str(OUT_DIR), help="output directory")
    args = parser.parse_args(argv)

    if args.print_schema:
        print_schema()
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    requests = load_requests()
    if args.only:
        if args.only not in requests:
            print(f"unknown request {args.only!r}; known: {', '.join(sorted(requests))}", file=sys.stderr)
            return 2
        requests = {args.only: requests[args.only]}

    client = _client()
    skipped = 0
    for name, body in requests.items():
        name, note = capture_one(client, name, body, out_dir)
        if note.startswith("skipped"):
            skipped += 1
        print(f"{name:44s} {note}")

    if skipped:
        print(
            f"\n{skipped} request(s) still contain {TODO_MARKER}. "
            f"Run --print-schema and fill in requests.json.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
