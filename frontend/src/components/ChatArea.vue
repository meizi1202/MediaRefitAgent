<template>
  <div class="messages" ref="messagesRef">
    <div v-if="groupedMessages.length === 0" class="empty-state">
      <div class="icon">💬</div>
      <p>开始一段新的对话</p>
    </div>
    <template v-else>
      <div
        v-for="(group, index) in groupedMessages"
        :key="index"
        class="message-group"
        :class="group.role"
      >
        <div class="message-avatar">{{ group.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="message-content">
          <div
            v-for="(item, subIndex) in group.items"
            :key="subIndex"
            class="message-bubble"
            :class="{ 'streaming': item.streaming, 'has-next': subIndex < group.items.length - 1 }"
            v-html="formatContent(item.content)"
          ></div>
          <div class="message-time">{{ formatTime(group.timestamp) }}</div>
          <!-- 预览（视频或图片）- 紧跟在助手消息下方 -->
          <div v-if="group.role === 'assistant' && group.previewPaths?.length" class="preview-list">
            <div v-for="(path, idx) in group.previewPaths" :key="idx" class="preview-item">
              <!-- 图片预览 -->
              <img v-if="isImage(path)" :src="getPreviewUrl(path)" class="preview-image" />
              <!-- 视频预览 -->
              <video v-else :src="getPreviewUrl(path)" controls class="preview-video"></video>
              <div class="preview-info">
                <a :href="getPreviewUrl(path)" target="_blank" class="download-link">⬇️ 下载</a>
              </div>
            </div>
          </div>
          <!-- 流式加载指示器 - 紧跟在助手消息下方 -->
          <div v-if="group.role === 'assistant' && group.items.some(item => item.streaming === true)" class="streaming-indicator" :data-tp="transformProgress" :data-items="group.items.map(i => i.streaming).join(',')" :data-cond="group.role === 'assistant' && group.items.some(item => item.streaming === true)">
            <!-- 有进度时（1-99%）展示进度条 -->
            <template v-if="Number(transformProgress) > 0 && Number(transformProgress) < 100">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: String(Number(transformProgress)) + '%' }" :data-w="String(Number(transformProgress)) + '%'"></div>
              </div>
              <span class="progress-text">{{ transformProgress }}%</span>
            </template>
            <!-- 无进度或100%时展示跳动点 -->
            <template v-else>
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, watch, ref } from 'vue';
import { useAppStore } from '../stores/app';
import { api } from '../api';

const store = useAppStore();
const messagesRef = ref<HTMLElement | null>(null);

const messages = computed(() => store.currentMessages);
const transformProgress = computed(() => store.transformProgress);

// 调试：监听 streaming 状态
watch(messages, (newMsgs) => {
  console.log('[DEBUG ChatArea] messages changed, count:', newMsgs.length);
  newMsgs.forEach((m: any, i) => {
    console.log(`[DEBUG ChatArea] msg[${i}] role=${m.role} streaming=${m.streaming}`);
  });
}, { deep: true });

// 调试：监听 transformProgress 变化
watch(transformProgress, (newVal, oldVal) => {
  console.log('[DEBUG ChatArea] transformProgress changed:', oldVal, '->', newVal);
});

// 计算预览视频 URL
function getPreviewUrl(path: string): string {
  if (!path) return '';
  const filename = path.split(/[/\\]/).pop() || '';
  return api.getDownloadUrl(filename);
}

// 判断是否为图片
function isImage(path: string): boolean {
  if (!path) return false;
  const ext = path.split('.').pop()?.toLowerCase() || '';
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext);
}

// 检查是否有正在流式传输的消息
const hasStreamingMessage = computed(() =>
  messages.value.some(msg => (msg as any).streaming)
);

// 简化：所有助手消息合并为一个带内容的列表，用户消息独立
const groupedMessages = computed(() => {
  const valid = messages.value.filter(msg => msg && typeof msg.content === 'string');
  const groups: Array<{
    role: string;
    items: Array<{ content: string; streaming?: boolean }>;
    timestamp: string;
    previewPaths?: string[];
  }> = [];

  for (const msg of valid) {
    const streaming = (msg as any).streaming;

    // 用户消息独立一行
    if (msg.role === 'user') {
      groups.push({
        role: msg.role,
        items: [{ content: msg.content, streaming }],
        timestamp: msg.timestamp,
      });
    } else {
      // 助手消息：合并到上一组
      const last = groups[groups.length - 1];
      // 提取所有预览路径（支持多张封面）
      const previewMatches = [...msg.content.matchAll(/\[PREVIEW:([^\]]+)\]/g)];
      const previewPaths = previewMatches.map(m => m[1]);

      if (last && last.role === 'assistant') {
        // 如果上一条还在流式，替换内容；否则追加
        if (last.items[last.items.length - 1].streaming) {
          last.items[last.items.length - 1] = { content: msg.content, streaming };
        } else {
          last.items.push({ content: msg.content, streaming });
        }
        // 追加预览路径
        if (previewPaths.length > 0) {
          last.previewPaths = [...(last.previewPaths || []), ...previewPaths];
        }
      } else {
        groups.push({
          role: msg.role,
          items: [{ content: msg.content, streaming }],
          timestamp: msg.timestamp,
          previewPaths: previewPaths.length > 0 ? previewPaths : undefined,
        });
      }
    }
  }
  return groups;
});

function formatTime(ts: string): string {
  if (!ts) return '';
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
}

function formatContent(content: string | null | undefined): string {
  if (!content) return '';
  // 检测 JSON 格式并提取 response 字段
  try {
    const parsed = JSON.parse(content);
    if (parsed && typeof parsed.response === 'string') {
      content = parsed.response;
    }
  } catch {}
  // 移除 [PREVIEW:...] 标签（用于触发视频预览，不显示在消息中）
  let text = content.replace(/\[PREVIEW:[^\]]*\]/g, '').trim();
  // 转义 HTML 特殊字符，防止 \n \t 等被解释
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/\t/g, '&nbsp;&nbsp;&nbsp;&nbsp;')  // Tab 转为 4 个空格
    .replace(/\n/g, '<br>')  // 换行符转为 <br>
    .replace(/\v/g, '<br>');  // 垂直制表符转为换行
  return escaped.replace(/\n/g, '<br>');
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = 9999;
    }
  });
}

// 仅当添加新消息时滚动，非流式更新时不滚动
// 流式消息时用 requestAnimationFrame 防抖，避免闪烁
let scrollRaf: number | null = null;
function scrollToBottomDebounced() {
  if (scrollRaf) cancelAnimationFrame(scrollRaf);
  scrollRaf = requestAnimationFrame(() => {
    scrollToBottom();
    scrollRaf = null;
  });
}

// 监听消息长度变化（新增消息时滚动）
watch(() => messages.value.length, () => {
  scrollToBottomDebounced();
});

// 流式消息时频繁滚动到底部
watch(hasStreamingMessage, (streaming) => {
  if (streaming) {
    // 开始流式传输时启动定时滚动
    const scrollInterval = setInterval(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = 9999;
      }
    }, 100);
    // 保存 interval 引用以便清除
    (messagesRef.value as any).__scrollInterval = scrollInterval;
  } else {
    // 结束流式传输时清除
    const interval = (messagesRef.value as any).__scrollInterval;
    if (interval) {
      clearInterval(interval);
    }
  }
});
</script>

<script lang="ts">
export default { name: 'ChatArea' };
</script>

<style scoped>
.message-group {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.message-group.user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--btv-surface);
  border: 2px solid var(--btv-border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.message-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  display: block;
}
.message-bubble.has-next {
  margin-bottom: 12px;
}
.message-group.user .message-bubble {
  background: var(--btv-surface);
  color: var(--btv-text);
  border: 1px solid var(--btv-border);
  border-bottom-right-radius: 4px;
}
.message-group.assistant .message-bubble {
  background: var(--btv-surface);
  color: var(--btv-text);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--btv-border);
}
/* 同一组内的多个气泡之间通过 formatContent 的 br 换行 */
.message-bubble.streaming {
  opacity: 0.8;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 0.6; }
}
.message-time {
  font-size: 11px;
  color: #666;
  padding: 0 4px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
}
.empty-state .icon {
  font-size: 48px;
  margin-bottom: 12px;
}
/* 流式消息加载指示器 */
.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}
.streaming-indicator .dot {
  width: 8px;
  height: 8px;
  background: #666;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}
.streaming-indicator .dot:nth-child(1) { animation-delay: -0.32s; }
.streaming-indicator .dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
/* 进度条 */
.streaming-indicator .progress-bar {
  flex: 1;
  height: 6px;
  background: var(--btv-surface);
  border-radius: 3px;
  overflow: hidden;
}
.streaming-indicator .progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--btv-red) 0%, var(--btv-gold) 100%);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.streaming-indicator .progress-text {
  font-size: 12px;
  color: #888;
  min-width: 32px;
  text-align: right;
}
/* 视频预览 */
.preview-list {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.preview-item {
  background: var(--btv-surface);
  border-radius: 8px;
  overflow: hidden;
  max-width: 300px;
}
.preview-video {
  width: 100%;
  max-height: 180px;
  display: block;
}
.preview-image {
  width: 100%;
  max-height: 180px;
  object-fit: cover;
  display: block;
}
.preview-info {
  padding: 4px 8px;
  text-align: right;
}
.download-link {
  color: var(--btv-gold);
  text-decoration: none;
  font-size: 12px;
}
.download-link:hover {
  text-decoration: underline;
}
</style>
