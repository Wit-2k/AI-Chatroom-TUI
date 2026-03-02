# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## 调试规则（非显而易见）

### LLM 错误不抛异常

- [`LLMClient.stream_chat()`](llm_client.py:40) 捕获所有异常后将错误信息 `yield` 为字符串流
- 错误格式：`\n[错误] API 调用失败: {str(e)}`
- 调用方收到的是包含错误文本的正常字符串，**不会触发 try/except**，需检查响应内容是否含 `[错误]` 前缀

### 总结解析失败的静默降级

- [`_parse_summary_response()`](engine.py:51) 三级解析全部失败时返回 `None`
- 引擎不抛异常，而是在终端显示黄色警告面板并跳过文件保存
- 调试总结问题时需检查 LLM 原始输出是否含合法 JSON 结构

### 配置加载失败回退

- [`ConfigLoader.load()`](config_loader.py:77) 失败时返回 `None`，`main.py` 会自动回退到 [`get_default_config()`](config_loader.py:158)
- 默认角色为 `fitness_coach` 和 `nutritionist`（定义在 [`config.py`](config.py:30)）
- 配置验证失败不会打印到日志，只通过 `rich.Panel` 显示在终端

### 随机性导致的不可复现问题

- [`_build_context_prompt()`](engine.py:131) 使用 `random.sample()` 抽取历史发言
- 每次运行结果不同是**预期行为**，调试时可临时将 `random.randint(1, 2)` 改为固定值

### Summary 目录

- 总结文件保存在运行目录下的 `Summary/` 子目录，首次运行时自动创建
- 文件名格式：`{sanitized_title}_{YYYYMMDD_HHMMSS}.md`
