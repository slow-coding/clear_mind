<div align="center">
  <img src="https://raw.githubusercontent.com/slow-coding/clear_mind/main/banner.png" alt="Clear Mind Banner" width="100%">
</div>

# Clear Mind（清心）

[English](README.md)

<div align="center">
  <img src="https://raw.githubusercontent.com/slow-coding/clear_mind/main/guide.gif" alt="Clear Mind 演示" width="100%">
</div>

**你和 AI 共管一个 Obsidian vault — 边界清晰，互不侵犯。**

Clear Mind 读懂你的笔记，理解你是谁，随时间推移和你一起成长。它记住你的模式、追踪你的变化、提出熵减建议。但它**永远不会碰你的笔记**——所有写入都限制在自己的文件夹内，代码层强制执行。

这不是又一个往你 vault 里乱塞文件的 AI。Clear Mind 是一个有纪律的共管者，清楚自己的位置。

## 核心理念：共管，不污染

大多数 AI 工具到处写文件，搞乱你精心维护的 vault。Clear Mind 不一样：

```
你的 Obsidian Vault
├── daily-notes/       ← 你的笔记。神圣不可侵犯。Agent 只读。
├── projects/          ← Agent 观察、理解，但绝不修改。
├── ideas/             ← 你的创意空间，永远是你的。
│
└── _clear_mind/       ← Agent 的空间。只在这里写入。
    ├── about_user.md      对你的持续理解（越写越懂你）
    ├── entropy_log.md     熵减观察记录
    ├── reflections/       每日反思：什么变了，意味着什么
    └── ...
```

**边界不只是提示词里的约束——它在代码中强制执行：**

- `write_agent_note` 和 `append_agent_note` 验证路径必须以 `_clear_mind/` 开头
- 路径穿越攻击被拦截（`../../etc/passwd` → 被拒绝）
- Agent 没有任何可以操作 `_clear_mind/` 以外的写入工具
- 即使 LLM "决定"要写到别处，工具层也会拒绝

**Agent 会做的事：**

- 读懂你的笔记，理解你的思维、项目和模式
- 在 `_clear_mind/about_user.md` 中建立你的画像——跨会话记住你
- 在 `_clear_mind/reflections/` 中写每日反思——追踪变化和意义
- 在 `_clear_mind/entropy_log.md` 中记录熵减机会——只建议，不行动

**Agent 绝不做的事：**

- 修改、删除或重新排列你的笔记
- 在 `_clear_mind/` 之外创建文件
- 未经你明确同意就执行任何操作

## 特性

- **本地优先** — 支持 LM Studio、Ollama 或任何 OpenAI 兼容 API，零云端依赖
- **Obsidian CLI 集成** — 使用官方 Obsidian CLI（v1.12+）进行所有 vault 操作
- **硬边界强制** — Agent 在代码层面无法写入 `_clear_mind/` 以外的位置，不只是提示词约束
- **心跳监控** — 每日 vault 变更检测，无变更时零 token 消耗
- **渐进成长** — `about_user.md` 随每次交互增长，建立真正的长期记忆

## 快速开始

### 前置条件

- Python 3.12+
- [Obsidian](https://obsidian.md) 桌面版运行中（v1.12+，需启用 CLI）
- 本地 LLM 服务（如 [LM Studio](https://lmstudio.ai)、[Ollama](https://ollama.com)）

### 安装

```bash
pip install clear-mind
```

### 初始化

```bash
clear-mind init
```

交互式设置会询问：
1. Obsidian vault 路径
2. LLM API 地址（默认：`http://localhost:1234/v1`）
3. API 密钥（默认：`lm-studio`）
4. 模型名称（默认：`qwen3.5-9b`）

这会创建 `.env` 文件并在 vault 中初始化 `_clear_mind/` 文件夹。

#### 示例：LM Studio + Qwen 3.5

1. 下载 [LM Studio](https://lmstudio.ai)，搜索并加载 `unsloth/qwen3.5-35b-a3b`
2. 启动本地服务器（默认端口 1234）
3. 运行：

```bash
clear-mind init
```

按提示输入：
```
Obsidian vault path: /Users/you/MyVault
LLM base URL [http://localhost:1234/v1]:       ← 回车
API key [lm-studio]:                            ← 回车
Model name [qwen3.5-9b]: unsloth/qwen3.5-35b-a3b
```

或者直接编辑 `.env`：

```env
CLEAR_MIND_VAULT_PATH=/Users/you/MyVault
CLEAR_MIND_BASE_URL=http://localhost:1234/v1
CLEAR_MIND_API_KEY=lm-studio
CLEAR_MIND_MODEL_NAME=unsloth/qwen3.5-35b-a3b
```

然后开始对话：

```bash
clear-mind chat
```

### 对话

```bash
clear-mind chat
```

启动交互式对话。Agent 可以读取你的笔记、搜索 vault、写反思——但只限于自己的文件夹。

### 心跳

单次运行（适合 cron）：

```bash
clear-mind heartbeat
```

常驻守护进程：

```bash
clear-mind serve
```

心跳扫描自上次运行以来的 vault 变更。如果没有任何变更，立即退出（零 token 消耗）。如果检测到变更，Agent 会阅读变更的笔记并更新理解。

### 诊断

```bash
clear-mind doctor
```

检查配置、vault 结构、Obsidian CLI 可用性和模型连接。

## 配置

所有设置从 `.env` 文件或带 `CLEAR_MIND_` 前缀的环境变量加载：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CLEAR_MIND_VAULT_PATH` | *（必填）* | Obsidian vault 路径 |
| `CLEAR_MIND_BASE_URL` | `http://localhost:1234/v1` | LLM API 地址 |
| `CLEAR_MIND_API_KEY` | `lm-studio` | API 密钥 |
| `CLEAR_MIND_MODEL_NAME` | `qwen3.5-9b` | 使用的模型 |
| `CLEAR_MIND_HEARTBEAT_CRON` | `0 9 * * *` | 心跳计划（每天上午 9 点） |
| `CLEAR_MIND_CHECKPOINTER_PATH` | `~/_clear_mind_state/checkpoints.db` | 状态持久化路径 |

## 真实用例

以下为 Clear Mind 使用 LM Studio + `unsloth/qwen3.5-35b-a3b` 在测试 vault 上的真实运行输出。

### 心跳：自动反思

Vault 中的笔记：
```markdown
daily/2026-03-28.md — "今天开始研究 gRPC，感觉流式传输比 REST 优雅很多。下周做 POC。
                      读了《思考快与慢》第 12 章，关于过度自信的偏见。"
daily/2026-03-29.md — "决定在项目里用 gRPC 替换 REST。流式 API 正好解决了实时推送的需求。
                      发现 Obsidian 标签命名不一致，需要统一。"

projects/distributed-system.md  — 分布式系统笔记（CAP 定理、Raft/Paxos、消息队列）
projects/decision-framework.md  — 技术选型方法论（边界→候选→打分→POC→回退）
```

运行 `clear-mind heartbeat` 后，Agent 阅读所有变更笔记并写入：

**`_clear_mind/about_user.md`** — 持续增长的用户画像：
```markdown
## Technical Focus
- Studying distributed systems: CAP theorem, consistency models, consensus algorithms
- Currently focused on gRPC for microservices, particularly streaming RPC
- Decided to replace REST with gRPC due to real-time push requirements
- Uses a structured decision framework: define boundaries → list options → score → POC → rollback

## Learning Habits
- Self-reflective about cognitive biases in coding ("this is simple" leading to debugging hell)
- Plans POCs before full adoption
```

**`_clear_mind/reflections/2026-03-29.md`** — 每日反思：
```markdown
## What Changed
The user made a concrete decision to migrate from REST to gRPC.
They didn't just switch because gRPC is "cooler" — they followed their
own methodology: identified the need (streaming), evaluated tradeoffs
(learning cost acceptable), and planned a POC before full migration.

There's a nice parallel between their technical work and personal growth:
studying overconfidence bias while simultaneously being disciplined enough
to do a POC rather than diving in headfirst.

## No Major Entropy Issues
The tag naming inconsistency is already on their TODO list — user is
aware and will address when ready.
```

**`_clear_mind/entropy_log.md`** — 熵追踪：
```markdown
## 2026-03-29: Tag Naming Inconsistency (Already Logged)
User noted tag system has mixed Chinese/English naming conventions.
Already on their TODO list. No action needed from agent.
```

### 对话：交互问答

```
You: 请读一下 daily/2026-03-29.md 然后告诉我你了解到了什么

Clear Mind: 从这篇日记中我了解到：
  • 决定在项目里用 gRPC 替换 REST，因为流式 API 能解决实时推送的需求
  • 在整理 Obsidian 的标签系统，发现了中英文混用的问题
  • 计划读《系统之美》第三章

  看起来你今天做了两个重要的决定：技术架构升级和知识管理系统优化。
  这两个都是熵减的好方向！
```

## Clear Mind vs Claude Code + Obsidian

| | Clear Mind | Claude Code + Obsidian |
|---|---|---|
| **运行方式** | 独立 CLI agent，本地运行或守护进程 | IDE 插件，需要编辑器会话 |
| **LLM** | 本地优先（LM Studio、Ollama） | 云端 API（Anthropic、OpenAI） |
| **Obsidian 集成** | 专用 Obsidian CLI 工具（14 个） | 通用文件读写 |
| **写入边界** | 硬性限制：agent 只能写入 `_clear_mind/` | 无边界：可写任意位置 |
| **心跳** | 内置：自动检测 vault 变更 | 无自动扫描 |
| **状态** | 跨会话持久化（SQLite checkpointer） | 单次会话，无跨会话记忆 |
| **成本** | 初始化后零成本（本地模型） | 按 token 计费 |

## 架构

```
clear_mind/
├── cli.py          Typer CLI（init, chat, heartbeat, serve, doctor）
├── agent.py        DeepAgents SDK Agent 组装
├── obsidian.py     Obsidian CLI 工具（14 个工具：读取、搜索、写入...）
├── config.py       pydantic-settings 配置管理
├── heartbeat.py    Vault 变更扫描 + 调度
└── prompts.py      系统提示词（身份、边界、心跳）
```

Agent 使用 [DeepAgents SDK](https://github.com/langchain-ai/deepagents) 在 [LangGraph](https://github.com/langchain-ai/langgraph) 上组装，通过 SQLite checkpointer 实现跨会话状态持久化。

## 许可证

MIT
