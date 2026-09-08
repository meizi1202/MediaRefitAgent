#!/bin/bash
# MediaRefitAgent - 容器初始化脚本

set -e

echo "🚀 MediaRefitAgent 初始化..."

# 创建必要的目录
mkdir -p /app/data/outputs
mkdir -p /app/data/bgm
mkdir -p /app/data/models

# 设置权限
chmod -R 755 /app/data

echo "✅ 初始化完成"
echo "   - 输出目录: /app/data/outputs"
echo "   - BGM 目录: /app/data/bgm"
echo "   - 模型目录: /app/data/models"

# 启动服务
exec "$@"
