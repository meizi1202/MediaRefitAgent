# SSE 流式输出实现 - 参考 Dify

## Context

使用与 Dify 相同的 SSE 流式处理逻辑，实现真正的流式输出。

## Dify SSE 模式

### 事件格式
```
data: {"event": "message", "answer": "Hi", "created_at": 1705398420}
data: {"event": "message", "answer": " I", "created_at": 1705398420}
data: {"event": "message_end", "conversation_id": "...", "metadata": {...}}
```

### 关键事件
- `message` - LLM 返回文本片段
- `message_end` - 消息结束
- `workflow_started` - 工作流开始
- `node_started` / `node_finished` - 节点开始/结束

## Chunk 分块逻辑

Dify 的流式输出是**逐字/逐词**发送的，而非一次性发送完整消息。

### 当前问题
- `send_stream_message()` 直接发送完整内容
- `_append_message()` 一次性发送整条消息
- SSE 事件每条消息是一次性完整发送

### 设计方案

#### 1. 文本分块器
```python
def chunk_text(text: str, chunk_size: int = 10) -> list[str]:
    """将长文本分块，每块10个字符"""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def char_stream(text: str):
    """逐字发送"""
    for char in text:
        yield char
```

#### 2. 分块策略
| 策略 | 块大小 | 适用场景 |
|------|--------|----------|
| 逐字 | 1 字符 | 打字机效果 |
| 逐词 | 按空格/标点分词 | 中文按标点分词 |
| 固定块 | 10-20 字符 | 平衡延迟和效率 |
| 智能块 | 标点处分词 | 语义完整性 |

#### 3. 实现位置
- `backend/agent/streaming.py` - 添加 `chunk_text()` 和 `chunk_generator()`
- `backend/api/fastapi_app.py` - SSE 事件生成器中使用分块

#### 4. 流式队列改造
```python
def send_stream_chunk(content: str):
    """发送分块内容到队列"""
    for chunk in chunk_text(content, chunk_size=10):
        queue.put(chunk)
        time.sleep(0.05)  # 控制发送速度，避免前端渲染不过来
```

### Chunk 分块策略
| 策略 | 说明 | 示例 |
|------|------|------|
| 逐字 | 每个字符一块 | - |
| 逐词 | 按空格/标点分词 | "你好！" / "我是AI。" |
| 智能分块 | 优先标点，保留比例格式 | "请选择比例：9:16 或 16:9" |

### 中文分词注意事项
- 中文按标点分词：`。！？；：、`
- 英文按空格分词
- **保留比例格式**（如 9:16, 16:9）不被拆分
- 保留标点符号在每块末尾

## 实现方案

由于 LangGraph 的 `graph.invoke()` 是同步的，需要改造为异步事件驱动：

### 1. 后端实现

#### 创建事件队列模块
- `backend/agent/events.py` - 事件队列管理

#### 改造节点发送事件
- 每个节点执行时发送事件到队列
- 事件格式：`{"event": "message", "answer": "...", "created_at": timestamp}`

#### SSE 接口
- `POST /api/agent/chat-stream`
- 返回 `text/event-stream`
- 异步消费事件队列并发送

### 2. 前端实现

#### SSE 客户端
- 使用 `EventSource` 或 `XMLHttpRequest` 接收流
- 逐条追加显示消息

#### 展示格式
```
data: {"event": "message", "answer": "部分内容"}
→ 显示: "部分内容"
→ 继续接收并追加
```

## 关键文件

1. `backend/agent/events.py` - 事件队列
2. `backend/agent/nodes/*.py` - 节点发送事件
3. `backend/api/fastapi_app.py` - SSE 接口
4. `frontend/src/api/index.ts` - SSE 客户端
5. `frontend/src/components/InputArea.vue` - 流式展示

## 验证

1. 启动服务
2. 上传视频发送消息
3. 观察消息是否实时逐字显示
