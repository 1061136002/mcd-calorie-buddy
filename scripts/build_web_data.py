#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the static data files used by the web app in docs/.

    python scripts/build_web_data.py

Reads data/nutrition.csv + data/images.json + community/combos.json and writes
docs/data/nutrition.json and docs/data/combos.json. Run this whenever the
nutrition data or the community library changes.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from plan import classify, load  # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "data")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    images = {}
    images_path = os.path.join(ROOT, "data", "images.json")
    if os.path.exists(images_path):
        with open(images_path, encoding="utf-8-sig") as fh:
            images = json.load(fh)

    items = load(os.path.join(ROOT, "data", "nutrition.csv"))
    nutrition = [{
        "n": i["name"],
        "k": i["energy_kcal"],
        "p": i["protein_g"],
        "f": i["fat_g"],
        "c": i["carbohydrate_g"],
        "na": i["sodium_mg"],
        "ca": i["calcium_mg"],
        "cat": i["category"],
        "img": images.get(i["name"], ""),
    } for i in items]

    with open(os.path.join(OUT_DIR, "nutrition.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "generated_at": "2026-10-23",
            "source": "McDonald's China MCP list-nutrition-foods",
            "count": len(nutrition),
            "items": nutrition,
        }, fh, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(ROOT, "community", "combos.json"), encoding="utf-8-sig") as fh:
        combos = json.load(fh)["combos"]
    for combo in combos:
        combo["images"] = [images.get(name, "") for name in combo["items"]]

    with open(os.path.join(OUT_DIR, "combos.json"), "w", encoding="utf-8") as fh:
        json.dump({"count": len(combos), "combos": combos}, fh,
                  ensure_ascii=False, separators=(",", ":"))

    with_images = sum(1 for i in nutrition if i["img"])
    print("nutrition.json: {} 个餐品，其中 {} 个有图片".format(len(nutrition), with_images))
    print("combos.json: {} 个社区套餐".format(len(combos)))
    print("写入 {}".format(OUT_DIR))


if __name__ == "__main__":
    main()
