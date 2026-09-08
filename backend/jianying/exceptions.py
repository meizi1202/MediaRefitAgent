"""
剪映对接异常类
"""


class JianyingError(Exception):
    """剪映对接基础异常"""
    pass


class DraftCreateError(JianyingError):
    """草稿创建失败"""
    pass


class DraftNotFoundError(JianyingError):
    """草稿不存在"""
    pass


class DraftSaveError(JianyingError):
    """草稿保存失败"""
    pass


class VideoAddError(JianyingError):
    """视频添加失败"""
    pass


class AudioAddError(JianyingError):
    """音频添加失败"""
    pass


class CaptionAddError(JianyingError):
    """字幕添加失败"""
    pass


class EffectAddError(JianyingError):
    """特效添加失败"""
    pass


class FilterAddError(JianyingError):
    """滤镜添加失败"""
    pass
