# MCP 集成说明

本项目真实、实质性地使用了麦当劳中国官方 MCP Server
（`https://mcp.mcd.cn`，Streamable HTTP 传输）提供的能力。

## 接入方式

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

Token 只在环境变量中传递。`scripts/mcp_client.py` 会拒绝在没有 `MCD_MCP_TOKEN` 时发起请求，
仓库中不存在任何明文凭据。

## 实际使用的 Tool

### 核心：`list-nutrition-foods`

**这是整个项目的地基。** 它一次性返回麦当劳常见餐品的完整营养数据（能量 kJ/kcal、蛋白质、
脂肪、碳水化合物、钠、钙），共 160 条。没有它，配餐算法就是无米之炊。

调用与解析：

```
scripts/fetch_nutrition.py
  → mcp_client.call_tool("list-nutrition-foods")
  → 解析返回的文本表格（[160]{productName,...}: 行数据）
  → 去重 → data/nutrition.csv
```

该 Tool 返回的是紧凑文本表而非 JSON，因此 `fetch_nutrition.py` 里做了专用解析：
先正则切出 `[N]{字段声明}:` 之后的表体，再按逗号切分并做 null/数值转换。

### 下单链路（在 WorkBuddy Skill 中串联）

配餐结果算出来之后，要变成真正的一餐，还需要这些 Tool：

| Tool | 作用 | 在流程中的位置 |
|---|---|---|
| `query-nearby-stores` | 按位置查到店自取 / 得来速门店，返回 `storeCode`、`beCode` | 第 1 步：确定门店 |
| `delivery-query-addresses` | 查外送地址 | 第 1 步（外送场景） |
| `delivery-query-stores` | 查某地址可配送的门店 | 第 1 步（外送场景） |
| `query-meals` | 查当前门店在售菜单，拿到 `productCode` | 第 2 步：餐品名 → 编码 |
| `query-meal-detail` | 查套餐组成与特制选项 | 第 2 步（可选） |
| `query-store-coupons` | 查该门店可用优惠券 | 第 3 步：找优惠 |
| `calculate-price` | 算价（返回金额单位为**分**） | 第 3 步：报价 |
| `create-order` | 创建订单 | 第 4 步：**仅在用户明确确认后** |

`SKILL.md` 中定义了这条链路的完整调用顺序和参数传递规则
（`beType` / `orderType` / `beCode` 的对应关系），并硬性要求下单前必须把
门店、餐品、金额列给用户确认。

## 调用流程

```
用户："600 大卡能吃啥"
        │
        ▼
  list-nutrition-foods ──► data/nutrition.csv
        │
        ▼
   plan.py：分类 → 预算约束下搜索 → 加权打分 → 去重/多样性
        │
        ▼
   输出 Top N 方案（热量/蛋白/脂肪/碳水/钠/钙 + 剩余预算）
        │
        ▼ （用户要下单）
  query-nearby-stores / delivery-query-stores
        │
        ▼
  query-meals ──► 餐品名映射 productCode
        │
        ▼
  query-store-coupons ──► calculate-price ──► 用户确认 ──► create-order
```

## 业务价值

1. **把静态数据变成决策**：MCP 给了营养数据这个「原材料」，本项目在其上加了约束求解和
   目标函数，输出的是可直接执行的方案，而非数据罗列。
2. **覆盖真实决策维度**：预算（热量上限）、饱腹度下限、营养目标、忌口、分类排除，
   都是用户真实会权衡的东西。
3. **形成闭环**：从营养数据出发，最终能落到真实门店的真实订单上，
   把 MCP 的查询能力与交易能力串成一条完整链路。
4. **场景高频且长期存在**：减脂、健身、控钠是长期需求，不是一次性玩具。
