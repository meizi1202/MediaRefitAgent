"""
命令行接口 - 与视频转换 Agent 对话

用法:
    python -m agent.cli
    python -m agent.cli --video path/to/video.mp4
    python -m agent.cli --interactive
"""
import argparse
import sys
from pathlib import Path

from agent.video_agent import VideoAgent, LANGGRAPH_AVAILABLE


def print_welcome():
    """打印欢迎信息"""
    print("=" * 50)
    print("  MediaRefitAgent CLI")
    print("  视频横竖屏转换智能体")
    print("=" * 50)
    print()
    print("支持自然语言指令，例如：")
    print("  - 把这个视频转成竖屏")
    print("  - 转换为横屏，使用智能裁剪")
    print("  - 旋转90度")
    print()
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'help' 查看帮助")
    print()


def print_help():
    """打印帮助信息"""
    print("""
可用命令:
  quit, exit      - 退出程序
  help            - 显示帮助
  status          - 显示当前会话状态
  clear           - 清屏
  reset           - 重置会话

示例:
  把这个视频转成竖屏
  转换为横屏，使用智能裁剪
  使用填充策略转为竖屏
  旋转视频90度
""")


def interactive_mode(agent: VideoAgent, video_path: str = None):
    """交互模式"""
    session_id = None

    print_welcome()

    if video_path:
        print(f"📁 已加载视频: {video_path}")
        print()

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n再见！")
            break

        if not user_input:
            continue

        # 处理命令
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        if user_input.lower() == "help":
            print_help()
            continue

        if user_input.lower() == "status":
            if session_id:
                state = agent.get_session(session_id)
                if state:
                    print(f"Session: {session_id}")
                    print(f"Step: {state.get('current_step')}")
                    print(f"Video: {state.get('temp_video_path') or state.get('video_path')}")
                    print(f"Orientation: {state.get('original_orientation')} -> {state.get('target_orientation')}")
                    print(f"Strategy: {state.get('strategy')}")
            else:
                print("No active session")
            continue

        if user_input.lower() == "reset":
            if session_id:
                agent.delete_session(session_id)
            session_id = None
            print("会话已重置")
            continue

        # 处理用户输入
        if video_path:
            result = agent.process_video(
                user_input=user_input,
                temp_video_path=video_path,
                session_id=session_id,
            )
            session_id = result.get("session_id")
        else:
            result = agent.run(user_input)

        # 打印结果
        if result.get("error"):
            print(f"错误: {result['error']}")
        else:
            for msg in result.get("messages", []):
                if msg.get("role") == "assistant":
                    print(f"助手: {msg.get('content')}")

        # 如果有 pending 问题，继续询问
        while result.get("pending_question"):
            print(f"助手: {result['pending_question']}")
            try:
                user_input = input("你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                return

            if user_input.lower() in ("quit", "exit", "q"):
                print("再见！")
                return

            if video_path:
                result = agent.continue_conversation(user_input, session_id)
            else:
                result = agent.run(user_input)

            for msg in result.get("messages", []):
                if msg.get("role") == "assistant":
                    print(f"助手: {msg.get('content')}")

        print()


def main():
    parser = argparse.ArgumentParser(description="MediaRefitAgent CLI")
    parser.add_argument("--video", "-v", type=str, help="视频文件路径")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument("--text", "-t", type=str, help="直接输入指令（单轮）")

    args = parser.parse_args()

    if not LANGGRAPH_AVAILABLE:
        print("错误: LangGraph 不可用")
        print("请安装: pip install langgraph")
        sys.exit(1)

    agent = VideoAgent()

    if args.text:
        # 单轮对话模式
        result = agent.run(args.text, args.video)
        for msg in result.get("messages", []):
            if msg.get("role") == "assistant":
                print(f"助手: {msg.get('content')}")

    elif args.video:
        # 有视频的交互模式
        if not Path(args.video).exists():
            print(f"错误: 视频文件不存在: {args.video}")
            sys.exit(1)

        interactive_mode(agent, args.video)

    elif args.interactive:
        # 纯交互模式
        interactive_mode(agent)

    else:
        # 默认显示帮助
        print_welcome()
        print("请使用 --video 指定视频文件，或 --interactive 进入交互模式")
        print()
        print("示例:")
        print("  python -m agent.cli --video path/to/video.mp4")
        print("  python -m agent.cli --interactive")
        print("  python -m agent.cli --text '把视频转成竖屏' --video path/to/video.mp4")


if __name__ == "__main__":
    main()
