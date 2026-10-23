# 🍔 麦麦热量管家 · mcd-calorie-buddy

> 给一句热量预算，用麦当劳中国的**真实营养数据**算出最划算的一餐。
> 减脂期也能吃麦当劳，只要算得清。

Built for [麦当劳程序员创意开发大赛](https://github.com/M-China/mcd-developer-innovation-challenge)，基于
[麦当劳 MCP Server](https://github.com/M-China/mcd-mcp-server) 开发。

---

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

## 安装

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
├── data/nutrition.csv          # 营养数据快照（160 条）
├── scripts/
│   ├── mcp_client.py           # 极简 MCP Streamable HTTP 客户端
│   ├── fetch_nutrition.py      # 从 MCP 拉数据 → CSV
│   └── plan.py                 # 配餐规划器
└── tests/test_plan.py
```

## 跑测试

```bash
python tests/test_plan.py
```

## 免责声明

营养数据来自麦当劳中国官方 MCP，仅作参考，实际以门店为准。钠摄入建议请遵医嘱。
本项目为参赛作品，与麦当劳官方无隶属关系；麦当劳名称和商标归其各自所有者所有。
