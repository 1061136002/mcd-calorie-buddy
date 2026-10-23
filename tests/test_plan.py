#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke tests: python tests/test_plan.py"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLAN = os.path.join(ROOT, "scripts", "plan.py")
CSV = os.path.join(ROOT, "data", "nutrition.csv")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import plan  # noqa: E402


def run(*args):
    proc = subprocess.run(
        [sys.executable, PLAN, *args], capture_output=True, text=True, encoding="utf-8"
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_data_loads():
    items = plan.load(CSV)
    assert len(items) > 100, "nutrition data looks empty"
    assert all(i["category"] in ("main", "side", "drink", "dessert") for i in items)


def test_classification():
    cases = {
        "巨无霸": "main",
        "中薯条": "side",
        "可乐中杯": "drink",
        "圆筒冰淇淋": "dessert",
        "柠檬拉明顿": "dessert",      # dessert wins over the 柠檬 drink keyword
        "阳光柠檬红茶中杯": "drink",
        "大杯玉米杯": "side",          # side wins over the 杯 drink keyword
        "蜜汁快乐": "main",            # 蜜汁 must not match the 汁 drink keyword
        "皮蛋鸡肉粥": "main",
    }
    for name, expected in cases.items():
        assert plan.classify(name) == expected, "{} => {} != {}".format(
            name, plan.classify(name), expected
        )


def test_budget_respected():
    for budget in (400, 600, 800):
        plans = plan.search(
            [[i for i in plan.load(CSV) if i["category"] == c and i["energy_kcal"] <= budget]
             for c in ("main", "side", "drink")],
            ["main", "side", "drink"], budget, plan.GOALS["balanced"],
            0.75, 4, 0, None, 5,
        )
        assert plans, "no plan found for {} kcal".format(budget)
        for p in plans:
            assert p["totals"]["energy_kcal"] <= budget
            assert p["totals"]["energy_kcal"] >= budget * 0.75


def test_low_sodium_actually_lowers_sodium():
    items = plan.load(CSV)
    pools = [[i for i in items if i["category"] == c and i["energy_kcal"] <= 600]
             for c in ("main", "side", "drink")]
    def best(goal):
        res = plan.search(pools, ["main", "side", "drink"], 600, plan.GOALS[goal], 0.75, 4, 0, None, 1)
        return res[0]["totals"]["sodium_mg"]
    assert best("low_sodium") < best("balanced"), "low_sodium goal is not effective"


def test_cli_runs():
    out = run("--budget", "500", "--goal", "high_protein", "--top", "3")
    assert "kcal" in out


def test_cli_json():
    import json
    out = run("--budget", "500", "--top", "2", "--json")
    data = json.loads(out)
    assert isinstance(data, list) and data
    assert "totals" in data[0]


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
