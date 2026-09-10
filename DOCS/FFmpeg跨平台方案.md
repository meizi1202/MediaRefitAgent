# FFmpeg 跨平台兼容方案

## 背景

当前项目代码中 FFmpeg 路径和命令存在 Windows 硬编码问题，导致在 Linux/macOS 环境（特别是 Docker 容器）中无法正常运行。

## 问题分析

### 1. 当前问题代码

| 文件 | 位置 | 问题 |
|------|------|------|
| `backend/video/processor.py` | 第 16-18 行 | FFmpeg 路径硬编码为 `C:/ffmpeg/.../ffmpeg.exe` |
| `backend/video/tts.py` | 第 213 行 | 拼接 `.exe` 后缀 |
| `backend/settings.py` | 第 49 行 | 默认路径为 Windows 格式 |
| `backend/video/bgm.py` | 第 61-62 行 | 默认目录为 `F:/video/bgm` |

### 2. 平台差异

| 平台 | `platform.system()` | ffmpeg 命令 | 示例路径 |
|------|---------------------|-------------|----------|
| Windows | `"Windows"` | `ffmpeg.exe` | `C:/ffmpeg/bin/ffmpeg.exe` |
| Linux | `"Linux"` | `ffmpeg` | `/usr/bin/ffmpeg` |
| macOS | `"Darwin"` | `ffmpeg` | `/usr/local/bin/ffmpeg` |

## 修改方案

### 方案 A：平台自动判断（推荐）

#### 1. 修改 `backend/settings.py`

新增跨平台工具函数：

```python
import os
import platform
import shutil
from pathlib import Path

def _get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default)

def _get_ffmpeg_path() -> str:
    """
    获取 FFmpeg 可执行文件路径（跨平台）

    优先级：
    1. 环境变量 FFMPEG_DIR
    2. PATH 中的 ffmpeg
    3. 常见系统路径
    """
    # 1. 优先使用环境变量
    ffmpeg_dir = os.getenv("FFMPEG_DIR", "")
    if ffmpeg_dir:
        ext = ".exe" if platform.system() == "Windows" else ""
        ffmpeg_path = Path(ffmpeg_dir) / f"ffmpeg{ext}"
        ffprobe_path = Path(ffmpeg_dir) / f"ffprobe{ext}"
        if ffmpeg_path.exists():
            return str(ffmpeg_path.parent)
        if shutil.which(str(ffmpeg_path)):
            return str(ffmpeg_path.parent)

    # 2. 直接使用命令名（已在 PATH 中）
    if shutil.which("ffmpeg"):
        return ""  # 空字符串表示使用 PATH 中的 ffmpeg

    # 3. 常见系统路径（Linux/macOS）
    for path in ["/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"]:
        if Path(path, "ffmpeg").exists():
            return path

    return ""  # 最后回退到 PATH
```

修改默认配置：

```python
# FFmpeg bin 目录（跨平台默认值）
FFMPEG_DIR = _get_str("FFMPEG_DIR", "")

def get_ffmpeg_bin() -> str:
    """获取 FFmpeg bin 目录"""
    return _get_ffmpeg_path()
```

#### 2. 修改 `backend/video/processor.py`

```python
import platform
from pathlib import Path

# 替换硬编码部分
def _get_ffmpeg_bin() -> tuple[str, str]:
    """获取 FFmpeg 和 FFprobe 路径"""
    from settings import get_ffmpeg_bin
    ffmpeg_dir = get_ffmpeg_bin()

    if platform.system() == "Windows":
        ffmpeg_name = "ffmpeg.exe"
        ffprobe_name = "ffprobe.exe"
    else:
        ffmpeg_name = "ffmpeg"
        ffprobe_name = "ffprobe"

    if ffmpeg_dir:
        return str(Path(ffmpeg_dir) / ffmpeg_name), str(Path(ffmpeg_dir) / ffprobe_name)
    else:
        return ffmpeg_name, ffprobe_name

FFMPEG_PATH, FFPROBE_PATH = _get_ffmpeg_bin()
```

#### 3. 修改 `backend/video/tts.py`

```python
# 第 213 行修改
import platform
from pathlib import Path

def _get_ffmpeg_cmd() -> str:
    """获取 FFmpeg 命令（跨平台）"""
    ffmpeg_dir = os.getenv("FFMPEG_DIR", "")
    if ffmpeg_dir and os.path.exists(ffmpeg_dir):
        ext = ".exe" if platform.system() == "Windows" else ""
        return str(Path(ffmpeg_dir) / f"ffmpeg{ext}")
    return "ffmpeg"
```

#### 4. 修改 `backend/video/bgm.py`

```python
# 第 61-62 行修改，使用配置化路径
possible_dirs = [
    Path.home() / "Music",
    Path.home() / "Music/BGM",
]
# 优先使用环境变量配置的目录
try:
    from settings import MUSIC_LIBRARY_DIR
    if MUSIC_LIBRARY_DIR:
        possible_dirs.insert(0, Path(MUSIC_LIBRARY_DIR))
except ImportError:
    pass
```

### 方案 B：配置文件驱动

在 `.env` 中添加注释说明：

```env
# FFmpeg 配置
# Linux/macOS: 留空（使用 PATH 中的 ffmpeg）或设置为 /usr/bin
# Windows: 设置为 FFmpeg bin 目录，如 C:/ffmpeg/ffmpeg-9.0-essentials_build/bin
FFMPEG_DIR=

# 音乐库目录（跨平台）
# Linux: /home/user/music/bgm
# macOS: /Users/user/Music/bgm
# Windows: F:/video/bgm
MUSIC_LIBRARY_DIR=
```

## Docker 适配

### Dockerfile 示例

```dockerfile
FROM python:3.11-slim

# 安装系统依赖（包括 ffmpeg）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用国内镜像加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY . .

# 设置环境变量（Linux 环境）
ENV FFMPEG_DIR=
ENV MUSIC_LIBRARY_DIR=/app/music

# 启动命令
CMD ["uvicorn", "api.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 修改清单汇总

| # | 文件 | 行号 | 修改内容 |
|---|------|------|---------|
| 1 | `settings.py` | 49 | 默认值改为空字符串 |
| 2 | `settings.py` | +新增 | 添加 `_get_ffmpeg_path()` 函数 |
| 3 | `settings.py` | +新增 | 添加 `get_ffmpeg_bin()` 函数 |
| 4 | `processor.py` | 16-18 | 使用 `get_ffmpeg_bin()` 替代硬编码 |
| 5 | `tts.py` | 213 | 使用 `_get_ffmpeg_cmd()` 函数 |
| 6 | `bgm.py` | 61-62 | 优先使用 `MUSIC_LIBRARY_DIR` 配置 |

## 验证方法

```python
# 验证跨平台获取
from settings import get_ffmpeg_bin
import platform

ffmpeg, ffprobe = get_ffmpeg_bin()
print(f"Platform: {platform.system()}")
print(f"FFmpeg: {ffmpeg}")
print(f"FFprobe: {ffprobe}")
```

在以下环境测试：
- [ ] Windows
- [ ] Linux (Docker)
- [ ] macOS
