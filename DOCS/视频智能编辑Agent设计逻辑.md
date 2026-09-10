# 视频处理 Agent 设计逻辑

## 概述

MediaRefitAgent 是一个基于 LangGraph 状态机的多轮对话式视频处理 Agent。用户可以通过自然语言描述需求，Agent 自动完成意图分析和执行相应的视频处理操作。

### 支持的功能

| 功能 | feature 值 | 说明 |
|------|-----------|------|
| 横竖屏转换 | `convert` | 转换视频方向（填充黑边/裁剪/智能裁剪等） |
| 视频压缩 | `compress` | 压缩视频文件大小 |
| 视频修剪 | `trim` | 裁剪视频片段 |
| 视频拼接 | `concat` | 拼接多个视频 |
| 智能缩编 | `condense` | 自动提取精彩片段 |
| 老视频修复 | `restore` | 修复老旧视频 |
| 智能剪辑 | `editor` | 智能剪辑视频 |
| 视频信息 | `info` | 获取视频元信息 |

---

## 整体架构

### 节点 (Nodes)

| 节点名 | 类型 | 职责 |
|--------|------|------|
| `__entry__` | 入口 | 初始化入口，根据 `current_step` 决定路由 |
| `analyze_intent` | 处理节点 | 分析用户意图，解析参数 (LLM/关键词) |
| `handle_user_response` | 处理节点 | 处理用户追问，预解析用户回答中的参数，**支持功能切换检测** |
| `waiting_for_user` | 暂停节点 | 等待用户输入（空节点，直接到 confirm_complete） |
| `execute_transform` | 执行节点 | 执行横竖屏转换 |
| `execute_compress` | 执行节点 | 执行视频压缩 |
| `execute_trim` | 执行节点 | 执行视频修剪 |
| `execute_concat` | 执行节点 | 执行视频拼接 |
| `execute_condense` | 执行节点 | 执行智能缩编 |
| `execute_restore` | 执行节点 | 执行老视频修复 |
| `execute_info` | 执行节点 | 获取视频信息 |
| `execute_editor` | 执行节点 | 执行智能剪辑 |
| `confirm_complete` | 结束节点 | 完成确认 |

### 边 (Edges) 完整条件

#### 1. `__entry__` → 条件边

```
route_from_entry(state):
  ┌─────────────────────────────────────────────────────────────┐
  │ 条件1: combined_input 存在                                  │
  │         → "handle_user_response"                            │
  └─────────────────────────┬───────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ 条件2: pending_question 存在                                 │
  │         → "handle_user_response"                            │
  └─────────────────────────┬───────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ 条件3: current_step == "waiting_for_user"                   │
  │         → "handle_user_response"                            │
  └─────────────────────────┬───────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ 条件4: pending_question 为 None，但 state 中已有明确参数    │
  │       (orientation_explicit / ratio_explicit /             │
  │        strategy_explicit / compression_explicit)            │
  │         → "handle_user_response"                            │
  │       说明：execute_* 后用户修改参数，应走预解析而非 LLM     │
  └─────────────────────────┬───────────────────────────────────┘
                            ▼
                   "analyze_intent"
```

---

#### 2. `analyze_intent` → 条件边 (经 `should_proceed`)

```
should_proceed(state):
  ┌──────────────────────────────────────────────────────────────┐
  │ 优先级1: current_step == "waiting_for_user"                  │
  │         → "handle_user_response"                             │
  └──────────────────────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────────────────────┐
  │ 优先级2: current_step in execute_* (执行中)                   │
  │         → 保持当前执行节点 (自循环)                           │
  └──────────────────────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────────────────────┐
  │ 优先级3: current_step == "analyze_intent"                   │
  │   ├─ combined_input 存在  → "handle_user_response"          │
  │   ├─ pending_question 存在 → "waiting_for_user"             │
  │   └─ 其他              → "analyze_intent" (自循环)          │
  └──────────────────────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────────────────────┐
  │ 优先级4: feature == "convert"                               │
  │   ├─ all_params == True  → "execute_transform"             │
  │   └─ pending_question 存在 → "waiting_for_user"             │
  └──────────────────────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────────────────────┐
  │ 优先级5: feature == "compress" AND all_params → "execute_compress" │
  │ 优先级6: feature == "concat"  AND all_params → "execute_concat"     │
  │ 优先级7: feature == "trim"    AND all_params → "execute_trim"       │
  │ 优先级8: 其他功能 AND all_params           → "execute_transform"       │
  └──────────────────────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────────────────────┐
  │ 默认: → "confirm_complete"                                   │
  └──────────────────────────────────────────────────────────────┘
```

---

#### 3. `handle_user_response` → 条件边

```
route_from_handle_user_response(state):
  ┌─────────────────────────────────────────────────────────────┐
  │ 条件1: current_step in execute_*                          │
  │         → 执行对应 execute 节点                            │
  │       (execute_transform / execute_compress / ...)          │
  └─────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ 条件2: current_step == "analyze_intent"                   │
  │         → "analyze_intent"                                │
  │       (功能切换时，重新走 LLM 解析新功能)                   │
  └─────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ 条件3: current_step == "waiting_for_user"                 │
  │         → "waiting_for_user"                              │
  │       (仍有缺失参数，等待用户下一轮回答)                     │
  └─────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ 否则 → "confirm_complete"                                   │
  └─────────────────────────────────────────────────────────────┘
```

---

#### 4. 固定边 (无条件)

```
waiting_for_user      → confirm_complete
execute_trim          → confirm_complete
execute_condense      → confirm_complete
execute_restore       → confirm_complete
execute_info          → confirm_complete
execute_editor        → confirm_complete
execute_transform     → confirm_complete
execute_compress      → confirm_complete
execute_concat        → confirm_complete
confirm_complete      → END
```

---

### 完整流程图

```
                           ┌─────────────────────────────────────────────────┐
                           │                    __entry__                    │
                           │             (根据 current_step 决定入口)           │
                           └──────────────────────┬────────────────────────────┘
                                                  │
                              ┌───────────────────┴────────────────────────┐
                              │  route_from_entry 条件边                     │
                              │                                           │
                              │  条件1: combined_input 存在                  │
                              │  条件2: pending_question 存在                 │
                              │  条件3: current_step == "waiting_for_user"   │
                              │  条件4: 已有明确参数（execute后修改参数）       │
                              ▼                                           ▼
                   ┌──────────────────────┐              ┌──────────────────────┐
                   │  handle_user_response │              │     analyze_intent    │
                   │  (预解析参数)          │              │     (分析意图)         │
                   │  + 功能切换检测        │              └──────────┬───────────┘
                   └──────────┬───────────┘                         │
                              │                                    │
          ┌───────────────────┼───────────────────┐                │
          │ route_from_       │                   │                │
          │ handle_user_     │                   │                │
          │ response          │                   │                │
          ▼                   ▼                   │         ┌──────┴──────────────┐
   ┌─────────────┐  ┌─────────────────┐  ┌──────────────┐   │   should_proceed      │
   │ execute_*  │  │ analyze_intent  │  │waiting_for_  │   │   条件边 (见上方详细)   │
   │ (执行节点)  │  │ (功能切换时)    │  │ user         │   └───────────┬───────────┘
   └──────┬─────┘  └────────┬────────┘  └──────┬───────┘                │
          │                 │                   │                         │
          │                 │                   ▼                         │
          │                 └───────────► waiting_for_user                │
          │                             (暂停等待)                        │
          │                                    │                         │
          │                                    ▼                         │
          │                              confirm_complete                │
          │                                    │                         │
          └────────────────────────────────────┴─────────────────────────┘
                                                                         │
                                                    ┌─────────────────────┴─────────────────────┐
                                                    │                                          │
                                                    ▼                                          ▼
                                             ┌───────────┐                            ┌─────────────────┐
                                             │ execute_* │                            │waiting_for_user  │
                                             │ (执行节点) │                            │ (暂停等待)        │
                                             └─────┬─────┘                            └────────┬────────┘
                                                   │                                          │
                                                   │                                          ▼
                                                   │                                   confirm_complete
                                                   │                                         │
                                                   └────────────────────────────────────────────┘
                                                                                                      │
                                                                                                      ▼
                                                                                                    END
```

---

### 典型场景流转

| 场景 | 流转路径 |
|------|----------|
| **UI完整参数** | `__entry__` → `analyze_intent` → `execute_transform` → `confirm_complete` → END |
| **缺策略参数** | `__entry__` → `analyze_intent` → `waiting_for_user` → `confirm_complete` → END |
| **用户回答策略** | `__entry__` → `handle_user_response` → `execute_transform` → `confirm_complete` → END |
| **多轮追问** | `__entry__` → `analyze_intent` → `waiting_for_user` → `handle_user_response` → `waiting_for_user` → ... → `execute_*` → END |
| **execute后修改参数** | `__entry__` → `handle_user_response`（路由到预解析）→ `execute_*` → END |
| **功能切换** | `__entry__` → `handle_user_response`（检测到 compress）→ `analyze_intent` → `execute_compress` → END |

---

## 详细设计

### 1. 意图分析 (analyze_intent)

**文件**: [backend/agent/nodes/analyze.py](backend/agent/nodes/analyze.py)

#### 1.1 输入与输出

- **输入**: `state["user_input"]` (用户文本), `state.get("combined_input")` (用户回答拼接后的输入)
- **输出**: 设置 `state["current_feature"]` 和对应功能的参数

#### 1.2 解析流程

```
用户输入
    │
    ▼
┌───────────────────────────┐
│  _parse_ui_params()       │ ← 优先解析前端UI格式
│  [用户已选择参数：功能=视频压缩，│
│   压缩级别=中等]            │
└────────────┬──────────────┘
             │ UI格式匹配
             ▼
      直接设置参数
      all_params_provided = True
             │
             │ UI格式不匹配
             ▼
┌───────────────────────────┐
│  LLM 意图解析              │
└────────────┬──────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌────────┐      ┌────────────┐
│ LLM可用 │      │  LLM不可用  │
└───┬────┘      └──────┬─────┘
    ▼                  ▼
parse_intent()     返回错误：
"请配置 MINIMAX_API_KEY"
```

#### 1.3 LLM 意图解析

使用 MiniMax API 进行意图解析，返回结构化数据：

```python
parsed = {
    "target_feature": "convert",       # 功能类型
    "target_orientation": "portrait",  # 目标方向（convert）
    "orientation_explicit": True,     # 方向是否明确
    "strategy": "pad",               # 转换策略（convert）
    "strategy_explicit": True,        # 策略是否明确
    "target_ratio": 0.5625,          # 目标比例（convert）
    "ratio_explicit": True,           # 比例是否明确
    "compression_level": "medium",   # 压缩级别（compress）
    "compression_explicit": True,     # 压缩级别是否明确
    "start_time": 10.0,              # 修剪开始时间（trim）
    "end_time": 30.0,               # 修剪结束时间（trim）
    "all_params_provided": True,    # 参数是否完整
    "response": "好的，将视频压缩为中等质量..."
}
```

#### 1.4 历史上下文处理

LLM 解析时会传入历史对话上下文，支持多轮对话：

```python
# 1. 优先使用 state["messages"]（当前会话已累积的消息）
state_messages = state.get("messages", [])
if session_id and len(state_messages) > 0:
    history = [{"role": "user"/"assistant", "content": ...}, ...]
# 2. 如果为空，从 LangChain Memory 获取
elif session_id:
    chat_history = get_conversation_history(session_id)
    history = [...]

# 3. 传给 LLM
parsed = _llm_parse_intent(user_input, llm, history=history)
```

| 消息来源 | 说明 |
|---------|------|
| `state["messages"]` | 当前会话中已添加的消息 |
| `get_conversation_history()` | LangChain Memory 持久化的历史 |

---

#### 1.5 各功能参数完整性判断

| 功能 | 必需参数 | 判断条件 |
|------|---------|---------|
| `convert` | 方向 + 比例 + 策略 | `orientation_explicit and strategy_explicit and ratio_explicit` |
| `compress` | 压缩级别 | `compression_explicit` |
| `trim` | 开始时间 + 结束时间 | `start_time_explicit and end_time_explicit` |
| `concat` | 视频文件数 ≥ 2 | `len(video_files) >= 2` |
| `condense` | 目标时长 | `target_duration_explicit` |
| `restore` | 无（直接执行） | `True` |
| `editor` | 目标时长 | `target_duration_explicit` |
| `info` | 无（直接执行） | `True` |

#### 1.6 状态设置

```python
if all_params_provided:
    state["pending_question"] = None
else:
    state["pending_question"] = f"请选择{缺失参数列表}"  # 记录缺失参数
```

---

### 2. 等待用户响应 (handle_user_response)

**文件**: [backend/agent/nodes/routing.py](backend/agent/nodes/routing.py)

#### 2.1 核心设计

用户回答时，`pending_question` 记录了缺失的参数类型（如"请选择比例/策略"）。`handle_user_response` 通过**预解析 + 关键词匹配**直接补全参数，跳过 LLM 重新解析，避免 LLM 误判。

#### 2.2 功能切换检测

当用户输入新需求时（如从"转竖屏"切换到"压缩视频"），系统需要识别并切换功能：

```python
def _identify_target_from_input(user_input: str) -> str | None:
    """从用户输入中识别目标（功能类型）"""
    # 1. 优先用 UI 参数格式解析（最准确）
    ui_params = _parse_ui_params(user_input)
    if ui_params.get("found"):
        return ui_params.get("feature")

    # 2. 自然语言：用关键词判断
    text = user_input.lower()
    if any(kw in text for kw in ["压缩", "compress", "小文件", "高压缩率"]):
        return "compress"
    if any(kw in text for kw in ["裁剪", "trim", "修剪"]):
        return "trim"
    # ... 其他功能关键词
    return None
```

**处理流程**：
1. 从用户输入识别目标功能类型
2. 若识别到目标 **且与历史不同** → 清除历史 explicit 参数，路由到 `analyze_intent` 重新解析
3. 若识别到目标 **与历史相同** → 继续参数补充逻辑
4. 若未识别到 → 默认按同历史逻辑处理

#### 2.3 参数映射配置（可扩展）

```python
# pending_question 关键词 → 对应参数的映射
PENDING_QUESTION_PARAMS = {
    "convert": {
        "比例": ["ratio", "orientation"],
        "策略": ["strategy"],
    },
    "compress": {
        "压缩级别": ["compression_level"],
    },
    "trim": {
        "时间": ["start_time", "end_time"],
    },
}

# 功能 → 执行节点的映射
FEATURE_TO_EXECUTE = {
    "convert": "execute_transform",
    "compress": "execute_compress",
    "trim": "execute_trim",
    "concat": "execute_concat",
    "condense": "execute_condense",
    "restore": "execute_restore",
    "editor": "execute_editor",
    "info": "execute_info",
}
```

#### 2.4 关键词解析

```python
def _parse_answer_params(user_input: str, feature: str) -> dict:
    """解析用户回答中的参数关键词"""
    if feature == "convert":
        # 比例解析
        ratio_map = {
            "9:16": (0.5625, "portrait"), "4:5": (0.8, "portrait"), "1:1": (1.0, "portrait"),
            "16:9": (1.7778, "landscape"), "21:9": (2.3333, "landscape"), "4:3": (1.3333, "landscape"),
        }
        # 策略解析（优先级高的在前，避免被通用词覆盖）
        strategy_map = [
            ("拉伸填充", "stretch"), ("拉伸", "stretch"),
            ("不要填充", "stretch"), ("不要黑边", "stretch"),
            ("填充黑边", "pad"), ("留边", "pad"), ("保持完整", "pad"),
            ("中心裁剪", "crop"),
            ("智能裁剪", "smart_crop"), ("AI裁剪", "smart_crop"),
        ]
    elif feature == "compress":
        level_map = {"低": "low", "中": "medium", "高": "high"}
    # ...
```

#### 2.5 处理流程

```
用户回答到达（new_user_input）
        │
        ▼
┌───────────────────────────────────────┐
│ 0. 功能切换检测                        │ → _identify_target_from_input()
│    _identify_target_from_input()       │   识别目标功能类型
└─────────────┬─────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
  识别到目标           未识别到
  且与历史不同         或与历史相同
    │                   │
    ▼                   │
清除 explicit 参数      │
current_step =         │
"analyze_intent"      │
(重新走 LLM)            ▼
    │         ┌─────────────────────────────┐
    │         │ 1. 关键词预解析用户回答     │ → "拉伸填充" → {strategy: "stretch"}
    │         │    _parse_answer_params()    │   始终解析，支持修改已有参数
    │         └─────────────┬───────────────┘
    │                       │
    │                       ▼
    │         ┌─────────────────────────────┐
    │         │ 2. 将解析结果写入 state       │   parsed 覆盖已有值
    │         └─────────────┬───────────────┘
    │                       │
    │                       ▼
    │         ┌─────────────────────────────┐
    │         │ 3. 重新计算剩余缺失参数      │
    │         │    _get_missing_params()       │
    │         └─────────────┬───────────────┘
    │                       │
    │                       ▼
    │         ┌─────────────────────────────┐
    │         │ 4. 检查参数是否完整           │
    │         │    _check_all_params_provided │
    │         └─────────────┬───────────────┘
    │                       │
    │              ┌────────┴────────┐
    │              ▼                 ▼
    │           完整              仍缺失
    │              │                 │
    │              ▼                 ▼
    │    current_step =         pending_question = 剩余缺失参数
    │    "execute_*"           发送追问消息
    │                           current_step = "waiting_for_user"
    └──────────────────────────────────────────────────────────────────┘
```

#### 2.6 pending_question 动态更新机制

`pending_question` 会随着用户回答动态更新：
- Turn 1: "转竖屏" → `pending_question = "请选择比例/策略"`
- Turn 2: "9:16" → `pending_question = "请选择策略"`（比例已补全）
- Turn 3: "拉伸填充" → `pending_question = None`（参数完整，执行）

#### 2.7 功能切换场景

```
Turn 1: 用户说"转竖屏"
  → analyze_intent → convert，缺比例/策略
  → pending_question = "请选择比例/策略"

Turn 2: 用户说"9:16"
  → handle_user_response → convert 参数部分补全
  → pending_question = "请选择策略"

Turn 3: 用户说"压缩视频"
  → _identify_target_from_input() = "compress"（识别到压缩关键词）
  → compress != convert（与历史不同）
  → 清除 convert 的 explicit 参数
  → current_step = "analyze_intent"
  → 重新走 LLM 解析 compress
  → compress 缺压缩级别

Turn 4: 用户说"高"
  → handle_user_response → compress 参数完整
  → current_step = "execute_compress"
```

---

### 3. 执行节点 (execute_xxx)

**文件**: [backend/agent/nodes/execute.py](backend/agent/nodes/execute.py)

所有执行节点遵循相同模式：

```python
def execute_xxx(state: VideoAgentState) -> VideoAgentState:
    video_path = state.get("temp_video_path") or state.get("video_path")

    # 1. 文件存在检查
    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    # 2. 生成输出路径
    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    output_path = str(output_dir / f"{prefix}_{timestamp}{suffix}")

    try:
        # 3. 调用处理函数
        def progress_callback(progress: float):
            # 推送进度到 SSE
            msg = f"[PROGRESS:{int(progress * 100)}]"
            from agent.streaming import send_stream_message
            send_stream_message(msg)

        result = process_xxx(video_path, output_path, params, progress_callback=progress_callback)

        # 4. 保存结果
        state["result"] = {...}
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"操作完成！\n[PREVIEW:{output_path}]")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"操作异常: {str(e)}")

    return state
```

#### 3.1 各功能执行函数

| 功能 | 函数 | 底层调用 |
|------|------|---------|
| `convert` | `execute_transform` | `transform()` → `processor.pad_to_ratio()` 等 |
| `compress` | `execute_compress` | `compress_video()` |
| `trim` | `execute_trim` | `trim_video()` |
| `concat` | `execute_concat` | `concat_videos()` |
| `condense` | `execute_condense` | `condense_video()` |
| `restore` | `execute_restore` | `restore_video()` |
| `editor` | `execute_editor` | `trim_video()` (简化版) |
| `info` | `execute_info` | `get_video_metadata()` |

---

### 4. 视频转换进度推送

**文件**: [backend/video/transformer.py](backend/video/transformer.py), [backend/video/processor.py](backend/video/processor.py)

#### 4.1 进度链路

```
FFmpeg stderr (time=00:05:32.45)
    │
    ▼
run_ffmpeg(total_duration=metadata.duration)
    │
    ▼
progress_callback(0.0-0.99)  ← 按实际视频时长计算百分比
    │
    ▼
ffmpeg_progress_wrapper()  ← 映射到 0.1-0.95
    │
    ▼
transform(request, progress_callback)
    │
    ▼
execute_transform progress_callback()
    │
    ▼
send_stream_message("[PROGRESS:45]")  ← SSE 推送
```

#### 4.2 run_ffmpeg 进度计算

```python
def run_ffmpeg(cmd, progress_callback=None, total_duration=None):
    # FFmpeg 解析 time= 输出
    time_match = re.search(r"time=(\d+):(\d+):(\d+)", line)
    if time_match:
        current_time = hours * 3600 + minutes * 60 + seconds
        # 使用实际视频时长计算进度百分比
        max_time = total_duration if total_duration else 300
        progress_callback(min(current_time / max_time, 0.99))
```

#### 4.3 前端进度条显示

前端 SSE 接收 `[PROGRESS:xx]` 格式消息，在助手消息下方展示进度条：

```
用户: "转竖屏"
🤖: 好的，使用9:16竖屏和填充黑边策略，正在为您转换...
    ████████████░░░░░░░░░░░ 45%
```

---

## 状态流转示例

### 场景1: 横竖屏转换 - 参数完整（单轮）

```
用户: "把视频转成竖屏 9:16，用拉伸填充"

analyze_intent
  → 解析出方向、比例、策略
  → all_params = True
  → should_proceed → execute_transform

execute_transform
  → 检查文件存在
  → 调用 transform()（带进度回调）
  → confirm_complete

结束
```

### 场景2: 横竖屏转换 - 多轮（用户逐步选择）

```
用户: "转竖屏"

analyze_intent
  → 解析出方向
  → 缺少比例、策略
  → pending_question = "请选择比例/策略"
  → should_proceed → waiting_for_user → confirm_complete

---
用户: "9:16"

handle_user_response
  → 解析 "9:16" → target_ratio, orientation_explicit
  → 参数仍缺失（策略）
  → pending_question = "请选择策略"
  → current_step = "waiting_for_user"

---
用户: "拉伸填充"

handle_user_response
  → 解析 "拉伸填充" → strategy_explicit
  → 参数完整！
  → current_step = "execute_transform"

execute_transform
  → 调用 transform()（推送进度）
  → confirm_complete
```

### 场景3: 功能切换 - convert → compress

```
用户: "转竖屏"

analyze_intent
  → 解析出方向
  → 缺少比例、策略
  → pending_question = "请选择比例/策略"
  → should_proceed → waiting_for_user → confirm_complete

---
用户: "9:16，填充黑边"

handle_user_response
  → 解析出比例、策略
  → 参数完整！
  → current_step = "execute_transform"

execute_transform
  → 转换完成
  → confirm_complete

---
用户: "压缩视频，高压缩"

handle_user_response
  → _identify_target_from_input() = "compress"
  → compress != convert（功能切换！）
  → 清除 convert 的 explicit 参数
  → current_step = "analyze_intent"

analyze_intent
  → 解析出 compress
  → 缺少压缩级别
  → pending_question = "请选择压缩级别"

---
用户: "高"

handle_user_response
  → 解析 "高" → compression_level="high", compression_explicit=True
  → 参数完整！
  → current_step = "execute_compress"

execute_compress
  → 压缩完成
  → confirm_complete
```

### 场景4: execute_* 后修改参数

```
execute_transform 完成
  → pending_question = None
  → confirm_complete → END

---
用户: "改为拉伸填充"

process_video
  → new_user_input = "改为拉伸填充"
  → pending_question = None, combined_input = None

route_from_entry
  → pending_question 为 None，但 state 中已有
    orientation_explicit=True, ratio_explicit=True
  → 路由到 handle_user_response

handle_user_response
  → _identify_target_from_input() = "convert"（未识别到压缩等关键词）
  → convert == convert（同历史）
  → 解析 "拉伸填充" → strategy="stretch", strategy_explicit=True
  → all_params_check = True
  → current_step = "execute_transform"

execute_transform
  → confirm_complete → END
```

---

## 新增功能扩展

如需新增功能（如"视频添加字幕"），需要修改以下文件：

| 文件 | 修改内容 |
|------|---------|
| [execute.py](backend/agent/nodes/execute.py) | 添加 `execute_xxx` 函数（含进度回调） |
| [analyze.py](backend/agent/nodes/analyze.py) | `FEATURE_TO_STEP` 添加 `"xxx": "execute_xxx"` |
| [routing.py](backend/agent/nodes/routing.py) | `FEATURE_PARAM_LABELS` 添加参数标签、`_check_all_params_provided()` 添加判断逻辑 |
| [video_agent.py](backend/agent/video_agent.py) | 节点注册 + 固定边连接 |

### 扩展步骤

1. **execute.py**: 添加 `execute_xxx` 函数（含 `progress_callback` 推送进度）
2. **analyze.py**: `FEATURE_TO_STEP["xxx"] = "execute_xxx"`
3. **routing.py**:
   - `FEATURE_PARAM_LABELS["xxx"] = {"param1": "参数1", ...}`
   - `_check_all_params_provided()` 添加 `elif feature == "xxx": return ...`
   - `_identify_target_from_input()` 添加 xxx 关键词检测
4. **video_agent.py**:
   - 导入 `execute_xxx`
   - `graph.add_node("execute_xxx", execute_xxx)`
   - `graph.add_edge("execute_xxx", "confirm_complete")`
   - `route_from_handle_user_response` 的 `execute_nodes` 添加 `"execute_xxx"`

---

## 关键数据结构

### VideoAgentState (types.py)

```python
class VideoAgentState(TypedDict):
    # 用户输入
    user_input: str
    video_path: Optional[str]
    temp_video_path: Optional[str]
    video_files: Optional[list[str]]  # 多文件场景

    # 意图解析结果
    current_feature: Optional[str]      # "convert", "compress", "trim", ...

    # 横竖屏转换参数
    target_orientation: Optional[str]   # "portrait", "landscape"
    original_orientation: Optional[str]
    strategy: Optional[str]             # "pad", "crop", "smart_crop", ...
    target_ratio: Optional[float]
    orientation_explicit: bool
    strategy_explicit: bool
    ratio_explicit: bool

    # 视频压缩参数
    compression_level: Optional[str]    # "low", "medium", "high"
    compression_explicit: bool

    # 视频修剪参数
    start_time: Optional[float]
    end_time: Optional[float]
    start_time_explicit: bool
    end_time_explicit: bool

    # 视频拼接参数
    keep_audio: bool

    # 智能缩编/剪辑参数
    target_duration: Optional[int]
    target_duration_explicit: bool
    num_clips: Optional[int]
    num_clips_explicit: bool

    # 转场参数
    transition_type: Optional[str]
    transition_type_explicit: bool
    transition_duration: Optional[float]

    # 参数状态
    all_params_provided: bool
    pending_question: Optional[str]     # 待用户回答的问题

    # 状态机
    current_step: str                   # 当前节点名
    messages: list[ConversationMessage]

    # 内部字段
    combined_input: Optional[str]       # 拼接后的用户输入（handle_user_response → analyze_intent）
    new_user_input: Optional[str]      # 新用户输入（process_video → handle_user_response）

    # 结果
    transform_result: Optional[dict]
    compress_result: Optional[dict]
    trim_result: Optional[dict]
    concat_result: Optional[dict]
    error: Optional[str]
    session_id: str
```

### ConversationMessage

```python
class ConversationMessage(TypedDict):
    role: str          # "user" / "assistant"
    content: str        # 消息内容
    timestamp: str      # ISO 格式时间戳
```
