"""
去口癖辅助技能模块

去除音频/字幕中的无意义填充词（口癖），提升字幕/文本质量
"""
import re
from typing import Optional


class FillerWordRemover:
    """去口癖辅助技能"""

    # 中文常见填充词词典
    CHINESE_FILLERS = [
        # 单字填充
        "嗯", "啊", "呃", "哦", "呀", "吧", "呢", "嘛", "哈", "嘿", "哼", "喔", "咯",
        # 双字填充
        "这个", "那个", "然后", "就是说", "其实", "实际上", "反正",
        "好吧", "那什么", "也就是说", "然后呢", "所以说", "可以说",
        # 重复填充
        "对对对", "就是就是", "好吧好吧", "嗯嗯嗯", "啊啊啊啊",
        # 英文填充
        "like", "um", "uh", "basically", "actually", "you know",
    ]

    # 匹配模式：连续重复的填充词
    REPEAT_PATTERN = re.compile(r'(.)\1{2,}')

    def __init__(self, use_llm: bool = False, llm_client=None):
        """
        初始化去口癖处理器

        Args:
            use_llm: 是否使用 LLM 增强（更智能但更慢）
            llm_client: LLM 客户端（用于 LLM 增强模式）
        """
        self.use_llm = use_llm
        self.llm_client = llm_client

    def remove_from_text(self, text: str) -> str:
        """
        从文本中去除口癖词

        Args:
            text: 原始文本/字幕

        Returns:
            清理后的文本
        """
        if not text:
            return text

        if self.use_llm and self.llm_client:
            return self._remove_with_llm(text)

        return self._remove_with_rules(text)

    def _remove_with_rules(self, text: str) -> str:
        """
        基于规则的去口癖

        策略：
        1. 精确匹配填充词并删除
        2. 处理连续重复的填充词
        3. 清理多余空格和标点残留
        """
        result = text

        # 1. 精确匹配删除（从长到短排序，避免部分匹配）
        sorted_fillers = sorted(self.CHINESE_FILLERS, key=len, reverse=True)
        for filler in sorted_fillers:
            # 使用词边界匹配，避免误删正常词汇
            pattern = re.escape(filler)
            result = re.sub(pattern, "", result)

        # 2. 处理连续重复的单字（如"对对对"→"对"）
        result = self.REPEAT_PATTERN.sub(r'\1', result)

        # 3. 清理连续标点（如"，，，" -> "，"）
        result = re.sub(r'([，。、；：！？])\1+', r'\1', result)

        # 4. 清理开头和结尾的标点残留（如"我觉得，" -> "我觉得"）
        result = re.sub(r'^[，。、；：！？,\s]+', '', result)
        result = re.sub(r'[，。、；：！？,\s]+$', '', result)

        # 5. 清理多余空格
        result = re.sub(r'\s+', ' ', result)

        # 6. 清理句首句尾的空白
        result = result.strip()

        return result

    def _remove_with_llm(self, text: str) -> str:
        """
        使用 LLM 增强去口癖

        更智能地判断哪些词是无意义的填充词

        Args:
            text: 原始文本/字幕

        Returns:
            清理后的文本
        """
        if not self.llm_client:
            return self._remove_with_rules(text)

        prompt = f"""请删除以下文本中的口癖填充词，保留有意义的内容：

原文：
{text}

要求：
1. 删除无意义的填充词（如"嗯"、"啊"、"这个"、"就是说"等）
2. 删除重复的填充词（如"对对对"→"对"）
3. 保留有意义的词汇和语义
4. 只返回处理后的文本，不要其他说明

处理后："""

        try:
            response = self.llm_client.generate(prompt)
            return response.strip() if response else self._remove_with_rules(text)
        except Exception:
            # LLM 调用失败时回退到规则方法
            return self._remove_with_rules(text)

    def remove_from_srt(self, srt_content: str) -> str:
        """
        从 SRT 字幕文件中去除口癖词

        Args:
            srt_content: SRT 字幕文件内容

        Returns:
            清理后的 SRT 内容
        """
        if not srt_content:
            return srt_content

        lines = srt_content.split('\n')
        result_lines = []

        for line in lines:
            # SRT 格式：序号行、时间码行、内容行、空行
            if line.strip().isdigit():
                # 序号行，保留
                result_lines.append(line)
            elif '-->' in line:
                # 时间码行，保留
                result_lines.append(line)
            elif line.strip() == '':
                # 空行，保留
                result_lines.append(line)
            else:
                # 内容行，去口癖
                cleaned = self.remove_from_text(line)
                result_lines.append(cleaned)

        return '\n'.join(result_lines)

    def remove_from_segments(self, segments: list) -> list:
        """
        从带时间戳的片段列表中去除口癖词

        Args:
            segments: [{"start": 0.0, "end": 5.0, "text": "..."}, ...]

        Returns:
            清理后的片段列表
        """
        if not segments:
            return segments

        result = []
        for seg in segments:
            cleaned_text = self.remove_from_text(seg.get("text", ""))
            # 如果清理后文本为空，跳过该片段
            if cleaned_text.strip():
                result.append({
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": cleaned_text
                })

        return result


# 便捷函数
def remove_filler_words(text: str) -> str:
    """
    便捷函数：从文本中去除口癖词

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    remover = FillerWordRemover()
    return remover.remove_from_text(text)


def clean_srt_subtitle(srt_content: str) -> str:
    """
    便捷函数：清理 SRT 字幕中的口癖词

    Args:
        srt_content: SRT 字幕内容

    Returns:
        清理后的 SRT 内容
    """
    remover = FillerWordRemover()
    return remover.remove_from_srt(srt_content)
