#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refresh data/nutrition.csv from the live McDonald's MCP server.

    export MCD_MCP_TOKEN='...'
    python scripts/fetch_nutrition.py --out data/nutrition.csv

The tool returns a compact text table instead of JSON, e.g.

    [160]{productName,nutritionDescription,energyKj,energyKcal,...}:
      猪柳麦满分,null,1288,308,16,16,24,781,213

so we split on the "}:" separator and parse the rows afterwards.
"""

import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_client import call_tool, tool_text  # noqa: E402

FIELDS = [
    "product_name",
    "ref_note",
    "energy_kj",
    "energy_kcal",
    "protein_g",
    "fat_g",
    "carbohydrate_g",
    "sodium_mg",
    "calcium_mg",
]

NUMERIC = set(FIELDS[2:])


def parse(raw_text):
    """Parse the MCP text table into a list of dicts."""
    match = re.search(r"\]\s*\{([^}]*)\}\s*:\s*(.*)", raw_text, re.S)
    if not match:
        raise SystemExit("Unexpected nutrition payload format:\n" + raw_text[:400])
    body = match.group(2)
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split(",")]
        if len(cells) < len(FIELDS):
            continue
        row = {}
        for key, value in zip(FIELDS, cells[: len(FIELDS)]):
            if value == "null" or value == "":
                row[key] = "" if key not in NUMERIC else 0
                continue
            row[key] = int(value) if key in NUMERIC else value
        rows.append(row)
    return rows


def dedupe(rows):
    seen, out = set(), []
    for row in rows:
        if row["product_name"] in seen:
            continue
        seen.add(row["product_name"])
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser(description="Pull McDonald's nutrition data via MCP")
    ap.add_argument("--out", default=os.path.join("data", "nutrition.csv"))
    args = ap.parse_args()

    raw = tool_text(call_tool("list-nutrition-foods"))
    rows = dedupe(parse(raw))
    if not rows:
        raise SystemExit("No rows parsed, aborting (existing file left untouched).")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote {} items to {}".format(len(rows), args.out))


if __name__ == "__main__":
    main()
