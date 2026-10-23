#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull product images and prices from the McDonald's menu API and map them
onto the nutrition catalogue names, so the web app can show real food photos
and let people filter by what they can afford.

    python scripts/build_images.py                      # 默认多城市多时段
    python scripts/build_images.py --store 1420762      # 指定门店
    python scripts/build_images.py --city 上海 --city 北京

Why multiple cities and time slots: the menu is different per store and per
time of day. 麦满分/粥 only appear with a morning reservation date, 下午茶
items only in the afternoon. Sampling several combinations is the only way to
get decent coverage of the 158-item nutrition catalogue.

Prices are store-specific (McDonald's prices by city/store tier), so the output
records which stores they came from and the web app shows a disclaimer.

The token is read from ~/.workbuddy/mcp.json or MCD_MCP_TOKEN. It never ends up
in the output file.
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

OUT = os.path.join(ROOT, "data", "menu.json")

# (label, reservationDate) — menu content depends on the time slot
SLOTS = [
    ("早餐", "2026-10-24 08:30"),
    ("午餐", "2026-10-24 11:30"),
    ("下午茶", "2026-10-24 15:00"),
    ("夜市", "2026-10-23 19:30"),
]

DEFAULT_STORES = ["1420762", "1420412"]


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
        "找不到 MCP Token。设 MCD_MCP_TOKEN，或在 ~/.workbuddy/mcp.json 里配好 mcd-mcp。"
    )


def stores_of_city(city):
    res = result_json(call_tool("query-nearby-stores", {
        "beType": 1, "searchType": 2, "city": city, "keyword": "中心区"
    }))
    return [s["storeCode"] for s in (res.get("data") or [])[:2]]


def fetch_menu(store, slot_date):
    args = {"storeCode": store, "orderType": 1, "beType": 1}
    if slot_date:
        args["reservationDate"] = slot_date
    return result_json(call_tool("query-meals", args)).get("data", {}).get("meals") or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", action="append", default=[])
    ap.add_argument("--city", action="append", default=[])
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    os.environ.setdefault("MCD_MCP_TOKEN", read_token())

    stores = list(args.store) or list(DEFAULT_STORES)
    for city in args.city:
        try:
            found = stores_of_city(city)
            print("{}: 门店 {}".format(city, found))
            stores.extend(found)
        except Exception as exc:  # noqa: BLE001
            print("{}: 查门店失败 {}".format(city, exc))

    merged = {}
    for store in stores:
        for label, slot in SLOTS:
            try:
                menu = fetch_menu(store, slot)
            except Exception as exc:  # noqa: BLE001
                print("  跳过 {} {}: {}".format(store, label, exc))
                continue
            merged.setdefault(store, {})
            merged[store].update(menu)
    print("\n共抓取 {} 个门店，{} 个菜单条目".format(len(merged), sum(len(m) for m in merged.values())))

    items = load(os.path.join(ROOT, "data", "nutrition.csv"))
    names = [i["name"] for i in items]

    catalogue = {}
    for store, menu in merged.items():
        matched, _ = match_items(names, menu)
        for m in matched:
            info = menu.get(m["code"]) or {}
            price = None
            try:
                price = float(info.get("currentPrice"))
            except (TypeError, ValueError):
                pass
            entry = catalogue.get(m["want"])
            # 取有图的一条；价格取该商品在各门店的中位数，避免单店促销失真
            if entry is None or (not entry.get("img") and info.get("image")):
                catalogue[m["want"]] = {
                    "code": m["code"],
                    "menu_name": info.get("name", m["want"]),
                    "img": info.get("image", ""),
                    "prices": [price] if price else [],
                }
            elif price:
                entry["prices"].append(price)

    out = {}
    for name, info in catalogue.items():
        prices = sorted(p for p in info["prices"] if p)
        out[name] = {
            "code": info["code"],
            "menu_name": info["menu_name"],
            "img": info["img"],
            "price": round(prices[len(prices) // 2], 1) if prices else None,
        }

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({
            "stores": stores,
            "note": "价格单位为元，取各门店中位数；不同城市/门店定价不同，仅供参考",
            "items": out,
        }, fh, ensure_ascii=False, indent=2)

    with_img = sum(1 for v in out.values() if v["img"])
    with_price = sum(1 for v in out.values() if v["price"] is not None)
    print("匹配 {} / {} 个餐品".format(len(out), len(names)))
    print("  有图 {} · 有价 {}".format(with_img, with_price))
    missing = [n for n in names if n not in out]
    if missing:
        print("  无匹配: " + "、".join(missing[:20]) + ("…" if len(missing) > 20 else ""))
    print("写入 {}".format(args.out))


if __name__ == "__main__":
    main()
