"""Fetch reference documentation into a caller-selected directory outside the repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "references.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--refresh", action="store_true", help="update the recorded hashes")
    args = parser.parse_args()
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))
    args.directory.mkdir(parents=True, exist_ok=True)
    for item in sources:
        request = urllib.request.Request(item["url"], headers={"User-Agent": "dirsize-tests/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        digest = hashlib.sha256(data).hexdigest()
        if args.refresh:
            from datetime import date

            item.update(sha256=digest, size=len(data), fetched=date.today().isoformat())
        elif digest != item["sha256"]:
            raise ValueError(f"reference changed: {item['name']}; review before --refresh")
        (args.directory / item["name"]).write_bytes(data)
        print(item["name"], len(data), digest)
    if args.refresh:
        MANIFEST.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
