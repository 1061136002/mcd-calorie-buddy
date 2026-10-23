#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Community library + menu matching tests: python tests/test_combo.py"""

import base64
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import combo  # noqa: E402
import order  # noqa: E402

LIBRARY = os.path.join(ROOT, "community", "combos.json")

# A tiny fake menu in the same shape as query-meals -> data.meals
FAKE_MENU = {
    "4810": {"name": "薯条", "currentPrice": "13.5"},
    "9900008751": {"name": "可乐", "currentPrice": "9.5"},
    "1406": {"name": "板烧鸡腿堡", "currentPrice": "23.5"},
    "3505": {"name": "锡兰红茶", "currentPrice": "11.5"},
    "507409": {"name": "麦咖啡™奶铁", "currentPrice": "13.9"},
    "4437": {"name": "玉米杯", "currentPrice": "13"},
}


def test_library_loads_and_has_nutrition():
    data = combo.read_library(LIBRARY)
    assert len(data["combos"]) >= 5, "community library is too small"
    for c in data["combos"]:
        assert c["items"], "combo without items"
        assert c["nutrition"] and c["nutrition"]["energy_kcal"] > 0, \
            "combo {} has no nutrition, run: python scripts/combo.py recalc".format(c["id"])


def test_nutrition_matches_source_data():
    """Stored nutrition must equal the sum computed from data/nutrition.csv."""
    table = {i["name"]: i for i in combo.load(combo.CSV)}
    for c in combo.read_library(LIBRARY)["combos"]:
        totals, missing = combo.nutrition_of(c["items"], table)
        assert not missing, "{} 引用了营养数据里没有的餐品: {}".format(c["id"], missing)
        assert totals == c["nutrition"], "{} 的营养值过期了，请跑 recalc".format(c["id"])


def test_match_exact_and_size_variants():
    matched, unmatched = order.match_items(["板烧鸡腿堡", "可乐中杯", "小薯条"], FAKE_MENU)
    got = {m["want"]: m["name"] for m in matched}
    assert got["板烧鸡腿堡"] == "板烧鸡腿堡"
    assert got["可乐中杯"] == "可乐", "杯型后缀应被剥离后匹配"
    assert got["小薯条"] == "薯条", "规格前缀应被剥离后匹配"
    assert unmatched == []


def test_match_fuzzy_for_coffee():
    matched, _ = order.match_items(["热奶铁中杯"], FAKE_MENU)
    assert matched and matched[0]["name"] == "麦咖啡™奶铁"


def test_match_reports_unmatched():
    matched, unmatched = order.match_items(["板烧鸡腿堡", "根本不存在的餐品"], FAKE_MENU)
    assert len(matched) == 1
    assert unmatched == ["根本不存在的餐品"]


def test_share_code_roundtrip(tmp_library=None):
    data = combo.read_library(LIBRARY)
    original = copy.deepcopy(data["combos"][0])
    payload = json.dumps(original, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    code = "MC1|" + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    body = code[4:] + "=" * (-len(code[4:]) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(body.encode("ascii")).decode("utf-8"))
    assert decoded["items"] == original["items"]
    assert decoded["nutrition"] == original["nutrition"]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except AssertionError as exc:
                failures += 1
                print("FAIL", name, "-", exc)
    print("\n{} failed".format(failures) if failures else "\nall passed")
    sys.exit(1 if failures else 0)
