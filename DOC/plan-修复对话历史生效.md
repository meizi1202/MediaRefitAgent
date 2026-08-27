# 计划：修复对话历史生效

## Context

`parse_intent` 在 [backend/agent/langchain_agent.py:98](backend/agent/langchain_agent.py#L98) 依赖 `history` 参数构建对话上下文，固定取最近 20 条消息。但 `state["history"]` **从未被写入**，始终是空列表 `[]`，导致多轮对话无法记忆上下文。

## 根因分析

`analyze.py` 调用 `parse_intent` 时构建 `history` 的逻辑 ([analyze.py:362-381](backend/agent/nodes/analyze.py#L362-L381))：

```python
# 优先使用 state["messages"]
if session_id and len(state_messages) > 0:
    history = []  # 从 messages 构建
elif session_id:
    # 当前会话暂无消息，才尝试从 LangChain Memory 获取
    chat_history = get_conversation_history(session_id)
    history = [{"role": ...} for m in chat_history.messages]
```

**关键问题**：`state["messages"]` 是 `list[ConversationMessage]`（TypedDict），而 `parse_intent` 期望的是 `list[dict]` 格式 `{"role": str, "content": str}`。

`analyze.py:366-373` 的转换代码本身是对的，但这个转换逻辑只在 `session_id` 存在且 `state_messages > 0` 时才执行。

## 修复方案

在 `analyze.py` 中，调用 `parse_intent` **之前**，将 `state["messages"]` 同步到 `state["history"]`：

```python
# 在 analyze.py:381 之前添加
state["history"] = history  # history 已经是 [{"role": ..., "content": ...}] 格式
```

这样两处历史来源（`state["messages"]` 和 `MinMaxChatHistory`）就统一为 `state["history"]`，`parse_intent` 后续调用时 `history` 不为空。

### 修改文件

**唯一修改文件**: [backend/agent/nodes/analyze.py](backend/agent/nodes/analyze.py)

在第 381 行 `parsed = _llm_parse_intent(...)` 之后，添加：

```python
parsed = _llm_parse_intent(user_input, llm, history=history)

# 同步到 state["history"]，供后续调用 parse_intent 使用
state["history"] = history
```

## 验证方式

1. 启动服务：`python -m api.fastapi_app`
2. 发送两轮对话：
   - 第一轮：`"把视频转成竖屏"`
   - 第二轮：`"改用智能裁剪"`
3. 观察日志：`history length:` 应在第二轮时 > 0
