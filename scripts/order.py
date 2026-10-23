#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把社区套餐一键下单：套餐 → 门店 → 菜单匹配 → 算价 → 下单。

    export MCD_MCP_TOKEN='...'
    python scripts/order.py ls-600-d470 --city 深圳 --keyword 科技园        # 只看，不下单
    python scripts/order.py ls-600-d470 --city 深圳 --keyword 科技园 --confirm

不加 --confirm 永远是试算，不会创建订单。
"""

import argparse
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from combo import LIBRARY, read_library  # noqa: E402
from mcp_client import call_tool  # noqa: E402

SIZE_WORDS = re.compile(r"(小杯|中杯|大杯|小|中|大|\d+块|块)")


def result_json(result):
    """Normalize a MCP tool result into a python dict."""
    if "structuredContent" in result:
        return result["structuredContent"]
    for block in result.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                continue
    return result


def find_combo(combo_id):
    data = read_library(LIBRARY)
    for combo in data["combos"]:
        if combo["id"] == combo_id:
            return combo
    raise SystemExit("社区库里找不到套餐 {}".format(combo_id))


def resolve_store(args):
    """Return (storeCode, beCode, storeName, addressId)."""
    if args.store_code:
        return args.store_code, args.be_code, args.store_code, args.address_id

    if args.be_type in (1, 5):
        res = result_json(call_tool("query-nearby-stores", {
            "beType": args.be_type, "searchType": 2,
            "city": args.city, "keyword": args.keyword}))
        stores = (res.get("data") or [])
        if not stores:
            raise SystemExit("没找到门店，换个关键词试试")
        print("找到 {} 家门店：".format(len(stores)))
        for i, s in enumerate(stores[:5], 1):
            print("  {}. {} [{}] {}m".format(
                i, s.get("storeName"), s.get("storeCode"), s.get("distance")))
        store = stores[0]
        print("  默认选第 1 家，可用 --store-code 指定\n")
        return store["storeCode"], store.get("beCode"), store.get("storeName"), None

    address_id = args.address_id
    if not address_id:
        res = result_json(call_tool("delivery-query-addresses", {}))
        addresses = ((res.get("data") or {}).get("addresses") or [])
        if not addresses:
            raise SystemExit("账号里没有配送地址，先用 delivery-create-address 建一个，或改用 --be-type 1 到店自取")
        address_id = addresses[0].get("addressId")
        print("使用地址: {}".format(addresses[0].get("fullAddress")))
    print("使用地址: {} {}".format(addresses[0].get("contactName"), addresses[0].get("fullAddress")))
    res = result_json(call_tool("delivery-query-stores", {
        "beType": args.be_type, "addressId": address_id}))
    stores = res.get("data") or []
    if not stores:
        raise SystemExit("该地址没有可配送门店")
    store = stores[0]
    print("配送门店: {}".format(store.get("storeName")))
    return store["storeCode"], store.get("beCode"), store.get("storeName"), address_id


def load_menu(store_code, order_type, be_type, be_code):
    res = result_json(call_tool("query-meals", {
        "storeCode": store_code, "orderType": order_type,
        "beType": be_type, "beCode": be_code}))
    return (res.get("data") or {}).get("meals") or {}


def longest_common_substring(a, b):
    """Length of the longest common substring, used as a last-resort fuzzy match."""
    if not a or not b:
        return 0
    best = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    top = 0
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                best[i][j] = best[i - 1][j - 1] + 1
                top = max(top, best[i][j])
    return top


def match_items(combo_items, menu):
    """Match nutrition-data names onto real menu codes. Returns (matched, unmatched)."""
    by_name = {}
    for code, info in menu.items():
        by_name[info.get("name", "").strip()] = (code, info)

    matched, unmatched = [], []
    for item in combo_items:
        name = item.strip()
        code_info = by_name.get(name)
        if not code_info:
            stripped = SIZE_WORDS.sub("", name).strip()
            code_info = by_name.get(stripped)
        if not code_info:
            # substrings both ways
            for menu_name, info in by_name.items():
                core = SIZE_WORDS.sub("", menu_name).strip()
                if core and (core in name or (stripped and stripped in menu_name)):
                    code_info = info
                    break
        if not code_info:
            close = difflib.get_close_matches(stripped or name, list(by_name), n=1, cutoff=0.62)
            if close:
                code_info = by_name[close[0]]
        if not code_info:
            # Last resort: shared core word, e.g. 热奶铁中杯 -> 麦咖啡™奶铁
            target = stripped or name
            best_score, best_name = 0.0, None
            for menu_name in by_name:
                core = SIZE_WORDS.sub("", menu_name).strip().lstrip("麦咖啡™")
                lcs = longest_common_substring(target, core)
                if lcs < 2:
                    continue
                score = lcs / min(len(target), len(core))
                if score > best_score:
                    best_score, best_name = score, menu_name
            if best_name and best_score >= 0.6:
                code_info = by_name[best_name]
        if code_info:
            code, info = code_info
            matched.append({
                "want": name, "code": code, "name": info.get("name"),
                "price": info.get("currentPrice"), "quantity": 1})
        else:
            unmatched.append(name)
    return matched, unmatched


def yuan(cents):
    try:
        return "{:.2f}".format(int(cents) / 100.0)
    except (TypeError, ValueError):
        return str(cents)


def main():
    ap = argparse.ArgumentParser(description="社区套餐一键下单")
    ap.add_argument("combo_id", help="社区套餐 id，用 combo.py list 查看")
    ap.add_argument("--city", help="城市，到店/得来速场景必填")
    ap.add_argument("--keyword", help="位置关键词，到店/得来速场景必填")
    ap.add_argument("--store-code", help="直接指定门店编号，跳过搜索")
    ap.add_argument("--be-code", help="得来速/外送场景的业务编码")
    ap.add_argument("--be-type", type=int, default=1, choices=[1, 2, 5],
                    help="1 到店自取（默认）/ 2 麦乐送 / 5 得来速")
    ap.add_argument("--address-id", help="外送场景的配送地址 id，默认用账号里第一个")
    ap.add_argument("--confirm", action="store_true", help="真正创建订单（默认只试算）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.store_code and not (args.city and args.keyword) and args.be_type in (1, 5):
        raise SystemExit("到店场景需要 --city 和 --keyword，或直接给 --store-code")

    combo = find_combo(args.combo_id)
    n = combo.get("nutrition") or {}
    print("套餐: {} [{}]".format(combo["name"], combo["id"]))
    print("营养: {kcal} kcal | 蛋白 {p}g | 钠 {na}mg\n".format(
        kcal=n.get("energy_kcal", "?"), p=n.get("protein_g", "?"), na=n.get("sodium_mg", "?")))

    order_type = 1 if args.be_type in (1, 5) else 2
    store_code, be_code, store_name, address_id = resolve_store(args)
    print("门店: {} [{}]\n".format(store_name, store_code))

    menu = load_menu(store_code, order_type, args.be_type, be_code)
    matched, unmatched = match_items(combo["items"], menu)

    print("餐品匹配：")
    for m in matched:
        print("  {} -> {} ({}) ¥{}".format(m["want"], m["name"], m["code"], m["price"]))
    if unmatched:
        print("\n这些餐品在当前门店菜单里没找到（可能下架或该店不售）：")
        for name in unmatched:
            print("  - {}".format(name))
    if not matched:
        raise SystemExit("\n一个都没匹配上，换门店或换套餐试试")

    price_args = {
        "storeCode": store_code, "orderType": order_type, "beType": args.be_type,
        "items": [{"productCode": m["code"], "quantity": m["quantity"]} for m in matched],
    }
    if be_code:
        price_args["beCode"] = be_code
    price = result_json(call_tool("calculate-price", price_args))
    pdata = price.get("data") or {}

    print("\n价格试算：")
    for key in ("totalPrice", "discountPrice", "deliveryFee", "payPrice"):
        if key in pdata:
            print("  {}: ¥{}".format(key, yuan(pdata[key])))
    if args.json:
        print(json.dumps({"store": store_code, "matched": matched, "unmatched": unmatched,
                          "price": pdata}, ensure_ascii=False, indent=2))

    if unmatched:
        print("\n注意: 有 {} 件没匹配上，下单内容会与套餐原意不符。".format(len(unmatched)))

    if not args.confirm:
        print("\n这是试算，没有下单。确认无误后加 --confirm 才会真正创建订单。")
        return

    order_args = dict(price_args)
    take_ways = pdata.get("takeWayList") or []
    if order_type == 1:
        if not take_ways:
            raise SystemExit("算价结果里没有取餐方式，无法下单")
        order_args["takeWayCode"] = take_ways[0].get("code")
    else:
        if address_id:
            order_args["addressId"] = address_id
        else:
            raise SystemExit("外送场景缺少 addressId，用 --address-id 指定")
    order = result_json(call_tool("create-order", order_args))
    print("\n下单结果：")
    print(json.dumps(order, ensure_ascii=False, indent=2)[:1500])


if __name__ == "__main__":
    main()
