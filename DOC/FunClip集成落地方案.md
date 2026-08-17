# FunClip 集成落地方案

## 1. 概述

### 1.1 集成目的

将 [FunClip](https://github.com/alibaba-damo-academy/FunClip) 集成到 MediaRefitAgent，作为"智能缩编"功能的核心技术方案。FunClip 通过语音识别 + LLM 分析实现视频智能裁剪，特别适合中文视频场景。

### 1.2 核心链路

```
输入视频 → 语音识别（带时间戳字幕）→ LLM 分析字幕选出关键片段 → FFmpeg 自动剪接拼接 → 输出缩编视频
```

### 1.3 已在项目中

FunClip 源码已下载至 `FunClip/` 目录。

---

## 2. 模型说明

### 2.1 语音识别模型（ASR）

| 模型 | 模型 ID (ModelScope) | 大小 | 精度 | 适用场景 |
|------|---------------------|------|------|----------|
| **Paraformer-Large**（默认） | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | ~1GB | 最高 | 精确按文本裁剪，中文首选 |
| **Fun-ASR-Nano** | `FunAudioLLM/Fun-ASR-Nano-2512` | ~500MB | 高 | 多语种（普通话/英语/日语/方言） |
| **SenseVoice** | `FunAudioLLM/SenseVoiceSmall` | ~400MB | 高 | 多语种 + 情绪识别 + 音频事件检测 |

**推荐**：中文视频使用 **Paraformer-Large**，因为它提供精确的字符级时间戳。

### 2.2 说话人识别模型（可选）

| 模型 | 模型 ID (ModelScope) | 大小 | 说明 |
|------|---------------------|------|------|
| **CAM++** | `iic/speech_campplus_sv_zh-cn_16k-common` | ~300MB | 用于区分不同说话人，按人裁剪 |

### 2.3 LLM 模型（智能段落选择）

| 模型 | 调用方式 | API | 说明 |
|------|----------|-----|------|
| **MiniMax** | OpenAI 兼容 | `minimax/` 前缀路由 | ✅ **已支持**，当前项目可用 |
| **Qwen** | DashScope | `qwen_plus` 等 | 阿里云百炼 |
| **GPT-4** | OpenAI | `gpt-4` 等 | 需 API Key |

**MiniMax 配置**：
```python
# 环境变量
MINIMAX_API_KEY = "your_minimax_api_key"
MINIMAX_API_BASE = "https://api.minimax.io/v1"  # 或国内版 https://api.minimaxi.com/v1

# 模型名称格式（已在 FunClip 中支持）
minimax/xxxtoken
```

---

## 3. 硬件资源需求

### 3.1 语音识别模型

| 配置 | CPU | 内存 | GPU | 适用场景 |
|------|-----|------|-----|----------|
| **最低** | 4核 | 8GB | 无（CPU 推理） | 测试体验，慢 |
| **推荐** | 8核 | 16GB | 4GB NVIDIA | 流畅处理 1 小时视频 |
| **最佳** | 16核 | 32GB | 8GB+ NVIDIA | 高效处理，多并发 |

### 3.2 各模型显存需求

| 模型 | GPU 显存 | 说明 |
|------|----------|------|
| Paraformer-Large | ~4GB | CPU 也能跑，但慢 5-10x |
| Fun-ASR-Nano | ~2GB | 更轻量 |
| SenseVoice | ~2GB | 支持多语种 |
| CAM++ | ~1GB | 说话人识别 |

### 3.3 视频处理

| 因素 | 需求 |
|------|------|
| 临时存储 | 视频大小的 2-3 倍（中间文件） |
| 内存 | 视频解码时约 2GB/小时视频 |
| 输出格式 | MP4 (H.264/H.265) |

---

## 3.5 纯 CPU 方案先跑通（无 GPU）

### 3.5.1 环境准备

#### 1. 安装 CPU 版 PyTorch（无 GPU 加速）

```bash
# 卸载 GPU 版本（如果有）
pip uninstall torch torchvision torchaudio -y

# 安装 CPU 版本
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

#### 2. 安装 FunClip 依赖

```bash
cd FunClip
pip install -r requirements.txt
```

#### 3. 安装系统依赖

```bash
# Ubuntu
apt-get update && apt-get install -y ffmpeg imagemagick

# Windows
# 下载安装 ImageMagick: https://imagemagick.org/script/download.php#windows
```

#### 4. 下载字体文件

```bash
cd FunClip
mkdir -p font
wget https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ClipVideo/STHeitiMedium.ttc -O font/STHeitiMedium.ttc
```

#### 5. 配置 MiniMax API

```bash
export MINIMAX_API_KEY="your_minimax_api_key"
export MINIMAX_API_BASE="https://api.minimax.io/v1"  # 或国内版 https://api.minimaxi.com/v1
```

### 3.5.2 选择轻量级 ASR 模型

在无 GPU 环境下，推荐使用 **Fun-ASR-Nano** 或 **SenseVoice**：

| 模型 | 内存需求 | CPU 兼容性 | 推荐场景 |
|------|----------|-----------|----------|
| **Fun-ASR-Nano** | ~4GB | ✅ 良好 | 中文视频首选 |
| **SenseVoice** | ~4GB | ✅ 良好 | 多语种 + 情绪识别 |

**不推荐 Paraformer-Large**：在 CPU 上非常慢（可能慢 5-10x）

### 3.5.3 启动命令（CPU 模式）

```bash
cd FunClip

# 使用 Fun-ASR-Nano（中文）
python funclip/launch.py -m fun-asr-nano

# 或使用 SenseVoice（多语种）
python funclip/launch.py -m sensevoice

# 指定端口
python funclip/launch.py -m fun-asr-nano -p 7860
```

### 3.5.4 命令行测试（无需 Gradio）

如果只想先测试核心功能，用命令行方式：

```bash
cd FunClip

# 创建示例目录
mkdir -p examples
# 放入你的测试视频

# 步骤1：语音识别（生成字幕）
python funclip/videoclipper.py --stage 1 \
    --file examples/你的视频.mp4 \
    --output_dir ./output

# 生成的字幕在 ./output/ 目录下

# 步骤2：查看识别结果后，手动指定片段裁剪
python funclip/videoclipper.py --stage 2 \
    --file examples/你的视频.mp4 \
    --output_dir ./output \
    --dest_text '你要裁剪的文本片段' \
    --start_ost 0 \
    --end_ost 100 \
    --output_file './output/result.mp4'
```

### 3.5.5 Python API 测试

```python
import os
os.environ['MINIMAX_API_KEY'] = 'your_api_key'

from funclip.videoclipper import VideoClipper
from funclip.llm.openai_api import openai_call

# 使用 Fun-ASR-Nano（CPU 友好）
clipper = VideoClipper(funasr_model='fun-asr-nano')

# 语音识别
audio_path = 'examples/你的视频.mp4'
result = clipper.recog(audio_path, output_dir='./output')

print("识别结果:", result)

# 使用 MiniMax 分析（API 调用，无本地算力）
srt_content = open('./output/xxx.srt').read()
analysis = openai_call(
    apikey=os.environ['MINIMAX_API_KEY'],
    model='minimax/xxxtoken',  # 你的 MiniMax 模型
    user_content=f"分析以下字幕，选出关键片段：\n{srt_content}",
    system_content="你是一个视频剪辑专家..."
)
print("LLM 分析结果:", analysis)
```

### 3.5.6 验证清单

- [ ] PyTorch CPU 版安装成功：`python -c "import torch; print(torch.__version__)"`
- [ ] FunClip 依赖安装成功：`python -c "import funasr; print(funasr.__version__)"`
- [ ] FFmpeg 可用：`ffmpeg -version`
- [ ] ImageMagick 可用：`convert -version`
- [ ] MiniMax API 可用：设置 `MINIMAX_API_KEY` 后测试
- [ ] 模型自动下载：首次运行会自动下载 ASR 模型

### 3.5.7 预期性能（CPU 模式）

| 视频时长 | Fun-ASR-Nano | SenseVoice |
|----------|-------------|------------|
| 1 分钟 | ~30 秒 | ~20 秒 |
| 10 分钟 | ~5 分钟 | ~3 分钟 |
| 1 小时 | ~30 分钟 | ~20 分钟 |

---

## 3.6 重要说明：GPU 资源与 MiniMax 调度

### 3.5.1 模型调用架构

| 模型类型 | 调用方式 | 是否需要本地 GPU |
|----------|----------|-----------------|
| **ASR 模型**（Paraformer/Fun-ASR-Nano/SenseVoice） | **本地运行** | ✅ 需要 |
| **LLM 模型**（MiniMax/Qwen/GPT） | **API 调用** | ❌ 不需要 |

### 3.5.2 处理流程中的资源消耗

```
┌─────────────────────────────────────────────────────────┐
│                    FunClip 处理流程                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  视频 → ASR 识别（本地）→ 字幕 → LLM 分析（API）→ 裁剪   │
│              ↓                                           │
│        需要 GPU/CPU                                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**结论**：即使 LLM 全部使用 MiniMax API，**ASR 模型仍需要本地算力**，无法完全脱离 GPU/CPU。

### 3.5.3 不同配置下的处理能力

| 配置 | ASR 处理速度 | 适用场景 |
|------|-------------|----------|
| **8核 CPU + 16GB RAM** | ~5-10x 实时 | 1 小时视频需 6-12 分钟 |
| **4核 CPU + 8GB RAM** | ~2-5x 实时 | 1 小时视频需 15-30 分钟 |
| **4GB GPU** | ~15-30x 实时 | 1 小时视频需 2-4 分钟 |

### 3.5.4 仅 CPU 运行建议

如果无 GPU，推荐使用更轻量的 ASR 模型：

| 模型 | CPU 兼容性 | 内存需求 | 处理速度 |
|------|-----------|----------|----------|
| **Fun-ASR-Nano** | ✅ 良好 | ~4GB RAM | 中等 |
| **SenseVoice** | ✅ 良好 | ~4GB RAM | 较快 |
| **Paraformer-Large** | ⚠️ 较慢 | ~8GB RAM | 较慢 |

---

## 4. 集成方案

### 4.1 目录结构

```
MediaRefitAgent/
├── FunClip/                    # [新增] FunClip 源码
│   ├── funclip/
│   │   ├── videoclipper.py    # 核心视频剪辑类
│   │   ├── llm/               # LLM 调用（已支持 MiniMax）
│   │   └── utils/
│   └── requirements.txt
├── video/
│   ├── processor.py           # [复用] FFmpeg 基础操作
│   └── condenser.py           # [新增] 缩编核心逻辑，调用 FunClip
└── ...
```

### 4.2 集成方式

#### 方案 A：直接调用 FunClip Python API

```python
from funclip.videoclipper import VideoClipper
from funclip.llm.openai_api import openai_call

# 初始化 VideoClipper（加载 Paraformer-Large 模型）
clipper = VideoClipper(funasr_model='paraformer')

# 步骤1：语音识别
result = clipper.recog(audio_input, output_dir='./output')
# 生成带时间戳的 SRT 字幕

# 步骤2：LLM 智能分析（使用 MiniMax）
selected_segments = openai_call(
    apikey=os.environ.get('MINIMAX_API_KEY'),
    model='minimax/xxxtoken',
    user_content=f"分析以下字幕，选出最精彩的片段：\n{srt_content}",
    system_content="你是一个视频剪辑专家..."
)

# 步骤3：FFmpeg 裁剪拼接
clipper.clip(...)
```

#### 方案 B：通过命令行封装

```python
import subprocess

def funclip_smart_crop(video_path, output_path, llm_model='minimax/xxxtoken'):
    # 阶段1：识别
    subprocess.run([
        'python', 'FunClip/funclip/videoclipper.py',
        '--stage', '1',
        '--file', video_path,
        '--output_dir', './output'
    ])

    # 阶段2：LLM 分析（自定义 prompt）

    # 阶段3：裁剪
    subprocess.run([
        'python', 'FunClip/funclip/videoclipper.py',
        '--stage', '2',
        '--file', video_path,
        '--dest_text', '用户选择的片段',
        '--output_file', output_path
    ])
```

### 4.3 新增文件

| 文件 | 说明 |
|------|------|
| `video/condenser.py` | 缩编核心逻辑，封装 FunClip 调用 |
| `video/funclip_wrapper.py` | FunClip Python API 封装 |
| `api/fastapi_app.py` | 添加 `/api/condense/funclip` 端点 |

---

## 5. MiniMax 模型配置

### 5.1 环境变量

```bash
# 设置 MiniMax API Key
export MINIMAX_API_KEY="your_api_key_here"

# 可选：国内版 API
export MINIMAX_API_BASE="https://api.minimaxi.com/v1"
```

### 5.2 模型名称格式

FunClip 中 MiniMax 模型使用 `minimax/` 前缀：

| 实际模型 | 在 FunClip 中的名称 |
|----------|---------------------|
| MiniMax-01 | `minimax/ MiniMax-01` |
| 其他 MiniMax 模型 | `minimax/<model_name>` |

### 5.3 LLM Prompt 示例（用于智能段落选择）

```python
SYSTEM_PROMPT = """你是一个专业的视频剪辑师。给定一段视频的字幕内容，
请分析并选出最精彩、最有价值的片段。
要求：
1. 选择 3-5 个片段，总时长控制在目标时长内
2. 每个片段需要有明确的开始和结束时间
3. 优先选择有信息量、有情感、有动作的画面
4. 返回格式：时间戳 - 片段内容摘要"""

USER_PROMPT = """请分析以下字幕，选出最精彩的片段（目标时长：60秒）：

{srt_content}

请按以下格式返回：
1. 00:15 - 00:25 | 讨论乡村振兴设计方案
2. 01:30 - 01:45 | 展示实际效果对比
..."""
```

---

## 6. 依赖安装

### 6.1 FunClip 依赖

```bash
cd FunClip
pip install -r requirements.txt
```

主要依赖：
- `funasr>=1.3.29` - FunASR 语音识别
- `transformers>=4.32.0` - 模型加载
- `moviepy==1.0.3` - 视频处理
- `openai` - LLM 调用
- `gradio>=4.31.3` - WebUI（可选）

### 6.2 系统依赖

```bash
# Ubuntu
apt-get install ffmpeg imagemagick

# Windows
# 安装 ImageMagick: https://imagemagick.org/script/download.php#windows
# 下载字体: https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ClipVideo/STHeitiMedium.ttc
```

---

## 7. API 接口设计

### 7.1 新增端点

#### POST `/api/condense/funclip`
**功能**：FunClip 智能缩编
```
请求：
{
  "file": File,
  "options": {
    "asr_model": "paraformer",        // paraformer / fun-asr-nano / sensevoice
    "llm_model": "minimax/xxxtoken",  // MiniMax 模型
    "target_duration": 60,            // 目标时长（秒）
    "hotwords": "",                   // 热词（可选）
    "speaker_id": null                // 指定说话人（可选）
  }
}

响应：
{
  "task_id": "xxx",
  "status": "completed",
  "output_file": "/outputs/xxx_funclip.mp4",
  "subtitle_file": "/outputs/xxx.srt",
  "segments": [
    {"start": 15.5, "end": 25.0, "text": "讨论乡村振兴..."},
    {"start": 90.2, "end": 105.0, "text": "展示效果对比..."}
  ]
}
```

---

## 8. 限制与注意事项

### 8.1 FunClip 限制

- **重度依赖音频字幕**：无声视频效果差，需要先添加配音或背景音乐
- 精确按文本裁剪请使用 **Paraformer**，因为 Nano 版本不提供可靠的字符级时间戳

### 8.2 解决方案

| 问题 | 解决方案 |
|------|----------|
| 无声视频 | 先用 TTS 添加配音，再使用 FunClip |
| 纯音乐视频 | 使用其他缩编方式（精彩片段识别） |
| 英文视频 | 使用 `-l en` 参数切换到 Paraformer 英文模型 |

---

## 9. 部署检查清单

- [ ] 安装 FunClip 依赖：`pip install -r FunClip/requirements.txt`
- [ ] 安装系统依赖：`ffmpeg`、`imagemagick`
- [ ] 下载字体文件：`font/STHeitiMedium.ttc`
- [ ] 配置环境变量：`MINIMAX_API_KEY`
- [ ] 首次运行会自动下载 ASR 模型（约 1-2GB）
- [ ] 验证：运行 FunClip CLI 或启动 Gradio WebUI

---

## 10. 实际实现方案（2026-08-17）

### 10.1 实现概述

> ✅ **已实现** - FunClip 调度层已完成

由于 FunClip 原生 ASR 模型（Paraformer-Large/Fun-ASR-Nano）在 Windows CPU 环境下存在依赖问题，当前实现采用 **Whisper ASR** 作为替代方案，保持了 FunClip 的核心处理流程。

### 10.2 技术架构

```
┌──────────────────────────────────────────────────────────────┐
│                      FunClip 调度层                           │
│                  video/condenser.py                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  输入视频 ──► FFmpeg ──► Whisper ASR ──► 片段评分/选择      │
│                   提取音频    (Base模型)     │                 │
│                                          ▼                 │
│                              ┌─────────────────────┐        │
│                              │  能量评分 或 LLM选择 │        │
│                              └─────────────────────┘        │
│                                          │                 │
│                                          ▼                 │
│                              FFmpeg ──► 输出视频            │
│                            Cut/Concat                       │
└──────────────────────────────────────────────────────────────┘
```

### 10.3 已实现文件

| 文件 | 路径 | 说明 |
|------|------|------|
| **FunClip 调度层** | `video/condenser.py` | 缩编核心逻辑，包含三种策略 |
| **ASR/FFmpeg 封装** | `video/funclip_wrapper.py` | Whisper ASR + FFmpeg 封装 |
| **CLI 工具** | `video/condenser_cli.py` | 命令行缩编工具 |
| **API 端点** | `api/fastapi_app.py` | `/api/condense` 等端点 |

### 10.4 三种缩编策略实现

#### 10.4.1 content_condense（内容缩编）

```python
# video/condenser.py - _condense_with_funclip()

# 流程：
# 1. FFmpeg 提取音频 (16kHz WAV)
# 2. Whisper Base 语音识别 → 获取带时间戳的文本片段
# 3. 能量评分 或 LLM 选择
#    - 有 MiniMax API Key → 调用 MiniMax LLM 智能选择
#    - 无 API Key → 基于音频能量评分选择
# 4. FFmpeg filter_complex 拼接
# 5. 生成 SRT 字幕
```

**代码位置**：`video/condenser.py` - `_condense_with_funclip()`

#### 10.4.2 smart_compress（智能压缩）

```python
# video/condenser.py - _smart_compress()

# 流程：
# 1. FFmpeg H.265 重编码
# 2. 保持原有时长
# 3. 文件体积减小
```

**代码位置**：`video/condenser.py` - `_smart_compress()`

#### 10.4.3 smart_crop（智能裁剪）

```python
# video/condenser.py - _smart_crop()

# 流程：
# 1. SmartCropper 采样视频帧（默认10帧）
# 2. YOLOv8 检测每帧中的主体
# 3. 合并检测框，计算主体中心
# 4. 根据目标比例计算裁剪窗口
# 5. FFmpeg crop filter 应用裁剪
```

**代码位置**：
- `video/condenser.py` - `_smart_crop()`
- `ml/smart_cropper.py` - `SmartCropper.crop_video_frames()`

### 10.5 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/condense` | POST | 视频智能缩编（支持三种策略） |
| `/api/condense/segments` | POST | 指定片段缩编拼接 |
| `/api/condense/transcribe` | POST | 仅语音识别，返回字幕 |

### 10.6 CLI 用法

```bash
# 内容缩编（目标60秒）
python -m video.condenser_cli --video input.mp4 --strategy content_condense --target-duration 60

# 智能压缩
python -m video.condenser_cli --video input.mp4 --strategy smart_compress

# 智能裁剪（目标9:16竖屏）
python -m video.condenser_cli --video input.mp4 --strategy smart_crop --target-ratio 0.5625

# 仅语音识别
python -m video.condenser_cli --video input.mp4 --transcribe-only
```

### 10.7 与 FunClip 源码的关系

| FunClip 组件 | 状态 | 替代方案 |
|-------------|------|----------|
| Paraformer-Large ASR | ⚠️ 依赖问题未解决 | Whisper Base（已验证可用） |
| Fun-ASR-Nano | ⚠️ 依赖问题未解决 | Whisper Base |
| SenseVoice | ⚠️ 未测试 | Whisper Base |
| VideoClipper 类 | ✅ 可复用思路 | 自研调度层 |
| SRT 生成 | ✅ 已实现 | `_segments_to_srt()` |
| FFmpeg 裁剪拼接 | ✅ 已实现 | `filter_complex` |
| LLM 智能选段 | ✅ 可选 | MiniMax API |

**说明**：FunClip 源码已下载至 `FunClip/` 目录，保留了后续集成的可能性。当 FunClip ASR 依赖问题解决后，可切换使用原生 Paraformer/Fun-ASR-Nano 模型。

### 10.8 待优化项

- [ ] FunClip ASR 模型（Paraformer/Fun-ASR-Nano）依赖问题解决后，替换 Whisper
- [ ] LLM 智能选段功能完善（当前为可选，需要配置 MiniMax API Key）
- [ ] 说话人识别（CAM++）集成
- [ ] 视频摘要生成（text/video）
