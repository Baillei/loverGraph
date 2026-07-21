# loverGraph
<<<<<<< HEAD

多智能体结构化对话模拟器（LangGraph）。当前主题为相亲组局，内核可复用于任意「多角色 + 阶段流程 + 主持控场」场景。

## 快速开始

```bash
cd loverGraph
pip install -e .
# 配置 config/api_keys_local.py 或环境变量 DEEPSEEK_API_KEY
lover-sim --random --dry-run    # 预览场景，不调用 LLM
lover-sim --random              # 运行完整 simulation
```

常用 CLI：`--random` / `--scenario <path>` / `--seed <n>` / `--budget-mode matchmaker_turns|time` / `--max-rounds` / `--max-steps`

---

## 通用架构

本项目采用 **LangGraph 有状态图 + 确定性 Harness + LLM 角色节点** 的分层设计，把「流程控制」和「内容生成」拆开，便于调试、审计和换皮。

### 执行流水线

```
SCRIPT（固定开场）
  → DETERMINISTIC（阶段推进 / Harness 教练）
  → MODEL（路由到当前发言角色）
  → DETERMINISTIC（发言校验 / 纪律打断）
  → … 循环 …
  → DETERMINISTIC（收尾）
  → MODEL_BATCH（最终结论 JSON）
```

节点按计算类型分为四类（见 `harness/kinds.py`）：

| 类型 | 是否调用 LLM | 典型用途 |
|------|-------------|----------|
| `SCRIPT` | 否 | 固定仪式台词、主持打断话术 |
| `DETERMINISTIC` | 否 | 阶段机、路由、预算统计、校验器 |
| `MODEL` | 是 | 各角色 think → speak 结构化生成 |
| `MODEL_BATCH` | 是 | 会话结束后一次性汇总输出 |

**设计意图**：确定性节点保证流程可复现；LLM 只负责「在当前约束下说什么」，不把阶段推进完全交给模型。

### LangGraph 状态（`SessionState`）

共享 TypedDict，关键字段：

| 字段 | 作用 |
|------|------|
| `session_input` / `scenario` | 运行时输入 + 完整场景定义 |
| `current_phase` / `phase_round` | 阶段 FSM 位置 |
| `dialogues` | 追加式对话轮次列表（`Annotated[..., operator.add]`） |
| `next_speaker` | 主持角色路由下一发言者 |
| `harness_context` | Harness 写入的 pacing 提示（模型只读） |
| `party_turn_buffer` | 当事人轮次先缓冲，校验通过后再写入 `dialogues` |
| `verdict` | 最终结构化结论 |

路由由 **主持 agent 的结构化输出**（`next_speaker`, `end_session`）驱动，Harness 可在阶段未饱满时 **否决过早结束**。

### Think / Speak 双通道 Agent

每个 MODEL 角色节点统一走 `run_thinking_agent()`：

1. 组装 system prompt：`shared format` + `role default` + `phase overlay` + `scenario slice` + `persona` + `skills context`
2. LLM 输出 Pydantic 模型 `ThinkingOutput`：`think`（内部推理）+ `speak`（对外文本）+ 可选 `emotion` / `next_speaker` 等
3. 仅 `speak` 进入对话历史；`think` 用于日志与调试

这是常见的 **CoT 与播出分离** 模式：推理可长，播出可控，且便于 JSONL 下游消费。

### Harness：确定性阶段教练

`harness/` 在每个 MODEL 轮次之前运行，**不调用 LLM**，只做：

- 按阶段统计已用轮次 / 词数，对比 `phase_schedule` 窗口
- 输出 `phase_pace_status`：`underfilled` / `in_band` / `approaching` / `overdue`
- 决定是否 `forbid_phase_advance`（防止主持过早转段或散场）
- 将 `coach_message` 注入主持角色的 skills 上下文

等价于给 LLM 套一层 **硬约束的 pacing controller**，适合任何「分阶段、有时长预算」的多轮对话。

### 预算系统（`constraints/`）

支持两种互斥预算维度：

| 模式 | 控什么 | 适用场景 |
|------|--------|----------|
| `matchmaker_turns` | 主持发言次数 | 默认；阶段窗口按主持轮切分 |
| `time` | 总词数 / 估算时长 | 模拟真实时间限制 |

软预算触发提醒，硬预算触发 `force_close` 进入收尾。预算参数可在场景 JSON 或 CLI 覆盖。

### Skills：角色 gated 上下文注入

Skills **不是**独立 agent，而是在主 LLM 调用前 **预检索、拼 prompt** 的工具链：

```
allowed_skills(role) → run_skills() → context_text + tool_calls log
```

典型 skill 类型（可迁移到其他域）：

| 模式 | 示例 |
|------|------|
| 本地 RAG | 规则/合约条文检索 → 拼入 prompt |
| 结构化清单 | 按角色过滤的信息列表 |
| 流程提示 | 当前阶段程序规则 |
| 策略 hint | 角色专属话术建议 |
| 时钟 / 教练 | 预算倒计时 + Harness 输出 |

所有 tool 调用写入 `tool_calls`，便于复现「模型当时看到了什么」。

### 场景与信息切片（`scenario/`）

`MatchScenario` 是静态世界模型；运行时通过 `build_role_scenario_context(scenario, role)` **按角色切片**，避免把全量 synopsis 灌给每个 agent。

通用模式：

- **5W1H** 背景摘要
- **信息池 + bundle**：全局 N 条信息，各方仅公开子集（PP/DP 泛化为 male_bundle / female_bundle）
- **可见性矩阵** `known_to` / `content_access`：支持信息差、传闻、隐瞒
- **private_knowledge**：仅该角色可见的隐藏上下文
- **value_tensions**：价值观冲突轴，驱动对话立场

操作者可在 CLI 看完整 `narrative.synopsis`；LLM 只看切片，降低剧透和 token 浪费。

### Prompt 组合策略（`prompts/`）

```
_shared/output_format.md
  + {role}/default.md
  + {role}/{phase}.md        # 阶段 overlay
  + matchmaker/phase_pace.md # 仅主持角色
```

换主题时通常 **只改 prompts/ 与 data/**，图结构与 Harness 可复用。

### 输出（JSONL）

`data/output/*.jsonl` 按行记录多种 record type，例如：

- `meta` / `persona`：场景与人设快照
- `turn`：每轮 think/speak/emotion/skills
- `verdict`：最终结构化结论
- `compliance`：阶段完整性审计

适合对接数字人、评测 pipeline 或 fine-grain 回放。

---

## 本仓库的业务映射（换皮参考）

| 通用概念 | loverGraph 实例 |
|----------|-----------------|
| 主持 / 仲裁 | 媒婆 `matchmaker` |
| 当事方 ×2 | 男方 / 女方 |
| 顾问 ×2 | 男方家长 / 女方家长 |
| 证据池 | 条件池（颜值、资产、隐疾…） |
| 法条 RAG | 媒婆合约 RAG |
| 判决 | 结婚 / 没谈成 |

同内核可参考 [courtGraph](../courtGraph)（庭审主题）。

---

## 目录结构

```
loverGraph/
├── src/lover_graph/
│   ├── graph/          # LangGraph 编译、state、edges、nodes
│   ├── harness/        # 确定性阶段教练
│   ├── skills/         # 角色 skills 注册与 runner
│   ├── tools/          # RAG、清单、流程规则、时钟
│   ├── scenario/       # 加载、随机生成、角色切片
│   ├── constraints/    # 预算跟踪
│   ├── prompts/        # prompt loader
│   └── output/         # JSONL writer、合规审计
├── prompts/            # 各角色 markdown prompt
├── data/
│   ├── contracts/      # RAG 语料
│   ├── procedure/      # 阶段规则、开场脚本
│   └── scenarios/      # 场景 JSON
└── langgraph.json      # LangGraph CLI / Studio 入口
```

## 扩展指南

1. **加角色**：`Role` enum → `roles.py` 节点 → `SPEAKER_NODES` → `prompts/{role}/` → `ROLE_SKILLS`
2. **加阶段**：`Phase` enum → `match_phases.json` → 各 role phase overlay → `PHASE_ORDER` / harness 窗口
3. **加 skill**：`registry.py` 登记 → `runner.py` 实现 → 可选新 tool
4. **换新域**：重写 `data/` + `prompts/`，保留 graph / harness / skills 框架

## License

MIT — 请自行配置 LLM API Key，勿将密钥提交到仓库。
=======
多智能体结构化对话模拟器（LangGraph）。当前主题为相亲组局，内核可复用于任意「多角色 + 阶段流程 + 主持控场」场景。
>>>>>>> 500f7991060f9c3df6118e9451fee2659ce1ea46
