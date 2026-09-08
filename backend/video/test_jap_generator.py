"""
剪映草稿 JSON 生成器测试

测试字幕处理流程（方案 E）
"""
import json
from video.jap_generator import (
    SubtitleStyle,
    SubtitleClip,
    JianYingDraft,
    generate_subtitle_track_from_asr,
    create_jianying_draft,
    export_draft_to_json,
    parse_jianying_style_from_json,
    load_jap_file,
)


def test_generate_subtitle_style():
    """测试字幕样式"""
    style = SubtitleStyle(
        font="STHeitiMedium",
        font_size=36,
        color="#FFFFFF",
        background="#00000080"
    )

    jap_style = style.to_jap_style()
    print("✅ 字幕样式生成成功")
    print(f"   样式: {jap_style}")


def test_generate_subtitle_clips():
    """测试从 ASR 结果生成字幕片段"""
    # 模拟 Whisper ASR 结果
    asr_segments = [
        {"start": 0.0, "end": 5.0, "text": "今天我要分享的是关于数字经济的重要观点。"},
        {"start": 5.0, "end": 10.0, "text": "首先，我们来了解一下当前的行业发展趋势。"},
        {"start": 10.0, "end": 15.0, "text": "专家认为，数字化转型是企业发展的必由之路。"},
    ]

    style = SubtitleStyle(font="STHeitiMedium", font_size=36)

    clips = generate_subtitle_track_from_asr(asr_segments, style)

    print(f"✅ 生成了 {len(clips)} 个字幕片段")
    for clip in clips:
        print(f"   [{clip.start_time_ms/1000:.1f}s - {clip.end_time_ms/1000:.1f}s] {clip.content[:20]}...")


def test_create_jianying_draft():
    """测试创建剪映草稿"""
    # 模拟 Whisper ASR 结果
    asr_segments = [
        {"start": 0.0, "end": 5.0, "text": "今天我要分享的是关于数字经济的重要观点。"},
        {"start": 5.0, "end": 10.0, "text": "首先，我们来了解一下当前的行业发展趋势。"},
    ]

    style = SubtitleStyle(
        font="STHeitiMedium",
        font_size=36,
        color="#FFFFFF",
        background="#00000080"
    )

    draft = create_jianying_draft(
        asr_segments=asr_segments,
        project_name="论坛高光集锦",
        style=style,
        aspect_ratio="9:16",
        resolution=(1080, 1920)
    )

    # 生成 JSON
    jap_dict = draft.to_jap_dict()

    print(f"✅ 剪映草稿创建成功")
    print(f"   项目名称: {jap_dict['name']}")
    print(f"   总时长: {jap_dict['duration']}ms")
    print(f"   画幅: {jap_dict['aspect_ratio']}")
    print(f"   轨道数: {len(jap_dict['tracks'])}")
    print(f"   字幕片段数: {len(jap_dict['tracks'][0]['clips'])}")

    return draft, jap_dict


def test_export_json():
    """测试导出 JSON 文件"""
    asr_segments = [
        {"start": 0.0, "end": 5.0, "text": "测试字幕内容"},
    ]

    draft = create_jianying_draft(asr_segments, "测试项目")
    output_path = "test_output.json"

    export_draft_to_json(draft, output_path)

    # 验证文件
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"✅ JSON 导出成功: {output_path}")
    print(f"   文件内容预览: {json.dumps(data, indent=2, ensure_ascii=False)[:200]}...")

    # 清理
    import os
    os.remove(output_path)


def test_parse_style_from_json():
    """测试从剪映 JSON 解析字幕样式"""
    # 模拟剪映导出的 JSON 结构
    mock_jap = {
        "tracks": [
            {
                "type": "text",
                "clips": [
                    {
                        "id": "subtitle_001",
                        "start_time": 0,
                        "end_time": 5000,
                        "content": "测试文字",
                        "style": {
                            "font": "STHeitiMedium",
                            "font_size": 36,
                            "color": "#FFFFFF",
                            "background": "#00000080",
                            "stroke_color": "#000000",
                            "stroke_width": 1.0,
                            "bold": False,
                            "italic": False
                        }
                    }
                ]
            }
        ]
    }

    style = parse_jianying_style_from_json(mock_jap)

    print(f"✅ 样式解析成功")
    print(f"   字体: {style.font}")
    print(f"   字号: {style.font_size}")
    print(f"   颜色: {style.color}")


def test_full_workflow():
    """完整工作流测试"""
    print("\n" + "="*50)
    print("完整工作流测试")
    print("="*50 + "\n")

    # Step 1: 模拟 Whisper ASR 结果
    print("Step 1: 模拟 Whisper ASR 识别结果...")
    asr_segments = [
        {"start": 0.0, "end": 4.5, "text": "今天我们邀请到三位数字经济领域的专家。"},
        {"start": 4.5, "end": 9.0, "text": "首先有请第一位嘉宾分享他的观点。"},
        {"start": 9.0, "end": 14.5, "text": "我认为数字化转型是企业发展必由之路。"},
        {"start": 14.5, "end": 19.0, "text": "未来三年将迎来行业发展的黄金期。"},
    ]
    print(f"   识别到 {len(asr_segments)} 个片段\n")

    # Step 2: 定义字幕样式
    print("Step 2: 定义字幕样式...")
    style = SubtitleStyle(
        font="STHeitiMedium",
        font_size=36,
        color="#FFFFFF",
        background="#00000080"
    )
    print(f"   字体: {style.font}, 字号: {style.font_size}\n")

    # Step 3: 创建剪映草稿
    print("Step 3: 创建剪映草稿...")
    draft = create_jianying_draft(
        asr_segments=asr_segments,
        project_name="数字经济专家论坛",
        style=style,
        aspect_ratio="9:16",
        resolution=(1080, 1920)
    )
    print(f"   项目: {draft.name}")
    print(f"   总时长: {draft.duration_ms}ms")
    print(f"   字幕片段: {len(draft.subtitle_clips)} 个\n")

    # Step 4: 导出 JSON
    print("Step 4: 导出为 JSON 文件...")
    output_path = "test_forum_subtitles.json"
    export_draft_to_json(draft, output_path)
    print(f"   已导出: {output_path}\n")

    # Step 5: 验证内容
    print("Step 5: 验证生成的 JSON...")
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"   ✓ project_id: {data['project_id']}")
    print(f"   ✓ name: {data['name']}")
    print(f"   ✓ aspect_ratio: {data['aspect_ratio']}")
    print(f"   ✓ tracks: {len(data['tracks'])} 个轨道")
    print(f"   ✓ 字幕片段: {len(data['tracks'][0]['clips'])} 个")

    # 清理
    import os
    os.remove(output_path)

    print("\n✅ 完整工作流测试通过!")


if __name__ == "__main__":
    print("="*50)
    print("剪映草稿 JSON 生成器测试")
    print("="*50 + "\n")

    test_generate_subtitle_style()
    print()

    test_generate_subtitle_clips()
    print()

    test_create_jianying_draft()
    print()

    test_export_json()
    print()

    test_parse_style_from_json()
    print()

    test_full_workflow()
