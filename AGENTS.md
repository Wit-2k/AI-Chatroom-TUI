# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## 项目概述

多智能体 AI 辩论系统（AI 讨论室）。多个 AI 角色围绕主题展开多轮辩论，最终生成结构化 Markdown 总结报告。

## 运行命令

```bash
# 安装依赖（需 Python >= 3.13，使用 uv）
uv sync

# 运行程序
python main.py
# 或
uv run python main.py
```

无测试框架，无 lint 配置。

## 环境配置

复制 `.env.example` 为 `.env`，填入：

- `OPENAI_API_KEY` — 必填
- `OPENAI_BASE_URL` — 默认 `https://api.openai.com/v1`，支持 DeepSeek 等 OpenAI 兼容 API
- `MODEL_NAME` — 默认 `gpt-4o-mini`

## 架构关键点

- **`config.json`** — 运行时配置文件，支持两种角色格式（见下方）
- **`Summary/`** — 讨论总结自动保存目录（运行时自动创建）
- `DiscussionEngine` 是核心，通过 `async for` 驱动，`run()` 是入口

## config.json 两种格式（非显而易见）

`config.json` 中角色支持**新旧两种格式**，`config_loader.py` 的 [`AppConfig.from_dict()`](config_loader.py:41) 自动兼容：

**新格式**（推荐）：

```json
{
  "name": "角色名",
  "role_description": "角色描述",
  "persona_prompt": "角色核心人设提示词",
  "interaction_examples": "「你说的X，我认为……」等互动句式示例"
}
```

`persona_prompt` + `interaction_examples` 会被自动拼接为完整 `system_prompt`，互动规范模板在 [`_INTERACTION_RULES_TEMPLATE`](config_loader.py:12) 中定义。

**旧格式**（兼容）：直接使用 `system_prompt` 字段。

## LLM 调用约定

- 所有 LLM 调用通过 [`LLMClient.stream_chat()`](llm_client.py:16) 进行流式输出
- 每次角色发言：`system` 消息 = 角色 `system_prompt`，`user` 消息 = 由 [`_build_context_prompt()`](engine.py:120) 构建的上下文
- 总结生成时 `max_tokens=2000`，角色发言默认 `max_tokens=500`
- `temperature` 固定为 `0.7`

## 总结 JSON 解析（三级容错）

[`_parse_summary_response()`](engine.py:51) 有三级解析策略：

1. 直接 `json.loads`
2. 修复字符串内裸换行后再解析
3. 正则逐字段提取（兜底）

LLM 返回的总结 JSON 中 `content` 字段必须是单行字符串，换行用 `\n` 表示。

## 代码风格

- 全部使用 `@dataclass`，无 Pydantic
- 异步：`asyncio` + `AsyncOpenAI`，入口 `asyncio.run(main())`
- UI 渲染：`rich`（`Panel`、`Console`、`Live`、`Prompt`）
- 类型注解：函数签名均有类型注解，返回 `Optional[X]` 表示可能失败
- 错误处理：LLM 错误直接 `yield` 错误字符串到流中，不抛异常
