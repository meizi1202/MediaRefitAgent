# 剪映对接 API 文档

MediaRefitAgent 通过直接集成 `pyJianYingDraft` 库实现与剪映的对接，无需额外部署 capcut-mate 服务。

**基础 URL**：`http://localhost:8004/api/jianying`

---

## 通用返回格式

```json
{
  "success": true,
  "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=xxx",
  "message": "操作成功",
  "data": { ... }
}
```

**错误响应**：
```json
{
  "detail": "错误信息"
}
```

---

## 1. 创建草稿

**POST** `/api/jianying/create_draft`

创建新的剪映草稿项目。

### 请求参数（FormData）

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|------|------|--------|------|------|
| `width` | int | 1920 | 否 | 视频宽度（像素） |
| `height` | int | 1080 | 否 | 视频高度（像素） |

### 请求示例

```
POST /api/jianying/create_draft
Content-Type: application/x-www-form-urlencoded

width=1080&height=1920
```

### 响应示例

```json
{
  "success": true,
  "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef",
  "message": "草稿创建成功",
  "data": {
    "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef",
    "tip_url": "https://docs.jcaigc.cn/"
  }
}
```

---

## 2. 添加视频

**POST** `/api/jianying/add_videos`

添加视频素材到草稿，支持转场效果。

### 请求参数（FormData）

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|------|------|--------|------|------|
| `draft_url` | string | - | 是 | 草稿URL |
| `videos` | string (JSON) | - | 是 | 视频信息列表 |
| `alpha` | float | 1.0 | 否 | 透明度 [0, 1] |
| `scale_x` | float | 1.0 | 否 | X轴缩放 |
| `scale_y` | float | 1.0 | 否 | Y轴缩放 |
| `transform_x` | int | 0 | 否 | X轴偏移（像素） |
| `transform_y` | int | 0 | 否 | Y轴偏移（像素） |

### videos JSON 格式

```json
[
  {
    "video_url": "https://example.com/video.mp4",
    "start": 0,
    "end": 5000000,
    "width": 1920,
    "height": 1080,
    "duration": 5000000,
    "transition": "fade",
    "transition_duration": 500000,
    "volume": 1.0
  }
]
```

**字段说明**：
- `video_url`：视频 URL（支持本地路径或网络 URL）
- `start`：开始时间（**微秒**，1秒 = 1000000微秒）
- `end`：结束时间（**微秒**）
- `width`/`height`：视频宽高（可选）
- `duration`：视频总时长（可选）
- `transition`：转场类型（可选），见下方
- `transition_duration`：转场时长（微秒，默认 500000）
- `volume`：音量 [0, 10]，默认 1.0

**转场类型**：
- `fade`：淡入淡出
- `slide`：滑动
- `zoom`：缩放
- `blur`：模糊
- `rotate`：旋转
- `dissolve`：溶解

### 请求示例

```
POST /api/jianying/add_videos
Content-Type: application/x-www-form-urlencoded

draft_url=http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef
videos=[{"video_url":"F:/video/input.mp4","start":0,"end":5000000}]
```

### 响应示例

```json
{
  "success": true,
  "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef",
  "message": "视频添加成功",
  "data": {
    "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef",
    "track_id": "video_track_abc123",
    "video_ids": ["video_001"],
    "segment_ids": ["segment_001"]
  }
}
```

---

## 3. 添加音频

**POST** `/api/jianying/add_audios`

添加音频素材到草稿。

### 请求参数（FormData）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `draft_url` | string | 是 | 草稿URL |
| `audios` | string (JSON) | 是 | 音频信息列表 |

### audios JSON 格式

```json
[
  {
    "audio_url": "https://example.com/bgm.mp3",
    "start": 0,
    "end": 30000000,
    "duration": 30000000,
    "volume": 1.0,
    "fade_in": 0,
    "fade_out": 0
  }
]
```

**字段说明**：
- `audio_url`：音频 URL
- `start`：开始时间（**微秒**）
- `end`：结束时间（**微秒**）
- `duration`：音频总时长（可选）
- `volume`：音量 [0, 10]，默认 1.0
- `fade_in`：淡入时长（微秒）
- `fade_out`：淡出时长（微秒）

### 请求示例

```
POST /api/jianying/add_audios
Content-Type: application/x-www-form-urlencoded

draft_url=http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef
audios=[{"audio_url":"F:/video/bgm.mp3","start":0,"end":30000000}]
```

### 响应示例

```json
{
  "success": true,
  "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef",
  "message": "音频添加成功",
  "data": {
    "draft_url": "...",
    "track_id": "audio_track_xyz789",
    "audio_ids": ["audio_001"]
  }
}
```

---

## 4. 添加字幕

**POST** `/api/jianying/add_captions`

添加字幕到草稿。

### 请求参数（FormData）

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|------|------|--------|------|------|
| `draft_url` | string | - | 是 | 草稿URL |
| `captions` | string (JSON) | - | 是 | 字幕信息列表 |
| `text_color` | string | #FFFFFF | 否 | 文字颜色 |
| `border_color` | string | #000000 | 否 | 描边颜色 |
| `font_size` | int | 40 | 否 | 字体大小 |

### captions JSON 格式

```json
[
  {
    "text": "第一行字幕内容",
    "start": 0,
    "end": 3000000
  },
  {
    "text": "第二行字幕内容",
    "start": 3000000,
    "end": 6000000
  }
]
```

**字段说明**：
- `text`：字幕文本内容
- `start`：开始时间（**微秒**）
- `end`：结束时间（**微秒**）

### 请求示例

```
POST /api/jianying/add_captions
Content-Type: application/x-www-form-urlencoded

draft_url=http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef
captions=[{"text":"Hello World","start":0,"end":3000000}]
text_color=#FFFF00
font_size=48
```

### 响应示例

```json
{
  "success": true,
  "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef",
  "message": "字幕添加成功",
  "data": {
    "draft_url": "...",
    "track_id": "text_track_sub001",
    "text_ids": ["text_001"],
    "segment_ids": ["segment_001"]
  }
}
```

---

## 5. 保存草稿

**POST** `/api/jianying/save_draft`

保存草稿到本地文件系统。

### 请求参数（FormData）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `draft_url` | string | 是 | 草稿URL |

### 请求示例

```
POST /api/jianying/save_draft
Content-Type: application/x-www-form-urlencoded

draft_url=http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef
```

### 响应示例

```json
{
  "success": true,
  "draft_url": "http://localhost:8004/api/jianying/get_draft?draft_id=20260903123456abcdef",
  "message": "草稿保存成功"
}
```

---

## 6. 获取草稿

**GET** `/api/jianying/get_draft`

获取草稿文件列表。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `draft_id` | string | 是 | 草稿ID（从 draft_url 中解析） |

### 请求示例

```
GET /api/jianying/get_draft?draft_id=20260903123456abcdef
```

### 响应示例

```json
{
  "success": true,
  "draft_url": "?draft_id=20260903123456abcdef",
  "message": "获取草稿成功",
  "data": {
    "files": ["draft_info.json", "draft_content.json"]
  }
}
```

---

## 7. 触发视频生成

**POST** `/api/jianying/gen_video`

触发视频生成（云渲染）。**注意：此功能需要 Windows 系统上安装剪映桌面版**。

### 请求参数（FormData）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `draft_url` | string | 是 | 草稿URL |
| `api_key` | string | 否 | API密钥 |

### 响应示例

```json
{
  "success": true,
  "message": "草稿已保存。请在 Windows 系统上使用剪映客户端导出视频。",
  "data": {
    "draft_url": "..."
  }
}
```

---

## 8. 查询生成状态

**GET** `/api/jianying/gen_video_status`

查询视频生成状态。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `draft_url` | string | 是 | 草稿URL |

### 响应示例

```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "status": "pending",
    "progress": 0,
    "video_url": "",
    "error_message": ""
  }
}
```

**status 可能的值**：
- `pending`：等待生成
- `completed`：已完成
- `failed`：生成失败

---

## 完整使用流程

### 场景：为视频添加字幕

```
1. 创建草稿
   POST /api/jianying/create_draft
   → 获取 draft_url

2. 添加视频（原始素材）
   POST /api/jianying/add_videos
   → 获取 track_id, video_ids

3. 语音识别生成字幕（外部处理）
   → 获取字幕列表 [{text, start, end}, ...]

4. 添加字幕
   POST /api/jianying/add_captions
   captions=[{text:"字幕内容", start:0, end:3000000}]

5. 保存草稿
   POST /api/jianying/save_draft

6. 获取草稿并打开
   GET /api/jianying/get_draft?draft_id=xxx
   → 在剪映客户端中打开编辑
```

### cURL 示例

```bash
# 1. 创建草稿（竖屏 1080x1920）
curl -X POST "http://localhost:8004/api/jianying/create_draft" \
  -d "width=1080" -d "height=1920"

# 2. 添加视频
curl -X POST "http://localhost:8004/api/jianying/add_videos" \
  -d "draft_url=http://localhost:8004/api/jianying/get_draft?draft_id=xxx" \
  -d 'videos=[{"video_url":"F:/video/input.mp4","start":0,"end":10000000}]'

# 3. 添加字幕
curl -X POST "http://localhost:8004/api/jianying/add_captions" \
  -d "draft_url=http://localhost:8004/api/jianying/get_draft?draft_id=xxx" \
  -d 'captions=[{"text":"第一句台词","start":0,"end":2000000},{"text":"第二句台词","start":2000000,"end":4000000}]' \
  -d "text_color=#FFFF00" -d "font_size=48"

# 4. 保存草稿
curl -X POST "http://localhost:8004/api/jianying/save_draft" \
  -d "draft_url=http://localhost:8004/api/jianying/get_draft?draft_id=xxx"
```

---

## 注意事项

1. **时间单位**：所有时间相关参数（start、end、duration、transition_duration 等）单位均为**微秒**
   - 1 秒 = 1,000,000 微秒
   - 例如：5 秒 = 5,000,000 微秒

2. **字体支持**：默认使用"思源黑体"，需确保剪映客户端安装了对应字体

3. **草稿有效期**：草稿数据存储在内存中，重启服务后会丢失，请及时保存

4. **视频导出**：视频生成导出功能仅支持 Windows 系统，需要安装剪映桌面版

5. **draft_url 格式**：`http://localhost:8004/api/jianying/get_draft?draft_id=xxx`
