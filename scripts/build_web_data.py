#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the static data files used by the web app in docs/.

    python scripts/build_web_data.py

Reads data/nutrition.csv + data/menu.json + community/combos.json and writes
docs/data/nutrition.json and docs/data/combos.json. Run after refreshing the
nutrition data, the menu snapshot or the community library.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from plan import load  # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "data")


def load_menu():
    path = os.path.join(ROOT, "data", "menu.json")
    if not os.path.exists(path):
        print("警告: 没有 data/menu.json，网页版将没有图片和价格。"
              "先跑 python scripts/build_images.py")
        return {}, [], ""
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    return data.get("items") or {}, data.get("stores") or [], data.get("note", "")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    menu, stores, note = load_menu()

    items = load(os.path.join(ROOT, "data", "nutrition.csv"))
    nutrition = []
    for i in items:
        info = menu.get(i["name"]) or {}
        nutrition.append({
            "n": i["name"],
            "k": i["energy_kcal"],
            "p": i["protein_g"],
            "f": i["fat_g"],
            "c": i["carbohydrate_g"],
            "na": i["sodium_mg"],
            "ca": i["calcium_mg"],
            "cat": i["category"],
            "img": info.get("img", ""),
            "pr": info.get("price"),
            "av": i["name"] in menu,  # 当前门店是否还卖
        })

    with open(os.path.join(OUT_DIR, "nutrition.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "generated_at": "2026-10-23",
            "source": "McDonald's China MCP list-nutrition-foods",
            "price_note": note,
            "price_stores": stores,
            "count": len(nutrition),
            "available": sum(1 for i in nutrition if i["av"]),
            "items": nutrition,
        }, fh, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(ROOT, "community", "combos.json"), encoding="utf-8-sig") as fh:
        combos = json.load(fh)["combos"]
    for combo in combos:
        prices = [menu.get(name, {}).get("price") for name in combo["items"]]
        known = [p for p in prices if p is not None]
        combo["images"] = [(menu.get(name) or {}).get("img", "") for name in combo["items"]]
        combo["price"] = round(sum(known), 1) if len(known) == len(prices) else None
        combo["all_available"] = len(known) == len(prices)

    with open(os.path.join(OUT_DIR, "combos.json"), "w", encoding="utf-8") as fh:
        json.dump({"count": len(combos), "combos": combos}, fh,
                  ensure_ascii=False, separators=(",", ":"))

    print("nutrition.json: {} 个餐品（在售 {}，有图 {}，有价 {}）".format(
        len(nutrition),
        sum(1 for i in nutrition if i["av"]),
        sum(1 for i in nutrition if i["img"]),
        sum(1 for i in nutrition if i["pr"] is not None)))
    print("combos.json: {} 个社区套餐".format(len(combos)))
    print("写入 {}".format(OUT_DIR))


if __name__ == "__main__":
    main()
