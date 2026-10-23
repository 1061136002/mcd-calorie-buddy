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


def build_single_file(nutrition_doc, combos_doc):
    """Render docs/index.html as a single self-contained file.

    Everything except the food photos is inlined: CSS, JS and the two data
    blobs. GitHub Pages serves from China can drop individual sub-requests,
    which used to leave the page unstyled; one file has no such failure mode.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "web_template.html"), encoding="utf-8") as fh:
        template = fh.read()
    with open(os.path.join(ROOT, "docs", "styles.css"), encoding="utf-8") as fh:
        css = fh.read()
    with open(os.path.join(ROOT, "docs", "app.js"), encoding="utf-8") as fh:
        js = fh.read()

    def safe(obj):
        # "</" inside a JSON string would terminate the inline <script> block
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    html = (template
            .replace("{{CSS}}", css)
            .replace("{{JS}}", js)
            .replace("{{NUTRITION}}", safe(nutrition_doc))
            .replace("{{COMBOS}}", safe(combos_doc))
            .replace("{{META}}", safe({
                "price_note": nutrition_doc.get("price_note", ""),
                "price_stores": nutrition_doc.get("price_stores", []),
                "generated_at": nutrition_doc.get("generated_at"),
            })))
    with open(os.path.join(ROOT, "docs", "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print("index.html: 单文件自包含，{} KB".format(os.path.getsize(os.path.join(ROOT, "docs", "index.html")) // 1024))


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

    nutrition_doc = {
        "generated_at": "2026-10-23",
        "source": "McDonald's China MCP list-nutrition-foods",
        "price_note": note,
        "price_stores": stores,
        "count": len(nutrition),
        "available": sum(1 for i in nutrition if i["av"]),
        "items": nutrition,
    }
    with open(os.path.join(OUT_DIR, "nutrition.json"), "w", encoding="utf-8") as fh:
        json.dump(nutrition_doc, fh, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(ROOT, "community", "combos.json"), encoding="utf-8-sig") as fh:
        combos = json.load(fh)["combos"]
    for combo in combos:
        prices = [menu.get(name, {}).get("price") for name in combo["items"]]
        known = [p for p in prices if p is not None]
        combo["images"] = [(menu.get(name) or {}).get("img", "") for name in combo["items"]]
        combo["price"] = round(sum(known), 1) if len(known) == len(prices) else None
        combo["all_available"] = len(known) == len(prices)

    combos_doc = {"count": len(combos), "combos": combos}
    with open(os.path.join(OUT_DIR, "combos.json"), "w", encoding="utf-8") as fh:
        json.dump(combos_doc, fh, ensure_ascii=False, separators=(",", ":"))

    print("nutrition.json: {} 个餐品（在售 {}，有图 {}，有价 {}）".format(
        len(nutrition),
        sum(1 for i in nutrition if i["av"]),
        sum(1 for i in nutrition if i["img"]),
        sum(1 for i in nutrition if i["pr"] is not None)))
    print("combos.json: {} 个社区套餐".format(len(combos)))
    build_single_file(nutrition_doc, combos_doc)
    print("写入 {}".format(OUT_DIR))


if __name__ == "__main__":
    main()
