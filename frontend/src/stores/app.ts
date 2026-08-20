import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Session, Message, Feature, VideoResult, Strategy, Orientation, CompressionLevel } from '../types';

export const useAppStore = defineStore('app', () => {
  // 状态 - 使用 ref 确保响应式
  const sessions = ref<Session[]>([]);
  const currentSessionId = ref<string | null>(null);
  const currentFeature = ref<Feature>('orient');
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

  function setFeature(feature: Feature) {
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

  // 格式化选中参数用于发送给 Agent
  function formatSelectedParams(): string {
    const parts: string[] = [];
    const feature = currentFeature.value;

    // 功能类型
    const featureMap: Record<Feature, string> = {
      orient: '横竖屏转换',
      compress: '视频压缩',
      trim: '视频修剪',
      concat: '视频拼接',
      condense: '智能缩编',
      restore: '老视频修复',
      editor: '智能剪辑',
      info: '视频信息获取',
    };
    parts.push(`功能=${featureMap[feature] || feature}`);

    if (feature === 'orient' && selectedOrientation.value) {
      const orientText = selectedOrientation.value === 'portrait' ? '竖屏' : '横屏';
      parts.push(`目标方向=${orientText} ${selectedRatio.value}`);
    }

    if (feature === 'orient' && selectedStrategy.value) {
      const strategyMap: Record<Strategy, string> = {
        pad: '填充黑边',
        crop: '中心裁剪',
        smart_crop: '智能裁剪',
        stretch: '拉伸填充',
        mirror_scroll: '镜像滚动',
        pan_scroll: '平移运镜',
      };
      parts.push(`转换策略=${strategyMap[selectedStrategy.value]}`);
    }

    if (feature === 'compress' && selectedCompression.value) {
      const levelMap: Record<CompressionLevel, string> = {
        low: '低',
        medium: '中',
        high: '高',
      };
      parts.push(`压缩级别=${levelMap[selectedCompression.value]}`);
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
  };
});
