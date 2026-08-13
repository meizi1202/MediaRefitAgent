"""
MediaRefitAgent 客户端

用于与 MediaRefitAgent API 交互的 Python 客户端库

Usage:
    from client import MediaRefitClient

    client = MediaRefitClient("http://localhost:8000")

    # Agent 聊天
    response = client.agent_chat("把视频转成竖屏", "video.mp4")

    # 继续对话
    response = client.agent_continue("改用智能裁剪", session_id=response.session_id)

    # 直接转换
    response = client.transform("video.mp4", target_orientation="portrait", strategy="pad")
"""
import requests
import base64
import os
from pathlib import Path
from typing import Optional, Generator
from urllib.parse import urljoin


class MediaRefitClient:
    """MediaRefitAgent API 客户端"""

    def __init__(self, base_url: str = "http://172.18.98.97:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _url(self, path: str) -> str:
        """构建完整 URL"""
        return urljoin(self.base_url + "/", path.lstrip("/"))

    # ============ 健康检查 ============

    def health_check(self) -> dict:
        """健康检查"""
        resp = self.session.get(self._url("/api/health"))
        resp.raise_for_status()
        return resp.json()

    def get_capabilities(self) -> dict:
        """获取支持的能力"""
        resp = self.session.get(self._url("/api/capabilities"))
        resp.raise_for_status()
        return resp.json()

    # ============ 视频转换 ============

    def transform(
        self,
        video_path: str,
        target_orientation: str = "portrait",
        strategy: str = "pad",
        target_ratio: float = 9 / 16,
    ) -> dict:
        """
        视频转换（同步）

        Args:
            video_path: 视频文件路径
            target_orientation: 目标方向 "portrait" 或 "landscape"
            strategy: 转换策略 "rotate" / "pad" / "crop" / "smart_crop"
            target_ratio: 目标比例，默认 9/16

        Returns:
            {
                "success": True,
                "output_path": "/path/to/output.mp4",
                ...
            }
        """
        with open(video_path, "rb") as f:
            files = {"file": (Path(video_path).name, f, "video/mp4")}
            data = {
                "target_orientation": target_orientation,
                "strategy": strategy,
                "target_ratio": str(target_ratio),
            }
            resp = self.session.post(
                self._url("/api/transform"),
                files=files,
                data=data,
            )

        resp.raise_for_status()
        return resp.json()

    def transform_stream(
        self,
        video_path: str,
        target_orientation: str = "portrait",
        strategy: str = "pad",
        target_ratio: float = 9 / 16,
    ) -> Generator[dict, None, None]:
        """
        视频转换（流式进度）

        Args:
            video_path: 视频文件路径
            target_orientation: 目标方向
            strategy: 转换策略
            target_ratio: 目标比例

        Yields:
            {"event": "start", "progress": 0.0, "message": "..."}
            {"event": "progress", "progress": 0.5, "message": "..."}
            {"event": "complete", "progress": 1.0, "message": "...", "data": {...}}
            {"event": "error", "message": "..."}
        """
        import json

        with open(video_path, "rb") as f:
            files = {"file": (Path(video_path).name, f, "video/mp4")}
            data = {
                "target_orientation": target_orientation,
                "strategy": strategy,
                "target_ratio": str(target_ratio),
            }
            resp = self.session.post(
                self._url("/api/transform-stream"),
                files=files,
                data=data,
                stream=True,
            )

        resp.raise_for_status()

        for line in resp.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    def detect_orientation(self, video_path: str) -> dict:
        """检测视频方向"""
        with open(video_path, "rb") as f:
            files = {"file": (Path(video_path).name, f, "video/mp4")}
            resp = self.session.post(self._url("/api/detect-orientation"), files=files)

        resp.raise_for_status()
        return resp.json()

    # ============ 文件管理 ============

    def list_outputs(self) -> dict:
        """列出输出文件"""
        resp = self.session.get(self._url("/api/outputs"))
        resp.raise_for_status()
        return resp.json()

    def download_file(self, filename: str, save_path: str) -> str:
        """
        下载文件

        Args:
            filename: 文件名
            save_path: 保存路径

        Returns:
            保存的文件路径
        """
        resp = self.session.get(self._url(f"/api/download/{filename}"), stream=True)
        resp.raise_for_status()

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        return save_path

    def delete_output(self, filename: str) -> dict:
        """删除输出文件"""
        resp = self.session.delete(self._url(f"/api/outputs/{filename}"))
        resp.raise_for_status()
        return resp.json()

    # ============ Agent 聊天 ============

    def agent_chat(
        self,
        message: str,
        video_path: str,
        session_id: Optional[str] = None,
    ) -> dict:
        """
        Agent 聊天（多轮对话）

        Args:
            message: 自然语言指令，如"把视频转成竖屏"
            video_path: 视频文件路径
            session_id: 会话 ID（用于继续对话）

        Returns:
            {
                "session_id": "abc123",
                "message": "好的，正在处理...",
                "success": True,
                "data": {
                    "output_path": "/path/to/output.mp4",
                    "strategy_used": "pad",
                    ...
                }
            }
        """
        with open(video_path, "rb") as f:
            files = {"file": (Path(video_path).name, f, "video/mp4")}
            data = {"message": message}
            if session_id:
                data["session_id"] = session_id

            resp = self.session.post(
                self._url("/api/agent/chat"),
                files=files,
                data=data,
            )

        resp.raise_for_status()
        return resp.json()

    def agent_continue(self, message: str, session_id: str) -> dict:
        """
        继续 Agent 对话

        Args:
            message: 用户的新消息
            session_id: 会话 ID

        Returns:
            Agent 响应
        """
        resp = self.session.post(
            self._url("/api/agent/continue"),
            json={"message": message, "session_id": session_id},
        )
        resp.raise_for_status()
        return resp.json()

    def get_agent_session(self, session_id: str) -> dict:
        """获取 Agent 会话状态"""
        resp = self.session.get(self._url(f"/api/agent/session/{session_id}"))
        resp.raise_for_status()
        return resp.json()

    def list_agent_sessions(self) -> dict:
        """列出所有 Agent 会话"""
        resp = self.session.get(self._url("/api/agent/sessions"))
        resp.raise_for_status()
        return resp.json()

    def delete_agent_session(self, session_id: str) -> dict:
        """删除 Agent 会话"""
        resp = self.session.delete(self._url(f"/api/agent/session/{session_id}"))
        resp.raise_for_status()
        return resp.json()


# ============ 便捷函数 ============

def chat(
    message: str,
    video_path: str,
    base_url: str = "http://localhost:8000",
) -> dict:
    """
    便捷函数：一句话聊天

    Args:
        message: 自然语言指令
        video_path: 视频文件路径
        base_url: API 地址

    Returns:
        Agent 响应
    """
    client = MediaRefitClient(base_url)
    return client.agent_chat(message, video_path)


def quick_transform(
    video_path: str,
    target_orientation: str = "portrait",
    strategy: str = "pad",
    base_url: str = "http://localhost:8000",
) -> dict:
    """
    便捷函数：快速转换

    Args:
        video_path: 视频文件路径
        target_orientation: 目标方向
        strategy: 转换策略
        base_url: API 地址

    Returns:
        转换结果
    """
    client = MediaRefitClient(base_url)
    return client.transform(video_path, target_orientation, strategy)


# ============ CLI ============

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MediaRefitAgent Client")
    parser.add_argument("--url", default="http://localhost:8000", help="API URL")
    parser.add_argument("command", choices=["health", "capabilities", "transform", "chat"])
    parser.add_argument("video", nargs="?", help="Video file path")
    parser.add_argument("--message", "-m", default="把视频转成竖屏", help="Message for agent")
    parser.add_argument("--orientation", "-o", default="portrait", help="Target orientation")
    parser.add_argument("--strategy", "-s", default="pad", help="Transform strategy")

    args = parser.parse_args()

    client = MediaRefitClient(args.url)

    if args.command == "health":
        print(client.health_check())
    elif args.command == "capabilities":
        print(client.get_capabilities())
    elif args.command == "transform":
        if not args.video:
            parser.error("video file required for transform")
        result = client.transform(args.video, args.orientation, args.strategy)
        print(result)
    elif args.command == "chat":
        if not args.video:
            parser.error("video file required for chat")
        result = client.agent_chat(args.message, args.video)
        print(result)
