# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## 架构约束（非显而易见）

### 数据流单向性

- `DiscussionState` 只追加消息（[`add_message()`](models.py:34)），无删除/修改接口
- 历史记录在整个讨论生命周期内不可变，总结基于完整历史生成

### 角色格式转换不可逆

- [`AppConfig.to_dict()`](config_loader.py:25) 保存时**始终输出旧格式**（`system_prompt`）
- 新格式（`persona_prompt` + `interaction_examples`）读入后立即被合并为 `system_prompt`，原始字段丢失
- 设计意图：保持 `config.json` 格式稳定，避免多版本格式共存

### `DiscussionEngine` 不是无状态的

- `DiscussionEngine` 持有 `DiscussionState` 实例，**不可复用**于多次讨论
- 每次讨论必须创建新的 `DiscussionEngine` 实例（见 [`main.py`](main.py:119)）

### 总结无 system 消息（有意设计）

- 角色发言：`[system(角色人设), user(上下文)]`
- 总结生成：`[user(含完整对话的总结提示)]`，**无 system 消息**
- `SUMMARY_PROMPT` 已将角色定义（"你是总结专家"）内嵌在 user 消息中

### 并发模型

- 角色发言**串行**执行（`for speaker in self.personas`），每条发言间有 `asyncio.sleep(0.5)` 间隔
- 无并行 LLM 调用，设计上避免了竞态条件
- 扩展为并行时需重构 `DiscussionState` 的消息追加逻辑

### 配置与运行时分离

- [`config.py`](config.py) — 静态默认值和提示词模板（代码级）
- [`config.json`](config.json) — 用户运行时配置（文件级）
- 两者通过 [`ConfigLoader`](config_loader.py:67) 桥接，`config.py` 中的 `PERSONAS` 仅作最终回退
