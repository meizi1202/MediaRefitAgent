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
  const selectedFile = ref<File | null>(null);
  const selectedFiles = ref<File[]>([]);
  const isLoading = ref(false);

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

  function setSelectedFile(file: File | null) {
    selectedFile.value = file;
  }

  function setSelectedFiles(files: File[]) {
    selectedFiles.value = files;
  }

  function setLoading(loading: boolean) {
    isLoading.value = loading;
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
    selectedFile,
    selectedFiles,
    isLoading,
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
    setSelectedFile,
    setSelectedFiles,
    setLoading,
    addSession,
    updateSession,
    removeSession,
    formatSelectedParams,
    updateStreamingMessage,
    finishStreamingMessage,
  };
});
