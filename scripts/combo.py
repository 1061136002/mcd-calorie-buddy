#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社区套餐库：保存、浏览、分享、导入别人分享的热量管理套餐。

    python scripts/combo.py list --max-budget 600 --goal high_protein
    python scripts/combo.py show hp-500-8f3a
    python scripts/combo.py save --name "我的减脂晚餐" --items "板烧鸡腿堡,无糖可口可乐中杯"
    python scripts/combo.py share hp-500-8f3a          # 生成一段可粘贴的分享码
    python scripts/combo.py import "MC1|..."           # 导入别人的分享码
    python scripts/combo.py submit hp-500-8f3a         # 生成提 PR 用的内容
    python scripts/combo.py recalc                     # 依据 nutrition.csv 重算全部营养值

数据落在 community/combos.json，分享方式是提 PR —— 没有后端，靠 GitHub 汇聚。
"""

import argparse
import base64
import json
import os
import random
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from plan import FIELDS, load  # noqa: E402

LIBRARY = os.path.join(ROOT, "community", "combos.json")
CSV = os.path.join(ROOT, "data", "nutrition.csv")


def read_library(path=LIBRARY):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_library(data, path=LIBRARY):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def nutrition_of(items, table):
    """Sum nutrition for a list of item names. Returns (totals, missing)."""
    totals = {k: 0 for k in FIELDS}
    missing = []
    for name in items:
        row = table.get(name.strip())
        if not row:
            missing.append(name)
            continue
        for key in FIELDS:
            totals[key] += row[key]
    return totals, missing


def make_id(goal, kcal):
    return "{}-{}-{}".format(goal[:2], int(kcal), uuid.uuid4().hex[:4])


def sort_key(combo, mode):
    n = combo.get("nutrition") or {}
    if mode == "protein":
        return -(n.get("protein_g") or 0)
    if mode == "kcal":
        return n.get("energy_kcal") or 0
    if mode == "sodium":
        return n.get("sodium_mg") or 0
    return combo.get("created_at", "")


def fmt_combo(combo, show_items=True):
    n = combo.get("nutrition") or {}
    lines = [
        "{name}  [{id}]".format(name=combo["name"], id=combo["id"]),
        "  作者 {author} · {created} · 目标 {goal} · 预算 {budget} kcal".format(
            author=combo.get("author", "anonymous"), created=combo.get("created_at", "-"),
            goal=combo.get("goal", "-"), budget=combo.get("budget", "-")),
    ]
    if n:
        lines.append(
            "  合计 {kcal} kcal | 蛋白 {p}g | 脂肪 {f}g | 碳水 {c}g | 钠 {na}mg | 钙 {ca}mg".format(
                kcal=n.get("energy_kcal", "?"), p=n.get("protein_g", "?"), f=n.get("fat_g", "?"),
                c=n.get("carbohydrate_g", "?"), na=n.get("sodium_mg", "?"), ca=n.get("calcium_mg", "?")))
    if show_items:
        lines.append("  餐品: " + " + ".join(combo["items"]))
    if combo.get("tags"):
        lines.append("  标签: " + "、".join(combo["tags"]))
    if combo.get("note"):
        lines.append("  备注: " + combo["note"])
    return "\n".join(lines)


def cmd_list(args):
    data = read_library()
    combos = data["combos"]
    if args.max_budget:
        combos = [c for c in combos if (c.get("nutrition") or {}).get("energy_kcal", 0) <= args.max_budget]
    if args.goal:
        combos = [c for c in combos if c.get("goal") == args.goal]
    if args.tag:
        combos = [c for c in combos if args.tag in (c.get("tags") or [])]
    if args.author:
        combos = [c for c in combos if c.get("author") == args.author]
    combos.sort(key=lambda c: sort_key(c, args.sort))
    combos = combos[: args.top]
    if args.json:
        print(json.dumps(combos, ensure_ascii=False, indent=2))
        return
    if not combos:
        print("没有匹配的套餐，放宽筛选条件试试。")
        return
    print("社区套餐库 · {} 个匹配\n".format(len(combos)))
    for combo in combos:
        print(fmt_combo(combo))
        print()


def cmd_show(args):
    data = read_library()
    for combo in data["combos"]:
        if combo["id"] == args.combo_id:
            if args.json:
                print(json.dumps(combo, ensure_ascii=False, indent=2))
            else:
                print(fmt_combo(combo))
            return
    raise SystemExit("找不到套餐 {}".format(args.combo_id))


def cmd_save(args):
    items = [i.strip() for i in args.items.split(",") if i.strip()]
    if not items:
        raise SystemExit("--items 不能为空")
    table = {i["name"]: i for i in load(CSV)}
    totals, missing = nutrition_of(items, table)
    if missing:
        print("警告: 营养数据中找不到这些餐品，已按 0 计入：{}".format("、".join(missing)), file=sys.stderr)

    combo = {
        "id": make_id(args.goal, totals["energy_kcal"]),
        "name": args.name,
        "author": args.author,
        "created_at": args.date,
        "goal": args.goal,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "budget": args.budget or totals["energy_kcal"],
        "items": items,
        "note": args.note,
        "nutrition": totals,
    }
    if args.dry_run:
        print(json.dumps(combo, ensure_ascii=False, indent=2))
        return
    data = read_library()
    data["combos"].append(combo)
    write_library(data)
    print("已保存到社区库：{}\n".format(combo["id"]))
    print(fmt_combo(combo))
    print("\n下一步：")
    print("  python scripts/combo.py share {}".format(combo["id"]))
    print("  python scripts/combo.py submit {}".format(combo["id"]))


def cmd_share(args):
    data = read_library()
    for combo in data["combos"]:
        if combo["id"] == args.combo_id:
            payload = json.dumps(combo, ensure_ascii=False, separators=(",", ":"))
            code = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
            print("MC1|" + code)
            print("\n把上面这一行发给别人，对方用：")
            print('  python scripts/combo.py import "MC1|..."')
            return
    raise SystemExit("找不到套餐 {}".format(args.combo_id))


def cmd_import(args):
    raw = args.code.strip()
    if os.path.exists(raw):
        with open(raw, encoding="utf-8-sig") as fh:
            raw = fh.read().strip()
    if not raw.startswith("MC1|"):
        raise SystemExit("分享码格式不对，应以 MC1| 开头")
    body = raw[4:] + "=" * (-len(raw[4:]) % 4)
    combo = json.loads(base64.urlsafe_b64decode(body.encode("ascii")).decode("utf-8"))
    combo["id"] = make_id(combo.get("goal", "balanced"),
                          (combo.get("nutrition") or {}).get("energy_kcal", 0))
    data = read_library()
    data["combos"].append(combo)
    write_library(data)
    print("已导入：{}\n".format(combo["name"]))
    print(fmt_combo(combo))


def cmd_recalc(args):
    table = {i["name"]: i for i in load(CSV)}
    data = read_library()
    missing_all = []
    for combo in data["combos"]:
        totals, missing = nutrition_of(combo["items"], table)
        combo["nutrition"] = totals
        if missing:
            missing_all.append((combo["id"], missing))
    write_library(data)
    print("已重算 {} 个套餐的营养值".format(len(data["combos"])))
    for cid, missing in missing_all:
        print("  警告 {} 找不到: {}".format(cid, "、".join(missing)))


def cmd_submit(args):
    data = read_library()
    for combo in data["combos"]:
        if combo["id"] == args.combo_id:
            print("把下面这段 JSON 加到 community/combos.json 的 combos 数组里，然后提 PR：\n")
            print(json.dumps(combo, ensure_ascii=False, indent=2))
            print("\nPR 流程：")
            print("  1. fork 本仓库")
            print("  2. 编辑 community/combos.json，把上面的条目粘进 combos 数组")
            print("  3. commit 后提 PR，标题写「分享套餐：{}」".format(combo["name"]))
            print("  4. 合并后所有人都能 browse 到你的套餐")
            return
    raise SystemExit("找不到套餐 {}".format(args.combo_id))


def main():
    ap = argparse.ArgumentParser(description="社区套餐库")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="浏览社区套餐")
    p.add_argument("--max-budget", type=int)
    p.add_argument("--goal")
    p.add_argument("--tag")
    p.add_argument("--author")
    p.add_argument("--sort", default="protein", choices=["protein", "kcal", "sodium", "recent"])
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="查看某个套餐")
    p.add_argument("combo_id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("save", help="保存自己的套餐")
    p.add_argument("--name", required=True)
    p.add_argument("--items", required=True, help="餐品名，逗号分隔")
    p.add_argument("--goal", default="balanced")
    p.add_argument("--tags", default="")
    p.add_argument("--author", default=os.environ.get("USER") or "anonymous")
    p.add_argument("--note", default="")
    p.add_argument("--budget", type=int)
    p.add_argument("--date", default=os.environ.get("COMBO_DATE") or "2026-10-23")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("share", help="生成分享码")
    p.add_argument("combo_id")
    p.set_defaults(func=cmd_share)

    p = sub.add_parser("import", help="导入别人的分享码")
    p.add_argument("code")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("recalc", help="重算全部营养值")
    p.set_defaults(func=cmd_recalc)

    p = sub.add_parser("submit", help="生成提 PR 用的内容")
    p.add_argument("combo_id")
    p.set_defaults(func=cmd_submit)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
