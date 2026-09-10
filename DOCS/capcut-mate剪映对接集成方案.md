# MediaRefitAgent x capcut-mate 剪映对接集成方案

## Context

MediaRefitAgent 通过直接集成 `pyJianYingDraft` 库实现与剪映的对接，无需额外部署 capcut-mate 服务。

**工作流**：
```
MediaRefitAgent 创建草稿 JSON
    ↓
前端获取 draft_url
    ↓
剪映小助手客户端打开草稿
    ↓
用户在剪映中编辑预览
    ↓
导出最终视频
```

## 架构分析

### 核心模块

```
backend/capcut-mate-main/src/pyJianYingDraft/
├── script_file.py       # ScriptFile - 读写草稿 JSON
├── draft_folder.py      # DraftFolder - 草稿目录管理
├── video_segment.py     # VideoSegment - 视频片段
├── audio_segment.py     # AudioSegment - 音频片段
├── text_segment.py       # TextSegment - 文本片段
└── jianying_controller.py # 自动化导出（仅 Windows）
```

### 关键类

```
ScriptFile
├── materials: ScriptMaterial
│   ├── videos: List[VideoMaterial]
│   └── audios: List[AudioMaterial]
├── tracks: Dict[str, Track]
│   ├── video Track -> List[VideoSegment]
│   └── audio Track -> List[AudioSegment]
└── methods:
    ├── add_segment() - 添加片段到轨道
    └── save() - 保存草稿 JSON
```

## 集成方案（直接集成模式）

直接 import `pyJianYingDraft` 库，无 HTTP 调用：

```
from src.pyJianYingDraft import ScriptFile, DraftFolder
```

## 实现计划

### Step 1: 新建 jianying 模块

创建 `backend/jianying/`：

```
backend/jianying/
├── __init__.py       # 模块入口
├── client.py        # 剪映客户端（直接集成）
├── models.py        # Pydantic 模型
└── exceptions.py    # 异常定义
```

### Step 2: 新增 API 端点

```python
# 草稿管理
POST /api/jianying/create_draft   # 创建草稿
POST /api/jianying/add_videos     # 添加视频（支持转场）
POST /api/jianying/add_audios     # 添加音频
POST /api/jianying/add_captions   # 添加字幕
POST /api/jianying/save_draft     # 保存草稿
GET  /api/jianying/get_draft      # 获取草稿文件列表
```

### Step 3: 配置集成

`.env` 新增：
```env
JIANYING_DRAFT_DIR=     # 草稿存储目录
JIANYING_DRAFT_URL_BASE=http://localhost:8004/api/jianying/get_draft
```

## 功能列表

| 类别 | 功能 | 说明 |
|------|------|------|
| 草稿 | 创建、保存、获取 | 基于模板创建草稿 |
| 素材 | 视频、音频 | 支持 URL 或本地路径 |
| 字幕 | 文本字幕 | 支持样式设置 |
| 转场 | fade/slide/zoom 等 | 添加视频时指定 |
| 变速 | scene_timelines | 通过场景时间线实现 |
| 导出 | gen_video | 仅 Windows，需剪映客户端 |

## 关键文件修改

| 文件 | 操作 |
|------|------|
| `backend/jianying/__init__.py` | 新建 |
| `backend/jianying/client.py` | 新建（直接集成） |
| `backend/jianying/models.py` | 新建 |
| `backend/jianying/exceptions.py` | 新建 |
| `backend/api/fastapi_app.py` | 修改 - 新增端点 |
| `.env` | 修改 - 新增配置 |

## 依赖

```bash
pip install pymediainfo
```

## 验证计划

1. 启动 MediaRefitAgent（端口 8004）
2. 测试创建草稿 -> 添加视频 -> 保存 -> 获取文件列表
3. 客户端测试：draft_url 能在剪映中打开
