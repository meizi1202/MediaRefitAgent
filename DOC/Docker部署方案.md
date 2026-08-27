# MediaRefitAgent Docker 部署方案

## 1. Context

MediaRefitAgent 是一个视频横竖屏转换智能体，目前无任何容器化配置。项目包含：
- **FastAPI 后端**（端口 8004）：视频处理 + LangGraph Agent
- **Vue 3 前端**（端口 8080）：Web 界面
- **ML 依赖**：torch、torchvision、ultralytics（YOLO），镜像较大
- **系统依赖**：FFmpeg（需加入 PATH）
- **持久化数据**：输出视频目录、BGM 音乐库

本文档为项目设计一套生产级 Docker 部署方案。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────┐
│                  nginx                   │
│         (端口 80/443 反向代理)            │
│                                         │
│   ┌─────────────┐    ┌──────────────┐  │
│   │  frontend   │    │    backend    │  │
│   │  (Vue dist) │    │   (FastAPI)   │  │
│   │  :8080      │    │    :8004      │  │
│   └─────────────┘    └──────────────┘  │
│                              │          │
│                     ┌────────┴────────┐ │
│                     │   data volume    │ │
│                     │ (videos + bgm)   │ │
│                     └─────────────────┘ │
└─────────────────────────────────────────┘
```

### 2.2 容器划分

| 容器 | 基础镜像 | 用途 | 端口 |
|------|---------|------|------|
| `backend` | `python:3.11-slim` + FFmpeg | FastAPI 后端服务 | 8004 |
| `frontend` | `node:20-alpine` → `nginx:alpine` | Vue 前端静态资源 | — (由 nginx 托管) |
| `nginx` | `nginx:alpine` | 反向代理 + 静态服务 | 80/443 |

> **注**：生产环境建议将 `frontend` 和 `nginx` 合并，减少容器数量。

### 2.3 数据卷

| 宿主机路径 | 容器内路径 | 说明 |
|-----------|-----------|------|
| `./data/outputs` | `/app/data/outputs` | 处理后视频输出 |
| `./data/bgm` | `/app/data/bgm` | BGM 音乐库 |
| `./data/models` | `/app/data/models` | YOLO 模型（可共享只读） |

---

## 3. 多阶段构建（Multi-Stage Build）

### 3.1 方案一：统一 Dockerfile（推荐生产环境）

```dockerfile
# ================================================
# Stage 1: Frontend build
# ================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ================================================
# Stage 2: Backend + FFmpeg
# ================================================
FROM python:3.11-slim

# 安装系统依赖（FFmpeg + 语言支持）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖（先复制 requirements，避免每次修改依赖后重新安装大包）
COPY requirements.txt .

# 预下载 ML 模型（减小运行时体积）
RUN pip install --no-cache-dir --break-system-packages \
    torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --break-system-packages \
    ultralytics==8.2.0

# 复制应用代码
COPY backend/ ./backend/
COPY yolov8n.pt /app/yolov8n.pt

# Python 依赖（非 ML 部分）
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt \
    || pip install --no-cache-dir --break-system-packages \
    ffmpeg-python Pillow fastapi uvicorn python-multipart \
    langchain langgraph python-dotenv pydantic

# 下载 YOLO 模型（如果宿主机没有 yolov8n.pt）
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
    || [ -f /app/yolov8n.pt ] || echo "Warning: YOLO model not found"

COPY --from=frontend-builder /app/dist ./frontend/dist

# 环境变量（运行时注入）
ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/app/data/outputs
ENV FFMPEG_DIR=/usr/bin
ENV FFMPEG_PATH=/usr/bin

EXPOSE 8004

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/api/health')" || exit 1

CMD ["uvicorn", "backend.api.fastapi_app:app", "--host", "0.0.0.0", "--port", "8004"]
```

### 3.2 方案二：docker-compose 分离部署（推荐开发/轻量级环境）

开发环境或资源受限场景可使用更轻量的方式：

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
      target: backend
    container_name: mediarefit-backend
    ports:
      - "8004:8004"
    volumes:
      - ./data/outputs:/app/data/outputs
      - ./data/bgm:/app/data/bgm
    environment:
      - API_PORT=8004
      - OUTPUT_DIR=/app/data/outputs
      - FFMPEG_PATH=/usr/bin
      - FFMPEG_DIR=/usr/bin
      - FFMPEG_PRESET_TRANSFORM=ultrafast
      - FFMPEG_CRF_TRANSFORM=23
      - MINIMAX_API_KEY=${MINIMAX_API_KEY}
      - MINIMAX_API_BASE=https://api.minimax.chat/v1
      - MINIMAX_API_URL=https://api.minimax.chat/v1/text/chatcompletion_v2
      - MINIMAX_MODEL_NAME=MiniMax-M2.7
      - MUSIC_LIBRARY_DIR=/app/data/bgm
      - WHISPER_MODEL=base
      - DEFAULT_TTS_VOICE=zh-CN-XiaoxiaoNeural
      - DEFAULT_STRATEGY=pad
      - DEFAULT_TARGET_RATIO=0.5625
      - DEBUG=false
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8004/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  frontend:
    image: node:20-alpine
    container_name: mediarefit-frontend-dev
    working_dir: /app
    command: sh -c "npm install && npm run dev -- --host 0.0.0.0 --port 8080"
    ports:
      - "8080:8080"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_BASE_URL=http://localhost:8004
    restart: unless-stopped
```

---

## 4. 详细文件设计

### 4.1 目录结构

```
MediaRefitAgent/
├── docker/
│   ├── Dockerfile              # 多阶段构建
│   ├── docker-compose.yml      # 开发环境
│   ├── docker-compose.prod.yml # 生产环境
│   ├── .dockerignore
│   ├── nginx/
│   │   └── nginx.conf         # nginx 配置
│   └── scripts/
│       ├── init.sh            # 容器启动脚本
│       └── wait-for-it.sh     # 依赖等待脚本
├── data/
│   ├── outputs/               # 输出视频（gitignore）
│   └── bgm/                    # BGM 音乐库（gitignore）
├── backend/                    # 已存在
├── frontend/                   # 已存在
├── yolov8n.pt                  # YOLO 模型
└── requirements.txt            # 已存在
```

### 4.2 nginx.conf

```nginx
server {
    listen 80;
    server_name localhost;

    # 前端静态资源
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://backend:8004/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 流式响应支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # WebSocket 支持（Agent 流式对话）
    location /api/agent/ {
        proxy_pass http://backend:8004/api/agent/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }
}
```

### 4.3 .dockerignore

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.git
.gitignore
.vscode
*.md
!requirements.txt
node_modules
.env
.venv
venv
*.log
.DS_Store
Thumbs.db
data/
tests/
docs/
```

### 4.4 生产级 docker-compose.prod.yml

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: mediarefit-agent
    restart: always
    ports:
      - "8004:8004"          # 后端 API（调试用）
    volumes:
      - ./data/outputs:/app/data/outputs
      - ./data/bgm:/app/data/bgm
      - ./data/models:/app/data/models:ro
    env_file:
      - .env.docker         # 生产环境变量（不含敏感信息）
    environment:
      - PYTHONUNBUFFERED=1
      - OUTPUT_DIR=/app/data/outputs
      - FFMPEG_DIR=/usr/bin
      - FFMPEG_PATH=/usr/bin
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8004/api/health')"]
      interval: 30s
      timeout: 10s
      start_period: 120s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: mediarefit-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
    depends_on:
      - app
    command: ["/wait-for-it.sh", "app:8004", "--", "nginx", "-g", "daemon off;"]

networks:
  default:
    name: mediarefit-network
```

---

## 5. 环境变量设计

### 5.1 .env.docker（生产环境）

```env
# =================== 服务配置 ===================
API_PORT=8004
OUTPUT_DIR=/app/data/outputs

# =================== FFmpeg 配置 ===================
FFMPEG_PATH=/usr/bin
FFMPEG_DIR=/usr/bin
FFMPEG_PRESET_TRANSFORM=ultrafast
FFMPEG_CRF_TRANSFORM=23

# =================== MiniMax API ===================
MINIMAX_API_KEY=your_api_key_here     # 通过 docker secret 或 CI/CD 注入
MINIMAX_API_BASE=https://api.minimax.chat/v1
MINIMAX_API_URL=https://api.minimax.chat/v1/text/chatcompletion_v2
MINIMAX_MODEL_NAME=MiniMax-M2.7

# =================== BGM 音乐库 ===================
MUSIC_LIBRARY_DIR=/app/data/bgm

# =================== Whisper 配置 ===================
WHISPER_MODEL=base

# =================== 默认值 ===================
DEFAULT_TTS_VOICE=zh-CN-XiaoxiaoNeural
DEFAULT_STRATEGY=pad
DEFAULT_TARGET_RATIO=0.5625

# =================== 日志 ===================
DEBUG=false
LOG_LEVEL=INFO
```

### 5.2 环境变量映射表

| .env 配置项 | Docker 环境变量 | 说明 |
|-----------|----------------|------|
| `FFMPEG_PATH=C:/ffmpeg/...` | `FFMPEG_PATH=/usr/bin` | Linux 路径 |
| `OUTPUT_DIR=F:/video` | `OUTPUT_DIR=/app/data/outputs` | Linux 路径 |
| `MUSIC_LIBRARY_DIR=F:/video/bgm` | `MUSIC_LIBRARY_DIR=/app/data/bgm` | Linux 路径 |

---

## 6. 镜像优化策略

### 6.1 减小镜像体积

1. **Python slim 基础镜像**：使用 `python:3.11-slim` 而非完整镜像（约 800MB → 150MB）
2. **多阶段构建**：frontend build 阶段用 `node:20-alpine`，运行时用 `nginx:alpine`
3. **pip 缓存禁用**：`--no-cache-dir` 避免 pip 缓存占用空间
4. **合并 layer**：将 `COPY requirements.txt` 和 `pip install` 放在一起，利用 Docker 缓存

### 6.2 构建时间优化

| 优化项 | 说明 |
|-------|------|
| CPU-only PyTorch | 使用 `--index-url https://download.pytorch.org/whl/cpu`，避免下载 CUDA 版本（约 1.5GB） |
| YOLO 模型预下载 | 在构建时下载而非容器启动时 |
| 依赖分层缓存 | requirements.txt 单独 COPY，修改代码不会重新安装依赖 |

### 6.3 GPU 支持（可选）

如需 GPU 加速（YOLO 推理加速），添加 NVIDIA GPU 支持：

```yaml
# docker-compose.yml
services:
  app:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

基础镜像需改为：
```dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
```

---

## 7. 数据备份与持久化

### 7.1 数据卷策略

```
data/
├── outputs/          # 处理完成的视频（定期备份）
│   └── .gitkeep
├── bgm/              # BGM 音乐库（定期备份）
│   └── .gitkeep
└── models/           # YOLO 模型（只读挂载）
    └── .gitkeep
```

### 7.2 备份脚本（可选）

```bash
#!/bin/bash
# docker/backup.sh
BACKUP_DIR="./backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
docker run --rm -v mediarefit_data_outputs:/data/outputs -v "$BACKUP_DIR:/backup" alpine \
    tar czf /backup/outputs.tar.gz -C /data/outputs .
echo "Backup saved to $BACKUP_DIR"
```

---

## 8. 部署流程

### 8.1 开发环境

```bash
# 1. 创建数据目录
mkdir -p data/outputs data/bgm data/models

# 2. 复制环境变量文件
cp .env .env.docker

# 3. 拉取 YOLO 模型（首次构建）
# 如 yolov8n.pt 不存在，Dockerfile 会自动下载
cp yolov8n.pt docker/ 2>/dev/null || true

# 4. 构建并启动
docker-compose -f docker/docker-compose.yml up -d --build

# 5. 查看日志
docker-compose -f docker/docker-compose.yml logs -f
```

### 8.2 生产环境

```bash
# 1. 配置生产环境变量
vim .env.docker
# 编辑 MINIMAX_API_KEY 等敏感信息

# 2. 构建生产镜像
docker build -f docker/Dockerfile -t mediarefit:latest .

# 3. 启动服务
docker-compose -f docker/docker-compose.prod.yml up -d

# 4. 验证健康状态
curl http://localhost:8004/api/health
```

### 8.3 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose -f docker/docker-compose.prod.yml up -d --build

# 清理旧镜像
docker image prune -f
```

---

## 9. 验证方案

### 9.1 容器健康检查

```bash
# 检查容器状态
docker ps --filter name=mediarefit

# 检查后端健康
curl http://localhost:8004/api/health

# 检查 capabilities
curl http://localhost:8004/api/capabilities
```

### 9.2 端到端测试

```bash
# 1. 视频方向检测
curl -X POST "http://localhost:8004/api/detect-orientation" \
  -F "file=@test_video.mp4"

# 2. 视频转换（SSE 流式）
curl -X POST "http://localhost:8004/api/transform-stream" \
  -F "file=@test_video.mp4" \
  -F "target_orientation=portrait" \
  -F "strategy=pad"

# 3. Agent 多轮对话
SESSION_ID=$(curl -s -X POST "http://localhost:8004/api/agent/chat" \
  -F "file=@test_video.mp4" \
  -F 'message=把视频转成竖屏' | jq -r '.session_id')

curl -X POST "http://localhost:8004/api/agent/continue" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"改用智能裁剪\", \"session_id\": \"$SESSION_ID\"}"
```

---

## 10. 文件清单

以下文件需要新建：

| 文件路径 | 说明 |
|---------|------|
| `docker/Dockerfile` | 多阶段构建 |
| `docker/docker-compose.yml` | 开发环境编排 |
| `docker/docker-compose.prod.yml` | 生产环境编排 |
| `docker/.dockerignore` | 构建排除 |
| `docker/nginx/nginx.conf` | nginx 反向代理配置 |
| `docker/scripts/init.sh` | 容器初始化脚本 |
| `docker/scripts/wait-for-it.sh` | 依赖等待脚本 |
| `docker/.env.docker` | 生产环境变量模板 |
| `data/outputs/.gitkeep` | 输出目录占位 |
| `data/bgm/.gitkeep` | BGM 目录占位 |
| `data/models/.gitkeep` | 模型目录占位 |

---

## 11. 关键技术决策

### 11.1 为什么不用 GPU 镜像作为默认？

PyTorch GPU 镜像约 7GB，CPU 镜像约 2GB。视频处理的主要瓶颈在 FFmpeg 而非 YOLO 推理（YOLOv8n 本身很轻量），CPU 版本已足够满足大多数场景。

### 11.2 为什么不直接用后端镜像 serve 前端？

将 Vue build 产物复制到后端容器会增加镜像复杂度。前端和后端分开构建、独立更新，更符合微服务实践。

### 11.3 为什么用 nginx 而不用 uvicorn 的静态文件服务？

- nginx 处理静态资源更高效
- 支持 HTTPS 终止、负载均衡等生产功能
- 前端路由（Vue Router history 模式）需要服务端 fallback 配置
