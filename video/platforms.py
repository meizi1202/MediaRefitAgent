"""
平台配置公共模块

定义各视频平台的推荐参数，供智能剪辑、横竖屏转换等功能共用
"""

from typing import Optional

# 平台配置
PLATFORM_SETTINGS = {
    "douyin": {
        "name": "抖音",
        "aspect_ratios": [(9, 16), (3, 4), (16, 9), (1, 1)],
        "max_duration": 180,
        "max_file_size": 4 * 1024 * 1024 * 1024,
        "recommended_resolution": (1080, 1920),
        "bitrate": 8000000,
        "fps": 30,
    },
    "kuaishou": {
        "name": "快手",
        "aspect_ratios": [(9, 16), (16, 9), (1, 1)],
        "max_duration": 300,
        "max_file_size": 4 * 1024 * 1024 * 1024,
        "recommended_resolution": (1080, 1920),
        "bitrate": 6000000,
        "fps": 30,
    },
    "bilibili": {
        "name": "B站",
        "aspect_ratios": [(16, 9), (9, 16), (1, 1)],
        "max_duration": 600,
        "max_file_size": 4 * 1024 * 1024 * 1024,
        "recommended_resolution": (1920, 1080),
        "bitrate": 6000000,
        "fps": 30,
    },
    "xiaohongshu": {
        "name": "小红书",
        "aspect_ratios": [(3, 4), (1, 1), (9, 16)],
        "max_duration": 300,
        "max_file_size": 2 * 1024 * 1024 * 1024,
        "recommended_resolution": (1080, 1440),
        "bitrate": 5000000,
        "fps": 30,
    },
    "weixinshipin": {
        "name": "微信视频号",
        "aspect_ratios": [(16, 9), (9, 16), (1, 1)],
        "max_duration": 600,
        "max_file_size": 2 * 1024 * 1024 * 1024,
        "recommended_resolution": (1080, 1920),
        "bitrate": 5000000,
        "fps": 30,
    },
}


def get_platform_settings(platform: str) -> Optional[dict]:
    """获取平台配置"""
    return PLATFORM_SETTINGS.get(platform)


def get_recommended_resolution(platform: str, orientation: str = "portrait") -> Optional[tuple]:
    """获取平台推荐分辨率

    Args:
        platform: 平台名称
        orientation: portrait/landscape

    Returns:
        (width, height) 或 None
    """
    settings = PLATFORM_SETTINGS.get(platform)
    if not settings:
        return None

    res = settings.get("recommended_resolution")
    if not res:
        return None

    width, height = res
    # 根据方向调整
    if orientation == "landscape" and height > width:
        return (height, width)
    return res


def get_aspect_ratio(platform: str, orientation: str = "portrait") -> Optional[float]:
    """获取平台推荐比例

    Args:
        platform: 平台名称
        orientation: portrait/landscape

    Returns:
        比例值 (如 9/16) 或 None
    """
    settings = PLATFORM_SETTINGS.get(platform)
    if not settings:
        return None

    ratios = settings.get("aspect_ratios", [])
    if not ratios:
        return None

    # 根据方向选择比例
    if orientation == "portrait":
        # 选择竖屏比例（宽 < 高）
        for r in ratios:
            if r[0] < r[1]:
                return r[0] / r[1]
    else:
        # 选择横屏比例（宽 > 高）
        for r in ratios:
            if r[0] > r[1]:
                return r[0] / r[1]

    # 没有对应方向，返回第一个
    return ratios[0][0] / ratios[0][1]


def get_platform_name(platform: str) -> str:
    """获取平台中文名"""
    settings = PLATFORM_SETTINGS.get(platform, {})
    return settings.get("name", platform)
