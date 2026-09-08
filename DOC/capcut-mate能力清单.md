# capcut-mate 能力清单

## 概述

capcut-mate 提供剪映草稿的**创建、编辑、导出**能力，支持通过 HTTP API 或直接集成 `pyJianYingDraft` 库操作剪映草稿 JSON 文件。

---

## 能力分类

### 1. 草稿管理

#### 创建草稿 `POST /create_draft`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| width | int | 否 | 1920 | 视频宽度 |
| height | int | 否 | 1080 | 视频高度 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| tip_url | string | 帮助文档 URL |

---

#### 保存草稿 `POST /save_draft`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_url | string | 是 | 草稿 URL |

---

#### 获取草稿 `GET /get_draft`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_id | string | 是 | 草稿 ID（Query） |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| files | list | 草稿文件列表 |

---

#### 视频生成 `POST /gen_video`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_url | string | 是 | 草稿 URL |
| apiKey | string | 否 | API Key（UUID 格式），非必填 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| message | string | 响应消息 |

> 注意：此功能需要 Windows 系统上安装剪映桌面版，通过 JianyingController 进行自动化导出。在非 Windows 系统上仅保存草稿。

---

#### 生成状态 `POST /gen_video_status`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_url | string | 是 | 草稿 URL |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 状态：pending / completed / failed |
| progress | int | 进度百分比 |
| video_url | string | 视频文件路径（如已完成） |
| error_message | string | 错误信息（如失败） |

---

#### 活跃任务数 `GET /gen_video_active_count`

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| count | int | 排队中 + 渲染中的任务数 |

---

### 2. 素材添加

#### 添加视频 `POST /add_videos`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| draft_url | string | 是 | | 草稿 URL |
| video_infos | string | 是 | | 视频信息列表（JSON 字符串），内部包含 video_url、start、end、transition、transition_duration、volume 等 |
| scene_timelines | list | 否 | None | 场景时间线列表，用于视频变速 |
| alpha | float | 否 | 1.0 | 全局透明度 [0, 1] |
| scale_x | float | 否 | 1.0 | X轴缩放比例，建议范围 [0.1, 5.0] |
| scale_y | float | 否 | 1.0 | Y轴缩放比例，建议范围 [0.1, 5.0] |
| transform_x | int | 否 | 0 | X轴位置偏移（像素） |
| transform_y | int | 否 | 0 | Y轴位置偏移（像素） |

**video_infos 内部结构：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| video_url | string | 是 | 视频 URL（http/https） |
| start | int | 是 | 开始时间（微秒） |
| end | int | 是 | 结束时间（微秒） |
| transition | string | 否 | 转场类型名称 |
| transition_duration | int | 否 | 转场时长（微秒） |
| volume | float | 否 | 音量 [0, 10] |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| track_id | string | 轨道 ID |
| video_ids | list | 视频 ID 列表 |
| segment_ids | list | 片段 ID 列表 |
| segment_infos | list | 片段信息列表 |

---

#### 添加音频 `POST /add_audios`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_url | string | 是 | 草稿 URL |
| audio_infos | string | 是 | 音频信息列表（JSON 字符串） |

**audio_infos 内部结构：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| audio_url | string | 是 | 音频 URL（http/https） |
| start | int | 是 | 开始时间（微秒） |
| end | int | 是 | 结束时间（微秒） |
| fade_in | int | 否 | 淡入时长（微秒） |
| fade_out | int | 否 | 淡出时长（微秒） |
| volume | float | 否 | 音量 [0, 10] |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| track_id | string | 音频轨道 ID |
| audio_ids | list | 音频 ID 列表 |

---

#### 添加字幕 `POST /add_captions`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| draft_url | string | 是 | | 草稿 URL |
| captions | string | 是 | | 字幕信息列表（JSON 字符串） |
| text_color | string | 否 | #ffffff | 文本颜色（十六进制） |
| border_color | string | 否 | None | 边框颜色（十六进制） |
| alignment | int | 否 | 1 | 文本对齐方式（0-5） |
| alpha | float | 否 | 1.0 | 文本透明度 [0.0, 1.0] |
| font | string | 否 | None | 字体名称 |
| font_size | int | 否 | 15 | 字体大小 |
| letter_spacing | float | 否 | None | 字间距 |
| line_spacing | float | 否 | None | 行间距 |
| scale_x | float | 否 | 1.0 | 水平缩放 |
| scale_y | float | 否 | 1.0 | 垂直缩放 |
| transform_x | float | 否 | 0.0 | 水平位移 |
| transform_y | float | 否 | 0.0 | 垂直位移 |
| style_text | bool | 否 | False | 是否使用样式文本 |
| underline | bool | 否 | False | 文字下划线 |
| italic | bool | 否 | False | 文本斜体 |
| bold | bool | 否 | False | 文本加粗 |
| has_shadow | bool | 否 | False | 是否启用文本阴影 |
| shadow_info | object | 否 | None | 阴影参数 |
| text_effect | string | 否 | None | 花字效果名称或 effect_id |

**shadow_info 结构：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| shadow_alpha | float | 1.0 | 阴影不透明度 [0, 1] |
| shadow_color | string | #000000 | 阴影颜色（十六进制） |
| shadow_diffuse | float | 15.0 | 阴影扩散程度 [0, 100] |
| shadow_distance | float | 5.0 | 阴影距离 [0, 100] |
| shadow_angle | float | -45.0 | 阴影角度 [-180, 180] |

**captions 内部结构（单条字幕）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start | int | 是 | 字幕开始时间（微秒） |
| end | int | 是 | 字幕结束时间（微秒） |
| text | string | 是 | 字幕文本内容 |
| keyword | string | 否 | 关键词（用 \| 分隔多个关键词） |
| keyword_color | string | 否 | #ff7100 | 关键词颜色 |
| keyword_border_color | string | 否 | None | 关键词边框颜色 |
| keyword_font_size | int | 否 | 15 | 关键词字体大小 |
| font_size | int | 否 | 15 | 文本字体大小 |
| in_animation | string | 否 | None | 入场动画 |
| out_animation | string | 否 | None | 出场动画 |
| loop_animation | string | 否 | None | 循环动画 |
| in_animation_duration | int | 否 | None | 入场动画时长 |
| out_animation_duration | int | 否 | None | 出场动画时长 |
| loop_animation_duration | int | 否 | None | 循环动画单次循环时长（微秒） |
| text_effect | string | 否 | None | 花字效果名称或 effect_id |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| track_id | string | 字幕轨道 ID |
| text_ids | list | 字幕 ID 列表 |
| segment_ids | list | 字幕片段 ID 列表 |
| segment_infos | list | 片段信息列表 |

---

#### 添加图片 `POST /add_images`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| draft_url | string | 是 | | 草稿 URL |
| image_infos | string | 是 | | 图片信息列表（JSON 字符串） |
| alpha | float | 否 | 1.0 | 全局透明度 [0, 1] |
| scale_x | float | 否 | 1.0 | X轴缩放比例 |
| scale_y | float | 否 | 1.0 | Y轴缩放比例 |
| transform_x | int | 否 | 0 | X轴位置偏移（像素） |
| transform_y | int | 否 | 0 | Y轴位置偏移（像素） |

**image_infos 内部结构：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| image_url | string | 是 | 图片 URL（http/https） |
| start | int | 是 | 开始时间（微秒） |
| end | int | 是 | 结束时间（微秒） |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| track_id | string | 视频轨道 ID |
| image_ids | list | 图片 ID 列表 |
| segment_ids | list | 片段 ID 列表 |
| segment_infos | list | 片段信息列表 |

---

#### 添加贴纸 `POST /add_sticker`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| draft_url | string | 是 | | 草稿 URL |
| sticker_id | string | 是 | | 贴纸的唯一标识 ID |
| start | int | 是 | | 贴纸开始时间（微秒） |
| end | int | 是 | | 贴纸结束时间（微秒） |
| scale | float | 否 | 1.0 | 贴纸缩放比例 [0.1, 5.0] |
| transform_x | int | 否 | 0 | X轴位置偏移（像素），以画布中心为原点 |
| transform_y | int | 否 | 0 | Y轴位置偏移（像素），以画布中心为原点 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| sticker_id | string | 贴纸的唯一标识 ID |
| track_id | string | 轨道 ID |
| segment_id | string | 片段 ID |
| duration | int | 贴纸显示时长（微秒） |

---

#### 添加特效 `POST /add_effects`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_url | string | 是 | 草稿 URL |
| effect_infos | string | 是 | 特效信息列表（JSON 字符串） |

**effect_infos 内部结构：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| effect_title | string | 是 | 特效名称/标题 |
| start | int | 是 | 特效开始时间（微秒） |
| end | int | 是 | 特效结束时间（微秒） |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| track_id | string | 特效轨道 ID |
| effect_ids | list | 特效 ID 列表 |
| segment_ids | list | 特效片段 ID 列表 |

---

#### 添加滤镜 `POST /add_filters`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_url | string | 是 | 草稿 URL |
| filter_infos | string | 是 | 滤镜信息列表（JSON 字符串） |

**filter_infos 内部结构：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| filter_title | string | 是 | | 滤镜名称/标题 |
| start | int | 是 | | 滤镜开始时间（微秒） |
| end | int | 是 | | 滤镜结束时间（微秒） |
| intensity | float | 否 | 100.0 | 滤镜强度 [0, 100] |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| track_id | string | 滤镜轨道 ID |
| filter_ids | list | 滤镜 ID 列表 |
| segment_ids | list | 滤镜片段 ID 列表 |

---

#### 添加遮罩 `POST /add_masks`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| draft_url | string | 是 | | 草稿 URL |
| segment_ids | list | 是 | | 要应用遮罩的片段 ID 数组 |
| name | string | 否 | 线性 | 遮罩类型名称 |
| X | int | 否 | 0 | 遮罩中心 X 坐标（像素） |
| Y | int | 否 | 0 | 遮罩中心 Y 坐标（像素） |
| width | int | 否 | 512 | 遮罩宽度（像素） |
| height | int | 否 | 512 | 遮罩高度（像素） |
| feather | int | 否 | 0 | 羽化程度 [0, 100] |
| rotation | int | 否 | 0 | 旋转角度（度） |
| invert | bool | 否 | False | 是否反转遮罩 |
| roundCorner | int | 否 | 0 | 圆角半径 [0, 100] |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| masks_added | int | 成功添加的遮罩数量 |
| affected_segments | list | 受影响的片段 ID 列表 |
| mask_ids | list | 遮罩 ID 列表 |

---

#### 添加关键帧 `POST /add_keyframes`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| draft_url | string | 是 | 草稿 URL |
| keyframes | string | 是 | 关键帧信息列表（JSON 字符串） |

**keyframes 内部结构：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| segment_id | string | 是 | 目标片段的唯一标识 ID |
| property | string | 是 | 动画属性类型：KFTypePositionX, KFTypePositionY, KFTypeScaleX, KFTypeScaleY, KFTypeRotation, KFTypeAlpha |
| offset | float | 是 | 关键帧在片段中的时间偏移 [0, 1] |
| value | float | 是 | 属性在该时间点的值 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |
| keyframes_added | int | 添加的关键帧数量 |
| affected_segments | list | 受影响的片段 ID 列表 |

---

#### 快速创建素材 `POST /easy_create_material`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| draft_url | string | 是 | | 目标草稿的完整 URL |
| audio_url | string | 是 | | 音频文件 URL（http/https） |
| text | string | 否 | None | 要添加的文字内容 |
| img_url | string | 否 | None | 图片文件 URL（http/https） |
| video_url | string | 否 | None | 视频文件 URL（http/https） |
| text_color | string | 否 | #ffffff | 文字颜色（十六进制格式） |
| font_size | int | 否 | 15 | 字体大小 |
| text_transform_y | int | 否 | 0 | 文字 Y 轴位置偏移 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_url | string | 草稿 URL |

---

### 3. 信息查询

#### 获取文字动画 `POST /get_text_animations`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| mode | int | 否 | 0 | 动画模式：0=所有，1=VIP，2=免费 |
| type | string | 是 | | 动画类型：in=入场，out=出场，loop=循环 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| effects | list | 文字出入场动画对象数组 |

**effects 内部结构：**

| 参数 | 类型 | 说明 |
|------|------|------|
| resource_id | string | 动画资源 ID |
| type | string | 动画类型 |
| category_id | string | 动画分类 ID |
| category_name | string | 动画分类名称 |
| duration | int | 动画时长（微秒） |
| id | string | 动画唯一标识 ID |
| name | string | 动画名称 |
| icon_url | string | 动画图标 URL |

---

#### 获取图片动画 `POST /get_image_animations`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| mode | int | 否 | 0 | 动画模式：0=所有，1=VIP，2=免费 |
| type | string | 是 | | 动画类型：in=入场，out=出场，loop=循环 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| effects | list | 图片出入场动画对象数组 |

---

#### 获取滤镜列表 `POST /get_filters`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| mode | int | 否 | 0 | 滤镜模式：0=所有，1=VIP，2=免费 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| filters | list | 滤镜对象数组 |

**filters 内部结构：**

| 参数 | 类型 | 说明 |
|------|------|------|
| name | string | 滤镜名称 |
| is_vip | bool | 是否为 VIP 滤镜 |
| resource_id | string | 资源 ID |
| effect_id | string | 效果 ID |
| has_params | bool | 是否有额外参数 |

---

#### 获取花字效果 `POST /get_text_effects`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| mode | int | 否 | 0 | 花字效果模式：0=所有，1=VIP，2=免费 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| text_effects | list | 花字效果对象数组 |

**text_effects 内部结构：**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 花字效果 ID |
| title | string | 花字效果名称 |
| is_vip | bool | 是否为 VIP 效果 |

---

#### 获取特效列表 `POST /get_effects`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| mode | int | 否 | 0 | 特效模式：0=所有，1=VIP，2=免费 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| effects | list | 特效对象数组 |

**effects 内部结构：**

| 参数 | 类型 | 说明 |
|------|------|------|
| name | string | 特效名称 |
| is_vip | bool | 是否为 VIP 特效 |
| resource_id | string | 资源 ID |
| effect_id | string | 效果 ID |
| icon_url | string | 图标 URL |
| has_params | bool | 是否有额外参数 |

---

#### 搜索贴纸 `POST /search_sticker`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| data | list | 贴纸数据列表 |

**data 内部结构：**

| 参数 | 类型 | 说明 |
|------|------|------|
| sticker_id | string | 贴纸 ID |
| title | string | 贴纸标题 |
| sticker | object | 贴纸信息（含大图、缩略图等） |

---

#### 获取音频时长 `POST /get_audio_duration`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| mp3_url | string | 是 | 音频文件 URL（HttpUrl 类型） |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| duration | int | 音频时长（微秒） |

---

### 4. 信息生成

根据时间线/参数生成各类信息的 JSON，用于后续添加到草稿：

#### 视频信息 `POST /video_infos`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| video_urls | list | 是 | 视频 URL 列表 |
| timelines | list | 是 | 时间线数组 |
| height | int | 否 | 视频高 |
| width | int | 否 | 视频宽 |
| mask | string | 否 | 视频蒙版：圆形、矩形、爱心、星形 |
| transition | string | 否 | 转场名称 |
| transition_duration | int | 否 | 转场时长（微秒） |
| volume | float | 否 | 音量 [0, 10]，默认 1 |

---

#### 音频信息 `POST /audio_infos`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| mp3_urls | list | 是 | 音频文件 URL 数组 |
| timelines | list | 是 | 时间线数组 |
| audio_effect | string | 否 | 音频效果 |
| volume | float | 否 | 音量 |

---

#### 图片信息 `POST /imgs_infos`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| imgs | list | 是 | 图片 URL 列表 |
| timelines | list | 是 | 时间线数组 |
| height | int | 否 | 视频高度 |
| width | int | 否 | 视频宽度 |
| in_animation | string | 否 | 入场动画名称（多个用 \| 分隔） |
| in_animation_duration | int | 否 | 入场动画时长 |
| loop_animation | string | 否 | 组合动画名称（多个用 \| 分隔） |
| loop_animation_duration | int | 否 | 组合动画时长 |
| out_animation | string | 否 | 出场动画名称（多个用 \| 分隔） |
| out_animation_duration | int | 否 | 出场动画时长 |
| transition | string | 否 | 转场名称 |
| transition_duration | int | 否 | 转场时长 |

---

#### 字幕信息 `POST /caption_infos`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| texts | list | 是 | 文本列表 |
| timelines | list | 是 | 时间线数组 |
| font_size | int | 否 | 字体大小 |
| keyword_color | string | 否 | 关键词颜色 |
| keyword_border_color | string | 否 | 关键词边框颜色 |
| keyword_font_size | int | 否 | 关键词字体大小 |
| keywords | list | 否 | 重点词列表 |
| in_animation | string | 否 | 入场动画名称 |
| in_animation_duration | int | 否 | 入场动画时长 |
| loop_animation | string | 否 | 组合动画名称 |
| loop_animation_duration | int | 否 | 循环动画单次循环时长（微秒） |
| out_animation | string | 否 | 出场动画名称 |
| out_animation_duration | int | 否 | 出场动画时长 |
| transition | string | 否 | 转场名称 |
| transition_duration | int | 否 | 转场时长 |

---

#### 特效信息 `POST /effect_infos`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| effects | list | 是 | 特效名称列表 |
| timelines | list | 是 | 时间线数组 |

---

#### 滤镜信息 `POST /filter_infos`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| filters | list | 是 | 滤镜名称列表 |
| timelines | list | 是 | 时间线数组 |
| intensities | list | 否 | 滤镜强度列表 [0, 100] |

---

#### 关键帧信息 `POST /keyframes_infos`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ctype | string | 是 | 关键帧类型：KFTypePositionX, KFTypePositionY, KFTypeRotation, UNIFORM_SCALE, KFTypeAlpha |
| offsets | string | 是 | 关键帧位置比例，如 0\|50\|100 |
| values | string | 是 | 对应 offsets 的值，长度要一致 |
| segment_infos | list | 是 | 轨道数据（id, start, end） |
| height | int | 否 | 视频高 |
| width | int | 否 | 视频宽 |

---

#### 时间线计算 `POST /timelines`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| duration | int | 是 | 总时长 |
| num | int | 是 | 时间线个数（2 表示将总时长分为 2 段） |
| start | int | 是 | 开始时间 |
| type | int | 是 | 0=平均分，1=随机 |

---

#### 音频时间线 `POST /audio_timelines`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| links | list | 是 | 音频文件 URL 数组 |

---

### 5. 工具函数

#### 富文本样式 `POST /add_text_style`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| text | string | 是 | | 要处理的文本内容 |
| keyword | string | 是 | | 关键词（多个用 \| 分隔） |
| font_size | int | 否 | 12 | 普通文本的字体大小 |
| keyword_color | string | 否 | #ff7100 | 关键词文本颜色（十六进制） |
| keyword_font_size | int | 否 | 15 | 关键词字体大小 |

**响应参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| text_style | string | 文本样式 JSON 字符串 |

---

#### URL 提取 `POST /get_url`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| output | string | 是 | 输出字符串 |

---

#### 字符串转对象列表 `POST /str_list_to_objs`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| infos | list | 是 | 字符串列表 |

---

#### 字符串转列表 `POST /str_to_list`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| obj | string | 是 | 字符串对象 |

---

#### 对象列表转字符串列表 `POST /objs_to_str_list`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| outputs | list | 是 | 对象列表 |

---

## MediaRefitAgent 集成方式

MediaRefitAgent 通过直接 import `pyJianYingDraft` 库集成，不启动 capcut-mate HTTP 服务：

```python
from backend.capcut-mate-main.src.pyJianYingDraft import ScriptFile, DraftFolder
```

当前 `backend/jianying/client.py` 封装的能力：

| 能力 | 方法 | 状态 |
|------|------|------|
| 创建草稿 | `create_draft()` | ✅ 已集成 |
| 保存草稿 | `save_draft()` | ✅ 已集成 |
| 获取草稿 | `get_draft()` | ✅ 已集成 |
| 添加视频 | `add_videos()` | ✅ 已集成（含转场） |
| 添加音频 | `add_audios()` | ✅ 已集成（含淡入淡出） |
| 添加字幕 | `add_captions()` | ✅ 已集成（含逐字高亮、花字） |
| 视频生成 | `gen_video()` | ✅ 已集成（Windows 需剪映客户端） |
| 添加特效 | `add_effects()` | ❌ 未集成 |
| 添加滤镜 | `add_filters()` | ❌ 未集成 |
| 添加图片 | `add_images()` | ❌ 未集成 |
| 添加贴纸 | `add_sticker()` | ❌ 未集成 |
| 添加遮罩 | `add_masks()` | ❌ 未集成 |
| 添加关键帧 | `add_keyframes()` | ❌ 未集成 |

---

## 核心数据结构

### ScriptFile
草稿 JSON 的内存表示，包含：
- `materials`: 素材库（视频、音频、图片、字幕等）
- `tracks`: 轨道（video/audio/text track）
- `canvas_config`: 画布尺寸

### DraftFolder
草稿目录管理器：
- `create_draft()`: 创建新草稿
- `load_draft()`: 加载已有草稿
- `duplicate_as_template()`: 从模板复制

### Segment（片段）
- `VideoSegment`: 视频片段，支持变速、转场
- `AudioSegment`: 音频片段，支持淡入淡出
- `TextSegment`: 文本片段，支持样式、动画
- `ImageSegment`: 图片片段

---

## 依赖关系

```
backend/jianying/client.py (MediaRefitAgent)
    └── backend/capcut-mate-main/src/pyJianYingDraft/
            ├── script_file.py      # ScriptFile 核心类
            ├── draft_folder.py     # 目录管理
            ├── video_segment.py    # 视频片段
            ├── audio_segment.py    # 音频片段
            ├── text_segment.py     # 文本片段
            ├── segment.py          # 基类
            ├── track.py            # 轨道
            ├── animation.py        # 动画
            ├── template_mode.py    # 模板模式
            ├── metadata/           # 元数据（滤镜/转场/花字枚举）
            └── assets/            # 模板 JSON
```

---

## 时间单位说明

API 参数中**时间单位统一使用微秒**（microseconds）：
- 1 秒 = 1,000,000 微秒
- 例如：3 秒 = 3000000 微秒
