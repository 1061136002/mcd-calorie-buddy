---
name: mcd-calorie-buddy
description: 麦当劳热量预算配餐。当用户给出热量预算（如"500大卡以内能吃什么"、"减脂期想吃麦当劳"、"预算600卡要高蛋白"）或询问麦当劳餐品热量、蛋白、钠含量时，用麦当劳 MCP 的真实营养数据规划最优组合，并可继续算价下单。关键词：麦当劳、热量、卡路里、大卡、减脂、配餐、营养、蛋白质、钠。
---

# 麦麦热量管家

在真实麦当劳菜单数据上做「给定热量预算 → 最优组合」的搜索，而不是凭印象推荐。

## 何时使用

- 用户说「我今天只剩 500 大卡的额度」「预算 600 卡，要高蛋白」「控钠，钠别超 1000mg」
- 用户问麦当劳某餐品热量/蛋白质/钠，或想比较几款
- 用户想减脂/增肌/控钠，又想吃麦当劳

## 工作流

### 1. 收集三个输入

依次确认（用户没说就给默认值，不要反复追问）：

| 输入 | 默认 | 说明 |
|---|---|---|
| 热量预算 | 必问 | 单位 kcal |
| 营养目标 | `balanced` | `balanced` / `high_protein` / `low_sodium` / `low_carb` / `high_calcium` |
| 忌口 | 无 | 用 `--avoid` 传关键词，如「香菜,菠萝」 |

### 2. 刷新营养数据（推荐）

优先用真实数据，别只用仓库快照：

```
export MCD_MCP_TOKEN='<用户的 token>'
python scripts/fetch_nutrition.py --out data/nutrition.csv
```

或直接调用 MCP 工具 `list-nutrition-foods`。数据没变化时复用 `data/nutrition.csv` 即可。

### 3. 跑配餐

```bash
python scripts/plan.py --budget 600 --goal high_protein --top 5
python scripts/plan.py --budget 500 --goal low_sodium --max-sodium 1000 --top 3
python scripts/plan.py --budget 450 --exclude drink --top 3      # 不喝饮料
python scripts/plan.py --budget 500 --json                        # 程序化消费
```

参数备忘：`--fill` 最低饱腹度（默认 0.75，即至少用掉 75% 预算，防止"给了预算却只吃 200 卡"）；
`--max-items` 最多件数；`--min-protein` / `--max-sodium` 硬约束；`--dessert` 才允许甜品。

### 4. 解读结果，别照抄

拿到方案后必须自己判断：

- **钠**：成人每日 NRV 约 2000mg。方案钠 >1500mg 时**主动提醒**，别默认推荐。
- **结构**：只有小食+饮料、没有主食的"方案"，说明预算太紧或已被 `--exclude` 过滤，要说明清楚。
- **多样性**：`--top` 返回的是去重后的不同思路，逐个简要说明各自适合什么场景。

### 5. 社区套餐库（先查，别每次都重算）

用户没指定预算、或想看看别人怎么吃时，先翻社区库：

```bash
python scripts/combo.py list --max-budget 600 --sort protein
python scripts/combo.py list --goal low_sodium --tag 早餐
python scripts/combo.py show <id>
```

用户对自己的搭配满意，帮他存下来并生成分享素材：

```bash
python scripts/combo.py save --name "600 卡增肌晚餐" --items "板烧鸡腿堡,麦乐鸡5块,无糖可口可乐中杯" --goal high_protein --tags "增肌" --author "<用户ID>"
python scripts/combo.py share <id>      # 生成一行 MC1| 分享码
```

`--items` 的名字必须能在 `data/nutrition.csv` 里找到，否则会警告并按 0 计入——
保存前先核对。

### 6. 想下单才走这一步

用 `scripts/order.py`，它把整条链路串好了：

```bash
python scripts/order.py <combo_id> --city 深圳 --keyword 科技园          # 试算
python scripts/order.py <combo_id> --city 深圳 --keyword 科技园 --confirm  # 真下单
```

只有用户明确说「下单」「确认购买」之类才加 `--confirm`。**默认永远是试算。**

它的内部流程（需要门店时也可以手动走）：

1. `query-nearby-stores`（到店自取 beType=1 / 得来速 beType=5）或 `delivery-query-addresses` + `delivery-query-stores`（外送 beType=2）拿 `storeCode`
2. `query-meals` 查菜单，把配餐结果里的餐品名映射成 `productCode`
3. `query-store-coupons` 查可用券，`calculate-price` 算价（返回金额单位是**分**，展示要 /100）
4. **把门店、餐品、金额列给用户，等明确确认**再调 `create-order`

⚠️ 硬规则：`create-order` 会真实扣款。没有用户明确的"确认下单"指令，绝对不调用。

## 常见坑

- 营养数据里 `energyKj` 是千焦、`energyKcal` 才是大卡，别混用。
- 餐品名与菜单 `query-meals` 返回名**经常不一致**：营养数据里是「小薯条」「可乐中杯」，
  菜单里是「薯条」「可乐」。`order.py` 已做剥离规格 + 模糊匹配，但**匹配不上的会列出来**，
  必须如实告诉用户，不能替他猜一个看着像的。
- 社区套餐里的餐品可能已下架或该门店不售，`order.py` 会打印未匹配清单，照实转述。
- `list-nutrition-foods` 返回的是文本表格而非 JSON，用 `scripts/fetch_nutrition.py` 解析，别手写正则。
- Token 只从环境变量读，绝不写进任何文件、日志或对话输出。

## 输出示例

```
预算 600 kcal · 目标 balanced

1. 绝代双翅(469 kcal) + 蒜了吧黄油风味薄皮脆汁鸡-带骨里脊(126 kcal) + 锡兰红茶(2 kcal)
   合计 597 kcal | 蛋白 51 g | 脂肪 29 g | 碳水 27 g | 钠 1917 mg | 钙 98 mg | 剩余预算 3 kcal
```
