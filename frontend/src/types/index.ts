// 会话相关
export interface Session {
  session_id: string;
  name?: string;
  messages: Message[];
  created?: string;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  data?: VideoResult;
}

// 视频结果
export interface VideoResult {
  output_path?: string;
  download_url?: string;
  width?: number;
  height?: number;
  duration?: number;
  success?: boolean;
  error?: string;
  original_size?: number;
  compressed_size?: number;
  compression_ratio?: number;
  original_orientation?: string;
  target_orientation?: string;
  strategy_used?: string;
  [key: string]: any;
}

// 功能类型
export type Feature = 'orient' | 'compress' | 'trim' | 'concat' | 'condense' | 'restore' | 'editor' | 'info';

// 转换策略
export type Strategy = 'pad' | 'crop' | 'smart_crop' | 'stretch' | 'mirror_scroll' | 'pan_scroll';

// 方向
export type Orientation = 'portrait' | 'landscape';

// 压缩级别
export type CompressionLevel = 'low' | 'medium' | 'high';

// 功能标签映射
export const FEATURE_LABELS: Record<Feature, string> = {
  orient: '横竖屏转换',
  compress: '视频压缩',
  trim: '视频修剪',
  concat: '视频拼接',
  condense: '智能缩编',
  restore: '老视频修复',
  editor: '智能剪辑',
  info: '视频信息获取',
};

// 策略标签映射
export const STRATEGY_LABELS: Record<Strategy, string> = {
  pad: '填充黑边',
  crop: '中心裁剪',
  smart_crop: '智能裁剪',
  stretch: '拉伸填充',
  mirror_scroll: '镜像滚动',
  pan_scroll: '平移运镜',
};

// 方向标签映射
export const ORIENTATION_LABELS: Record<Orientation, string> = {
  portrait: '竖屏',
  landscape: '横屏',
};
