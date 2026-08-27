"""
意图分析 Node

新增技能步骤：
1. 在 execute.py 添加 execute_xxx 函数
2. 在 analyze.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
3. 在 routing.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
4. 在 frontend/src/stores/app.ts formatSelectedParams() 添加参数格式化
"""
from datetime import datetime
from typing import Optional
import os

from agent.types import VideoAgentState, ConversationMessage
from agent.streaming import send_stream_chunk, is_streaming_enabled
from langchain_core.messages import HumanMessage


def _append_message(state: VideoAgentState, role: str, content: str):
    """添加消息并发送流式消息"""
    msg = ConversationMessage(
        role=role,
        content=content,
        timestamp=datetime.now().isoformat(),
    )
    state["messages"].append(msg)
    if is_streaming_enabled():
        send_stream_chunk(content)


# 功能到执行步骤的映射
FEATURE_TO_STEP = {
    "convert": "execute_transform",
    "compress": "execute_compress",
    "trim": "execute_trim",
    "concat": "execute_concat",
    "condense": "execute_condense",
    "restore": "execute_restore",
    "editor": "execute_editor",
    "info": "execute_info",
}


def _complete_params_provided(state: VideoAgentState, feature: str):
    """通用：参数完整时设置执行步骤并清除 pending_question"""
    state["pending_question"] = None
    state["current_step"] = FEATURE_TO_STEP.get(feature, "execute_transform")


def _setup_feature_state(state: VideoAgentState, feature: str, all_params_provided: bool,
                          pending_question: Optional[str], llm_response: str):
    """通用：设置功能状态和消息

    所有功能最终都调用此函数，确保统一的行为。
    """
    state["current_feature"] = feature
    state["all_params_provided"] = all_params_provided
    state["pending_question"] = pending_question

    if llm_response:
        _append_message(state, "assistant", llm_response)

    if all_params_provided:
        _complete_params_provided(state, feature)
    else:
        state["current_step"] = None


class IntentParser:
    """意图解析器"""

    # 方向关键词
    ORIENTATION_KEYWORDS = {
        "portrait": ["竖屏", "portrait", "垂直", "竖", "9:16", "9/16", "4:5", "4/5", "1:1", "1/1", "2:3", "2/3", "短视频", "抖音", "快手", "Instagram", "IG"],
        "landscape": ["横屏", "landscape", "水平", "横", "16:9", "16/9", "21:9", "21/9", "4:3", "4/3", "3:2", "3/2", "横版", "电影"],
    }

    # 策略关键词（按优先级排序：更具体的在前）
    STRATEGY_KEYWORDS = {
        "smart_crop": ["智能裁剪", "smart", "AI裁剪", "ai crop", "智能", "AI"],
        "stretch": ["拉伸填充", "拉伸", "stretch"],
        "mirror_scroll": ["镜像滚动", "镜像", "mirror"],
        "pan_scroll": ["平移运镜", "平移", "运镜", "pan"],
        "crop": ["裁剪", "crop", "切", "截"],
        "pad": ["填充", "pad", "黑边", "留边", "保持完整"],
        "rotate": ["旋转", "rotate", "旋转90度", "rotate90"],
    }

    # 压缩级别关键词
    COMPRESSION_KEYWORDS = {
        "low": ["大文件", "low", "低压缩", "保持质量", "高质量"],
        "medium": ["中等", "medium", "平衡", "普通"],
        "high": ["小文件", "high", "高压缩", "高压缩率", "压缩率高", "高质量小文件"],
    }

    @classmethod
    def parse_orientation(cls, text: str) -> tuple[Optional[str], bool]:
        """解析目标方向，返回 (方向, 是否明确指定)"""
        text_lower = text.lower()
        for orientation, keywords in cls.ORIENTATION_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return orientation, True
        return None, False

    @classmethod
    def parse_strategy(cls, text: str) -> tuple[Optional[str], bool]:
        """解析转换策略，返回 (策略, 是否明确指定)"""
        text_lower = text.lower()
        for strategy, keywords in cls.STRATEGY_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return strategy, True
        return None, False

    @classmethod
    def parse_ratio(cls, text: str) -> tuple[Optional[float], bool]:
        """解析比例参数，返回 (比例, 是否明确指定)"""
        import re
        patterns = [
            r'(\d+):(\d+)',
            r'(\d+)/(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
                if h > 0:
                    return w / h, True
        return None, False

    @classmethod
    def parse_compression(cls, text: str) -> tuple[Optional[str], bool]:
        """解析压缩级别，返回 (级别, 是否明确指定)"""
        text_lower = text.lower()
        for level, keywords in cls.COMPRESSION_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return level, True
        return None, False

    @classmethod
    def parse(cls, text: str) -> dict:
        """解析用户输入"""
        orientation, orientation_explicit = cls.parse_orientation(text)
        strategy, strategy_explicit = cls.parse_strategy(text)
        ratio, ratio_explicit = cls.parse_ratio(text)
        compression, compression_explicit = cls.parse_compression(text)
        return {
            "orientation": orientation,
            "orientation_explicit": orientation_explicit,
            "strategy": strategy,
            "strategy_explicit": strategy_explicit,
            "ratio": ratio,
            "ratio_explicit": ratio_explicit,
            "compression": compression,
            "compression_explicit": compression_explicit,
        }


def _parse_ui_params(user_input: str) -> dict:
    """解析前端UI选择的参数格式"""
    import re
    result = {"found": False}

    if "[用户已选择参数：" not in user_input:
        return result

    # 解析功能类型
    feature_match = re.search(r'功能\s*=\s*([^，,\]]+)', user_input)
    if feature_match:
        feature_text = feature_match.group(1).strip()
        feature_map = {
            "横竖屏转换": "convert", "视频压缩": "compress", "视频修剪": "trim",
            "视频拼接": "concat", "智能缩编": "condense", "老视频修复": "restore",
            "智能剪辑": "editor", "视频信息获取": "info",
        }
        for name, feat in feature_map.items():
            if name in feature_text:
                result["feature"] = feat
                result["found"] = True
                break

    # 解析目标方向
    orient_match = re.search(r'目标方向\s*=\s*([^，,\]]+)', user_input)
    if orient_match:
        orient_text = orient_match.group(1).strip()
        if "竖屏" in orient_text:
            result["target_orientation"] = "portrait"
            result["ratio_text"] = orient_text
        elif "横屏" in orient_text:
            result["target_orientation"] = "landscape"
            result["ratio_text"] = orient_text
        ratio_map = {"9:16": 0.5625, "4:5": 0.8, "16:9": 1.7778, "21:9": 2.3333, "4:3": 1.3333}
        for ratio_text, ratio_value in ratio_map.items():
            if ratio_text in orient_text:
                result["target_ratio"] = ratio_value
                break

    # 解析转换策略
    strategy_match = re.search(r'转换策略\s*=\s*([^，,\]]+)', user_input)
    if strategy_match:
        strategy_text = strategy_match.group(1).strip()
        strategy_map = {
            "填充黑边": "pad", "中心裁剪": "crop", "智能裁剪": "smart_crop",
            "拉伸填充": "stretch", "镜像滚动": "mirror_scroll", "平移运镜": "pan_scroll",
        }
        for name, strategy in strategy_map.items():
            if name in strategy_text:
                result["strategy"] = strategy
                result["strategy_text"] = name
                break

    if result.get("target_orientation") and result.get("strategy"):
        result["found"] = True

    # 解析压缩级别
    compress_match = re.search(r'压缩级别\s*=\s*([^，,\]]+)', user_input)
    if compress_match:
        level_text = compress_match.group(1).strip()
        level_map = {"低": "low", "中": "medium", "高": "high"}
        for name, level in level_map.items():
            if name in level_text:
                result["compression_level"] = level
                result["compression_level_text"] = name
                result["found"] = True
                break

    # 解析修剪时间
    trim_time_match = re.search(r'从(\d+\.?\d*)秒到(\d+\.?\d*)秒', user_input)
    if trim_time_match:
        result["start_time"] = float(trim_time_match.group(1))
        result["end_time"] = float(trim_time_match.group(2))
        result["start_time_explicit"] = True
        result["end_time_explicit"] = True
        result["found"] = True
    else:
        start_match = re.search(r'修剪开始时间\s*=\s*(\d+\.?\d*)秒', user_input)
        end_match = re.search(r'修剪结束时间\s*=\s*(\d+\.?\d*)秒', user_input)
        if start_match and end_match:
            result["start_time"] = float(start_match.group(1))
            result["end_time"] = float(end_match.group(1))
            result["start_time_explicit"] = True
            result["end_time_explicit"] = True
            result["found"] = True

    # 解析缩编策略
    condense_strategy_match = re.search(r'缩编策略\s*=\s*([^，,\]]+)', user_input)
    if condense_strategy_match:
        strategy_text = condense_strategy_match.group(1).strip()
        strategy_map = {
            "内容缩编": "content_condense", "智能压缩": "smart_compress",
        }
        for name, strategy in strategy_map.items():
            if name in strategy_text:
                result["condense_strategy"] = strategy
                result["condense_strategy_text"] = name
                result["found"] = True
                break

    # 解析目标时长
    duration_match = re.search(r'目标时长\s*=\s*(\d+\.?\d*)秒', user_input)
    if duration_match:
        result["target_duration"] = float(duration_match.group(1))
        result["target_duration_explicit"] = True
        result["found"] = True

    # 解析修复套餐
    restore_preset_match = re.search(r'修复套餐\s*=\s*([^，,\]]+)', user_input)
    if restore_preset_match:
        preset_text = restore_preset_match.group(1).strip()
        preset_map = {
            "基础修复": "basic", "胶片修复": "film", "增强版": "enhanced",
        }
        for name, preset in preset_map.items():
            if name in preset_text:
                result["restoration_preset"] = preset
                result["restoration_preset_explicit"] = True
                result["found"] = True
                break

    # 解析编辑器模式
    editor_mode_match = re.search(r'编辑器模式\s*=\s*([^，,\]]+)', user_input)
    if editor_mode_match:
        mode_text = editor_mode_match.group(1).strip()
        mode_map = {
            "精彩片段": "highlight", "自动字幕": "subtitle", "添加转场": "transition",
            "智能配乐": "bgm", "配音": "tts", "滤镜": "filter",
            "内容分析": "analyze", "封面生成": "cover", "片头片尾": "title-package",
        }
        for name, mode in mode_map.items():
            if name in mode_text:
                result["editor_mode"] = mode
                result["editor_mode_explicit"] = True
                result["found"] = True
                break

    # 解析字幕样式
    subtitle_style_match = re.search(r'字幕样式\s*=\s*([^，,\]]+)', user_input)
    if subtitle_style_match:
        style_text = subtitle_style_match.group(1).strip()
        style_map = {"默认": "default", "简洁": "minimal"}
        for name, style in style_map.items():
            if name in style_text:
                result["subtitle_style"] = style
                result["subtitle_style_explicit"] = True
                result["found"] = True
                break

    # 解析转场类型
    transition_type_match = re.search(r'转场类型\s*=\s*([^，,\]]+)', user_input)
    if transition_type_match:
        trans_text = transition_type_match.group(1).strip()
        trans_map = {"淡入淡出": "fade", "滑动": "slide", "缩放": "zoom"}
        for name, trans in trans_map.items():
            if name in trans_text:
                result["transition_type"] = trans
                result["transition_type_explicit"] = True
                result["found"] = True
                break

    # 解析音乐风格
    bgm_mood_match = re.search(r'音乐风格\s*=\s*([^，,\]]+)', user_input)
    if bgm_mood_match:
        mood_text = bgm_mood_match.group(1).strip()
        mood_map = {"自动": "auto", "欢快": "happy", "平静": "calm", "动感": "energetic"}
        for name, mood in mood_map.items():
            if name in mood_text:
                result["bgm_mood"] = mood
                result["bgm_mood_explicit"] = True
                result["found"] = True
                break

    # 解析BGM音量
    bgm_volume_match = re.search(r'BGM音量\s*=\s*(\d+\.?\d*)', user_input)
    if bgm_volume_match:
        result["bgm_volume"] = float(bgm_volume_match.group(1))
        result["bgm_volume_explicit"] = True
        result["found"] = True

    # 解析滤镜预设
    filter_preset_match = re.search(r'滤镜预设\s*=\s*([^，,\]]+)', user_input)
    if filter_preset_match:
        filter_text = filter_preset_match.group(1).strip()
        # 支持中文标签和原始值
        filter_map = {
            "无": "none", "none": "none",
            "复古": "vintage", "vintage": "vintage",
            "电影感": "cinematic", "cinematic": "cinematic",
            "清新": "fresh", "fresh": "fresh",
            "黑白": "bw", "bw": "bw",
            "暖色": "warm", "warm": "warm",
            "冷色": "cold", "cold": "cold",
        }
        for name, f in filter_map.items():
            if name in filter_text:
                result["filter_preset"] = f
                result["filter_preset_explicit"] = True
                result["found"] = True
                break

    # 解析配音音色
    tts_voice_match = re.search(r'配音音色\s*=\s*([^，,\]]+)', user_input)
    if tts_voice_match:
        voice_text = tts_voice_match.group(1).strip()
        voice_map = {
            "晓晓": "zh-CN-XiaoxiaoNeural", "小艺": "zh-CN-XiaoyiNeural",
            "云希": "zh-CN-YunxiNeural", "云扬": "zh-CN-YunyangNeural",
            "辽宁": "zh-CN-liaoning", "陕西": "zh-CN-shaanxi",
        }
        for name, voice in voice_map.items():
            if name in voice_text:
                result["tts_voice"] = voice
                result["tts_voice_explicit"] = True
                result["found"] = True
                break

    # 解析配音文本
    tts_text_match = re.search(r'配音文本\s*=\s*([^，,\]]+)', user_input)
    if tts_text_match:
        result["tts_text"] = tts_text_match.group(1).strip()
        result["tts_text_explicit"] = True
        result["found"] = True

    return result


# ============ 各功能处理器 ============

def _handle_convert_ui(state, ui_params):
    """处理 convert - UI 参数"""
    state["target_orientation"] = ui_params.get("target_orientation")
    state["strategy"] = ui_params.get("strategy")
    state["target_ratio"] = ui_params.get("target_ratio")
    state["orientation_explicit"] = True
    state["strategy_explicit"] = True
    state["ratio_explicit"] = True
    orient_str = "竖屏" if ui_params.get("target_orientation") == "portrait" else "横屏"
    ratio_str = ui_params.get("ratio_text", "9:16")
    strategy_str = ui_params.get("strategy_text", "填充黑边")
    return f"好的，我把视频转换为{orient_str}（{ratio_str}），使用{strategy_str}策略。", True


def _handle_compress_ui(state, ui_params):
    """处理 compress - UI 参数"""
    state["compression_level"] = ui_params.get("compression_level")
    state["compression_explicit"] = True
    level_text = ui_params.get("compression_level_text", "中等")
    return f"好的，我将把视频压缩为{level_text}质量。", True


def _handle_info_ui(state, ui_params):
    """处理 info - UI 参数"""
    return "好的，我来获取视频的详细信息。", True


def _handle_trim_ui(state, ui_params):
    """处理 trim - UI 参数"""
    start_time = ui_params.get("start_time")
    end_time = ui_params.get("end_time")
    start_explicit = ui_params.get("start_time_explicit", False)
    end_explicit = ui_params.get("end_time_explicit", False)
    if start_time is not None:
        state["start_time"] = start_time
    if end_time is not None:
        state["end_time"] = end_time
    state["start_time_explicit"] = start_explicit
    state["end_time_explicit"] = end_explicit
    all_params = start_explicit and end_explicit
    if all_params:
        return f"好的，我来修剪视频从{start_time}秒到{end_time}秒。", True
    return "好的，我来处理视频修剪。", False


def _handle_concat_ui(state):
    """处理 concat - UI 参数"""
    return "好的，我来拼接视频。", True


def _handle_condense_ui(state, ui_params):
    """处理 condense - UI 参数"""
    strategy = ui_params.get("condense_strategy")
    target_duration = ui_params.get("target_duration")
    # 使用 strategy 兼容 routing.py 和 execute_condense 的读取方式
    state["strategy"] = strategy
    state["target_duration"] = target_duration
    state["strategy_explicit"] = ui_params.get("condense_strategy") is not None
    state["target_duration_explicit"] = ui_params.get("target_duration_explicit", False)

    # 判断参数完整性（必须用户明确选择）
    all_params = state["strategy_explicit"] and state["target_duration_explicit"]

    if all_params:
        strategy_text = ui_params.get("condense_strategy_text", "内容缩编")
        duration_text = target_duration
        return f"好的，使用{strategy_text}策略，目标时长{duration_text}秒。", all_params
    else:
        missing = []
        if not state["strategy_explicit"]:
            missing.append("缩编策略")
        if not state["target_duration_explicit"]:
            missing.append("目标时长")

        # 构造策略提示
        strategy_tips = """
可选的缩编策略：
1. 内容缩编 - 保留视频中的精彩片段，智能筛选高光内容，适合想要精简内容突出重点
2. 智能压缩 - 通过 H.265 重编码压缩视频体积，保持内容完整，适合想要减小文件大小
3. 智能裁剪 - AI 主体检测，智能裁剪画面，适合想要重新构图"""

        pending_q = f"请选择{'/'.join(missing)}"
        if not state["strategy_explicit"] and not state["target_duration_explicit"]:
            return f"好的，我来处理智能缩编。{pending_q}？{strategy_tips}", False, pending_q
        elif not state["strategy_explicit"]:
            return f"好的，{pending_q}？{strategy_tips}", False, pending_q
        else:
            return f"好的，{pending_q}（如：30秒、60秒、120秒）", False, pending_q


def _handle_restore_ui(state, ui_params):
    """处理 restore - UI 参数"""
    preset = ui_params.get("restoration_preset", "basic")
    state["restoration_preset"] = preset
    state["restoration_preset_explicit"] = ui_params.get("restoration_preset_explicit", False)
    preset_names = {"basic": "基础修复", "film": "胶片修复", "enhanced": "增强版"}
    preset_text = preset_names.get(preset, preset)
    return f"好的，使用{preset_text}套餐进行老视频修复。", True


def _handle_editor_ui(state, ui_params):
    """处理 editor - UI 参数"""
    # 解析编辑器模式
    editor_mode = ui_params.get("editor_mode")
    editor_mode_explicit = ui_params.get("editor_mode_explicit", False)
    state["editor_mode"] = editor_mode
    state["editor_mode_explicit"] = editor_mode_explicit

    # 解析字幕样式
    if ui_params.get("subtitle_style"):
        state["subtitle_style"] = ui_params.get("subtitle_style")
        state["subtitle_style_explicit"] = ui_params.get("subtitle_style_explicit", False)

    # 解析转场类型
    if ui_params.get("transition_type"):
        state["transition_type"] = ui_params.get("transition_type")
        state["transition_type_explicit"] = ui_params.get("transition_type_explicit", False)

    # 解析音乐风格
    if ui_params.get("bgm_mood"):
        state["bgm_mood"] = ui_params.get("bgm_mood")
        state["bgm_mood_explicit"] = ui_params.get("bgm_mood_explicit", False)

    # 解析BGM音量
    if ui_params.get("bgm_volume") is not None:
        state["bgm_volume"] = ui_params.get("bgm_volume")
        state["bgm_volume_explicit"] = ui_params.get("bgm_volume_explicit", False)

    # 解析滤镜预设
    if ui_params.get("filter_preset"):
        state["filter_preset"] = ui_params.get("filter_preset")
        state["filter_preset_explicit"] = ui_params.get("filter_preset_explicit", False)

    # 解析配音音色
    if ui_params.get("tts_voice"):
        state["tts_voice"] = ui_params.get("tts_voice")
        state["tts_voice_explicit"] = ui_params.get("tts_voice_explicit", False)

    # 解析配音文本
    if ui_params.get("tts_text"):
        state["tts_text"] = ui_params.get("tts_text")
        state["tts_text_explicit"] = ui_params.get("tts_text_explicit", False)

    mode_names = {
        "highlight": "精彩片段", "subtitle": "自动字幕", "transition": "添加转场",
        "bgm": "智能配乐", "tts": "配音", "filter": "滤镜",
        "analyze": "内容分析", "cover": "封面生成", "title-package": "片头片尾",
    }
    mode_text = mode_names.get(editor_mode, "智能剪辑")
    return f"好的，使用{mode_text}模式进行智能剪辑。", True


def _handle_convert_llm(state, parsed, local_parsed):
    """处理 convert - LLM 参数"""
    # 获取 LLM 解析结果（parsed 已在 analyze_intent 中填充了 state 历史值作为 fallback）
    target_orientation = parsed.get("target_orientation")
    orientation_explicit = parsed.get("orientation_explicit", False)
    strategy = parsed.get("strategy")
    strategy_explicit = parsed.get("strategy_explicit", False)
    ratio = parsed.get("target_ratio")
    ratio_explicit = parsed.get("ratio_explicit", False)

    # 转换比例字符串
    if ratio and isinstance(ratio, str) and ":" in ratio:
        try:
            w, h = ratio.split(":")
            ratio = int(w) / int(h)
        except (ValueError, ZeroDivisionError):
            pass

    # 转换方向格式
    if target_orientation and isinstance(target_orientation, str):
        if target_orientation.lower() not in ["portrait", "landscape"]:
            target_orientation = None
            orientation_explicit = False

    # 本地关键词补充
    if local_parsed.get("orientation_explicit") and local_parsed.get("orientation"):
        target_orientation = local_parsed["orientation"]
        orientation_explicit = True
    if local_parsed.get("strategy_explicit") and local_parsed.get("strategy"):
        strategy = local_parsed["strategy"]
        strategy_explicit = True
    if local_parsed.get("ratio_explicit") and local_parsed.get("ratio"):
        ratio = local_parsed["ratio"]
        ratio_explicit = True

    # 更新状态
    if target_orientation:
        state["target_orientation"] = target_orientation
    if strategy:
        state["strategy"] = strategy
    if ratio:
        state["target_ratio"] = ratio
    state["orientation_explicit"] = orientation_explicit
    state["strategy_explicit"] = strategy_explicit
    state["ratio_explicit"] = ratio_explicit

    # 判断参数完整性
    all_params = orientation_explicit and strategy_explicit and ratio_explicit
    if all_params:
        orient_str = "竖屏" if target_orientation == "portrait" else "横屏"
        ratio_str = "9:16" if ratio and ratio < 1 else ("16:9" if ratio and ratio > 1 else "")
        strategy_map = {"pad": "填充黑边", "crop": "中心裁剪", "smart_crop": "智能裁剪",
                       "stretch": "拉伸填充", "mirror_scroll": "镜像滚动", "pan_scroll": "平移运镜"}
        strategy_str = strategy_map.get(strategy, strategy or "")
        return f"好的，使用{ratio_str}{orient_str}和{strategy_str}策略，正在为您转换...", True, None
    else:
        missing = []
        if not orientation_explicit:
            missing.append("方向")
        if not ratio_explicit:
            missing.append("比例")
        if not strategy_explicit:
            missing.append("策略")
        pending_question = f"请选择{'/'.join(missing)}" if missing else None
        return None, False, pending_question


def _handle_compress_llm(state, parsed, local_parsed):
    """处理 compress - LLM 参数"""
    compression_level = parsed.get("compression_level")
    compression_explicit = parsed.get("compression_explicit", False)

    # 本地关键词补充
    if not compression_explicit and local_parsed.get("compression_explicit"):
        compression_level = local_parsed.get("compression")
        compression_explicit = True

    state["compression_level"] = compression_level
    state["compression_explicit"] = compression_explicit

    all_params = compression_explicit and bool(compression_level)
    if all_params:
        level_map = {"low": "大文件/低压缩", "medium": "中等压缩", "high": "小文件/高压缩"}
        level_str = level_map.get(compression_level, "")
        return f"好的，将视频压缩为{level_str}。", True, None
    else:
        return "请选择压缩级别：低压缩（大文件）、中等压缩（中等文件）、高压缩（小文件）", False, "请选择压缩级别"


def _handle_info_llm(state, llm_response):
    """处理 info - LLM 参数"""
    return llm_response or "好的，我来获取视频的详细信息。", True, None


def _handle_trim_llm(state, parsed):
    """处理 trim - LLM 参数"""
    start_time = parsed.get("start_time")
    end_time = parsed.get("end_time")
    start_explicit = parsed.get("start_time_explicit", False)
    end_explicit = parsed.get("end_time_explicit", False)

    # LLM 未返回 explicit 标志时，fallback 到 state 中的历史值
    if not start_explicit:
        start_explicit = state.get("start_time_explicit", False)
    if not end_explicit:
        end_explicit = state.get("end_time_explicit", False)
    if start_time is None:
        start_time = state.get("start_time")
    if end_time is None:
        end_time = state.get("end_time")

    if start_time is not None:
        try:
            state["start_time"] = float(start_time)
        except (ValueError, TypeError):
            state["start_time"] = start_time
    if end_time is not None:
        try:
            state["end_time"] = float(end_time)
        except (ValueError, TypeError):
            state["end_time"] = end_time
    state["start_time_explicit"] = start_explicit
    state["end_time_explicit"] = end_explicit

    all_params = start_explicit and end_explicit
    if all_params:
        return f"好的，我来修剪视频从{start_time}秒到{end_time}秒。", True, None
    else:
        missing = []
        if not start_explicit:
            missing.append("开始时间")
        if not end_explicit:
            missing.append("结束时间")
        pending_question = f"请提供{'和'.join(missing)}" if missing else None
        return None, False, pending_question


def _handle_concat_llm(state, parsed):
    """处理 concat - LLM 参数"""
    user_input = state.get("new_user_input") or state.get("combined_input") or state.get("user_input", "")
    concat_explicit = parsed.get("concat_explicit", False)
    keep_audio = parsed.get("keep_audio")  # 不给默认值
    video_files = state.get("video_files") or []

    if len(video_files) < 2:
        return "请上传至少2个视频进行拼接。", False, "需要至少2个视频"

    # 如果用户输入明确提到"拼接"，认为是 concat_explicit=true（LLM 有时返回 false）
    if not concat_explicit and any(kw in user_input for kw in ["拼接", "合并", "concat"]):
        concat_explicit = True

    # concat_explicit=true 表示用户明确说了要拼接
    # keep_audio 为 None 表示用户未明确回答是否保留音频 → 需要询问
    if concat_explicit and keep_audio is None:
        return "好的，我已准备好进行视频拼接。请问您是否需要在拼接后的视频中保留原始音频？", False, "请确认是否保留音频"

    # 用户已明确回答
    if keep_audio is not None:
        state["keep_audio"] = keep_audio
        state["concat_explicit"] = True
        return f"好的，保留{'音频' if keep_audio else '无音频'}，开始拼接视频。", True, None

    # concat_explicit=false 且用户未提到拼接时
    return "请确认是否要进行视频拼接。", False, "请确认是否拼接"


def _handle_restore_llm(state, parsed):
    """处理 restore - LLM 参数"""
    # LLM 返回的 key 是 "preset"，UI 参数解析用 "restoration_preset"
    preset = parsed.get("restoration_preset") or parsed.get("preset") or state.get("restoration_preset")
    preset_explicit = parsed.get("restoration_preset_explicit", False) or parsed.get("preset_explicit", False)
    llm_response_text = parsed.get("response", "")

    # LLM fallback
    if not preset_explicit:
        preset_explicit = state.get("restoration_preset_explicit", False)
    if not preset:
        preset = state.get("restoration_preset", "basic")

    state["restoration_preset"] = preset
    state["restoration_preset_explicit"] = preset_explicit

    if preset_explicit:
        # 参数完整时使用 LLM 的详细响应（包含套餐描述），并拼接执行提示
        preset_names = {"basic": "基础修复", "film": "胶片修复", "enhanced": "增强版"}
        preset_text = preset_names.get(preset, preset)
        # 如果 LLM 有详细响应，追加执行提示
        if llm_response_text:
            exec_hint = f"，正在处理..."
            full_msg = llm_response_text + exec_hint
        else:
            full_msg = f"好的，使用{preset_text}套餐进行老视频修复，正在处理..."
        return full_msg, True, None
    else:
        return "好的，我来处理老视频修复。请选择修复套餐：基础修复（去噪、去抖动、色彩校正）、胶片修复（基础+划痕、闪烁修复）、增强版（完整+补帧、超分辨率）", False, "请选择修复套餐"


def _handle_editor_llm(state, parsed, local_parsed):
    """处理 editor - LLM 参数"""
    # 解析编辑器模式
    editor_mode = parsed.get("editor_mode") or state.get("editor_mode")
    editor_mode_explicit = parsed.get("editor_mode_explicit", False) or state.get("editor_mode_explicit", False)

    # 字幕样式
    subtitle_style = parsed.get("subtitle_style") or local_parsed.get("subtitle_style") or state.get("subtitle_style")
    subtitle_style_explicit = parsed.get("subtitle_style_explicit", False) or state.get("subtitle_style_explicit", False)

    # 转场类型
    transition_type = parsed.get("transition_type") or local_parsed.get("transition_type") or state.get("transition_type")
    transition_type_explicit = parsed.get("transition_type_explicit", False) or state.get("transition_type_explicit", False)

    # 目标时长
    target_duration = parsed.get("target_duration") or local_parsed.get("target_duration") or state.get("target_duration")
    target_duration_explicit = parsed.get("target_duration_explicit", False) or state.get("target_duration_explicit", False)

    # 音乐风格
    bgm_mood = parsed.get("bgm_mood") or local_parsed.get("bgm_mood") or state.get("bgm_mood")
    bgm_mood_explicit = parsed.get("bgm_mood_explicit", False) or state.get("bgm_mood_explicit", False)

    # BGM音量
    bgm_volume = parsed.get("bgm_volume") or local_parsed.get("bgm_volume") or state.get("bgm_volume")
    bgm_volume_explicit = parsed.get("bgm_volume_explicit", False) or state.get("bgm_volume_explicit", False)

    # 滤镜预设
    filter_preset = parsed.get("filter_preset") or local_parsed.get("filter_preset") or state.get("filter_preset")
    filter_preset_explicit = parsed.get("filter_preset_explicit", False) or state.get("filter_preset_explicit", False)

    # 配音音色
    tts_voice = parsed.get("tts_voice") or local_parsed.get("tts_voice") or state.get("tts_voice")
    tts_voice_explicit = parsed.get("tts_voice_explicit", False) or state.get("tts_voice_explicit", False)

    # 配音文本
    tts_text = parsed.get("tts_text") or local_parsed.get("tts_text") or state.get("tts_text")
    tts_text_explicit = parsed.get("tts_text_explicit", False) or state.get("tts_text_explicit", False)

    # 平台
    platform = parsed.get("platform") or local_parsed.get("platform") or state.get("platform")
    platform_explicit = parsed.get("platform_explicit", False) or state.get("platform_explicit", False)

    # 更新 state
    if editor_mode:
        state["editor_mode"] = editor_mode
    if editor_mode_explicit or state.get("editor_mode_explicit"):
        state["editor_mode_explicit"] = True
    if subtitle_style:
        state["subtitle_style"] = subtitle_style
    if subtitle_style_explicit:
        state["subtitle_style_explicit"] = True
    if transition_type:
        state["transition_type"] = transition_type
    if transition_type_explicit:
        state["transition_type_explicit"] = True
    if target_duration:
        state["target_duration"] = int(target_duration)
    if target_duration_explicit:
        state["target_duration_explicit"] = True
    if bgm_mood:
        state["bgm_mood"] = bgm_mood
    if bgm_mood_explicit:
        state["bgm_mood_explicit"] = True
    if bgm_volume:
        state["bgm_volume"] = bgm_volume
    if bgm_volume_explicit:
        state["bgm_volume_explicit"] = True
    if filter_preset:
        state["filter_preset"] = filter_preset
    if filter_preset_explicit:
        state["filter_preset_explicit"] = True
    if tts_voice:
        state["tts_voice"] = tts_voice
    if tts_voice_explicit:
        state["tts_voice_explicit"] = True
    if tts_text:
        state["tts_text"] = tts_text
    if tts_text_explicit:
        state["tts_text_explicit"] = True
    if platform:
        state["platform"] = platform
    if platform_explicit:
        state["platform_explicit"] = True

    # 判断参数完整性（editor_mode 必须明确，tts 模式还需要 tts_text）
    all_params = state.get("editor_mode_explicit", False)
    if editor_mode == "tts" and not state.get("tts_text_explicit"):
        all_params = False

    mode_names = {
        "highlight": "精彩片段", "subtitle": "自动字幕", "transition": "添加转场",
        "bgm": "智能配乐", "tts": "配音", "filter": "滤镜",
        "analyze": "内容分析", "cover": "封面生成", "title-package": "片头片尾",
    }
    mode_text = mode_names.get(editor_mode, "智能剪辑")

    if all_params:
        msg = f"好的，使用{mode_text}模式进行智能剪辑，正在处理..."
        return msg, True, None
    else:
        # tts 模式缺少配音文本时，提示输入
        if editor_mode == "tts" and not state.get("tts_text_explicit"):
            return "好的，使用配音模式进行智能剪辑。请输入配音文本", False, "请输入配音文本"
        mode_options = "、".join(mode_names.values())
        return f"好的，我来处理智能剪辑。请选择剪辑模式：{mode_options}", False, "请选择剪辑模式"


def _handle_condense_llm(state, parsed, local_parsed):
    """处理 condense - LLM 参数"""
    # 使用 strategy 兼容 execute_condense 的读取方式
    strategy = parsed.get("condense_strategy") or local_parsed.get("condense_strategy")
    strategy_explicit = parsed.get("condense_strategy_explicit", False)
    target_duration = parsed.get("target_duration")
    target_duration_explicit = parsed.get("target_duration_explicit", False)

    # 本地关键词补充
    if not strategy and local_parsed.get("condense_strategy"):
        strategy = local_parsed["condense_strategy"]
        strategy_explicit = True
    if not target_duration and local_parsed.get("target_duration"):
        target_duration = local_parsed["target_duration"]
        target_duration_explicit = True

    # 更新状态
    if strategy:
        state["strategy"] = strategy
    if target_duration:
        state["target_duration"] = target_duration
    state["strategy_explicit"] = strategy_explicit
    state["target_duration_explicit"] = target_duration_explicit

    # 判断参数完整性（必须用户明确指定，不能有默认值）
    all_params = strategy_explicit and target_duration_explicit

    if all_params:
        strategy_names = {
            "content_condense": "内容缩编",
            "smart_compress": "智能压缩",
            "smart_crop": "智能裁剪",
        }
        strategy_text = strategy_names.get(strategy, strategy)
        return f"好的，使用{strategy_text}策略，目标时长{target_duration}秒，正在为您缩编...", True, None
    else:
        missing = []
        if not strategy_explicit:
            missing.append("缩编策略")
        if not target_duration_explicit:
            missing.append("目标时长")

        # 构造策略提示
        strategy_tips = """
可选的缩编策略：
1. 内容缩编 - 保留视频中的精彩片段，智能筛选高光内容，适合想要精简内容突出重点
2. 智能压缩 - 通过 H.265 重编码压缩视频体积，保持内容完整，适合想要减小文件大小
3. 智能裁剪 - AI 主体检测，智能裁剪画面，适合想要重新构图"""

        pending_q = f"请选择{'/'.join(missing)}"
        if not strategy_explicit and not target_duration_explicit:
            return f"好的，我来处理智能缩编。{pending_q}？{strategy_tips}", False, pending_q
        elif not strategy_explicit:
            return f"好的，{pending_q}？{strategy_tips}", False, pending_q
        else:
            return f"好的，{pending_q}（如：30秒、60秒、120秒）", False, pending_q


def analyze_intent(state: VideoAgentState) -> VideoAgentState:
    """分析用户意图"""
    import os

    user_input = state.get("new_user_input") or state.get("combined_input") or state["user_input"]
    video_files = state.get("video_files") or []

    print(f"[DEBUG analyze_intent] user_input: {user_input[:100]}, video_files count: {len(video_files)}")

    # 优先解析UI参数格式
    ui_params = _parse_ui_params(user_input)
    if ui_params.get("found"):
        feature = ui_params.get("feature", "convert")
        state["current_feature"] = feature

        handlers = {
            "convert": _handle_convert_ui,
            "compress": _handle_compress_ui,
            "info": _handle_info_ui,
            "trim": _handle_trim_ui,
            "concat": _handle_concat_ui,
            "condense": _handle_condense_ui,
            "restore": _handle_restore_ui,
            "editor": _handle_editor_ui,
        }
        handler = handlers.get(feature)
        if handler:
            llm_response, all_params = handler(state, ui_params)
            _setup_feature_state(state, feature, all_params, None if all_params else "请选择参数", llm_response)
        return state

    # 本地关键词解析
    local_parsed = IntentParser.parse(user_input)

    # LLM 解析
    LLM_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
    llm_parse_intent = None
    if LLM_API_KEY:
        try:
            from agent.langchain_agent import parse_intent as llm_parse_intent_impl
            llm_parse_intent = llm_parse_intent_impl
        except ImportError:
            pass

    parsed = None
    llm_response = ""
    target_feature = "convert"

    if llm_parse_intent:
        try:
            from agent.langchain_agent import MinMaxLLM
            from agent.memory import get_conversation_history
            llm = MinMaxLLM(api_key=LLM_API_KEY)

            session_id = state.get("session_id")
            state_messages = state.get("messages", [])
            if session_id and len(state_messages) > 0:
                history = []
                for m in state_messages:
                    if isinstance(m, dict):
                        role = "user" if m.get("role") in ("user", "human") else "assistant"
                        history.append({"role": role, "content": m.get("content", "")})
                    else:
                        role = "user" if isinstance(m, HumanMessage) else "assistant"
                        history.append({"role": role, "content": m.content})
            elif session_id:
                chat_history = get_conversation_history(session_id)
                history = [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                          for m in chat_history.messages]
            else:
                history = []

            parsed = llm_parse_intent(user_input, llm, history=history)
            # 如果 LLM 解析没有返回 explicit 标志，fallback 到 state 中的历史值
            explicit_fields = [
                ("orientation_explicit", "target_orientation"),
                ("ratio_explicit", "target_ratio"),
                ("strategy_explicit", "strategy"),
                ("compression_explicit", "compression_level"),
                ("start_time_explicit", "start_time"),
                ("end_time_explicit", "end_time"),
            ]
            for explicit_key, value_key in explicit_fields:
                if not parsed.get(explicit_key):
                    parsed[explicit_key] = state.get(explicit_key, False)
                if not parsed.get(value_key):
                    parsed[value_key] = state.get(value_key)
            # 同步到 state["history"]，供后续调用 parse_intent 使用
            state["history"] = history
            llm_response = parsed.get("response", "")
            target_feature = parsed.get("target_feature", "convert")
        except Exception as e:
            llm_response = f"LLM 解析出错：{str(e)}"
            target_feature = "convert"
    else:
        target_feature = "transform"

    # 根据功能类型处理
    feature_handlers = {
        "convert": lambda: _handle_convert_llm(state, parsed or {}, local_parsed),
        "compress": lambda: _handle_compress_llm(state, parsed or {}, local_parsed),
        "info": lambda: _handle_info_llm(state, llm_response),
        "trim": lambda: _handle_trim_llm(state, parsed or {}),
        "concat": lambda: _handle_concat_llm(state, parsed or {}),
        "restore": lambda: (_handle_restore_llm(state, parsed or {})),
        "editor": lambda: (_handle_editor_llm(state, parsed or {}, local_parsed)),
        "condense": lambda: _handle_condense_llm(state, parsed or {}, local_parsed),
    }

    handler = feature_handlers.get(target_feature)
    if handler:
        result = handler()
        if len(result) == 3:
            msg, all_params, pending_q = result
            _setup_feature_state(state, target_feature, all_params, pending_q, msg or llm_response)
        elif len(result) == 2:
            msg, all_params = result
            _setup_feature_state(state, target_feature, all_params, None, msg or llm_response)
    else:
        _setup_feature_state(state, target_feature, False, "请选择参数", llm_response)

    return state
