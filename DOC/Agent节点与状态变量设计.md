# Agent 节点与状态变量设计

## 概述

本文档说明 `analyze_intent`、`handle_user_response`、`waiting_for_user` 三个核心节点及 `pending_question` 状态变量的职责与协作关系。

---

## 节点职责

| 节点 | 职责 | 输出 |
|------|------|------|
| `analyze_intent` | **理解用户意图** - 解析输入识别功能类型（convert/compress/trim...），提取参数，判断是否完整 | `current_feature`、`pending_question`（记录缺什么参数）、`messages`（LLM回复） |
| `handle_user_response` | **处理用户追问** - 预解析用户回答的关键词补全参数，或发送追问消息 | 更新 `state` 参数，设置 `current_step` |
| `waiting_for_user` | **空节点** - 标记"本轮结束等待下一轮"，通过固定边直接到 `confirm_complete` | 仅作为流程标记，不做实际处理 |
| `pending_question` | **状态变量** - 记录还缺什么参数，如 `"请选择比例/策略"` | 被 `should_proceed` 和 `handle_user_response` 读取，决定路由方向 |

---

## 关键设计思想

1. **`analyze_intent` 只负责理解** - 不决定下一步，通过 `pending_question` 告知系统"还缺参数"
2. **`should_proceed` 统一路由** - 同一份逻辑判断所有功能的下一跳
3. **`waiting_for_user` 是结束标记** - 不是真正的处理节点，本轮迭代到此结束
4. **`handle_user_response` 在下一轮被调用** - 读取 `new_user_input`（本轮用户输入）和 `pending_question`（上轮遗留的缺失参数）

---

## 状态变量优先级

用户输入的读取优先级（`analyze_intent` 中）：

```python
user_input = state.get("combined_input") or state.get("new_user_input") or state["user_input"]
```

| 变量 | 含义 | 使用场景 |
|------|------|---------|
| `combined_input` | `handle_user_response` 拼接的上轮 pending_question + 用户回答 | 用户回答了追问后，`analyze_intent` 继续解析 |
| `new_user_input` | 新一轮请求的用户输入（Turn N） | 每次新请求时由 `process_video` 设置 |
| `user_input` | 初始输入（降级用） | 前两者都不存在时的 fallback |

---

## 入口路由 (`route_from_entry`)

```
请求到达
    │
    ▼
route_from_entry(current_step, pending_question, combined_input)
    │
    ├── current_step == "waiting_for_user"
    │   或 (pending_question 存在 且 combined_input 不存在)
    │   → handle_user_response
    │
    └── 其他情况
        → analyze_intent
```

> 条件 `pending_question 存在 且 combined_input 不存在` 的含义：上轮 `analyze_intent` 结束时设置了 `pending_question`，且用户是带着新输入（`new_user_input`）来到下一轮，此时应进入 `handle_user_response` 处理追问。

---

## `should_proceed` 路由逻辑

`analyze_intent` 执行完后，条件边调用 `should_proceed` 决定下一跳：

```
should_proceed(state)
    │
    ├── current_step == "waiting_for_user"
    │   → handle_user_response
    │
    ├── current_step 是 execute_* 节点
    │   → 继续该执行节点
    │
    ├── current_step == "analyze_intent"
    │   ├── combined_input 存在 → handle_user_response
    │   └── pending_question 存在 → waiting_for_user（本轮结束）
    │
    ├── feature == "convert" 且 all_params == True
    │   → execute_transform
    │
    ├── feature == "convert" 且 pending_question 存在
    │   → waiting_for_user
    │
    └── 其他 → confirm_complete
```

---

## 多轮状态流转示例（横竖屏转换）

### Turn 1: "转竖屏"

```
请求到达
    │
    ▼
route_from_entry(current_step=None) → analyze_intent

analyze_intent
    • 识别 convert，方向=portrait
    • 缺比例 ratio、策略 strategy
    • pending_question = "请选择比例/策略"
    • LLM 消息: "已识别到您想转换为竖屏。请问选择哪个比例？9:16/4:5/1:1"
    → 返回 state

should_proceed(state)
    • current_step == None，走 convert 分支
    • pending_question 存在 → waiting_for_user
    → 返回 waiting_for_user

waiting_for_user → confirm_complete（结束）
```

### Turn 2: "9:16"

```
请求到达
    │
    ▼
route_from_entry(current_step=confirm_complete, pending_question="请选择比例/策略")
    • pending_question 存在 且 combined_input 不存在
    → handle_user_response

handle_user_response
    • new_user_input = "9:16"
    • 解析 "9:16" → ratio_explicit=True, target_ratio=0.5625
    • 仍缺策略 strategy
    • pending_question 更新为 "请选择策略"
    • 发送消息: "请问选择哪个策略？"
    → state["current_step"] = "waiting_for_user"
    → 返回 state

should_proceed(state)
    • current_step == "waiting_for_user" → handle_user_response（下一轮才会真正进入）

waiting_for_user → confirm_complete（结束）
```

### Turn 3: "拉伸填充"

```
请求到达
    │
    ▼
route_from_entry(current_step=confirm_complete, pending_question="请选择策略")
    • pending_question 存在 且 combined_input 不存在
    → handle_user_response

handle_user_response
    • new_user_input = "拉伸填充"
    • 解析 "拉伸填充" → strategy="stretch", strategy_explicit=True
    • 参数完整！
    → current_step = "execute_transform"
    → 返回 state

should_proceed(state)
    • current_step == "execute_transform" → execute_transform

execute_transform
    • 执行视频转换
    → confirm_complete（结束）
```

---

## `handle_user_response` 内部流程

```
用户回答到达
    │
    ▼
_get_missing_params(feature, state)  → 获取仍缺失的参数列表
    │
    ▼
_parse_answer_params(user_input, feature)  → 关键词预解析
    │
    ▼
将解析结果写入 state
    │
    ▼
remaining_missing = _get_missing_params(feature, state)  → 重新计算缺失
    │
    ├── 有缺失
    │   • 更新 pending_question 为剩余缺失参数
    │   • 发送追问消息给用户
    │   • current_step = "waiting_for_user"
    │   → 等待下一轮
    │
    └── 全部补全
        • current_step = "execute_xxx"
        → 下一轮直接进入执行节点
```
