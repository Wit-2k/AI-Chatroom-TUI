# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## 文档与代码理解（非显而易见）

### 两套角色系统并存

- [`config.py`](config.py:30) 中的 `PERSONAS` 字典是**硬编码的默认角色**（健身教练、营养师），仅作回退用
- [`config.json`](config.json) 是**运行时角色**，优先级更高，支持任意数量角色
- 两套系统互不干扰，`config.json` 不存在时才使用 `PERSONAS`

### `stream_chat()` 的 `system_prompt` 参数是死代码

- [`LLMClient.stream_chat()`](llm_client.py:16) 有 `system_prompt` 可选参数，但 [`DiscussionEngine`](engine.py:26) **从不传入此参数**
- 引擎直接将 `system` 消息放入 `messages` 列表首位，绕过该参数
- 该参数仅在 `wizard.py` 的 AI 生成角色功能中间接使用

### `run_discussion()` vs `run()` 的区别

- [`run_discussion()`](engine.py:197) 是 `AsyncGenerator`，逐条 `yield (speaker, content)`
- [`run()`](engine.py:296) 是对 `run_discussion()` 的简单包装，消费所有 yield 后返回 `state`
- 外部调用应使用 `run()`；需要实时流式处理每条发言时才用 `run_discussion()`

### wizard.py 的 AI 生成角色功能

- [`ConfigWizard`](wizard.py:40) 内置调用 LLM 自动生成角色的功能（选项 4）
- 生成提示词 `PERSONA_GENERATION_PROMPT` 定义在 [`wizard.py`](wizard.py:16) 顶部
- 生成的角色使用旧格式（`system_prompt`），不使用新格式

### 互动规范模板的注入位置

- [`_INTERACTION_RULES_TEMPLATE`](config_loader.py:12) 在**读取**新格式角色时自动追加到 `system_prompt` 末尾
- 旧格式角色不会自动追加此模板，需在 `system_prompt` 中手动包含互动规范
