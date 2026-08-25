# Agent 状态机设计

## 概述

MediaRefitAgent 是一个基于 LangGraph 状态机的多轮对话式视频处理 Agent。用户可以通过自然语言描述需求，Agent 自动完成意图分析和执行相应的视频处理操作。

---

## 状态流转图

```
                                    ┌─────────────────────┐
                                    │       __entry__       │ ← 入口
                                    └──────────┬──────────┘
                                               │
                          ┌────────────────────┴────────────────────┐
                          │                                         │
                          ▼                                         │
           ┌──────────────────────────────┐                        │
           │  pending_question / combined_  │                        │
           │  input / current_step 存在?    │                        │
           └──────────────┬───────────────┘                        │
                          │ Yes                                     │ No
                          ▼                                         ▼
           ┌─────────────────────────────┐    ┌────────────────────────────┐
           │   handle_user_response       │    │      analyze_intent         │
           │   (预解析参数 + 发送消息)     │    │      (意图分析/LLM)          │
           └─────────────┬───────────────┘    └─────────────┬────────────┘
                         │                                   │
                         │ 参数完整时                          │ 参数完整时
                         ▼                                   ▼
           ┌─────────────────────────────┐    ┌────────────────────────────┐
           │   直接路由到 execute_xxx     │    │    路由到 execute_xxx       │
           └─────────────────────────────┘    └────────────────────────────┘
                                                │ 参数不完整时
                                                │ (设置 pending_question)
                                                ▼
                                   ┌─────────────────────────────┐
                                   │   should_proceed 判断      │
                                   │   → waiting_for_user       │
                                   │   → confirm_complete        │
                                   └─────────────────────────────┘
```

---

## 入口路由 (`route_from_entry`)

```python
def route_from_entry(state: VideoAgentState) -> str:
    current_step = state.get("current_step")
    pending_question = state.get("pending_question")
    combined_input = state.get("combined_input")
    
    # combined_input 存在 → handle_user_response（用户回答了追问）
    if combined_input:
        return "handle_user_response"
    # pending_question 存在 → handle_user_response（等待用户回答下一轮）
    if pending_question:
        return "handle_user_response"
    # current_step 是 waiting_for_user → handle_user_response
    if current_step == "waiting_for_user":
        return "handle_user_response"
    # 其他情况 → analyze_intent
    return "analyze_intent"
```

---

## 节点说明

| 节点 | 文件 | 职责 |
|------|------|------|
| `__entry__` | video_agent.py | 入口节点，根据 `pending_question` / `combined_input` 决定路由 |
| `analyze_intent` | nodes/analyze.py | 解析用户意图，提取功能类型和参数，设置 `pending_question` |
| `handle_user_response` | nodes/routing.py | 处理用户追问，预解析参数后直接执行或发送追问消息 |
| `execute_xxx` | nodes/execute.py | 执行具体视频处理操作 |
| `confirm_complete` | nodes/execute.py | 结束流程 |
| `waiting_for_user` | video_agent.py | 空节点，标记本轮结束等待用户输入 |

---

## 关键状态变量

| 变量 | 说明 |
|------|------|
| `pending_question` | 记录还缺什么参数，如 `"请选择比例/策略"` |
| `combined_input` | 用户回答拼接后的输入 |
| `current_step` | 当前节点名，用于路由判断 |
| `new_user_input` | 新一轮请求的用户输入 |

---

## 用户输入优先级

```python
user_input = state.get("new_user_input") or state.get("combined_input") or state["user_input"]
```

---

## `handle_user_response` 流程

```
用户回答到达（new_user_input）
    │
    ▼
有 pending_question？否 → 设置 current_step="analyze_intent"，返回
    │
    ▼ 是
_get_missing_params() 获取仍缺失的参数
    │
    ▼
_parse_answer_params() 关键词预解析
    │
    ├── 全部补全 → current_step="execute_xxx"，返回
    │
    └── 仍有缺失
        • 更新 pending_question 为剩余缺失参数
        • 发送追问消息给用户
        • current_step="waiting_for_user"，返回
```

---

## `should_proceed` 路由逻辑

```python
def should_proceed(state: VideoAgentState) -> str:
    current_step = state.get("current_step")
    pending_question = state.get("pending_question")
    all_params = state.get("all_params_provided", False)
    feature = state.get("current_feature")

    # 正在执行中的节点
    if current_step in EXECUTE_NODES:
        return current_step

    # waiting_for_user → handle_user_response
    if current_step == "waiting_for_user":
        return "handle_user_response"

    # 参数完整 → 对应 execute_* 节点
    if feature and all_params:
        return f"execute_{feature}"

    # 参数不完整 + pending_question → waiting_for_user
    if pending_question:
        return "waiting_for_user"

    # 其他 → confirm_complete
    return "confirm_complete"
```

---

## 多轮状态流转示例（横竖屏转换）

### Turn 1: "转竖屏"

```
route_from_entry → analyze_intent
    • 识别 convert，缺比例/策略
    • pending_question = "请选择比例/策略"
    • 发送消息: "请问选择哪个比例？9:16/4:5/1:1"
    • current_step = None
should_proceed: pending_question 存在 → waiting_for_user
waiting_for_user → confirm_complete（结束）
```

### Turn 2: "9:16"

```
route_from_entry: pending_question 存在 → handle_user_response
    • 解析 "9:16" → ratio 补全，仍缺策略
    • pending_question = "请选择策略"
    • 发送消息: "请问选择哪个策略？"
    • current_step = "waiting_for_user"
should_proceed: current_step="waiting_for_user" → waiting_for_user
waiting_for_user → confirm_complete（结束）
```

### Turn 3: "填充黑边"

```
route_from_entry: pending_question 存在 → handle_user_response
    • 解析 "填充黑边" → strategy 补全，参数完整
    • current_step = "execute_transform"
should_proceed: current_step="execute_transform" → execute_transform
execute_transform → confirm_complete（结束）
```

---

## 参数完整性判断

| 功能 | 必需参数 | 判断条件 |
|------|---------|---------|
| `convert` | 方向 + 比例 + 策略 | `orientation_explicit and strategy_explicit and ratio_explicit` |
| `compress` | 压缩级别 | `compression_explicit` |
| `trim` | 开始时间 + 结束时间 | `start_time_explicit and end_time_explicit` |
| `info` | 无 | `True` |
