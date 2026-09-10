# 统一 Agent 意图处理逻辑

## Context

问题：视频拼接等多轮对话功能不稳定，原因是 `analyze_intent` 和 `handle_user_response` 中存在大量重复的业务逻辑。

- `analyze_intent`: 处理用户首次输入
- `handle_user_response`: 处理用户追问

两处都包含 compress、trim、concat、convert 的处理逻辑，导致：
1. 代码重复，难以维护
2. 首次输入和多轮对话行为不一致
3. 新增功能需要改两个地方

## 解决方案

**简化 `handle_user_response`：只做消息转发，不做业务逻辑**

核心思路：
1. `analyze_intent` 负责所有业务逻辑（意图识别、参数解析、状态设置）
2. `handle_user_response` 只负责把用户的追问内容合并到上下文，然后重新进入 `analyze_intent`

## 实现步骤

### 1. 简化 `handle_user_response`

修改 `backend/agent/nodes/routing.py`：

```python
def handle_user_response(state: VideoAgentState) -> VideoAgentState:
    """处理用户追问 - 简单合并到上下文后重新分析"""
    user_input = state["user_input"]
    pending_question = state.get("pending_question")

    # 简单拼接用户的回答和之前的问题
    if pending_question:
        combined_input = f"{pending_question}\n用户回答：{user_input}"
        state["user_input"] = combined_input

    # 重新进入 analyze_intent
    from agent.nodes.analyze import analyze_intent
    return analyze_intent(state)
```

### 2. 清理 `analyze_intent`

移除 `analyze_intent` 中专门给 LLM 解析结果的处理分支，因为多轮时会重新走 `analyze_intent`。

### 3. 路由逻辑简化

`select_strategy` 节点已移除，路由逻辑统一由 `should_proceed` 和 `handle_user_response` 处理。

## 验证

1. 重启后端服务
2. 测试视频拼接（未选标签）- 上传2个文件，发送"视频拼接"
3. 测试视频压缩（未选标签）- 发送"视频压缩"
4. 测试横竖屏转换 - 发送"转竖屏"
5. 测试多轮对话 - 先问一个问题，再追问
