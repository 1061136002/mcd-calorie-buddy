#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull product images from the McDonald's menu API and map them onto the
nutrition catalogue names, so the web app can show real food photos.

    python scripts/build_images.py            # writes data/images.json
    python scripts/build_images.py --store 1420762 --store 1420412

The token is read from the WorkBuddy MCP config (~/.workbuddy/mcp.json) or the
MCD_MCP_TOKEN environment variable. It never ends up in the output file.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from mcp_client import call_tool  # noqa: E402
from order import match_items, result_json  # noqa: E402
from plan import load  # noqa: E402

OUT = os.path.join(ROOT, "data", "images.json")
# Several scenarios, because the menu differs by time of day:
# breakfast (麦满分/粥) only shows up with a morning reservation date.
SCENARIOS = [
    {"label": "正餐", "reservationDate": None},
    {"label": "早餐", "reservationDate": "2026-10-24 08:30"},
]


def read_token():
    token = os.environ.get("MCD_MCP_TOKEN")
    if token:
        return token
    cfg = os.path.join(os.path.expanduser("~"), ".workbuddy", "mcp.json")
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        server = (data.get("mcpServers") or {}).get("mcd-mcp") or {}
        header = (server.get("headers") or {}).get("Authorization") or ""
        if header.startswith("Bearer "):
            return header[7:]
    raise SystemExit(
        "找不到 MCP Token。设 MCD_MCP_TOKEN 环境变量，或在 ~/.workbuddy/mcp.json 里配好 mcd-mcp。"
    )


def fetch_menu(store, reservation_date):
    args = {"storeCode": store, "orderType": 1, "beType": 1}
    if reservation_date:
        args["reservationDate"] = reservation_date
    return result_json(call_tool("query-meals", args)).get("data", {}).get("meals") or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", action="append", default=[])
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    if not args.store:
        args.store = ["1420762", "1420412"]

    os.environ.setdefault("MCD_MCP_TOKEN", read_token())

    items = load(os.path.join(ROOT, "data", "nutrition.csv"))
    names = [i["name"] for i in items]

    merged = {}
    for store in args.store:
        for scenario in SCENARIOS:
            try:
                menu = fetch_menu(store, scenario["reservationDate"])
            except Exception as exc:  # noqa: BLE001
                print("跳过 {} {}: {}".format(store, scenario["label"], exc))
                continue
            print("{} {}: 菜单 {} 项".format(store, scenario["label"], len(menu)))
            for code, info in menu.items():
                merged.setdefault(code, info)

    matched, unmatched = match_items(names, merged)
    images = {}
    for m in matched:
        info = merged.get(m["code"]) or {}
        if info.get("image"):
            images[m["want"]] = info["image"]

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(images, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print("\n匹配到图片 {} / {} 个餐品".format(len(images), len(names)))
    print("写入 {}".format(args.out))
    if len(images) < len(names) * 0.5:
        print("提示: 覆盖率偏低，多加几个 --store 再跑一次")


if __name__ == "__main__":
    main()
