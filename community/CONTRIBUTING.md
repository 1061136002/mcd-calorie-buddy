# 分享你的套餐

社区套餐库就在 [`combos.json`](./combos.json) 里。没有后端、没有账号系统——
**分享 = 提一个 PR**，合并后所有人 `combo.py list` 就能看到你的搭配。

## 三步分享

### 1. 生成你的套餐

自己配一个，或者让规划器帮你算：

```bash
# 让规划器算，挑一个满意的
python scripts/plan.py --budget 600 --goal high_protein --top 5

# 存进社区库（营养值会自动算，不用手填）
python scripts/combo.py save \
  --name "600 卡增肌晚餐" \
  --items "板烧鸡腿堡,麦乐鸡5块,无糖可口可乐中杯" \
  --goal high_protein \
  --tags "增肌,晚餐" \
  --author "你的 GitHub ID" \
  --note "蛋白质够，钠 1200mg 偏高，控钠的人别选这个"
```

`--items` 里的名字要和 `data/nutrition.csv` 里的一致，找不到会警告并按 0 计入。

### 2. 生成提交内容

```bash
python scripts/combo.py submit <你的套餐id>
```

会打印一段 JSON 和 PR 步骤。

### 3. 提 PR

1. fork 本仓库
2. 编辑 `community/combos.json`，把那段 JSON 粘进 `combos` 数组
3. commit（信息随意，比如 `分享套餐：600 卡增肌晚餐`）
4. 提 PR，标题写 `分享套餐：<名字>`

合并后你的套餐就进库了。

## 懒得提 PR？用分享码

```bash
python scripts/combo.py share <套餐id>
```

会输出一行 `MC1|...` 的分享码，发给朋友，对方：

```bash
python scripts/combo.py import "MC1|..."
```

就能把它加进自己的本地库。分享码自带全部营养数据，不联网也能用。
（这种方式只有对方看得到，不会进公共库。）

## 套餐里该写什么

| 字段 | 说明 |
|---|---|
| `name` | 让人一眼看懂，最好带热量，如「500 卡增肌餐」 |
| `author` | 你的 GitHub ID |
| `goal` | `balanced` / `high_protein` / `low_sodium` / `low_carb` / `high_calcium` |
| `tags` | 场景标签，如 早餐、增肌、控钠、蔬食 |
| `items` | 餐品名，必须与营养数据一致 |
| `note` | **最重要的一栏**：这套餐适合谁、有什么坑 |

`note` 请务必写实话。比如钠超过 1500mg 就明说「钠偏高，控钠人群别选」——
社区库的价值在于诚实，不在于每个套餐都好看。

## 条目规范

- `nutrition` 字段**不要手改**，它由 `python scripts/combo.py recalc` 依据
  `data/nutrition.csv` 自动计算。手改会被 CI 测试判为不一致。
- 一个 PR 可以放多个套餐。
- 餐品名拼错的话，`recalc` 会给出警告，PR 前请确认没有警告。
