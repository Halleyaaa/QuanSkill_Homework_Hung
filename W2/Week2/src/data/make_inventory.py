"""Create data/raw/SOURCE_INVENTORY.csv: one row per raw source file, with a SHA-256 hash.

Run once, immediately after the raw data is obtained and BEFORE any processing.
The pipeline (build_dataset.py) re-hashes every raw file and stops if a hash no longer
matches this inventory (critical gate G1: raw data must not change silently).

Usage:  python -m src.data.make_inventory
"""
from __future__ import annotations

import csv
from pathlib import Path

from .rules import sha256_bytes

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OBTAINED_AT = "2026-09-30"  # date the export / snapshot was taken

FIELDS = ["source_id", "source_name", "source_type", "location", "owner_or_origin",
          "collection_method", "obtained_at", "volume", "refresh_frequency", "expected_role",
          "sensitivity", "known_limitation", "bytes", "sha256"]


def main() -> None:
    rows = []
    for p in sorted((RAW / "knowledge_base").glob("KB-*.md")):
        data = p.read_bytes()
        rows.append(dict(
            source_id=f"SRC-{p.stem}", source_name=p.stem, source_type="markdown article with front matter",
            location=p.relative_to(ROOT).as_posix(), owner_or_origin="ShopNova help-center CMS (synthetic)",
            collection_method="CMS export, one file per article", obtained_at=OBTAINED_AT,
            volume="1 article", refresh_frequency="on policy change (owner review yearly)",
            expected_role="knowledge (retrieval evidence)", sensitivity="internal, no personal data",
            known_limitation="approval / review dates are self-reported metadata",
            bytes=len(data), sha256=sha256_bytes(data)))
    t = RAW / "tickets" / "tickets_export_2026-09-30.csv"
    data = t.read_bytes()
    n_rows = data.decode("utf-8").count("\nMSG-")
    rows.append(dict(
        source_id="SRC-TICKETS-2026-09-30", source_name=t.stem, source_type="CSV helpdesk export",
        location=t.relative_to(ROOT).as_posix(), owner_or_origin="ShopNova helpdesk (synthetic)",
        collection_method="full export of tickets created 1 Jun - 29 Sep 2026", obtained_at=OBTAINED_AT,
        volume=f"{n_rows} message rows", refresh_frequency="weekly export (planned)",
        expected_role="interactions (evaluation questions and reference replies)",
        sensitivity="CONFIDENTIAL if real: free text may contain personal and payment data",
        known_limitation="mixed timestamp formats; agent labels optional; export may duplicate rows",
        bytes=len(data), sha256=sha256_bytes(data)))
    out = RAW / "SOURCE_INVENTORY.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"inventory: {len(rows)} sources -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
