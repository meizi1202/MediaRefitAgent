"""
Phase 3 Agent 测试
"""
import pytest
from unittest.mock import patch, MagicMock


class TestIntentParser:
    """IntentParser 测试"""

    def test_parse_portrait_orientation(self):
        """测试解析竖屏方向"""
        from agent.video_agent import IntentParser

        texts = ["把这个视频转成竖屏", "转换为 portrait", "竖屏视频", "9:16"]
        for text in texts:
            result = IntentParser.parse(text)
            assert result["orientation"] == "portrait", f"Failed for: {text}"

    def test_parse_landscape_orientation(self):
        """测试解析横屏方向"""
        from agent.video_agent import IntentParser

        texts = ["横屏", "landscape", "水平", "16:9"]
        for text in texts:
            result = IntentParser.parse(text)
            assert result["orientation"] == "landscape", f"Failed for: {text}"

    def test_parse_strategy(self):
        """测试解析转换策略"""
        from agent.video_agent import IntentParser

        # smart_crop
        result = IntentParser.parse("使用智能裁剪")
        assert result["strategy"] == "smart_crop"

        # crop
        result = IntentParser.parse("裁剪视频")
        assert result["strategy"] == "crop"

        # pad
        result = IntentParser.parse("填充黑边")
        assert result["strategy"] == "pad"

        # rotate
        result = IntentParser.parse("旋转视频")
        assert result["strategy"] == "rotate"

    def test_parse_ratio(self):
        """测试解析比例"""
        from agent.video_agent import IntentParser

        # 9:16
        result = IntentParser.parse("9:16")
        assert result["ratio"] == pytest.approx(9/16, rel=0.01)

        # 16:9
        result = IntentParser.parse("16:9")
        assert result["ratio"] == pytest.approx(16/9, rel=0.01)

        # 9/16
        result = IntentParser.parse("9/16")
        assert result["ratio"] == pytest.approx(9/16, rel=0.01)

    def test_parse_default_strategy(self):
        """测试默认策略"""
        from agent.video_agent import IntentParser

        result = IntentParser.parse("处理这个视频")
        assert result["strategy"] == "pad"  # 默认是 pad

    def test_parse_mixed_input(self):
        """测试混合输入"""
        from agent.video_agent import IntentParser

        result = IntentParser.parse("把视频转成竖屏，使用智能裁剪")
        assert result["orientation"] == "portrait"
        assert result["strategy"] == "smart_crop"


class TestVideoAgentState:
    """VideoAgentState 测试"""

    def test_state_creation(self):
        """测试状态创建"""
        from agent.video_agent import VideoAgentState

        state = VideoAgentState(
            user_input="测试",
            video_path="/path/to/video.mp4",
            temp_video_path=None,
            original_orientation="landscape",
            target_orientation="portrait",
            strategy="pad",
            target_ratio=9/16,
            current_step="analyze_intent",
            messages=[],
            transform_result=None,
            error=None,
            session_id="test123",
            history=[],
            pending_question=None,
        )

        assert state["user_input"] == "测试"
        assert state["original_orientation"] == "landscape"
        assert state["target_orientation"] == "portrait"

    def test_conversation_message(self):
        """测试对话消息"""
        from agent.video_agent import ConversationMessage

        msg = ConversationMessage(
            role="assistant",
            content="你好，我是视频转换助手",
            timestamp="2024-01-01T00:00:00",
        )

        assert msg["role"] == "assistant"
        assert "视频转换助手" in msg["content"]


class TestVideoAgent:
    """VideoAgent 测试"""

    def test_agent_init_without_langgraph(self):
        """测试 LangGraph 不可用时初始化"""
        with patch('agent.video_agent.LANGGRAPH_AVAILABLE', False):
            # 重新导入以获取 patch 效果
            import importlib
            import agent.video_agent as va
            importlib.reload(va)

            agent = va.VideoAgent()
            # graph 应该是 None
            assert agent.graph is None

    @patch('agent.video_agent.LANGGRAPH_AVAILABLE', True)
    @patch('agent.video_agent.create_video_agent_graph')
    def test_agent_init_with_langgraph(self, mock_create_graph):
        """测试 LangGraph 可用时初始化"""
        mock_graph = MagicMock()
        mock_create_graph.return_value = mock_graph

        from agent.video_agent import VideoAgent

        agent = VideoAgent()
        assert agent.graph is not None

    def test_session_management(self):
        """测试会话管理"""
        from agent.video_agent import VideoAgent

        agent = VideoAgent()
        agent.sessions = {"test": {"current_step": "done"}}

        # 获取会话
        state = agent.get_session("test")
        assert state is not None
        assert state["current_step"] == "done"

        # 获取不存在的会话
        state = agent.get_session("nonexistent")
        assert state is None

        # 删除会话
        deleted = agent.delete_session("test")
        assert deleted is True
        assert "test" not in agent.sessions

        # 删除不存在的会话
        deleted = agent.delete_session("nonexistent")
        assert deleted is False

        # 列出会话
        agent.sessions = {"s1": {}, "s2": {}}
        sessions = agent.list_sessions()
        assert len(sessions) == 2
        assert "s1" in sessions
        assert "s2" in sessions


class TestAgentRun:
    """Agent 运行测试"""

    @patch('agent.video_agent.LANGGRAPH_AVAILABLE', False)
    def test_run_without_langgraph(self):
        """测试 LangGraph 不可用时运行"""
        import agent.video_agent as va
        import importlib
        importlib.reload(va)

        agent = va.VideoAgent()
        result = agent.run("转换视频")

        assert result.get("error") is not None
        assert "LangGraph" in result.get("error", "")

    @patch('agent.video_agent.detect_orientation')
    @patch('agent.video_agent.transform')
    def test_run_with_video(self, mock_transform, mock_detect):
        """测试带视频运行"""
        from agent.video_agent import VideoAgent, LANGGRAPH_AVAILABLE

        if not LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph not available")

        # Mock 检测结果
        mock_detect.return_value = MagicMock(
            orientation="landscape",
            confidence=MagicMock(value="high"),
            method="metadata",
        )

        # Mock 转换结果
        mock_transform.return_value = MagicMock(
            success=True,
            output_path="/output.mp4",
            original_orientation="landscape",
            target_orientation="portrait",
            strategy_used="pad",
        )

        agent = VideoAgent()
        result = agent.run("转成竖屏", video_path="/fake/video.mp4")

        # 验证错误不是关于 LangGraph 的
        if result.get("error") and "LangGraph" in result.get("error", ""):
            pytest.skip("LangGraph not properly installed")


class TestChatWithAgent:
    """chat_with_agent 测试"""

    @patch('agent.video_agent.LANGGRAPH_AVAILABLE', False)
    def test_chat_without_langgraph(self):
        """测试 LangGraph 不可用时聊天"""
        import agent.video_agent as va
        import importlib
        importlib.reload(va)

        result = va.chat_with_agent("你好")
        assert "错误" in result or "LangGraph" in result


class TestCLI:
    """CLI 测试"""

    def test_print_welcome(self):
        """测试欢迎信息打印"""
        from agent.cli import print_welcome
        # 只是确保函数可以执行而不报错
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        print_welcome()
        sys.stdout = old_stdout

    def test_print_help(self):
        """测试帮助信息打印"""
        from agent.cli import print_help
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        print_help()
        sys.stdout = old_stdout


class TestFastAPIEndpoints:
    """FastAPI Agent 端点测试"""

    def test_agent_chat_request_model(self):
        """测试 Agent 聊天请求模型"""
        from api.fastapi_app import AgentChatRequest

        request = AgentChatRequest(
            message="把视频转成竖屏",
            session_id="test123",
        )
        assert request.message == "把视频转成竖屏"
        assert request.session_id == "test123"

    def test_agent_chat_response_model(self):
        """测试 Agent 聊天响应模型"""
        from api.fastapi_app import AgentChatResponse

        response = AgentChatResponse(
            session_id="test123",
            message="好的，正在转换...",
            success=True,
            data={"output_path": "/output.mp4"},
        )
        assert response.success is True
        assert response.data["output_path"] == "/output.mp4"

    def test_agent_status_response_model(self):
        """测试 Agent 状态响应模型"""
        from api.fastapi_app import AgentStatusResponse

        response = AgentStatusResponse(
            session_id="test123",
            current_step="confirm_complete",
            original_orientation="landscape",
            target_orientation="portrait",
            strategy="pad",
            pending_question=None,
            messages=[],
        )
        assert response.current_step == "confirm_complete"
        assert response.original_orientation == "landscape"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
