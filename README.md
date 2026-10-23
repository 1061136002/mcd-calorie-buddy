# 🍔 麦麦热量管家 · mcd-calorie-buddy

> 给一句热量预算，用麦当劳中国的**真实营养数据**算出最划算的一餐。
> 减脂期也能吃麦当劳，只要算得清。

**不想装环境？直接用网页版** 👉 https://1061136002.github.io/mcd-calorie-buddy/

输入大卡数，网页直接给出带图的推荐组合；还能自己勾选餐品分析营养、
浏览社区里别人分享的套餐。数据全部内置在页面里，不连后端、不上传任何信息。

Built for [麦当劳程序员创意开发大赛](https://github.com/M-China/mcd-developer-innovation-challenge)，基于
[麦当劳 MCP Server](https://github.com/M-China/mcd-mcp-server) 开发。

---

## 三件事

1. **配餐** — 给热量预算，算出最优组合（`plan.py`）
2. **社区** — 保存、浏览、分享别人的套餐（`combo.py`）
3. **下单** — 把任意社区套餐一键下到门店（`order.py`）

## 它解决什么问题

麦当劳官网和各路 App 只告诉你「某个汉堡 513 大卡」，但没人回答真正的问题：

> **我今天只剩 600 大卡，还能吃麦当劳吗？吃什么最划算？**

手工算要翻十几个餐品、做加减法、还要权衡蛋白质和钠。这个工具把这件事变成一条命令：

```bash
$ python scripts/plan.py --budget 600 --goal balanced --top 3

预算 600 kcal · 目标 balanced

1. 绝代双翅(469 kcal) + 蒜了吧黄油风味薄皮脆汁鸡-带骨里脊(126 kcal) + 锡兰红茶(2 kcal)
   合计 597 kcal | 蛋白 51 g | 脂肪 29 g | 碳水 27 g | 钠 1917 mg | 钙 98 mg | 剩余预算 3 kcal
   结构: 主食、小食、饮料
```

## 网页版（不用装任何东西）

<https://1061136002.github.io/mcd-calorie-buddy/>

三个标签页：

- **智能配餐** — 输入**热量预算**和**价格上限**，选营养目标，实时给出带实物图和价格的推荐组合
  - 排序：推荐 / 价格低→高 / 价格高→低 / 蛋白质 / 热量
  - 「换一批」翻页看更多方案（600 卡均衡档有 50+ 个方案）
  - 「只用在售餐品」默认开启，过滤掉营养库里已下架的季节限定
- **自己搭配** — 按分类浏览全部 158 个餐品，点一下加进套餐，实时看热量、价格、钠合计
- **社区套餐** — 浏览别人分享的搭配（含价格），一键载入自己改

纯静态页面，算法在浏览器里跑，数据打包在 `docs/data/` 里。
**不连后端、不需要 Token、不收集任何信息**——这也是为什么它能直接挂在 GitHub Pages 上。

本地想跑：

```bash
cd docs && python -m http.server 8000
# 打开 http://localhost:8000
```

数据更新后重新生成：`python scripts/build_web_data.py`

## 安装（命令行版）

只需要 Python 3.8+，**零第三方依赖**。

```bash
git clone https://github.com/1061136002/mcd-calorie-buddy.git
cd mcd-calorie-buddy
```

仓库自带一份从 MCP 拉取的营养数据快照 `data/nutrition.csv`（160 个餐品），开箱即用。

想拿最新数据，去 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) 申请 MCP Token：

```bash
export MCD_MCP_TOKEN='你的 token'
python scripts/fetch_nutrition.py --out data/nutrition.csv
```

> 把 Token 写进环境变量即可，代码里没有任何硬编码凭据。
> WorkBuddy 用户请复制 `mcp-config.example.json` 的内容到连接器配置。

## 用法

```bash
# 基础：600 大卡，均衡
python scripts/plan.py --budget 600

# 增肌：要高蛋白，蛋白质至少 30g
python scripts/plan.py --budget 600 --goal high_protein --min-protein 30

# 控钠：钠不超过 1000mg
python scripts/plan.py --budget 500 --goal low_sodium --max-sodium 1000

# 生酮/低碳
python scripts/plan.py --budget 400 --goal low_carb

# 控制花费：套餐总价不超过 45 元（需要 data/menu.json）
python scripts/plan.py --budget 600 --max-price 45

# 只保留当前门店还在卖的餐品
python scripts/plan.py --budget 600 --in-stock

# 不喝饮料（省下的预算全给吃的）
python scripts/plan.py --budget 500 --exclude drink

# 避开某些东西 + 允许甜品
python scripts/plan.py --budget 700 --avoid 菠萝,香芋 --dessert

# 给程序用
python scripts/plan.py --budget 500 --json
```

### 全部参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget` | **必填** | 热量预算（kcal） |
| `--goal` | `balanced` | `balanced` / `high_protein` / `low_sodium` / `low_carb` / `high_calcium` |
| `--exclude` | 无 | 排除分类：`main` / `side` / `drink` / `dessert` |
| `--dessert` | 关 | 允许甜品入局 |
| `--fill` | `0.75` | 最低饱腹度，至少用掉预算的比例 |
| `--max-items` | `4` | 最多几件 |
| `--min-protein` | `0` | 最低蛋白质（g）硬约束 |
| `--max-sodium` | 无 | 最高钠（mg）硬约束 |
| `--avoid` | 无 | 避开含这些关键词的餐品 |
| `--top` | `5` | 返回几个方案 |
| `--json` | 关 | 输出 JSON |

## 社区套餐库

一个人算得再准，也不如一千个人各贡献一个搭配。社区库在
[`community/combos.json`](community/combos.json)，已有 8 个真实套餐。

```bash
# 浏览：600 卡以内，按蛋白质排序
python scripts/combo.py list --max-budget 600 --sort protein

# 按目标/标签/作者筛选
python scripts/combo.py list --goal low_sodium
python scripts/combo.py list --tag 早餐

# 看详情
python scripts/combo.py show ls-600-d470

# 保存自己的
python scripts/combo.py save --name "600 卡增肌晚餐" \
  --items "板烧鸡腿堡,麦乐鸡5块,无糖可口可乐中杯" \
  --goal high_protein --tags "增肌,晚餐" --author "你的ID"

# 分享：生成一行分享码发给朋友
python scripts/combo.py share <套餐id>
python scripts/combo.py import "MC1|..."

# 提 PR 让所有人都能看到
python scripts/combo.py submit <套餐id>
```

**分享 = 提 PR**，没有后端、没有账号。合并后所有人 `list` 都能刷到你的搭配。
完整流程见 [community/CONTRIBUTING.md](community/CONTRIBUTING.md)。

## 一键下单

看到别人的套餐想直接吃？一条命令从套餐走到订单：

```bash
export MCD_MCP_TOKEN='你的 token'

# 试算（默认，不下单）
python scripts/order.py ls-600-d470 --city 深圳 --keyword 科技园

# 确认无误后加 --confirm 才真正下单
python scripts/order.py ls-600-d470 --city 深圳 --keyword 科技园 --confirm
```

它会：查门店 → 拉菜单 → 把套餐里的餐品名匹配成 `productCode` → 算价 → （确认后）下单。

⚠️ 两个设计上的克制：

- **不加 `--confirm` 永远是试算**，不会创建订单
- 匹配不上的餐品会**明确列出来**而不是猜一个。麦当劳菜单经常上下架，
  社区套餐里的餐品可能你附近门店没有——宁可告诉你「匹配失败」，也不能给你点错的东西

## 它是怎么算的

1. **分类**：按关键词把 160 个餐品分成主食/小食/饮料/甜品（甜品和小食优先匹配，避免「柠檬拉明顿」被当成饮料）。
2. **搜索**：在「主食 × 小食 × 饮料」的组合空间里做深度优先搜索，每个分类按热量升序排列，超出预算立即剪枝。
3. **打分**：不同目标用不同权重——

   ```
   score = w_protein × 蛋白质 + w_calcium × 钙/100 − w_sodium × 钠/100 − w_carb × 碳水
   ```

   `high_protein` 把蛋白质权重拉到 1.8，`low_sodium` 把钠权重拉到 3.0。
4. **去重与多样性**：只差一杯红茶的两个方案会被合并；同一个主食最多出现两次，保证给出的是不同思路而不是同一方案的变体。

`--fill 0.75` 是个刻意的设计：不加这个约束，算法会为了刷高「蛋白质/热量比」给出一份 200 卡的鸡胸肉，看着漂亮但根本不顶饱。

## 目录结构

```
├── SKILL.md                    # WorkBuddy Skill 定义
├── README.md
├── MCP_INTEGRATION.md          # 用了哪些 MCP 能力
├── CONTEST_DECLARATION.md      # 官方参赛声明（未改动）
├── mcp-config.example.json     # 脱敏配置，仅环境变量占位符
├── workbuddy.md                # WorkBuddy 开发上下文
├── community/
│   ├── combos.json             # 社区共享套餐库
│   └── CONTRIBUTING.md         # 怎么分享自己的套餐
├── data/nutrition.csv          # 营养数据快照（160 条）
├── docs/                       # 网页版（GitHub Pages 源目录）
│   ├── index.html
│   ├── app.js                  # 配餐算法的 JS 实现（与 plan.py 结果一致）
│   ├── styles.css
│   └── data/                   # 由 build_web_data.py 生成
├── scripts/
│   ├── mcp_client.py           # 极简 MCP Streamable HTTP 客户端
│   ├── fetch_nutrition.py      # 从 MCP 拉数据 → CSV
│   ├── plan.py                 # 配餐规划器
│   ├── combo.py                # 社区套餐库：保存/浏览/分享/导入
│   ├── order.py                # 社区套餐一键下单
│   ├── build_images.py         # 从菜单接口拉餐品图 → data/images.json
│   └── build_web_data.py       # 生成网页版数据
└── tests/
    ├── test_plan.py
    └── test_combo.py
```

## 跑测试

```bash
python tests/test_plan.py
python tests/test_combo.py
```

12 项，覆盖餐品分类、预算约束、低钠目标有效性、社区库营养值一致性、
餐品名到菜单编码的匹配（含杯型/规格剥离与模糊匹配）。

## 免责声明

营养数据来自麦当劳中国官方 MCP，仅作参考，实际以门店为准。钠摄入建议请遵医嘱。
本项目为参赛作品，与麦当劳官方无隶属关系；麦当劳名称和商标归其各自所有者所有。
