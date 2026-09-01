"""
公众号平台知识库 - 存储各平台视频比例和缺省时长要求
"""

from typing import Optional

# 公众号平台知识库（不含已在 platforms.py 中定义的技术参数）
PLATFORM_GUIDE = {
    "抖音": {
        "ratio": "9:16",
        "duration": "15-60秒",
        "alias": ["抖音极速", "douyin"],
    },
    "快手": {
        "ratio": "9:16",
        "duration": "30-90秒",
        "alias": ["kuaishou"],
    },
    "视频号": {
        "ratio": "9:16 或 1:1",
        "duration": "60秒优先",
        "alias": ["央视频视频号", "weixinshipin"],
    },
    "B站": {
        "ratio": "16:9",
        "duration": "2-6分钟",
        "alias": ["bilibili", "央视频B站"],
    },
    "小红书": {
        "ratio": "3:4",
        "duration": "15-30秒",
        "alias": ["xiaohongshu"],
    },
    "微博视频": {
        "ratio": "16:9",
        "duration": "30-90秒",
        "alias": ["头条号"],
    },
    "央视频": {
        "ratio": "16:9",
        "duration": "全长版本",
        "alias": ["CCTV"],
    },
    "央视自有端": {
        "ratio": "16:9",
        "duration": "全长版本",
    },
}


def match_platform(user_input: str) -> Optional[str]:
    """从用户输入中匹配平台名称，返回标准平台名（含别名匹配）"""
    for platform, info in PLATFORM_GUIDE.items():
        if platform in user_input:
            return platform
        for alias in info.get("alias", []):
            if alias in user_input:
                return platform
    return None


def get_platform_guide(platform: str) -> Optional[dict]:
    """查询平台指南信息"""
    return PLATFORM_GUIDE.get(platform)


def format_platform_suggestion(platform: str) -> str:
    """生成符合平台要求的建议文本，用于对话提示"""
    info = get_platform_guide(platform)
    if not info:
        return ""
    return f"{platform}推荐{info['ratio']}，时长{info['duration']}效果最佳"
