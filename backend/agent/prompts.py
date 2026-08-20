"""
Agent 提示词模板

按工具分类，避免重复内容
"""

# ============ 通用部分 ============
HISTORY_CONTEXT = """【对话历史】（请结合历史理解用户意图）
{history}

【当前输入】
{user_input}
"""

VIDEO_INFO = """【视频信息】
{video_info}"""

# ============ 工具识别 ============
TOOL_RECOGNITION_PROMPT = """用户输入：{user_input}

请识别用户想要使用的工具：
- 转换、横屏、竖屏 -> convert
- 压缩、变小 -> compress
- 视频信息、时长 -> info
- 修剪、裁剪、截取 -> trim
- 拼接、合并 -> concat
- 修复、老视频、去噪 -> restore
- 精彩片段、高光 -> highlight
- 转场、过渡 -> transition
- 无法判断 -> null

只返回一个词：convert/compress/info/trim/concat/restore/highlight/transition/null"""

# ============ convert 工具 ============
CONVERT_PARAM_PROMPT = """【任务】解析视频转换需求

{history_context}

{video_info}

---

【参数说明】
方向：portrait=竖屏，landscape=横屏
比例：竖屏9:16/4:5/1:1，横屏16:9/21:9/4:3
策略：pad=填充黑边，crop=中心裁剪，smart_crop=AI裁剪，stretch=拉伸

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"orientation_explicit":true/false,"strategy_explicit":true/false,"ratio_explicit":true/false,"target_orientation":"portrait/landscape/null","target_ratio":"9:16/4:5/1:1/16:9/21:9/4:3/null","strategy":"pad/crop/smart_crop/stretch/null","response":"助手回复"}}

【示例】
输入"转竖屏" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":false,"target_orientation":"portrait","target_ratio":null,"strategy":null,"response":"已识别到您想转换为竖屏。请问选择哪个比例？9:16/4:5/1:1"}}"""

# ============ info 工具 ============
INFO_PARAM_PROMPT = """【任务】获取视频信息

{history_context}

{video_info}

---
用户输入：{user_input}

【输出格式】
{{"response":"助手回复"}}"""

# ============ compress 工具 ============
COMPRESS_PARAM_PROMPT = """【任务】解析视频压缩需求

{history_context}

{video_info}

---

级别：low=高质量大文件，medium=平衡，high=小体积低质量

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"compression_explicit":true/false,"compression_level":"low/medium/high/null","response":"助手回复"}}"""

# ============ trim 工具 ============
TRIM_PARAM_PROMPT = """【任务】解析视频修剪需求

{history_context}

{video_info}

---

时间格式：支持"30"(秒)、"0:30"(分:秒)、"1:30:00"(时:分:秒)

用户输入：{user_input}

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"start_time_explicit":true/false,"end_time_explicit":true/false,"start_time":"数字或时间格式/null","end_time":"数字或时间格式/null","response":"助手回复"}}"""

# ============ concat 工具 ============
CONCAT_PARAM_PROMPT = """【任务】解析视频拼接需求

{history_context}

{video_info}

---

注意：拼接至少需要2个视频

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"concat_explicit":true/false,"file_count":数字,"keep_audio":true/false,"response":"助手回复"}}"""

# ============ restore 工具 ============
RESTORE_PARAM_PROMPT = """【任务】解析老视频修复需求

{history_context}

{video_info}

---

套餐：basic=基础修复，film=胶片修复，enhanced=增强版
选项：denoise去噪，scratch划痕，flicker闪烁，interpolate补帧，super_resolution超分

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"preset_explicit":true/false,"preset":"basic/film/enhanced/custom/null","denoise":true/false,"scratch":true/false,"flicker":true/false,"interpolate":true/false,"super_resolution":true/false,"response":"助手回复"}}"""

# ============ highlight 工具 ============
HIGHLIGHT_PARAM_PROMPT = """【任务】解析精彩片段提取需求

{history_context}

{video_info}

---

参数：target_duration=目标时长(秒)，num_clips=片段数量

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"target_duration_explicit":true/false,"target_duration":60,"num_clips_explicit":true/false,"num_clips":5,"response":"助手回复"}}"""

# ============ transition 工具 ============
TRANSITION_PARAM_PROMPT = """【任务】解析转场效果需求

{history_context}

{video_info}

---

类型：fade=淡入淡出，slide=滑动，zoom=缩放，blur=模糊，rotate=旋转，dissolve=溶解
时长：transition_duration=秒数

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"transition_type_explicit":true/false,"transition_type":"fade/slide/zoom/blur/rotate/dissolve/null","transition_duration_explicit":true/false,"transition_duration":1.0,"response":"助手回复"}}"""

# ============ 工具映射 ============
TOOL_PROMPTS = {
    "convert": CONVERT_PARAM_PROMPT,
    "compress": COMPRESS_PARAM_PROMPT,
    "trim": TRIM_PARAM_PROMPT,
    "concat": CONCAT_PARAM_PROMPT,
    "restore": RESTORE_PARAM_PROMPT,
    "highlight": HIGHLIGHT_PARAM_PROMPT,
    "transition": TRANSITION_PARAM_PROMPT,
    "info": INFO_PARAM_PROMPT,
}

# ============ 通用响应模板 ============
NULL_RESPONSE = "抱歉，我没有理解您的需求。您是想转换视频方向、压缩视频、修剪视频还是获取视频信息？"
