# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## 编码规则（非显而易见）

### 角色格式双轨制

- `config.json` 保存时**始终写入旧格式**（`system_prompt` 字段），见 [`AppConfig.to_dict()`](config_loader.py:25)
- 读取时自动兼容新格式（`persona_prompt` + `interaction_examples`）
- 新增角色时若使用新格式，保存后会被转换为旧格式，**不可逆**

### LLM 消息构建方式

- 角色发言：`system_prompt` 单独作为 `system` 消息，**不通过** `stream_chat()` 的 `system_prompt` 参数传入，而是直接放入 `messages` 列表首位，见 [`run_discussion()`](engine.py:219)
- `stream_chat()` 的 `system_prompt` 参数实际上是**可选的冗余接口**，引擎内部未使用

### 上下文构建的随机性

- [`_build_context_prompt()`](engine.py:120) 每次随机抽取 1-2 条他人历史发言作为"需要回应的目标"
- 这是**有意设计**，不是 bug，目的是模拟真实辩论中的随机互动

### 总结提示词位置

- `SUMMARY_PROMPT` 定义在 [`config.py`](config.py:57)，不在 `engine.py` 中
- 总结调用时**没有** `system` 消息，只有 `user` 消息

### 文件名清理

- [`_sanitize_filename()`](engine.py:47) 截断为 50 字符，移除 `<>:"/\|?*`
- 保存路径格式：`Summary/{title}_{YYYYMMDD_HHMMSS}.md`

### max_rounds 约束

- [`_validate_config()`](config_loader.py:131) 强制限制 `max_rounds` 在 1-10 之间
- 超出范围会导致配置加载失败，回退到默认配置
