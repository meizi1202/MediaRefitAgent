"""
Agent 提示词模板

按工具分类，避免重复内容
"""

# ============ 通用部分 ============
CONVERSATION_HISTORY = """
【对话历史】（请结合历史理解用户意图）
{history}
"""

VIDEO_INFO = """【视频信息】
{video_info}"""

# ============ 工具识别 ============
TOOL_RECOGNITION_PROMPT = """

{conversation_history}
用户输入：{user_input}
请根据对话历史和用户输入识别用户想要使用的工具：
- 转换、横屏、竖屏、转竖屏、转横屏、转竖屏9:16、转横屏16:9 -> convert
- 9:16、16:9、4:5、1:1、21:9、4:3 -> convert
- 填充黑边、中心裁剪、AI裁剪、拉伸 -> convert
- 压缩、变小 -> compress
- 视频信息、时长 -> info
- 修剪、裁剪、截取 -> trim
- 拼接、合并 -> concat
- 修复、老视频、去噪 -> restore
- 精彩片段、高光、字幕、配乐、转场、滤镜、封面、片头片尾、智能剪辑 -> editor
- 缩编、精简、缩短、智能缩编、内容缩编 -> condense

【严格规则】
- 用户说"转竖屏"、"竖屏"、"9:16"、"填充黑边"等任何转换相关 -> 必须返回 convert
- 即使输入很短，只要涉及视频方向/比例/策略 -> 返回 convert
- 只返回一个词：convert/compress/info/trim/concat/restore/editor/condense/null"""

# ============ convert 工具 ============
CONVERT_PARAM_PROMPT = """【任务】解析视频转换需求

{conversation_history}
用户输入：{user_input}

---

【参数说明】
方向：portrait=竖屏，landscape=横屏
比例：竖屏9:16/4:5/1:1，横屏16:9/21:9/4:3
策略：pad=填充黑边，crop=中心裁剪，smart_crop=AI裁剪，stretch=拉伸

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"orientation_explicit":true/false,"strategy_explicit":true/false,"ratio_explicit":true/false,"target_orientation":"portrait/landscape/null","target_ratio":"9:16/4:5/1:1/16:9/21:9/4:3/null","strategy":"pad/crop/smart_crop/stretch/null","response":"助手回复"}}

【示例】
输入"转竖屏" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":false,"target_orientation":"portrait","target_ratio":null,"strategy":null,"response":"已识别到您想转换为竖屏。请问选择哪个比例？9:16/4:5/1:1"}}
输入"竖屏" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":null,"response":"好的，已选择9:16竖屏比例。请问选择哪个策略？填充黑边/中心裁剪/AI裁剪/拉伸"}}
输入"转竖屏9:16" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":null,"response":"好的，已选择9:16竖屏比例。请问选择哪个策略？填充黑边/中心裁剪/AI裁剪/拉伸"}}
输入"竖屏9:16" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":null,"response":"好的，已选择9:16竖屏比例。请问选择哪个策略？"}}
输入"9:16" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":null,"response":"好的，已选择9:16竖屏比例。请问选择哪个策略？填充黑边/中心裁剪/AI裁剪/拉伸"}}
输入"9:16填充黑边" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"pad","response":"好的，使用9:16竖屏和填充黑边策略，正在为您转换..."}}
输入"竖屏9:16填充黑边" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"pad","response":"好的，使用9:16竖屏和填充黑边策略，正在为您转换..."}}
输入"转竖屏9:16填充黑边" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"pad","response":"好的，使用9:16竖屏和填充黑边策略，正在为您转换..."}}
输入"填充黑边" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"pad","response":"好的，使用填充黑边策略，正在为您转换..."}}
输入"pad" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"pad","response":"好的，使用填充黑边策略，正在为您转换..."}}
输入"16:9" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":true,"target_orientation":"landscape","target_ratio":"16:9","strategy":null,"response":"好的，已选择16:9横屏比例。请问选择哪个策略？"}}
输入"横屏16:9" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":true,"target_orientation":"landscape","target_ratio":"16:9","strategy":null,"response":"好的，已选择16:9横屏比例。请问选择哪个策略？"}}
输入"横屏16:9填充黑边" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"landscape","target_ratio":"16:9","strategy":"pad","response":"好的，使用16:9横屏和填充黑边策略，正在为您转换..."}}
输入"中心裁剪" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"crop","response":"好的，使用中心裁剪策略，正在为您转换..."}}
输入"AI裁剪" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"smart_crop","response":"好的，使用AI智能裁剪策略，正在为您转换..."}}
输入"拉伸" -> {{"orientation_explicit":true,"strategy_explicit":true,"ratio_explicit":true,"target_orientation":"portrait","target_ratio":"9:16","strategy":"stretch","response":"好的，使用拉伸填充策略，正在为您转换..."}}
输入"转横屏" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":false,"target_orientation":"landscape","target_ratio":null,"strategy":null,"response":"已识别到您想转换为横屏。请问选择哪个比例？16:9/21:9/4:3"}}
输入"转换视频方向" -> {{"orientation_explicit":true,"strategy_explicit":false,"ratio_explicit":false,"target_orientation":"landscape","target_ratio":null,"strategy":null,"response":"好的，检测到视频是横屏的。请问您想转换为竖屏还是横屏？"}}"""

# ============ info 工具 ============
INFO_PARAM_PROMPT = """【任务】获取视频信息

{conversation_history}
用户输入：{user_input}

---

【输出格式】
{{"response":"助手回复"}}"""

# ============ compress 工具 ============
COMPRESS_PARAM_PROMPT = """【任务】解析视频压缩需求

{conversation_history}
用户输入：{user_input}

---

【参数说明】级别：low=低压缩/高质量大文件，medium=中压缩/平衡，high=高压缩/小体积低质量

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"compression_explicit":true/false,"compression_level":"low/medium/high/null","response":"助手回复"}}"""

# ============ trim 工具 ============
TRIM_PARAM_PROMPT = """【任务】解析视频修剪需求

{conversation_history}
用户输入：{user_input}


---

时间格式：支持"30"(秒)、"0:30"(分:秒)、"1:30:00"(时:分:秒)

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"start_time_explicit":true/false,"end_time_explicit":true/false,"start_time":"数字或时间格式/null","end_time":"数字或时间格式/null","response":"助手回复"}}"""

# ============ concat 工具 ============
CONCAT_PARAM_PROMPT = """【任务】解析视频拼接需求

{conversation_history}
用户输入：{user_input}


---
 用户输入：{user_input}
 是否保留音频：keep_audio=true/false/null（用户明确回答则填true/false，未明确回答则填null）

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"concat_explicit":true/false,"keep_audio":true/false/null,"response":"助手回复"}}"""

# ============ restore 工具 ============
RESTORE_PARAM_PROMPT = """【任务】解析老视频修复需求

{conversation_history}
用户输入：{user_input}

---

套餐：basic=基础修复，film=胶片修复，enhanced=增强版
选项：denoise去噪，scratch划痕，flicker闪烁，interpolate补帧，super_resolution超分

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"preset_explicit":true/false,"preset":"basic/film/enhanced/custom/null","denoise":true/false,"scratch":true/false,"flicker":true/false,"interpolate":true/false,"super_resolution":true/false,"response":"助手回复"}}"""

# ============ highlight 工具 ============
HIGHLIGHT_PARAM_PROMPT = """【任务】解析精彩片段提取需求

{conversation_history}
用户输入：{user_input}

---

参数：target_duration=目标时长(秒)，num_clips=片段数量

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"target_duration_explicit":true/false,"target_duration":60,"num_clips_explicit":true/false,"num_clips":5,"response":"助手回复"}}"""

# ============ transition 工具 ============
TRANSITION_PARAM_PROMPT = """【任务】解析转场效果需求

{conversation_history}
用户输入：{user_input}

---

类型：fade=淡入淡出，slide=滑动，zoom=缩放，blur=模糊，rotate=旋转，dissolve=溶解
时长：transition_duration=秒数

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"transition_type_explicit":true/false,"transition_type":"fade/slide/zoom/blur/rotate/dissolve/null","transition_duration_explicit":true/false,"transition_duration":1.0,"response":"助手回复"}}"""

# ============ condense 工具 ============
CONDENSE_PARAM_PROMPT = """【任务】解析视频智能缩编需求

{conversation_history}
用户输入：{user_input}

---

策略：content_condense=内容缩编（保留精彩片段），smart_compress=智能压缩（H.265重编码）
目标时长：target_duration=秒数，默认60秒

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"condense_strategy_explicit":true/false,"condense_strategy":"content_condense/smart_compress/null","target_duration_explicit":true/false,"target_duration":60,"response":"助手回复"}}

【示例】
输入"缩编视频" -> {{"condense_strategy_explicit":false,"condense_strategy":null,"target_duration_explicit":false,"target_duration":60,"response":"好的，我来为您智能缩编视频。请问选择哪种策略？内容缩编/智能压缩"}}
输入"内容缩编" -> {{"condense_strategy_explicit":true,"condense_strategy":"content_condense","target_duration_explicit":false,"target_duration":60,"response":"好的，使用内容缩编策略。请问目标时长是多少秒？"}}
输入"缩编成30秒" -> {{"condense_strategy_explicit":false,"condense_strategy":null,"target_duration_explicit":true,"target_duration":30,"response":"好的，目标时长30秒。请问选择哪种策略？"}}
输入"内容缩编，60秒" -> {{"condense_strategy_explicit":true,"condense_strategy":"content_condense","target_duration_explicit":true,"target_duration":60,"response":"好的，使用内容缩编策略，目标时长60秒，正在为您缩编..."}}"""

# ============ editor 工具 ============
EDITOR_PARAM_PROMPT = """【任务】解析智能剪辑需求

{conversation_history}
用户输入：{user_input}

---

剪辑模式：editor_mode=highlight(精彩片段)/subtitle(自动字幕)/transition(添加转场)/bgm(智能配乐)/tts(配音)/filter(滤镜)/analyze(内容分析)/cover(封面生成)/title-package(片头片尾)
字幕样式：subtitle_style=default(默认)/minimal(简洁)
转场类型：transition_type=fade(淡入淡出)/slide(滑动)/zoom(缩放)
音乐风格：bgm_mood=auto(自动)/happy(欢快)/calm(平静)/energetic(动感)
滤镜预设：filter_preset=none(无)/vintage(复古)/cinematic(电影感)/fresh(清新)/bw(黑白)/warm(暖色)/cold(冷色)
目标平台：platform=douyin(抖音)/kuaishou(快手)/bilibili(B站)/xiaohongshu(小红书)
目标时长：target_duration=秒数，默认60秒

【规则】用户已回答的用 explicit=true，未回答的用 explicit=false

【输出格式】
{{"editor_mode_explicit":true/false,"editor_mode":"highlight/subtitle/transition/bgm/tts/filter/analyze/cover/title-package/null","subtitle_style_explicit":true/false,"subtitle_style":"default/minimal/null","transition_type_explicit":true/false,"transition_type":"fade/slide/zoom/null","bgm_mood_explicit":true/false,"bgm_mood":"auto/happy/calm/energetic/null","filter_preset_explicit":true/false,"filter_preset":"none/vintage/cinematic/fresh/bw/warm/cold/null","platform_explicit":true/false,"platform":"douyin/kuaishou/bilibili/xiaohongshu/null","target_duration_explicit":true/false,"target_duration":60,"response":"助手回复"}}

【示例】
输入"智能剪辑" -> {{"editor_mode_explicit":false,"editor_mode":null,"response":"好的，我来为您进行智能剪辑。请选择剪辑模式：精彩片段/自动字幕/添加转场/智能配乐/配音/滤镜/内容分析/封面生成/片头片尾"}}
输入"精彩片段" -> {{"editor_mode_explicit":true,"editor_mode":"highlight","response":"好的，使用精彩片段模式。请问目标时长是多少秒？"}}
输入"智能配乐" -> {{"editor_mode_explicit":true,"editor_mode":"bgm","bgm_mood_explicit":false,"response":"好的，使用智能配乐模式。请问选择什么音乐风格？自动/欢快/平静/动感"}}
输入"添加转场" -> {{"editor_mode_explicit":true,"editor_mode":"transition","transition_type_explicit":false,"response":"好的，使用添加转场模式。请问选择什么转场类型？淡入淡出/滑动/缩放"}}
输入"滤镜" -> {{"editor_mode_explicit":true,"editor_mode":"filter","filter_preset_explicit":false,"response":"好的，使用滤镜模式。请问选择什么滤镜？无/复古/电影感/清新/黑白/暖色/冷色"}}
输入"精彩片段，60秒" -> {{"editor_mode_explicit":true,"editor_mode":"highlight","target_duration_explicit":true,"target_duration":60,"response":"好的，使用精彩片段模式，目标时长60秒，正在为您处理..."}}"""

# ============ 工具映射 ============
TOOL_PROMPTS = {
    "convert": CONVERT_PARAM_PROMPT,
    "compress": COMPRESS_PARAM_PROMPT,
    "trim": TRIM_PARAM_PROMPT,
    "concat": CONCAT_PARAM_PROMPT,
    "restore": RESTORE_PARAM_PROMPT,
    "editor": EDITOR_PARAM_PROMPT,
    "condense": CONDENSE_PARAM_PROMPT,
    "info": INFO_PARAM_PROMPT,
}

# ============ 通用响应模板 ============
NULL_RESPONSE = "抱歉，我没有理解您的需求。您是想转换视频方向、压缩视频、修剪视频、缩编视频还是获取视频信息？"
