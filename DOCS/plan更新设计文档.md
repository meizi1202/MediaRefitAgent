# Plan: 更新视频智能编辑Agent设计文档

## Context

`handle_user_response` 在 recent commits (718562e "统一Agent意图处理逻辑") 中经历了较大重构，文档内容与实际代码存在多处不一致，需要同步更新以避免后续维护困惑。

---

## 发现的不一致

### 1. `handle_user_response` 流程 (文档 2.4 节)

| 项目 | 文档描述 | 实际代码 |
|------|---------|---------|
| 缺失参数来源 | 从 `pending_question` 解析 | 从 `state` 计算（`_get_missing_params`） |
| 缺失参数内容 | `["ratio", "orientation"]` | `["ratio", "strategy"]`（取决于 explicit 标志） |
| 仍缺失时 `current_step` | `"analyze_intent"` | `"waiting_for_user"` |
| `pending_question` 处理 | 直接清除设为 None | 动态更新为剩余缺失参数 |

### 2. 仍缺失参数时的处理 (文档 2.5 代码示例)

**文档：**
```python
state["combined_input"] = f"{pending_question}\n用户回答：{user_input}"
state["pending_question"] = None  # 清除
state["new_user_input"] = None
state["current_step"] = "analyze_intent"  # 继续 LLM
```

**实际代码：**
```python
state["combined_input"] = f"{pending_question}\n用户回答：{user_input}"
state["new_user_input"] = None
state["current_step"] = "waiting_for_user"  # 等待下一轮
# pending_question 更新为剩余缺失参数（不清除）
```

### 3. 用户响应时发送消息

**文档 2.4 节流程图：** 没有描述向用户发送"请选择策略"这类消息的动作。

**实际代码：** 当仍有缺失参数时，会 `state["messages"].append(...)` + `send_stream_chunk(...)` 向用户发送追问消息。

### 4. `pending_question` 动态更新

文档中 `pending_question` 是静态的（一旦设置就不再变化），实际是动态的——每轮 `handle_user_response` 解析后，会根据剩余缺失参数重新生成，如：
- `"请选择比例/策略"` → 用户选 "9:16" → 更新为 `"请选择策略"`

### 5. 状态流转示例 (文档场景2)

文档示例中第二轮 `analyze_intent` 仍会重新解析 `combined_input`，但实际上 `handle_user_response` 已经处理了预解析，不会再走 LLM。

---

## 需修改的文件

- [DOC/视频智能编辑Agent设计逻辑.md](DOC/视频智能编辑Agent设计逻辑.md)

---

## 修改内容

### 1. 更新 2.4 节流程图

```
用户回答（例："9:16"）
        │
        ▼
┌─────────────────────────────┐
│ 1. 获取缺失参数              │ → 从 state 计算: _get_missing_params()
│    _get_missing_params()   │   而非从 pending_question 解析
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 2. 关键词预解析用户回答     │ → _parse_answer_params()
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 3. 更新 state + 重新计算    │
│    剩余缺失参数              │
└─────────────┬───────────────┘
              │
       ┌──────┴──────┐
       │              │
       ▼              ▼
    完整          仍缺失
       │              │
       ▼              ▼
 current_step =      current_step = "waiting_for_user"
 "execute_xxx"       + 向用户发送追问消息
                     + pending_question 更新为剩余缺失参数
```

### 2. 更新 2.5 节代码示例

替换为实际代码逻辑（包含 `pending_question` 动态更新 + 发送消息）。

### 3. 更新 2.2 节注释

`PENDING_QUESTION_PARAMS` 在实际代码中已不再从 `pending_question` 解析参数，仅作为文档参考保留。

### 4. 更新场景2状态流转示例

反映实际行为：
- `handle_user_response` 处理 "9:16" → 更新 `pending_question = "请选择策略"` → 设置 `current_step = "waiting_for_user"` → 发送"请问选择哪个策略？"消息
- 下一轮 `handle_user_response` 处理 "拉伸填充" → 参数完整 → 路由到 `execute_transform`

### 5. 文档补充说明

- `pending_question` 动态更新机制
- 用户响应时会主动发送追问消息（`state["messages"]` + `send_stream_chunk`）

---

## Verification

1. 阅读修改后的文档，确认与 [routing.py](backend/agent/nodes/routing.py) 实际代码一致
2. 无需运行代码（此次仅为文档更新）
