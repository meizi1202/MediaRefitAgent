# ================================================
# MediaRefitAgent - Docker 多阶段构建
# ================================================
# 使用方法：
#   1. CPU 部署：直接构建（默认使用 CPU 版 torch）
#   2. GPU 部署：取消下方对应 CUDA 版本的注释，再构建
# ================================================

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

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# ================================================
# ML 依赖：选择你的环境，取消对应注释
# ================================================

# --- CPU 版本（默认，约 2GB）---
RUN pip install --no-cache-dir --break-system-packages \
    torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cpu

# --- GPU 版本（NVIDIA CUDA 11.8，约 7GB）---
# RUN pip install --no-cache-dir --break-system-packages \
#     torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu118

# --- GPU 版本（NVIDIA CUDA 12.1）---
# RUN pip install --no-cache-dir --break-system-packages \
#     torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121

# 安装 ultralytics（YOLO）
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

# 下载 YOLO 模型
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
    || [ -f /app/yolov8n.pt ] || echo "Warning: YOLO model not found"

# 复制前端构建产物
COPY --from=frontend-builder /app/dist ./frontend/dist

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/app/data/outputs
# FFMPEG_DIR 留空，代码会自动从 PATH 检测
ENV FFMPEG_DIR=
ENV MUSIC_LIBRARY_DIR=/app/data/bgm

EXPOSE 8004

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/api/health')" || exit 1

CMD ["uvicorn", "backend.api.fastapi_app:app", "--host", "0.0.0.0", "--port", "8004"]
