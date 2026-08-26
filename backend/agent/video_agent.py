"""
视频转换 Agent - 基于 LangGraph

状态机设计：
analyze_intent → waiting_for_user ↔ handle_user_response → execute_* → confirm_complete

支持多轮对话，可以记忆上下文

文件结构：
- types.py: 共享类型定义
- nodes/: Node 函数（analyze, detect, execute, routing）
- memory/: 会话历史存储
- video_agent.py: 状态机编排入口
"""
from typing import Optional
from datetime import datetime
import shutil
from pathlib import Path
import os

# 会话目录
SESSIONS_DIR = Path.home() / ".mediarefit" / "sessions"

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# Import shared types
from agent.types import VideoAgentState, ConversationMessage

# LLM-based intent parsing - checked at runtime to allow API key from request
LLM_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
llm_parse_intent = None


def _get_llm_parse_intent():
    """Lazy import for LLM parsing"""
    global llm_parse_intent
    if llm_parse_intent is None:
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        if api_key:
            try:
                from agent.langchain_agent import parse_intent as llm_parse_intent_impl
                llm_parse_intent = llm_parse_intent_impl
            except ImportError:
                llm_parse_intent = None
    return llm_parse_intent


# ============ IntentParser (kept here for backward compatibility) ============

class IntentParser:
    """意图解析器"""

    # 方向关键词
    ORIENTATION_KEYWORDS = {
        "portrait": ["竖屏", "portrait", "垂直", "竖", "9:16", "9/16", "4:5", "4/5", "1:1", "1/1", "2:3", "2/3", "短视频", "抖音", "快手", "Instagram", "IG"],
        "landscape": ["横屏", "landscape", "水平", "横", "16:9", "16/9", "21:9", "21/9", "4:3", "4/3", "3:2", "3/2", "横版", "电影"],
    }

    # 策略关键词
    STRATEGY_KEYWORDS = {
        "smart_crop": ["智能裁剪", "smart", "AI裁剪", "ai crop", "智能", "AI"],
        "crop": ["裁剪", "crop", "切", "截"],
        "pad": ["填充", "pad", "黑边", "留边", "保持完整"],
        "rotate": ["旋转", "rotate", "旋转90度", "rotate90"],
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
    def parse(cls, text: str) -> dict:
        """解析用户输入"""
        orientation, orientation_explicit = cls.parse_orientation(text)
        strategy, strategy_explicit = cls.parse_strategy(text)
        ratio, ratio_explicit = cls.parse_ratio(text)
        return {
            "orientation": orientation,
            "orientation_explicit": orientation_explicit,
            "strategy": strategy,
            "strategy_explicit": strategy_explicit,
            "ratio": ratio,
            "ratio_explicit": ratio_explicit,
        }


def _parse_ui_params(user_input: str) -> dict:
    """解析前端UI选择的参数格式 [用户已选择参数：目标方向=竖屏 9:16，转换策略=填充黑边]"""
    import re
    result = {"found": False}

    # 检查是否包含UI参数格式
    if "[用户已选择参数：" not in user_input:
        return result

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

        # 解析比例
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
            "填充黑边": "pad",
            "中心裁剪": "crop",
            "智能裁剪": "smart_crop",
            "拉伸填充": "stretch",
            "镜像滚动": "mirror_scroll",
            "平移运镜": "pan_scroll",
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
        level_map = {
            "低": "low",
            "中": "medium",
            "高": "high",
        }
        for name, level in level_map.items():
            if name in level_text:
                result["compression_level"] = level
                result["compression_level_text"] = name
                result["found"] = True
                break

    return result


# ============ Graph Construction ============

def create_video_agent_graph():
    """创建视频转换 Agent 图"""
    if not LANGGRAPH_AVAILABLE:
        return None

    # Import nodes here to avoid circular imports
    from agent.nodes.analyze import analyze_intent
    from agent.nodes.execute import (
        execute_transform,
        execute_compress,
        execute_trim,
        execute_concat,
        execute_condense,
        execute_restore,
        execute_info,
        execute_editor,
        confirm_complete,
    )
    from agent.nodes.routing import should_proceed, handle_user_response

    graph = StateGraph(VideoAgentState)

    # 添加节点
    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("execute_transform", execute_transform)
    graph.add_node("execute_compress", execute_compress)
    graph.add_node("execute_concat", execute_concat)
    graph.add_node("execute_trim", execute_trim)
    graph.add_node("execute_condense", execute_condense)
    graph.add_node("execute_restore", execute_restore)
    graph.add_node("execute_info", execute_info)
    graph.add_node("execute_editor", execute_editor)
    graph.add_node("confirm_complete", confirm_complete)
    graph.add_node("handle_user_response", handle_user_response)
    graph.add_node("waiting_for_user", lambda state: state)  # 暂停等待用户输入

    # 入口节点：根据 current_step 决定路由
    def entry_node(state: VideoAgentState) -> VideoAgentState:
        return state

    graph.add_node("__entry__", entry_node)
    graph.set_entry_point("__entry__")

    # __entry__ 条件边：根据 current_step 决定入口节点
    def route_from_entry(state: VideoAgentState) -> str:
        current_step = state.get("current_step")
        pending_question = state.get("pending_question")
        combined_input = state.get("combined_input")
        print(f"[DEBUG route_from_entry] ENTER current_step={current_step}, pending_question={pending_question}, combined_input={combined_input}")
        # combined_input 存在说明上轮回答了 pending_question，需要进入 handle_user_response 处理
        if combined_input:
            print(f"[DEBUG route_from_entry] -> handle_user_response (combined_input exists)")
            return "handle_user_response"
        # pending_question 存在说明上轮结束等待用户回答下一轮
        if pending_question:
            print(f"[DEBUG route_from_entry] -> handle_user_response (pending_question exists)")
            return "handle_user_response"
        # current_step 是 waiting_for_user 也说明等待用户回答
        if current_step == "waiting_for_user":
            print(f"[DEBUG route_from_entry] -> handle_user_response (current_step=waiting_for_user)")
            return "handle_user_response"
        print(f"[DEBUG route_from_entry] -> analyze_intent (default)")
        return "analyze_intent"
        if current_step == "waiting_for_user":
            return "handle_user_response"
        return "analyze_intent"

    graph.add_conditional_edges(
        "__entry__",
        route_from_entry,
        {
            "handle_user_response": "handle_user_response",
            "analyze_intent": "analyze_intent",
        }
    )

    # analyze_intent 条件边：所有功能统一经 should_proceed 路由
    graph.add_conditional_edges(
        "analyze_intent",
        should_proceed,
        {
            "analyze_intent": "analyze_intent",
            "execute_transform": "execute_transform",
            "execute_compress": "execute_compress",
            "execute_concat": "execute_concat",
            "execute_trim": "execute_trim",
            "execute_condense": "execute_condense",
            "execute_restore": "execute_restore",
            "execute_info": "execute_info",
            "execute_editor": "execute_editor",
            "handle_user_response": "handle_user_response",
            "waiting_for_user": "waiting_for_user",
            "confirm_complete": "confirm_complete",
        }
    )

    # waiting_for_user 节点：直接结束，等待下一轮请求
    graph.add_edge("waiting_for_user", "confirm_complete")

    # 执行节点完成后直接结束
    graph.add_edge("execute_trim", "confirm_complete")
    graph.add_edge("execute_condense", "confirm_complete")
    graph.add_edge("execute_restore", "confirm_complete")
    graph.add_edge("execute_info", "confirm_complete")
    graph.add_edge("execute_editor", "confirm_complete")

    # handle_user_response 节点：处理完用户回答后，根据 current_step 决定下一步
    def route_from_handle_user_response(state: VideoAgentState) -> str:
        next_step = state.get("current_step", "")
        execute_nodes = {"execute_transform", "execute_compress", "execute_concat",
                         "execute_trim", "execute_condense", "execute_restore",
                         "execute_info", "execute_editor"}
        if next_step in execute_nodes:
            return next_step
        # 功能切换时，重新走 analyze_intent 解析
        if next_step == "analyze_intent":
            return "analyze_intent"
        # 仍有缺失参数，等待用户下一轮回答
        if next_step == "waiting_for_user":
            return "waiting_for_user"
        return "confirm_complete"

    graph.add_conditional_edges(
        "handle_user_response",
        route_from_handle_user_response,
        {
            "execute_transform": "execute_transform",
            "execute_compress": "execute_compress",
            "execute_concat": "execute_concat",
            "execute_trim": "execute_trim",
            "execute_condense": "execute_condense",
            "execute_restore": "execute_restore",
            "execute_info": "execute_info",
            "execute_editor": "execute_editor",
            "analyze_intent": "analyze_intent",
            "waiting_for_user": "waiting_for_user",
            "confirm_complete": "confirm_complete",
        }
    )

    graph.add_edge("execute_transform", "confirm_complete")
    graph.add_edge("execute_compress", "confirm_complete")
    graph.add_edge("execute_concat", "confirm_complete")
    graph.add_edge("confirm_complete", END)

    return graph.compile().with_config(recursion_limit=100)


# ============ Agent Runner ============

class VideoAgent:
    """视频转换 Agent"""

    def __init__(self):
        self.graph = create_video_agent_graph()
        self.sessions: dict[str, VideoAgentState] = {}

    def _create_initial_state(
        self,
        user_input: str,
        video_path: Optional[str] = None,
        temp_video_path: Optional[str] = None,
        session_id: Optional[str] = None,
        video_files: Optional[list[str]] = None,
    ) -> VideoAgentState:
        """创建初始状态"""
        return VideoAgentState(
            user_input=user_input,
            video_path=video_path,
            temp_video_path=temp_video_path,
            video_files=video_files,
            original_orientation=None,
            target_orientation=None,
            strategy="pad",
            target_ratio=9/16,
            orientation_explicit=False,
            strategy_explicit=False,
            ratio_explicit=False,
            all_params_provided=False,
            current_step="analyze_intent",
            current_feature=None,
            messages=[],
            transform_result=None,
            error=None,
            session_id=session_id or datetime.now().strftime("%Y%m%d%H%M%S"),
            history=[],
            pending_question=None,
            compression_level=None,
            compression_explicit=False,
            start_time=None,
            end_time=None,
            start_time_explicit=False,
            end_time_explicit=False,
            keep_audio=True,
            concat_explicit=False,
            trim_result=None,
        )

    def run(
        self,
        user_input: str,
        video_path: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> VideoAgentState:
        """运行 Agent（单轮）"""
        if not self.graph:
            return {
                "error": "LangGraph 不可用，请安装: pip install langgraph",
                "current_step": "error",
                "messages": [],
            }

        state = self._create_initial_state(
            user_input=user_input,
            video_path=video_path,
            session_id=session_id,
        )

        result = self.graph.invoke(state)
        return result

    def process_video(
        self,
        user_input: str,
        temp_video_path: str,
        session_id: Optional[str] = None,
        video_files: Optional[list[str]] = None,
    ) -> VideoAgentState:
        """处理上传的视频（多轮）"""
        if not self.graph:
            return {
                "error": "LangGraph 不可用",
                "current_step": "error",
                "messages": [],
            }

        # 如果有 session，重置状态重新分析意图
        old_messages_count = 0
        if session_id and session_id in self.sessions:
            state = self.sessions[session_id]
            old_messages_count = len(state.get("messages", []))
            print(f"[DEBUG process_video] Turn 2 session found, current_step={state.get('current_step')}, pending_question={state.get('pending_question')}")
            # 始终传递新输入，通过 new_user_input 字段让 handle_user_response 读取
            state["new_user_input"] = user_input
            # 清除 combined_input，避免 analyze_intent 使用旧输入
            state["combined_input"] = None
            print(f"[DEBUG process_video] new_user_input set to: {user_input}, combined_input cleared")
            # 只有上传了新文件时才更新视频路径
            if temp_video_path:
                state["temp_video_path"] = temp_video_path
            if video_files:
                state["video_files"] = video_files
            # 如果有待回答的问题，设置 current_step 为 waiting_for_user 让流程走到 handle_user_response
            # 注意：如果 handle_user_response 已经设置了 current_step = "analyze_intent"，则不覆盖
            if state.get("current_step") != "analyze_intent":
                if state.get("pending_question") or state.get("current_step") == "waiting_for_user":
                    state["current_step"] = "waiting_for_user"
                    # 保留已解析的参数状态，不重置
                else:
                    # pending_question 为 None，检查是否有明确参数
                    # 如果有，说明用户在修改参数，应该走 handle_user_response
                    if (state.get("orientation_explicit") or state.get("ratio_explicit")
                        or state.get("strategy_explicit") or state.get("compression_explicit")):
                        state["current_step"] = "waiting_for_user"
                    else:
                        # 重置关键状态，让流程重新走意图分析
                        state["current_step"] = "analyze_intent"
                        state["current_feature"] = None
                        state["all_params_provided"] = False
                        state["error"] = None
                        # 重置参数相关状态，避免被旧值影响
                        state["compression_level"] = None
                        state["compression_explicit"] = False
                        state["orientation_explicit"] = False
                        state["strategy_explicit"] = False
                        state["ratio_explicit"] = False
        else:
            print(f"[DEBUG process_video] Session {session_id} NOT FOUND in sessions. Available: {list(self.sessions.keys())}")
            # 创建会话目录并持久化视频
            actual_session_id = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
            session_dir = SESSIONS_DIR / actual_session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # 复制主视频到会话目录
            if temp_video_path and Path(temp_video_path).exists():
                dest_path = session_dir / f"video{Path(temp_video_path).suffix}"
                shutil.copy2(temp_video_path, dest_path)
                temp_video_path = str(dest_path)

            # 复制多个视频到会话目录（用于拼接）
            if video_files:
                persisted_files = []
                for i, vf in enumerate(video_files):
                    if Path(vf).exists():
                        dest_path = session_dir / f"video_{i}{Path(vf).suffix}"
                        shutil.copy2(vf, dest_path)
                        persisted_files.append(str(dest_path))
                video_files = persisted_files

            state = self._create_initial_state(
                user_input=user_input,
                temp_video_path=temp_video_path,
                session_id=actual_session_id,
            )
            if video_files:
                state["video_files"] = video_files

        result = self.graph.invoke(state)

        # 使用结果中的 session_id（可能由 _create_initial_state 生成）
        actual_session_id = result.get("session_id")

        # 只返回新产生的消息（排除历史消息）
        all_messages = result.get("messages", [])
        new_messages = all_messages[old_messages_count:] if old_messages_count > 0 else all_messages
        result["messages"] = new_messages

        # 同步消息到 LangChain Memory
        if actual_session_id:
            self._sync_messages_to_memory(actual_session_id, all_messages)

        # 保存到 sessions
        if actual_session_id:
            self.sessions[actual_session_id] = result

        return result

    def continue_conversation(
        self,
        user_input: str,
        session_id: str,
    ) -> VideoAgentState:
        """继续多轮对话"""
        if session_id not in self.sessions:
            return {
                "error": "Session not found",
                "current_step": "error",
                "messages": [],
            }

        state = self.sessions[session_id]
        state["user_input"] = user_input
        print(f"[DEBUG continue_conversation] session_id={session_id}, user_input={user_input}, current_step={state.get('current_step')}, pending_question={state.get('pending_question')}")

        result = self.graph.invoke(state)

        # 同步消息到 LangChain Memory
        self._sync_messages_to_memory(session_id, result.get("messages", []))

        self.sessions[session_id] = result
        return result

    def get_session(self, session_id: str) -> Optional[VideoAgentState]:
        """获取会话状态"""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        return list(self.sessions.keys())

    def _sync_messages_to_memory(self, session_id: str, messages: list) -> None:
        """同步消息到 LangChain Memory"""
        from agent.memory import get_conversation_history
        try:
            chat_history = get_conversation_history(session_id)
            # 获取已存储的消息数量，避免重复添加
            existing_count = len(chat_history.messages)
            # 只添加新消息
            for msg in messages[existing_count:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user" or role == "human":
                    chat_history.add_user_message(content)
                elif role == "assistant" or role == "ai":
                    chat_history.add_ai_message(content)
        except Exception:
            pass  # Memory 同步失败不影响主流程


# ============ Convenience Functions ============

def run_video_agent(
    user_input: str,
    video_path: Optional[str] = None,
) -> VideoAgentState:
    """快捷运行函数"""
    agent = VideoAgent()
    return agent.run(user_input, video_path)


def chat_with_agent(
    user_input: str,
    video_path: Optional[str] = None,
) -> str:
    """简易聊天接口，返回助手的回复文本"""
    agent = VideoAgent()
    result = agent.run(user_input, video_path)

    if result.get("error"):
        return f"错误: {result['error']}"

    # 返回最后一条助手消息
    for msg in reversed(result.get("messages", [])):
        if msg.get("role") == "assistant":
            return msg.get("content", "")

    return "处理完成"
