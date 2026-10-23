#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""McDonald's calorie-budget meal planner.

Given a calorie budget (e.g. 500 kcal) and a nutrition goal, search the real
McDonald's China catalogue for the best combinations that fit the budget.

    python scripts/plan.py --budget 500
    python scripts/plan.py --budget 600 --goal high_protein --min-protein 30
    python scripts/plan.py --budget 450 --exclude drink --json

Data source: data/nutrition.csv, refreshed from the `list-nutrition-foods`
MCP tool via scripts/fetch_nutrition.py.
"""

import argparse
import csv
import json
import os
import sys

FIELDS = ["energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "sodium_mg", "calcium_mg"]

# Category keywords are matched in this order; the first hit wins.
# Dessert and side are checked first because their names often contain words
# that also appear in drinks (e.g. 柠檬拉明顿 vs 阳光柠檬红茶).
DESSERT_KEYS = ["冰淇淋", "新地", "麦旋风", "拉明顿", "奶冻", "爆珠", "雪冰", "阿芙佳朵"]
SIDE_KEYS = [
    "薯条", "薯饼", "麦乐鸡", "鸡块", "鸡翅", "V翅", "鸡球", "派", "玉米",
    "油条", "香肠", "鸡排", "苹果片", "脆汁鸡",
]
DRINK_KEYS = [
    "可乐", "雪碧", "茶", "咖啡", "美式", "奶铁", "玛奇朵", "卡布奇诺", "浓缩",
    "牛奶", "燕麦", "抹茶", "豆浆", "果汁", "苹果汁", "纯悦", "怡泉", "美汁源",
    "柠檬", "橙", "朱古力", "杯",
]
MAIN_KEYS = ["麦满分", "汉堡", "堡", "卷", "粥", "多肉", "双翅", "牛气", "快乐", "薯鱼", "支撑"]

CATEGORY_LABEL = {"main": "主食", "side": "小食", "drink": "饮料", "dessert": "甜品"}

# score = w_protein*protein + w_calcium*calcium/100 - w_sodium*sodium/100 - w_carb*carb
GOALS = {
    "balanced":    {"protein": 1.00, "calcium": 0.05, "sodium": 0.15, "carb": 0.00},
    "high_protein": {"protein": 1.80, "calcium": 0.05, "sodium": 0.10, "carb": 0.00},
    "low_sodium":  {"protein": 0.50, "calcium": 0.05, "sodium": 3.00, "carb": 0.00},
    "low_carb":    {"protein": 1.20, "calcium": 0.05, "sodium": 0.15, "carb": 0.15},
    "high_calcium": {"protein": 0.80, "calcium": 0.30, "sodium": 0.15, "carb": 0.00},
}


def load(path):
    if not os.path.exists(path):
        raise SystemExit(
            "Nutrition data not found at {}. Run:\n"
            "  export MCD_MCP_TOKEN='...' && python scripts/fetch_nutrition.py".format(path)
        )
    items, seen = [], set()
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("product_name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            item = {"name": name, "category": classify(name)}
            for key in FIELDS:
                try:
                    item[key] = int(float(row.get(key) or 0))
                except ValueError:
                    item[key] = 0
            item["ref_note"] = (row.get("ref_note") or "").strip()
            items.append(item)

    # 价格与图片来自菜单快照（data/menu.json），缺失时不影响配餐本身
    menu_path = os.path.join(os.path.dirname(os.path.abspath(path)), "menu.json")
    if os.path.exists(menu_path):
        with open(menu_path, encoding="utf-8-sig") as fh:
            menu = json.load(fh).get("items") or {}
        for item in items:
            info = menu.get(item["name"])
            item["price"] = (info or {}).get("price")
            item["available"] = item["name"] in menu
    return items


def classify(name):
    for key in DESSERT_KEYS:
        if key in name:
            return "dessert"
    for key in SIDE_KEYS:
        if key in name:
            return "side"
    for key in DRINK_KEYS:
        if key in name:
            return "drink"
    for key in MAIN_KEYS:
        if key in name:
            return "main"
    return "main"


def score(items, weights):
    protein = sum(i["protein_g"] for i in items)
    sodium = sum(i["sodium_mg"] for i in items)
    calcium = sum(i["calcium_mg"] for i in items)
    carb = sum(i["carbohydrate_g"] for i in items)
    return (
        weights["protein"] * protein
        + weights["calcium"] * calcium / 100.0
        - weights["sodium"] * sodium / 100.0
        - weights["carb"] * carb
    )


def totals(items):
    return {key: sum(i[key] for i in items) for key in FIELDS}


def search(pools, order, budget, weights, fill_ratio, max_items,
           min_protein, max_sodium, top_n):
    """Depth-first search over `order` categories, pruning on the calorie budget."""
    pools = [sorted(pool, key=lambda i: i["energy_kcal"]) for pool in pools]
    results = []
    picked = []

    def walk(idx, used):
        if len(results) >= 20000:  # safety valve
            return
        if idx == len(order):
            if not picked:
                return
            if len(picked) > max_items:
                return
            if used > budget or used < budget * fill_ratio:
                return
            agg = totals(picked)
            if agg["protein_g"] < min_protein:
                return
            if max_sodium is not None and agg["sodium_mg"] > max_sodium:
                return
            results.append({
                "items": list(picked),
                "totals": agg,
                "score": score(picked, weights),
                "leftover": budget - used,
            })
            return
        # Skip this category entirely.
        walk(idx + 1, used)
        for item in pools[idx]:
            if used + item["energy_kcal"] > budget:
                break  # sorted ascending: everything after is too big
            picked.append(item)
            walk(idx + 1, used + item["energy_kcal"])
            picked.pop()

    walk(0, 0)
    results.sort(key=lambda r: (-r["score"], r["leftover"]))
    return results[:top_n]


def dedupe(plans):
    """Collapse plans that differ only by drink (锡兰红茶 vs 伯爵红茶 is noise)."""
    seen, out = set(), []
    for plan in plans:
        key = tuple(i["name"] for i in plan["items"] if i["category"] != "drink")
        if key in seen:
            continue
        seen.add(key)
        out.append(plan)
    return out


def diversify(plans, limit, per_main=2):
    """Avoid five near-identical plans built on the same main item."""
    picked, counts = [], {}
    for plan in plans:
        key = next((i["name"] for i in plan["items"] if i["category"] == "main"), "")
        if counts.get(key, 0) >= per_main:
            continue
        counts[key] = counts.get(key, 0) + 1
        picked.append(plan)
        if len(picked) >= limit:
            return picked
    for plan in plans:  # fall back if the catalogue is too narrow
        if plan not in picked and len(picked) < limit:
            picked.append(plan)
    return picked


def render(plans, budget, goal, weights):
    if not plans:
        print("没有找到符合条件的组合，试试放宽预算（--budget）或降低饱腹度要求（--fill）。")
        return
    print("预算 {} kcal · 目标 {} · 共 {} 个方案\n".format(budget, goal, len(plans)))
    for rank, plan in enumerate(plans, 1):
        agg = plan["totals"]
        mix = " + ".join(
            "{}({} kcal)".format(i["name"], i["energy_kcal"]) for i in plan["items"]
        )
        print("{}. {}".format(rank, mix))
        prices = [i.get("price") for i in plan["items"] if i.get("price") is not None]
        cost = " | 合计 ¥{:.1f}".format(sum(prices)) if len(prices) == len(plan["items"]) else ""
        print(
            "   合计 {kcal} kcal | 蛋白 {p} g | 脂肪 {f} g | 碳水 {c} g | 钠 {na} mg | 钙 {ca} mg"
            " | 剩余预算 {left} kcal{cost} | 得分 {s:.1f}".format(
                kcal=agg["energy_kcal"], p=agg["protein_g"], f=agg["fat_g"],
                c=agg["carbohydrate_g"], na=agg["sodium_mg"], ca=agg["calcium_mg"],
                left=plan["leftover"], cost=cost, s=plan["score"],
            )
        )
        print("   结构: " + "、".join(CATEGORY_LABEL[i["category"]] for i in plan["items"]))
        print()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_csv = os.path.join(os.path.dirname(here), "data", "nutrition.csv")

    ap = argparse.ArgumentParser(description="麦当劳热量预算配餐")
    ap.add_argument("--budget", type=int, required=True, help="热量预算（kcal）")
    ap.add_argument("--goal", default="balanced", choices=sorted(GOALS), help="营养目标")
    ap.add_argument("--exclude", default="", help="排除分类，逗号分隔：main,side,drink,dessert")
    ap.add_argument("--dessert", action="store_true", help="允许加入甜品（默认不加）")
    ap.add_argument("--fill", type=float, default=0.75, help="最低饱腹度，占用预算比例，默认 0.75")
    ap.add_argument("--max-items", type=int, default=4, help="最多几件，默认 4")
    ap.add_argument("--min-protein", type=int, default=0, help="最低蛋白质（g）")
    ap.add_argument("--max-sodium", type=int, default=None, help="最高钠（mg）")
    ap.add_argument("--avoid", default="", help="避开含这些关键词的餐品，逗号分隔")
    ap.add_argument("--max-price", type=float, default=None, help="价格上限（元），需要 data/menu.json")
    ap.add_argument("--in-stock", action="store_true", help="只用在售餐品（菜单快照里有的）")
    ap.add_argument("--top", type=int, default=5, help="返回几个方案，默认 5")
    ap.add_argument("--csv", default=default_csv, help="营养数据路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    weights = GOALS[args.goal]
    items = load(args.csv)

    avoid = [k.strip() for k in args.avoid.split(",") if k.strip()]
    items = [i for i in items if not any(k in i["name"] for k in avoid)]

    if args.in_stock:
        items = [i for i in items if i.get("available")]

    excluded = {k.strip() for k in args.exclude.split(",") if k.strip()}
    order = [c for c in ("main", "side", "drink", "dessert") if c not in excluded]
    if not args.dessert:
        order = [c for c in order if c != "dessert"]
    if not order:
        raise SystemExit("所有分类都被排除了。")

    pools = [[i for i in items if i["category"] == c and i["energy_kcal"] <= args.budget] for c in order]
    if any(not p for p in pools) and len(order) > 1:
        print("提示: 部分分类在 {} kcal 预算内没有可选餐品，已跳过。\n".format(args.budget), file=sys.stderr)

    plans = search(
        pools, order, args.budget, weights, args.fill,
        args.max_items, args.min_protein, args.max_sodium, args.top * 10,
    )
    # --max-price 限制的是套餐总价，不是单品单价
    if args.max_price is not None:
        priced = []
        for plan in plans:
            prices = [i.get("price") for i in plan["items"] if i.get("price") is not None]
            if len(prices) == len(plan["items"]) and sum(prices) <= args.max_price:
                priced.append(plan)
        if priced:
            plans = priced

    plans = diversify(dedupe(plans), args.top)

    if args.json:
        print(json.dumps(
            [{"items": [i["name"] for i in p["items"]], "totals": p["totals"],
              "score": round(p["score"], 2), "leftover": p["leftover"]} for p in plans],
            ensure_ascii=False, indent=2))
    else:
        render(plans, args.budget, args.goal, weights)


if __name__ == "__main__":
    main()
