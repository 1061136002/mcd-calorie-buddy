# WorkBuddy 开发上下文

本文件记录 `mcd-calorie-buddy` 在 [WorkBuddy](https://www.workbuddy.cn) 中的真实开发过程，
用于麦当劳程序员创意开发大赛的 WorkBuddy 联动奖励核验。

---

## 一、需求来源

用户在 WorkBuddy 中完成麦当劳 MCP 连接器的配置后，提出希望参加
[麦当劳程序员创意开发大赛](https://github.com/M-China/mcd-developer-innovation-challenge)。
我（WorkBuddy）读取了赛事仓库与 `activityGuidelines.md`，梳理出硬性要求：

- 必须真实使用麦当劳 MCP 的能力
- 必须包含 `README.md` / `CONTEST_DECLARATION.md`（内容不可改）/ `MCP_INTEGRATION.md` / 源代码
- `mcp-config.example.json` 必须脱敏，只允许环境变量占位符
- 排名依据 GitHub Star，报名截止 2026-10-25 23:59

用户从官方给的几个方向（套餐推荐助手、麦门省钱助手、麦麦活动推荐助手）中选择了
**热量预算配餐**。

## 二、在 WorkBuddy 中的开发过程

### 1. 用 MCP 摸清数据（而非凭空设计）

我先实际调用了 `list-nutrition-foods`，发现它返回的是**紧凑文本表而非 JSON**：

```
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  猪柳麦满分,null,1288,308,16,16,24,781,213
```

这个发现直接决定了 `scripts/fetch_nutrition.py` 的解析实现方式。
数据共 160 条，字段完整（千焦/大卡/蛋白/脂肪/碳水/钠/钙），足以支撑约束求解。

同时也调用了 `query-my-account` 验证链路可用（返回 200）。

### 2. 用真实工具验证想法，而不是先写代码

先确认了数据长什么样，才决定"分类 + 预算内组合搜索 + 加权打分"的方案。

### 3. 迭代记录

| # | 问题 | 处理 |
|---|---|---|
| 1 | `plan.py` 读 CSV 返回 0 条 | 首字段名带 BOM，改用 `utf-8-sig` 读取 |
| 2 | 「冰浓浓黑巧中杯」被分类成主食 | 分类顺序错误，改为 甜品 → 小食 → 饮料 → 主食 的优先级 |
| 3 | `--goal low_sodium` 完全不起作用，结果钠仍 1900mg | 钠权重 0.5 相对蛋白质过低，调到 3.0，结果降到 254mg |
| 4 | 「蜜汁快乐」因含「汁」被判为饮料 | 把裸关键词 `汁` 换成 `果汁`/`苹果汁` |
| 5 | Top5 里 5 个方案都基于同一个主食 | 加入 `diversify()`：同一主食最多出现 2 次 |
| 6 | 两个方案只差一杯红茶（锡兰红茶 vs 伯爵红茶） | 加入 `dedupe()`：非饮料部分相同的组合只保留最优的一个 |
| 7 | 算法为刷"蛋白质/热量比"给出 200 卡方案，不顶饱 | 引入 `--fill` 最低饱腹度约束，默认至少用掉 75% 预算 |

每一轮都是实际跑命令看到结果后改的，不是凭推测。

### 4. 安全约束（贯穿全程）

- Token 全程只出现在环境变量和 MCP 配置里，未写入任何仓库文件、日志或输出
- `scripts/mcp_client.py` 在缺少 `MCD_MCP_TOKEN` 时直接报错退出
- `SKILL.md` 里写死了硬规则：`create-order` 必须等用户明确确认，禁止自动下单
- `.gitignore` 显式忽略 `mcp.json`

## 三、WorkBuddy 承担的工作

- 赛事规则梳理与时间节点提醒（报名仅剩约 3 天）
- 通过已连接的麦当劳 MCP 连接器获取真实营养数据并验证链路
- 项目结构设计、算法设计、三个脚本的全部代码编写
- 6 轮「跑命令 → 看输出 → 定位问题 → 修改」的调试循环
- 参赛文档（README / MCP_INTEGRATION / SKILL / 本文件）撰写

## 四、产物

```
SKILL.md                 WorkBuddy Skill 定义，可在 WorkBuddy 中直接调用
scripts/mcp_client.py    零依赖 MCP Streamable HTTP 客户端
scripts/fetch_nutrition.py   MCP 营养数据 → CSV
scripts/plan.py           配餐规划器（分类/搜索/打分/去重）
data/nutrition.csv        160 条真实营养数据快照
tests/test_plan.py        6 项测试，全部通过
```

安装 Skill：把本仓库放到 `~/.workbuddy/skills/mcd-calorie-buddy/` 即可在 WorkBuddy 中直接使用。
