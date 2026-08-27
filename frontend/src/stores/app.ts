import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Session, Message, Feature, VideoResult, Strategy, Orientation, CompressionLevel } from '../types';

export const useAppStore = defineStore('app', () => {
  // 状态 - 使用 ref 确保响应式
  const sessions = ref<Session[]>([]);
  const currentSessionId = ref<string | null>(null);
  const currentFeature = ref<Feature | null>(null);  // 初始为 null，快捷标签非必选
  const currentVideoData = ref<VideoResult | null>(null);

  // UI 状态
  const selectedStrategy = ref<Strategy>('pad');
  const selectedOrientation = ref<Orientation>('portrait');
  const selectedCompression = ref<CompressionLevel>('medium');
  const selectedRatio = ref<string>('9:16');
  const selectedTrim = ref({ startTime: 0, endTime: 0 });
  const selectedCondenseStrategy = ref<string>('content_condense');
  const selectedCondenseDuration = ref<number | null>(null);
  const selectedRestorePreset = ref<string>('basic');
  const selectedEditorMode = ref<string>('highlight');
  const selectedEditorDuration = ref<number | null>(null);
  const selectedSubtitleStyle = ref<string>('default');
  const selectedTransitionType = ref<string>('fade');
  const selectedBGMMood = ref<string>('auto');
  const selectedBGMVolume = ref<number>(50);
  const selectedTTSVoice = ref<string>('zh-CN-XiaoxiaoNeural');
  const selectedTTSText = ref<string>('');
  const selectedFilterPreset = ref<string>('none');
  const selectedCoverMode = ref<string>('single');
  const selectedPlatform = ref<string>('douyin');
  const selectedFile = ref<File | null>(null);
  const selectedFiles = ref<File[]>([]);
  const isLoading = ref(false);
  const transformProgress = ref<number | null>(null);  // 0-100，null 表示无进度

  // 计算属性
  const currentSession = computed(() =>
    sessions.value.find(s => s.session_id === currentSessionId.value)
  );

  const currentMessages = computed(() =>
    currentSession.value?.messages || []
  );

  // Actions
  function addMessage(sessionId: string, message: Message) {
    const session = sessions.value.find(s => s.session_id === sessionId);
    if (session) {
      // 触发响应式更新 - 替换整个 sessions 数组
      const index = sessions.value.findIndex(s => s.session_id === sessionId);
      const updatedSession = {
        ...session,
        messages: [...session.messages, message],
      };
      const newSessions = [...sessions.value];
      newSessions[index] = updatedSession;
      sessions.value = newSessions;
    }
  }

  function setCurrentSession(sessionId: string | null) {
    currentSessionId.value = sessionId;
  }

  function setFeature(feature: Feature | null) {
    currentFeature.value = feature;
  }

  function setVideoData(data: VideoResult | null) {
    currentVideoData.value = data;
  }

  function setStrategy(strategy: Strategy) {
    selectedStrategy.value = strategy;
  }

  function setOrientation(orientation: Orientation) {
    selectedOrientation.value = orientation;
  }

  function setCompression(level: CompressionLevel) {
    selectedCompression.value = level;
  }

  function setSelectedRatio(ratio: string) {
    selectedRatio.value = ratio;
  }

  function setTrim(startTime: number, endTime: number) {
    selectedTrim.value = { startTime, endTime };
  }

  function setCondenseStrategy(strategy: string) {
    selectedCondenseStrategy.value = strategy;
  }

  function setCondenseDuration(duration: number | null) {
    selectedCondenseDuration.value = duration;
  }

  function setRestorePreset(preset: string) {
    selectedRestorePreset.value = preset;
  }

  function setEditorMode(mode: string) {
    selectedEditorMode.value = mode;
  }

  function setEditorDuration(duration: number | null) {
    selectedEditorDuration.value = duration;
  }

  function setSubtitleStyle(style: string) {
    selectedSubtitleStyle.value = style;
  }

  function setTransitionType(type: string) {
    selectedTransitionType.value = type;
  }

  function setBGMMood(mood: string) {
    selectedBGMMood.value = mood;
  }

  function setBGMVolume(volume: number) {
    selectedBGMVolume.value = volume;
  }

  function setTTSVoice(voice: string) {
    selectedTTSVoice.value = voice;
  }

  function setTTSText(text: string) {
    selectedTTSText.value = text;
  }

  function setFilterPreset(preset: string) {
    selectedFilterPreset.value = preset;
  }

  function setCoverMode(mode: string) {
    selectedCoverMode.value = mode;
  }

  function setPlatform(platform: string) {
    selectedPlatform.value = platform;
  }

  function setSelectedFile(file: File | null) {
    selectedFile.value = file;
  }

  function setSelectedFiles(files: File[]) {
    selectedFiles.value = files;
  }

  function setLoading(loading: boolean) {
    isLoading.value = loading;
  }

  function setTransformProgress(percent: number | null) {
    transformProgress.value = percent;
  }

  function addSession(session: Session) {
    sessions.value = [session, ...sessions.value];
  }

  function updateSession(sessionId: string, updates: Partial<Session>) {
    const index = sessions.value.findIndex(s => s.session_id === sessionId);
    if (index !== -1) {
      const updatedSession = { ...sessions.value[index], ...updates };
      const newSessions = [...sessions.value];
      newSessions[index] = updatedSession;
      sessions.value = newSessions;
    }
  }

  function removeSession(sessionId: string) {
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId);
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null;
    }
  }

  // 流式消息支持 - 直接修改对象触发响应式
  function updateStreamingMessage(sessionId: string, messageId: string, content: string) {
    const session = sessions.value.find(s => s.session_id === sessionId);
    if (session) {
      const index = session.messages.findIndex((m: Message) => m.id === messageId);
      if (index !== -1) {
        // 直接修改 message 对象的 content 属性
        session.messages[index].content = content;
        // Vue 会自动检测到变化
      }
    }
  }

  function finishStreamingMessage(sessionId: string, messageId: string, content: string) {
    const session = sessions.value.find(s => s.session_id === sessionId);
    if (session) {
      const index = session.messages.findIndex((m: Message) => m.id === messageId);
      if (index !== -1) {
        session.messages[index].content = content;
        session.messages[index].streaming = false;
      }
    }
  }

  // 格式化选中参数用于发送给 Agent
  function formatSelectedParams(): string {
    const parts: string[] = [];

    // 功能类型
    if (currentFeature.value) {
      const featureMap: Record<string, string> = {
        'orient': '横竖屏转换',
        'compress': '视频压缩',
        'trim': '视频修剪',
        'concat': '视频拼接',
        'condense': '智能缩编',
        'restore': '老视频修复',
        'editor': '智能剪辑',
        'info': '视频信息获取',
      };
      const featureLabel = featureMap[currentFeature.value];
      if (featureLabel) {
        parts.push(`功能=${featureLabel}`);
      }

      // 横竖屏转换的参数
      if (currentFeature.value === 'orient') {
        if (selectedOrientation.value) {
          const ratioText = selectedRatio.value || '';
          parts.push(`目标方向=${selectedOrientation.value === 'portrait' ? '竖屏' : '横屏'} ${ratioText}`);
        }
        if (selectedStrategy.value) {
          const strategyMap: Record<string, string> = {
            'pad': '填充黑边',
            'crop': '中心裁剪',
            'smart_crop': '智能裁剪',
            'stretch': '拉伸填充',
            'mirror_scroll': '镜像滚动',
            'pan_scroll': '平移运镜',
          };
          const strategyLabel = strategyMap[selectedStrategy.value];
          if (strategyLabel) {
            parts.push(`转换策略=${strategyLabel}`);
          }
        }
      }

      // 视频压缩的参数
      if (currentFeature.value === 'compress' && selectedCompression.value) {
        const levelMap: Record<string, string> = {
          'low': '低',
          'medium': '中',
          'high': '高',
        };
        const levelLabel = levelMap[selectedCompression.value];
        if (levelLabel) {
          parts.push(`压缩级别=${levelLabel}`);
        }
      }

      // 视频修剪的参数
      if (currentFeature.value === 'trim' && selectedTrim.value.endTime > selectedTrim.value.startTime) {
        parts.push(`修剪开始时间=${selectedTrim.value.startTime}秒`);
        parts.push(`修剪结束时间=${selectedTrim.value.endTime}秒`);
      }

      // 智能缩编的参数
      if (currentFeature.value === 'condense') {
        const strategyMap: Record<string, string> = {
          'content_condense': '内容缩编',
          'smart_compress': '智能压缩',
        };
        const strategyLabel = strategyMap[selectedCondenseStrategy.value];
        if (strategyLabel) {
          parts.push(`缩编策略=${strategyLabel}`);
        }
        if (selectedCondenseDuration.value !== null && selectedCondenseDuration.value > 0) {
          parts.push(`目标时长=${selectedCondenseDuration.value}秒`);
        }
      }

      // 老视频修复的参数
      if (currentFeature.value === 'restore') {
        const presetMap: Record<string, string> = {
          'basic': '基础修复',
          'film': '胶片修复',
          'enhanced': '增强版',
        };
        const presetLabel = presetMap[selectedRestorePreset.value];
        if (presetLabel) {
          parts.push(`修复套餐=${presetLabel}`);
        }
      }

      // 智能剪辑的参数（只包含当前模式相关的参数）
      if (currentFeature.value === 'editor') {
        const modeMap: Record<string, string> = {
          'highlight': '精彩片段',
          'subtitle': '自动字幕',
          'transition': '添加转场',
          'bgm': '智能配乐',
          'tts': '配音',
          'filter': '滤镜',
          'analyze': '内容分析',
          'cover': '封面生成',
          'title-package': '片头片尾',
        };
        const modeLabel = modeMap[selectedEditorMode.value];
        if (modeLabel) {
          parts.push(`编辑器模式=${modeLabel}`);
        }
        // 仅 highlight 模式包含目标时长
        if (selectedEditorMode.value === 'highlight' && selectedEditorDuration.value !== null && selectedEditorDuration.value > 0) {
          parts.push(`目标时长=${selectedEditorDuration.value}秒`);
        }
        // 仅 highlight/subtitle 模式包含字幕样式
        if ((selectedEditorMode.value === 'highlight' || selectedEditorMode.value === 'subtitle') && selectedSubtitleStyle.value) {
          const styleMap: Record<string, string> = { 'default': '默认', 'minimal': '简洁' };
          parts.push(`字幕样式=${styleMap[selectedSubtitleStyle.value] || selectedSubtitleStyle.value}`);
        }
        // 仅 highlight/transition 模式包含转场类型
        if ((selectedEditorMode.value === 'highlight' || selectedEditorMode.value === 'transition') && selectedTransitionType.value) {
          const transMap: Record<string, string> = { 'fade': '淡入淡出', 'slide': '滑动', 'zoom': '缩放' };
          parts.push(`转场类型=${transMap[selectedTransitionType.value] || selectedTransitionType.value}`);
        }
        // 仅 bgm 模式包含音乐风格
        if (selectedEditorMode.value === 'bgm' && selectedBGMMood.value) {
          const moodMap: Record<string, string> = { 'auto': '自动', 'happy': '欢快', 'calm': '平静', 'energetic': '动感' };
          parts.push(`音乐风格=${moodMap[selectedBGMMood.value] || selectedBGMMood.value}`);
        }
        // 仅 filter 模式包含滤镜预设
        if (selectedEditorMode.value === 'filter' && selectedFilterPreset.value && selectedFilterPreset.value !== 'none') {
          parts.push(`滤镜预设=${selectedFilterPreset.value}`);
        }
        // 仅 tts 模式包含配音音色和文本
        if (selectedEditorMode.value === 'tts') {
          const voiceMap: Record<string, string> = {
            'zh-CN-XiaoxiaoNeural': '晓晓（女声）',
            'zh-CN-XiaoyiNeural': '小艺（女声）',
            'zh-CN-YunxiNeural': '云希（男声）',
            'zh-CN-YunyangNeural': '云扬（男声）',
            'zh-CN-liaoning': '辽宁（男声）',
            'zh-CN-shaanxi': '陕西（男声）',
          };
          if (selectedTTSVoice.value) {
            parts.push(`配音音色=${voiceMap[selectedTTSVoice.value] || selectedTTSVoice.value}`);
          }
          if (selectedTTSText.value) {
            const textPreview = selectedTTSText.value.length > 20
              ? selectedTTSText.value.substring(0, 20) + '...'
              : selectedTTSText.value;
            parts.push(`配音文本=${textPreview}`);
          }
        }
      }
    }

    if (parts.length === 0) {
      return '';
    }

    return `[用户已选择参数：${parts.join('，')}]`;
  }

  return {
    // 状态
    sessions,
    currentSessionId,
    currentFeature,
    currentVideoData,
    selectedStrategy,
    selectedOrientation,
    selectedCompression,
    selectedRatio,
    selectedTrim,
    selectedCondenseStrategy,
    selectedCondenseDuration,
    selectedRestorePreset,
    selectedEditorMode,
    selectedEditorDuration,
    selectedSubtitleStyle,
    selectedTransitionType,
    selectedBGMMood,
    selectedBGMVolume,
    selectedTTSVoice,
    selectedTTSText,
    selectedFilterPreset,
    selectedCoverMode,
    selectedPlatform,
    selectedFile,
    selectedFiles,
    isLoading,
    transformProgress,
    // 计算属性
    currentSession,
    currentMessages,
    // Actions
    addMessage,
    setCurrentSession,
    setFeature,
    setVideoData,
    setStrategy,
    setOrientation,
    setCompression,
    setSelectedRatio,
    setTrim,
    setCondenseStrategy,
    setCondenseDuration,
    setRestorePreset,
    setEditorMode,
    setEditorDuration,
    setSubtitleStyle,
    setTransitionType,
    setBGMMood,
    setBGMVolume,
    setTTSVoice,
    setTTSText,
    setFilterPreset,
    setCoverMode,
    setPlatform,
    setSelectedFile,
    setSelectedFiles,
    setLoading,
    setTransformProgress,
    addSession,
    updateSession,
    removeSession,
    formatSelectedParams,
    updateStreamingMessage,
    finishStreamingMessage,
  };
});
