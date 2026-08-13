# MediaRefitAgent

视频横竖屏转换智能体，基于 FFmpeg + LangGraph + FastAPI。

## 功能

- **视频方向检测**：FFprobe 元数据 + ML 辅助判断
- **横竖屏转换**：
  - `rotate` - 旋转视频（90°/180°/270°）
  - `pad` - 填充黑边，保持所有内容完整
  - `crop` - 直接裁剪，可能丢失边缘内容
  - `smart_crop` - YOLO AI 智能裁剪，保留主体
- **自然语言交互**：支持自然语言指令，理解用户意图
- **多轮对话**：记忆上下文，支持连续操作
- **FastAPI 服务**：供 DIFY 等第三方调用

## 技术栈

- **FFmpeg** - 视频处理核心
- **Python** + ffmpeg-python
- **LangGraph** - Agent 状态机框架
- **FastAPI** - API 服务框架
- **YOLO** (ultralytics) - 智能裁剪主体检测

## 目录结构

```
MediaRefitAgent/
├── agent/
│   ├── __init__.py
│   ├── video_agent.py    # LangGraph Agent (多轮对话)
│   ├── prompts.py        # Agent 提示词
│   └── cli.py            # 命令行界面
├── ml/
│   ├── __init__.py
│   ├── orientation_detector.py  # 方向检测
│   └── smart_cropper.py  # YOLO 智能裁剪
├── video/
│   ├── __init__.py
│   ├── processor.py      # FFmpeg 封装
│   └── transformer.py    # 转换核心逻辑
├── api/
│   ├── __init__.py
│   └── fastapi_app.py    # FastAPI 服务
├── tests/
│   ├── __init__.py
│   ├── test_video_processor.py
│   ├── test_smart_cropper.py
│   └── test_agent.py
├── requirements.txt
└── CLAUDE.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

**必需的系统依赖**：
- FFmpeg（需要加入 PATH）

**可选依赖**：
- ultralytics（YOLO，用于智能裁剪）：`pip install ultralytics`

### 2. 启动 API 服务

```bash
python -m api.fastapi_app
# 或
uvicorn api.fastapi_app:app --host 0.0.0.0 --port 8000
```

服务启动后访问 http://localhost:8000/docs 查看 API 文档。

### 3. 使用 CLI

```bash
# 单轮对话
python -m agent.cli --text "把视频转成竖屏" --video path/to/video.mp4

# 交互模式
python -m agent.cli --video path/to/video.mp4

# 纯交互模式（无视频）
python -m agent.cli --interactive
```

## API 接口

### 基础接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/health` | 健康检查 | |
| `GET /api/capabilities` | 获取支持的能力 | |
| `POST /api/detect-orientation` | 检测视频方向 | 上传文件 |
| `POST /api/transform` | 视频转换（同步） | 上传文件 |
| `POST /api/transform-stream` | 视频转换（SSE 流） | 支持进度回调 |

### Agent 接口（多轮对话）

| 接口 | 方法 | 说明 |
|------|------|------|
| `POST /api/agent/chat` | Agent 聊天 | 上传视频 + 自然语言 |
| `POST /api/agent/continue` | 继续对话 | 传入 session_id 继续 |
| `GET /api/agent/session/{id}` | 获取会话状态 | |
| `DELETE /api/agent/session/{id}` | 删除会话 | |
| `GET /api/agent/sessions` | 列出所有会话 | |

### 文件管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/outputs` | 列出输出文件 | |
| `GET /api/download/{filename}` | 下载文件 | |
| `DELETE /api/outputs/{filename}` | 删除文件 | |

## DIFY 集成示例

### 1. 直接调用 transform 接口

```bash
curl -X POST "http://localhost:8000/api/transform" \
  -F "file=@video.mp4" \
  -F "target_orientation=portrait" \
  -F "strategy=pad"
```

### 2. 使用 SSE 流式接口（长视频推荐）

```javascript
const response = await fetch('/api/transform-stream', {
  method: 'POST',
  body: formData,
});

// 处理 SSE 流
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  const lines = text.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6));
      console.log(`[${event.event}] ${event.message} (${event.progress})`);
    }
  }
}
```

### 3. 使用 Agent 接口（自然语言）

```javascript
// 第一轮：发送视频和自然语言指令
const chatResponse = await fetch('/api/agent/chat', {
  method: 'POST',
  body: formData,  // formData 包含 file 和 JSON 字段 message
});

// 获取 session_id 继续对话
const sessionId = chatResponse.session_id;

// 继续对话
await fetch('/api/agent/continue', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: '改用智能裁剪',
    session_id: sessionId,
  }),
});
```

## 自然语言指令示例

```
把视频转成竖屏
转换为横屏
使用智能裁剪转为竖屏
填充黑边
裁剪视频
旋转90度
```

## 进度跟踪

视频转换支持进度回调：

```python
def progress_callback(progress: float):
    print(f"进度: {int(progress * 100)}%")

result = transform(request, progress_callback=progress_callback)
```

SSE 接口实时推送进度事件：

```json
{"event": "start", "progress": 0.0, "message": "Starting..."}
{"event": "progress", "progress": 0.45, "message": "Processing... 45%"}
{"event": "complete", "progress": 1.0, "message": "Transform completed"}
```

## 测试

```bash
pytest tests/ -v
```

## 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 启动服务
python -m api.fastapi_app

# CLI 交互
python -m agent.cli --interactive
```
